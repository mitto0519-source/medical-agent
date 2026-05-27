"""Citation graph — 논문 reference 간 co-citation / bridging / missing seminal 분석.

기존 자산 통합:
  · `src/export/reference_library.py` (PubMed/CrossRef API · Vancouver formatter)
  · `src/knowledge/medical_graph.py`     (NetworkX 의학 키워드 그래프)
  → 본 모듈이 reference list를 받아 citation network를 NetworkX로 빌드.

설계:
  1. reference list 입력 → PubMed `cited_by` lookup으로 인접 ref 추출
  2. NetworkX DiGraph 구축 (node=PMID, edge=cites)
  3. 분석:
     - co-citation: 같이 자주 인용되는 ref 쌍 → "Yoosun 인접 군집"
     - bridging: 두 cluster를 연결하는 핵심 ref
     - missing seminal: 본문에는 없지만 cited_by 횟수 높은 ref → 추천
  4. 결과는 reference_library에 PubMed lookup으로 검증

호출:
    from src.knowledge.citation_graph import build_citation_graph, find_missing_seminal
    g = build_citation_graph(["10.1056/NEJMra2030063", ...])  # DOI 또는 PMID
    seminal = find_missing_seminal(g, current_refs)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_CACHE_DIR = Path("data/knowledge_graph")


def _nx():
    try:
        import networkx as nx
        return nx
    except ImportError:
        _log.warning("networkx 미설치 — citation_graph 비활성")
        return None


def _normalize_id(ref: str) -> str:
    ref = str(ref or "").strip()
    if not ref:
        return ""
    # PMID는 8자리 이하 숫자
    if ref.isdigit() and len(ref) <= 8:
        return f"PMID:{ref}"
    # DOI는 10.xxxx/...
    if "/" in ref and ref.startswith("10."):
        return f"DOI:{ref.lower()}"
    if ref.lower().startswith("doi:"):
        return f"DOI:{ref[4:].lower()}"
    if ref.lower().startswith("pmid:"):
        return ref.upper()
    return ref


def build_citation_graph(refs: List[str],
                          depth: int = 1,
                          max_per_ref: int = 20,
                          use_cache: bool = True) -> Optional[object]:
    """ref list로 NetworkX DiGraph 생성.

    Args:
        refs: PMID 또는 DOI 리스트
        depth: 1=직접 cited_by, 2=cited_by의 cited_by (실험적)
        max_per_ref: 각 ref당 최대 인접 노드 수 (API 부하 제한)
        use_cache: data/knowledge_graph/citation_graph.json 캐시 활용
    """
    nx = _nx()
    if nx is None:
        return None

    cache_path = _CACHE_DIR / "citation_graph.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: Dict[str, List[str]] = {}
    if use_cache and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    g = nx.DiGraph()
    for r in refs:
        nid = _normalize_id(r)
        if not nid:
            continue
        g.add_node(nid, source="seed")

    # 인접 노드 fetch (PubMed eLink — reference_library가 fetch 함수 보유 가정)
    seeds = list(g.nodes())
    for nid in seeds:
        if nid in cache:
            neighbors = cache[nid][:max_per_ref]
        else:
            neighbors = _fetch_cited_by(nid, max_per_ref)
            cache[nid] = neighbors
        for nb in neighbors:
            g.add_node(nb, source="cited_by")
            g.add_edge(nb, nid)  # nb cites nid

    if use_cache:
        try:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        except Exception:
            pass

    _log.info("citation_graph: %d nodes, %d edges", g.number_of_nodes(), g.number_of_edges())
    return g


def _fetch_cited_by(node_id: str, max_n: int) -> List[str]:
    """PubMed eLink로 cited_by 조회. 실패 시 빈 리스트."""
    if not node_id.startswith("PMID:"):
        return []
    pmid = node_id.replace("PMID:", "")
    try:
        import urllib.request
        url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?"
               f"dbfrom=pubmed&id={pmid}&linkname=pubmed_pubmed_citedin&retmode=json")
        req = urllib.request.Request(url, headers={"User-Agent": "medical-agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            linksets = data.get("linksets", [])
            if not linksets:
                return []
            db = linksets[0].get("linksetdbs", [])
            if not db:
                return []
            ids = db[0].get("links", [])[:max_n]
            return [f"PMID:{i}" for i in ids]
    except Exception as e:
        _log.debug("eLink 실패 %s: %s", node_id, e)
        return []


def find_co_citations(g, min_pair_weight: int = 2) -> List[Tuple[str, str, int]]:
    """함께 자주 인용되는 pair 추출 (둘 다 같은 citing ref에 인용)."""
    nx = _nx()
    if nx is None or g is None:
        return []
    # node u, v: count = |predecessors(u) ∩ predecessors(v)|
    seeds = [n for n, d in g.nodes(data=True) if d.get("source") == "seed"]
    pairs: Dict[Tuple[str, str], int] = {}
    for i, u in enumerate(seeds):
        pu = set(g.predecessors(u))
        for v in seeds[i + 1:]:
            pv = set(g.predecessors(v))
            inter = pu & pv
            if len(inter) >= min_pair_weight:
                key = tuple(sorted([u, v]))
                pairs[key] = len(inter)
    return [(u, v, w) for (u, v), w in sorted(pairs.items(),
                                                 key=lambda x: -x[1])]


def find_bridging_refs(g, top_n: int = 5) -> List[Tuple[str, float]]:
    """betweenness centrality — 두 cluster를 연결하는 핵심 ref."""
    nx = _nx()
    if nx is None or g is None:
        return []
    try:
        bc = nx.betweenness_centrality(g)
        return sorted(bc.items(), key=lambda x: -x[1])[:top_n]
    except Exception:
        return []


def find_missing_seminal(g, current_refs: List[str], min_inbound: int = 5,
                          top_n: int = 10) -> List[Tuple[str, int]]:
    """본문에는 없지만 인접 군집에서 자주 인용되는 ref → 보강 추천.

    Returns: [(node_id, inbound_count), ...]
    """
    if g is None:
        return []
    current_set = {_normalize_id(r) for r in current_refs}
    candidates: List[Tuple[str, int]] = []
    for n in g.nodes():
        if n in current_set:
            continue
        in_count = g.in_degree(n)
        if in_count >= min_inbound:
            candidates.append((n, in_count))
    return sorted(candidates, key=lambda x: -x[1])[:top_n]
