"""RAG 즉시 스케일업 스크립트 — 그래프 저장 논문 + 확장 PubMed 수집.

사용법:
    python scripts/rag_scale_up.py              # 전체 (그래프 + 확장 PubMed)
    python scripts/rag_scale_up.py --graph-only # 그래프 논문만 인제스트
    python scripts/rag_scale_up.py --pubmed-only # PubMed 수집만
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger("rag_scale_up")


def ingest_graph_papers() -> int:
    """의학 그래프에 저장된 논문들을 RAG에 인제스트."""
    from src.knowledge.medical_graph import get_graph
    from src.vectordb.store import get_vector_store
    from src.ingestion.chunker import TextChunker

    graph = get_graph()
    stats = graph.stats()
    print(f"[그래프] 노드: {stats.get('total_nodes', 0)}, 논문: {stats.get('paper_nodes', 0)}")

    papers = graph.get_papers(limit=500)
    if not papers:
        print("[그래프] 저장된 논문 없음")
        return 0

    store = get_vector_store()
    chunker = TextChunker(chunk_size=400, overlap=50)
    total = 0

    for p in papers:
        title = p.get("title", "")
        abstract = p.get("abstract", "") or p.get("summary", "") or ""
        text = f"Title: {title}\n\nAbstract: {abstract}".strip()
        if len(text) < 30:
            continue
        meta = {
            "filename": title[:80],
            "source": f"pubmed:{p.get('pmid', p.get('id', ''))}",
            "pmid": str(p.get("pmid", "")),
            "year": str(p.get("year", "")),
            "journal": p.get("journal", ""),
            "topic": "graph_paper",
            "datasets": ",".join(p.get("datasets", [])),
        }
        chunks = chunker.chunk(text, metadata=meta)
        added = store.add_chunks(chunks)
        total += added

    count_before = store.count()
    print(f"[그래프 인제스트] {len(papers)}편 → {total}청크 추가 (총 {store.count()}청크)")
    return total


def ingest_pubmed_expanded(days: int = 180, max_per_query: int = 50) -> dict:
    """확장된 쿼리로 PubMed 수집 + RAG 인제스트."""
    from src.knowledge.trend_learner import run_trend_learn
    print(f"[PubMed] 최근 {days}일, 쿼리당 최대 {max_per_query}편 수집...")
    result = run_trend_learn(days=days, max_per_query=max_per_query)
    print(
        f"[PubMed] 신규: {result.get('new_papers', 0)}편, "
        f"RAG 인제스트: {result.get('rag_ingested', 0)}편, "
        f"그래프 노드: {result.get('graph_nodes_before', 0)} → {result.get('graph_nodes_after', 0)}"
    )
    return result


def show_rag_stats():
    from src.vectordb.store import get_vector_store
    store = get_vector_store()
    n = store.count()
    print(f"\n[RAG 현재 상태] 총 {n}청크")
    if n > 0:
        try:
            hits = store.search("Korean adolescent depression sleep", top_k=3)
            print(f"  샘플 검색('Korean adolescent depression sleep') → {len(hits)}건 반환")
            for h in hits[:2]:
                print(f"    dist={h.get('distance', '?'):.3f} | {h.get('metadata', {}).get('filename', '')[:50]}")
        except Exception as e:
            print(f"  검색 샘플 오류: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-only", action="store_true")
    parser.add_argument("--pubmed-only", action="store_true")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--max-per-query", type=int, default=30)
    args = parser.parse_args()

    print("=" * 60)
    print("  RAG 스케일업")
    print("=" * 60)
    show_rag_stats()

    if not args.pubmed_only:
        print("\n[1] 그래프 논문 인제스트...")
        ingest_graph_papers()

    if not args.graph_only:
        print("\n[2] 확장 PubMed 수집...")
        ingest_pubmed_expanded(days=args.days, max_per_query=args.max_per_query)

    show_rag_stats()
    print("\n완료")
