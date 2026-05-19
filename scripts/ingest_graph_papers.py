"""지식 그래프의 모든 논문 노드를 ChromaDB RAG로 일괄 인제스트.

graph.json → paper nodes → chunks → VectorStore.add_chunks()

실행: python scripts/ingest_graph_papers.py
옵션:
  --dry-run   실제 인제스트 없이 통계만 출력
  --batch 500 배치 크기 (기본 500)
  --dir data/chromadb_test  ChromaDB 경로 (기본 data/chromadb)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.config.env import bootstrap
bootstrap()

_GRAPH_FILE = Path("data/knowledge_graph/graph.json")


def build_chunk(node: dict, idx: int) -> dict | None:
    """paper 노드 → add_chunks() 형식 청크."""
    title = (node.get("title") or "").strip()
    abstract = (node.get("abstract") or "").strip()

    if not title and not abstract:
        return None

    # 제목 + 초록 결합 텍스트
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    text = "\n".join(parts)

    pmid = str(node.get("pmid") or node.get("id", "").replace("paper:", ""))
    year = node.get("year")
    journal = (node.get("journal") or "").strip()

    meta: dict = {
        "filename": f"pubmed_{pmid}.txt",
        "source": "knowledge_graph",
        "pmid": pmid,
    }
    if year:
        meta["year"] = int(year)
    if journal:
        meta["journal"] = journal

    return {
        "text": text,
        "metadata": meta,
        "word_start": 0,
        "word_end": len(text.split()),
        "chunk_id": idx,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--dir", default="data/chromadb_test")
    args = parser.parse_args()

    if not _GRAPH_FILE.exists():
        print(f"그래프 파일 없음: {_GRAPH_FILE}")
        sys.exit(1)

    print(f"그래프 로드 중: {_GRAPH_FILE} ({_GRAPH_FILE.stat().st_size // 1024:,} KB)")
    data = json.loads(_GRAPH_FILE.read_text(encoding="utf-8"))

    nodes = data.get("nodes", [])
    paper_nodes = [n for n in nodes if n.get("type") == "paper"]
    print(f"전체 노드: {len(nodes):,}  |  paper 노드: {len(paper_nodes):,}")

    if args.dry_run:
        sample = paper_nodes[:3]
        for p in sample:
            print(f"  [{p.get('pmid')}] {p.get('title', '')[:60]}")
        print("(--dry-run: 실제 인제스트 건너뜀)")
        return

    # ChromaDB 연결
    from src.vectordb.store import VectorStore
    store = VectorStore(persist_dir=args.dir)
    before = store.count()
    print(f"현재 ChromaDB 청크 수: {before:,}  ({args.dir})")

    total_added = 0
    total_skipped = 0
    seen_ids: set = set()
    batch: list = []

    def flush(batch):
        # Deduplicate within batch by SHA256 of text
        deduped = {}
        for c in batch:
            h = hashlib.sha256(c["text"].encode()).hexdigest()
            if h not in seen_ids and h not in deduped:
                deduped[h] = c
        seen_ids.update(deduped.keys())
        return store.add_chunks(list(deduped.values()))

    for i, node in enumerate(paper_nodes):
        chunk = build_chunk(node, i)
        if chunk is None:
            total_skipped += 1
            continue
        batch.append(chunk)

        if len(batch) >= args.batch:
            added = flush(batch)
            total_added += added
            done = i + 1
            pct = done / len(paper_nodes) * 100
            print(f"  배치 완료: {done:,}/{len(paper_nodes):,} ({pct:.1f}%)  "
                  f"+{added} 청크 (누적 {total_added:,})")
            batch = []

    # 마지막 배치
    if batch:
        added = flush(batch)
        total_added += added

    after = store.count()
    print(f"\n인제스트 완료!")
    print(f"  추가된 청크: {total_added:,}")
    print(f"  스킵 (빈 텍스트): {total_skipped:,}")
    print(f"  ChromaDB 청크: {before:,} → {after:,}")


if __name__ == "__main__":
    main()
