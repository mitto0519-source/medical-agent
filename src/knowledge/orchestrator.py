"""Knowledge Orchestrator — 단일 PMID/DOI → graph + vector + ontology + citation_graph
**동시 등록**으로 cross-link 유지.

사용자 진단 (2026-05-28): "그래프DB·벡터DB·온톨로지가 따로 존재 → 통합 ontology 부재".
본 모듈이 그 누락을 메운다. 모든 새 논문 ingestion이 본 클래스를 거치게 wire:
  - `src.ingestion.oa_bulk_fetcher.fetch_oa_batch` (Europe PMC OA bulk)
  - `src.runtime.backlog._h_paper_ingest` (첨부 PDF/DOCX)
  - `src.knowledge.trend_learner` (24h PubMed)

cross-modal query:
  `KnowledgeOrchestrator().query("ZCB depression")` →
  벡터 hit + 인접 concept + graph neighbors + citation cluster 통합 반환

호출 양식:
    orch = KnowledgeOrchestrator()
    orch.ingest(pmid="38123456", title="...", abstract="...", full_text="...")
    result = orch.query("zero-calorie beverage depression adolescents", k=8)
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# Cross-modal id helpers
def _paper_node(pmid: str) -> str:
    return f"paper:{pmid}"


def _concept_node(cid: str) -> str:
    return f"concept:{cid}"


def _chunk_id(pmid: str, idx: int, text: str) -> str:
    """안정적 chunk id (재실행에 동일)."""
    h = hashlib.sha1(f"{pmid}#{idx}#{text[:80]}".encode("utf-8")).hexdigest()[:16]
    return f"pmcorch:{pmid}:{idx}:{h}"


class KnowledgeOrchestrator:
    """4 자산 (graph/vector/ontology/citation) 단일 entity ID 통합 ingest + query."""

    _instance: Optional["KnowledgeOrchestrator"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_lazy()
        return cls._instance

    def _init_lazy(self):
        self._graph = None
        self._vstore = None
        self._ontology = None
        self._citation_cache: Dict[str, List[str]] = {}

    @property
    def graph(self):
        if self._graph is None:
            try:
                from src.knowledge.medical_graph import get_graph
                self._graph = get_graph()
            except Exception as e:
                _log.warning("graph load fail: %s", e)
        return self._graph

    @property
    def vstore(self):
        if self._vstore is None:
            try:
                from src.vectordb.store import get_vector_store
                self._vstore = get_vector_store("data/chromadb")
            except Exception as e:
                _log.warning("vstore load fail: %s", e)
        return self._vstore

    @property
    def ontology(self):
        if self._ontology is None:
            try:
                from src.knowledge.medical_ontology import get_ontology
                self._ontology = get_ontology()
            except Exception as e:
                _log.warning("ontology load fail: %s", e)
        return self._ontology

    # ── Ingest ──────────────────────────────────────────────────────────────

    def ingest(self, pmid: str, title: str = "", abstract: str = "",
                full_text: str = "", year: Optional[int] = None,
                journal: str = "", doi: str = "",
                figures: Optional[List[str]] = None,
                tables: Optional[List[str]] = None) -> Dict:
        """단일 논문을 4 자산에 동시 등록.

        Returns:
            {"pmid": ..., "concepts": [...], "n_chunks": N, "graph_node": ...,
             "citation_added": True/False}
        """
        from src.runtime import events as _events
        pmid = str(pmid).strip()
        if not pmid:
            return {"error": "empty pmid"}

        # 1. ontology 매핑
        concepts: List[str] = []
        try:
            text_for_concept = f"{title}\n{abstract}"[:4000]
            if self.ontology:
                ext = self.ontology.extract_concepts(text_for_concept) or []
                concepts = [c.get("id") or c.get("concept_id") or "" for c in ext if c]
                concepts = [c for c in concepts if c]
        except Exception as e:
            _log.debug("concept extract fail %s: %s", pmid, e)

        # 2. vector 색인 (chunk + metadata에 pmid/concepts 같이)
        chunks_added = self._index_chunks(pmid, full_text or abstract, title,
                                            concepts, year, journal, doi)

        # 3. graph 노드 (paper + concept edges)
        graph_node = self._add_to_graph(pmid, title, abstract, year, journal,
                                          concepts)

        # 4. citation graph 확장 (cited_by 1-hop)
        cited_added = self._extend_citation_graph(pmid)

        # 5. ★ Component 추출 (reusable microcomponent 자산화)
        n_components = 0
        try:
            from src.library.component_extractor import extract_and_store
            n_components = extract_and_store(
                full_text or abstract,
                source_pmid=pmid,
                author_style="",   # OA 일반. yoosun_cho 시드는 별도 source
            )
        except Exception as e:
            _log.debug("component extract fail %s: %s", pmid, e)

        # 6. events 기록
        try:
            _events.append("orchestrator_ingest",
                            {"pmid": pmid, "n_concepts": len(concepts),
                             "n_chunks": chunks_added, "year": year,
                             "cited_added": cited_added,
                             "n_components": n_components},
                            actor="knowledge_orchestrator")
        except Exception:
            pass

        return {"pmid": pmid, "concepts": concepts,
                "n_chunks": chunks_added, "graph_node": graph_node,
                "citation_added": cited_added,
                "n_components": n_components}

    # ── Internal: ontology → concept_ids ────────────────────────────────────

    def _index_chunks(self, pmid: str, text: str, title: str,
                       concepts: List[str], year: Optional[int],
                       journal: str, doi: str) -> int:
        """텍스트를 chunk로 쪼개 ChromaDB에 등록 (metadata에 pmid/concepts)."""
        if not text or not self.vstore:
            return 0
        try:
            from src.ingestion.hierarchical_chunker import chunk_paper
        except Exception:
            chunk_paper = None

        chunks_data: List[Dict] = []
        if chunk_paper is not None and len(text) > 1500:
            try:
                parsed = chunk_paper(text, base_meta={"pmid": pmid, "title": title[:200]})
                # chunk_paper returns list of dicts with .text and .meta
                for i, ch in enumerate(parsed[:80]):
                    text_val = ch.get("text") if isinstance(ch, dict) else getattr(ch, "text", str(ch))
                    meta = ch.get("meta", {}) if isinstance(ch, dict) else getattr(ch, "meta", {}) or {}
                    chunks_data.append({
                        "text": text_val[:2000],
                        "id": _chunk_id(pmid, i, text_val),
                        "metadata": {
                            "pmid": pmid, "doi": doi, "title": title[:200],
                            "year": year, "journal": journal[:100],
                            "concepts": ",".join(concepts[:10]),
                            "section": meta.get("section", ""),
                            "chunk_id": i,
                            "source": f"oa_orch:{pmid}",
                        },
                    })
            except Exception as e:
                _log.debug("hierarchical chunk fail, fallback: %s", e)
                chunks_data = []

        if not chunks_data:
            # 단순 절반-슬라이스 fallback
            step = 1500
            for i, start in enumerate(range(0, min(len(text), 80 * step), step)):
                seg = text[start:start + step]
                if not seg.strip():
                    continue
                chunks_data.append({
                    "text": seg,
                    "id": _chunk_id(pmid, i, seg),
                    "metadata": {
                        "pmid": pmid, "doi": doi, "title": title[:200],
                        "year": year, "journal": journal[:100],
                        "concepts": ",".join(concepts[:10]),
                        "chunk_id": i,
                        "source": f"oa_orch:{pmid}",
                    },
                })

        try:
            return int(self.vstore.add_chunks(chunks_data))
        except Exception as e:
            _log.warning("vstore add fail %s: %s", pmid, e)
            return 0

    def _add_to_graph(self, pmid: str, title: str, abstract: str,
                       year: Optional[int], journal: str,
                       concepts: List[str]) -> str:
        """graph에 paper node + concept edges."""
        g = self.graph
        if g is None:
            return _paper_node(pmid)
        try:
            paper_id = g.add_paper(pmid, title=title, abstract=abstract,
                                    year=year, journal=journal)
            for cid in concepts:
                try:
                    cnode = g.add_concept(cid, label=cid)
                    if hasattr(g, "_G"):
                        g._G.add_edge(paper_id, cnode, type="mentions")
                except Exception:
                    continue
            # 저장 (있으면)
            if hasattr(g, "save"):
                try:
                    g.save()
                except Exception:
                    pass
            return paper_id
        except Exception as e:
            _log.warning("graph add fail %s: %s", pmid, e)
            return _paper_node(pmid)

    def _extend_citation_graph(self, pmid: str) -> bool:
        """citation_graph에 PMID 노드 + 1-hop cited_by 자동 추가."""
        try:
            from src.knowledge.citation_graph import build_citation_graph
            g = build_citation_graph([pmid], depth=1, max_per_ref=10, use_cache=True)
            return g is not None and g.number_of_nodes() > 0
        except Exception as e:
            _log.debug("citation_graph extend fail %s: %s", pmid, e)
            return False

    # ── Cross-modal query ──────────────────────────────────────────────────

    def query(self, q: str, k: int = 8) -> Dict:
        """vector top-K → 각 hit의 concept/graph neighbors/citations 통합 회수.
        agentic_loop의 새 cross_modal tool 또는 mcp의 새 도구로 노출."""
        hits: List[Dict] = []
        try:
            if self.vstore is not None:
                hits = self.vstore.search(q, n_results=k) or []
        except Exception as e:
            _log.warning("vector search fail: %s", e)

        # 각 hit의 PMID로 graph neighbors + concepts 회수
        enriched: List[Dict] = []
        seen_pmids: set = set()
        for h in hits[:k]:
            md = (h.get("metadata") or {}) if isinstance(h, dict) else {}
            pmid = str(md.get("pmid") or md.get("source", "").replace("pubmed:", "")
                        .replace("oa_orch:", "") or "")
            neighbors: List[str] = []
            concepts_str = md.get("concepts", "")
            if pmid and pmid not in seen_pmids and self.graph is not None:
                try:
                    node = _paper_node(pmid)
                    if hasattr(self.graph, "_G") and self.graph._G.has_node(node):
                        nbrs = list(self.graph._G.neighbors(node))[:10]
                        neighbors = nbrs
                except Exception:
                    pass
            seen_pmids.add(pmid)
            enriched.append({
                "text": (h.get("text") or "")[:400] if isinstance(h, dict) else "",
                "score": (h.get("score") if isinstance(h, dict) else 0) or 0,
                "pmid": pmid,
                "title": md.get("title", "")[:160],
                "year": md.get("year"),
                "concepts": [c for c in concepts_str.split(",") if c] if concepts_str else [],
                "graph_neighbors": neighbors,
            })

        # 인접 concept aggregation (어떤 concept이 결과들에 가장 자주 등장하나)
        from collections import Counter
        cnt = Counter()
        for e in enriched:
            for c in e["concepts"]:
                cnt[c] += 1
        top_concepts = cnt.most_common(8)

        return {
            "query": q,
            "n_hits": len(enriched),
            "hits": enriched,
            "top_concepts": [{"concept": c, "n": n} for c, n in top_concepts],
        }

    # ── Bulk helpers ────────────────────────────────────────────────────────

    def ingest_oa_paper(self, pmcid: str, meta: Dict, body_text: str) -> Dict:
        """oa_bulk_fetcher가 한 편씩 호출. meta는 .meta.json 내용."""
        return self.ingest(
            pmid=meta.get("pmid", "") or pmcid.replace("PMC", ""),
            title=meta.get("title", ""),
            abstract=body_text[:2000],
            full_text=body_text,
            year=meta.get("year"),
            journal=meta.get("journal", ""),
            doi=meta.get("doi", ""),
            figures=meta.get("figures", []),
            tables=meta.get("tables", []),
        )


def get_orchestrator() -> KnowledgeOrchestrator:
    """싱글톤 helper — 다른 모듈에서 KnowledgeOrchestrator()와 동일."""
    return KnowledgeOrchestrator()
