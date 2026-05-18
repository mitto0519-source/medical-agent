"""Medical Knowledge Graph — 논문-개념 관계 그래프.

NetworkX 기반 경량 그래프 레이어.
논문(Paper), 개념(Concept), 데이터셋(Dataset), 저자(Author) 를
노드로 연결하고 관계 엣지를 저장한다.

파일 저장: data/knowledge_graph/graph.json (JSON adjacency list)
용도:
  - 유사 논문 탐색 (공유 개념 기반)
  - 연구 갭 발견 (연결 없는 개념 쌍)
  - RAG 검색 강화 (그래프 이웃 → 추가 컨텍스트)
  - 온톨로지 기반 주제 생성 힌트
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)

try:
    import networkx as nx
    _NX_OK = True
except ImportError:
    _NX_OK = False
    _log.warning("networkx not installed — graph features disabled. pip install networkx")

_GRAPH_DIR = Path("data/knowledge_graph")
_GRAPH_FILE = _GRAPH_DIR / "graph.json"
_META_FILE  = _GRAPH_DIR / "meta.json"

NODE_TYPES = {"paper", "concept", "dataset", "author"}


class MedicalGraph:
    """논문-개념 관계 그래프.

    노드 타입:
      paper   — PubMed 논문 (pmid 기준)
      concept — 온톨로지 개념 (concept_id 기준)
      dataset — KYRBS / KNHANES 등
      author  — 저자 (first_last 형식)

    엣지 타입 (relation):
      paper→concept : HAS_CONCEPT
      paper→dataset : USES_DATASET
      paper→author  : HAS_AUTHOR
      concept→concept: RELATED_TO (도메인 내 연관)
    """

    def __init__(self):
        if not _NX_OK:
            self._G = None
            return
        self._G = nx.DiGraph()
        self._load()

    # ── 저장/로드 ─────────────────────────────────────────────────────────────

    def _load(self):
        if not _NX_OK or not _GRAPH_FILE.exists():
            return
        try:
            data = json.loads(_GRAPH_FILE.read_text(encoding="utf-8"))
            self._G = nx.node_link_graph(data, edges="links")
            meta = json.loads(_META_FILE.read_text(encoding="utf-8")) if _META_FILE.exists() else {}
            _log.info("[graph] loaded: %d nodes, %d edges (last_updated=%s)",
                      self._G.number_of_nodes(), self._G.number_of_edges(),
                      meta.get("last_updated", "?"))
        except Exception as e:
            _log.warning("[graph] load failed, starting fresh: %s", e)
            self._G = nx.DiGraph()

    def save(self):
        if not _NX_OK or self._G is None:
            return
        _GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._G, edges="links")
        _GRAPH_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _META_FILE.write_text(json.dumps({
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "nodes": self._G.number_of_nodes(),
            "edges": self._G.number_of_edges(),
            "paper_count": sum(1 for _, d in self._G.nodes(data=True) if d.get("type") == "paper"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 노드 추가 ─────────────────────────────────────────────────────────────

    def add_paper(self, pmid: str, title: str, abstract: str = "",
                  year: Optional[int] = None, journal: str = "") -> str:
        if not _NX_OK:
            return pmid
        node_id = f"paper:{pmid}"
        self._G.add_node(node_id, type="paper", pmid=pmid,
                         title=title[:200], abstract=abstract[:500],
                         year=year, journal=journal[:100],
                         added_at=datetime.now().strftime("%Y-%m-%d"))
        return node_id

    def add_concept(self, concept_id: str, label: str, domain: str = "") -> str:
        if not _NX_OK:
            return concept_id
        node_id = f"concept:{concept_id}"
        if not self._G.has_node(node_id):
            self._G.add_node(node_id, type="concept",
                             concept_id=concept_id, label=label, domain=domain)
        return node_id

    def add_dataset(self, name: str) -> str:
        if not _NX_OK:
            return name
        node_id = f"dataset:{name}"
        if not self._G.has_node(node_id):
            self._G.add_node(node_id, type="dataset", name=name)
        return node_id

    # ── 엣지 추가 ─────────────────────────────────────────────────────────────

    def link_paper_concept(self, paper_node: str, concept_node: str, weight: float = 1.0):
        if not _NX_OK:
            return
        self._G.add_edge(paper_node, concept_node, relation="HAS_CONCEPT", weight=weight)

    def link_paper_dataset(self, paper_node: str, dataset_node: str):
        if not _NX_OK:
            return
        self._G.add_edge(paper_node, dataset_node, relation="USES_DATASET", weight=1.0)

    def link_concepts(self, c1: str, c2: str, weight: float = 0.5):
        """같은 도메인 개념 간 연결 (양방향)."""
        if not _NX_OK:
            return
        self._G.add_edge(c1, c2, relation="RELATED_TO", weight=weight)
        self._G.add_edge(c2, c1, relation="RELATED_TO", weight=weight)

    # ── 쿼리 ─────────────────────────────────────────────────────────────────

    def papers_with_concept(self, concept_id: str, limit: int = 20) -> List[Dict]:
        """특정 개념을 다루는 논문 목록 반환."""
        if not _NX_OK or self._G is None:
            return []
        target = f"concept:{concept_id}"
        result = []
        for node, data in self._G.nodes(data=True):
            if data.get("type") != "paper":
                continue
            if self._G.has_edge(node, target):
                result.append({"node": node, **data})
        return result[:limit]

    def similar_papers(self, pmid: str, top_k: int = 5) -> List[Tuple[str, int]]:
        """공유 개념 수 기준 유사 논문 반환."""
        if not _NX_OK or self._G is None:
            return []
        src = f"paper:{pmid}"
        if not self._G.has_node(src):
            return []
        src_concepts = set(self._G.successors(src))
        scores: Dict[str, int] = {}
        for c in src_concepts:
            for paper in self._G.predecessors(c):
                if paper != src and self._G.nodes[paper].get("type") == "paper":
                    scores[paper] = scores.get(paper, 0) + 1
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    def concept_gap_pairs(self, min_papers: int = 3) -> List[Tuple[str, str]]:
        """논문에서 자주 함께 나타나지만 그래프에서 아직 연결 안 된 개념 쌍.
        새 연구 갭 발견에 활용."""
        if not _NX_OK or self._G is None:
            return []
        concept_paper_sets: Dict[str, set] = {}
        for node, data in self._G.nodes(data=True):
            if data.get("type") != "paper":
                continue
            for c in self._G.successors(node):
                if self._G.nodes[c].get("type") == "concept":
                    concept_paper_sets.setdefault(c, set()).add(node)

        pairs = []
        concepts = list(concept_paper_sets.keys())
        for i, c1 in enumerate(concepts):
            for c2 in concepts[i+1:]:
                shared = concept_paper_sets[c1] & concept_paper_sets[c2]
                if len(shared) >= min_papers and not self._G.has_edge(c1, c2):
                    pairs.append((c1, c2))
        return pairs[:20]

    def stats(self) -> Dict[str, Any]:
        if not _NX_OK or self._G is None:
            return {"available": False}
        type_counts: Dict[str, int] = {}
        for _, d in self._G.nodes(data=True):
            t = d.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "available": True,
            "total_nodes": self._G.number_of_nodes(),
            "total_edges": self._G.number_of_edges(),
            **type_counts,
        }

    def ingest_paper(self, paper: Dict) -> bool:
        """논문 딕셔너리를 받아 그래프에 추가.

        paper 필드: pmid, title, abstract, year, journal, datasets(list), concepts(list of concept_id)
        """
        if not _NX_OK:
            return False
        pmid = str(paper.get("pmid", ""))
        if not pmid:
            return False

        paper_node = self.add_paper(
            pmid=pmid,
            title=paper.get("title", ""),
            abstract=paper.get("abstract", ""),
            year=paper.get("year"),
            journal=paper.get("journal", ""),
        )

        for ds in paper.get("datasets", []):
            ds_node = self.add_dataset(ds)
            self.link_paper_dataset(paper_node, ds_node)

        for c in paper.get("concepts", []):
            c_node = self.add_concept(c["concept_id"], c["label"], c.get("domain_label", ""))
            self.link_paper_concept(paper_node, c_node,
                                    weight=c.get("weight", 1.0))
        return True


_singleton: Optional[MedicalGraph] = None


def get_graph() -> MedicalGraph:
    global _singleton
    if _singleton is None:
        _singleton = MedicalGraph()
    return _singleton


def ensure_networkx():
    """networkx 미설치 시 설치 안내."""
    if not _NX_OK:
        raise ImportError(
            "networkx가 설치되지 않았습니다. "
            "pip install networkx 실행 후 다시 시도하세요."
        )
