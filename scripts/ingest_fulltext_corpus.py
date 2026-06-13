"""FIX-3 (REVIEW_FIX_SPEC) — 12,625편 본문을 정식 경로로 재인제스트.

문제: ingest_graph_papers.py는 abstract만 청킹. 결과: 편당 ~2 청크.
이번 런처: data/oa_papers/*.txt 본문을 orchestrator.ingest(pmid, ..., full_text=...)로
보내 본문 청킹 + 개념 추출 + 그래프 노드/엣지 + ChromaDB 동시 갱신.

전제 (의존성):
  - FIX-6 임베딩 결정 (안 바꾸면 현 MiniLM 그대로) — 변경 시 별도 사전 실행
  - FIX-2 ontology 확장 (이미 PASS, 114 concepts) → 본문에서 양식 양식 매칭

실행:
    python scripts/ingest_fulltext_corpus.py --limit 50      # 검증 양식 양식
    python scripts/ingest_fulltext_corpus.py                  # 전체 (12,625편)
    python scripts/ingest_fulltext_corpus.py --skip-existing  # 이미 인제스트된 pmid 건너뛰기
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.env import bootstrap
bootstrap()

OA_DIR = ROOT / "data" / "oa_papers"


def iter_papers(skip_existing: bool = True):
    """각 .txt + 같은 stem의 .meta.json 쌍을 yield."""
    seen_pmids = set()
    if skip_existing:
        try:
            g = json.loads((ROOT / "data" / "knowledge_graph" / "graph.json").read_text(encoding="utf-8"))
            for n in g.get("nodes", []):
                if n.get("type") == "paper" and n.get("pmid"):
                    seen_pmids.add(str(n["pmid"]))
        except Exception:
            pass

    for txt in OA_DIR.glob("*.txt"):
        stem = txt.stem  # PMC12345
        meta_path = OA_DIR / f"{stem}.meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            body = txt.read_text(encoding="utf-8", errors="ignore")
            if len(body) < 500:
                continue
        except Exception:
            continue

        pmid = str(meta.get("pmid") or meta.get("pmcid") or stem).replace("PMC", "")
        if skip_existing and pmid in seen_pmids:
            continue
        yield pmid, meta, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    ap.add_argument("--no-skip", dest="skip_existing", action="store_false")
    args = ap.parse_args()

    from src.knowledge.orchestrator import KnowledgeOrchestrator
    orch = KnowledgeOrchestrator()

    t0 = time.time()
    n_ok, n_fail, n_skip = 0, 0, 0
    for i, (pmid, meta, body) in enumerate(iter_papers(args.skip_existing)):
        if args.limit and i >= args.limit:
            break
        try:
            r = orch.ingest(
                pmid=pmid,
                title=meta.get("title", "")[:300],
                abstract=meta.get("abstract", "")[:5000],
                full_text=body,
                year=int(meta.get("year") or meta.get("pub_year") or 0) or None,
                journal=meta.get("journal", ""),
                doi=meta.get("doi", ""),
                fast_mode=True,  # citation eLink는 별도 backlog
            )
            n_ok += 1
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                print(f"[{i+1}] ok={n_ok} fail={n_fail} skip={n_skip} "
                      f"({rate:.1f} papers/sec, last pmid={pmid}, "
                      f"chunks={r.get('n_chunks')})", flush=True)
        except Exception as e:
            n_fail += 1
            if n_fail % 20 == 0:
                print(f"  fail {pmid}: {str(e)[:120]}", flush=True)

    print(f"\nDONE in {time.time()-t0:.1f}s: ok={n_ok} fail={n_fail}")


if __name__ == "__main__":
    main()
