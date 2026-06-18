"""mitto 라벨 작업 도구 — RAG에서 PMID 후보를 *제안*만 함.

★ SELF_EVOLUTION_SPEC §9: 시스템이 라벨을 결정 X. 이 스크립트는 후보 출력만,
mitto가 그 중에서 직접 골라 eval/gold_set.json 에 박는다.

사용:
    python scripts/suggest_gold_labels.py --query-id q_sleep_metabolic --top 8
    python scripts/suggest_gold_labels.py --pair-id ce_caffeine_dep --top 5
    python scripts/suggest_gold_labels.py --status     # 현재 라벨 진척 보고
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.env import bootstrap; bootstrap()

GOLD = ROOT / "eval" / "gold_set.json"


def _load() -> dict:
    return json.loads(GOLD.read_text(encoding="utf-8"))


def suggest_for_query(qid: str, top: int = 8) -> None:
    d = _load()
    q = next((x for x in d.get("queries", []) if x.get("id") == qid), None)
    if q is None:
        print(f"❌ query id '{qid}' 없음")
        return
    print(f"=== {qid}: {q['query']!r} ===")
    print(f"이미 박힌 expected_pmids: {q.get('expected_pmids', [])}")
    print()
    from src.service.rag import retrieve
    hits = retrieve(q["query"], top_k=top)
    print(f"RAG top-{len(hits)} 후보:")
    for i, h in enumerate(hits, 1):
        m = h.get("metadata", {}) or {}
        pmid = m.get("pmid", "?")
        title = (m.get("title") or h.get("text", ""))[:120]
        year = m.get("year", "?")
        score = h.get("score", 0.0)
        already = "★있음" if str(pmid) in q.get("expected_pmids", []) else ""
        print(f"  {i:2d}. PMID:{pmid} ({year}) score={score:.3f} {already}")
        print(f"      {title}")
    print()
    print("★ mitto 작업: 이 중 진짜 관련 있는 2~3건 골라 expected_pmids에 직접 박기.")
    print("  단순 키워드 매칭 X — PubMed에서 abstract 확인 후 결정.")


def suggest_for_pair(pid: str, top: int = 5) -> None:
    d = _load()
    p = next((x for x in d.get("claim_evidence_pairs", []) if x.get("id") == pid), None)
    if p is None:
        print(f"❌ pair id '{pid}' 없음")
        return
    print(f"=== {pid} ===")
    print(f"claim: {p['claim']!r}")
    print(f"이미 박힌 evidence_pmids: {p.get('evidence_pmids', [])}, label: {p.get('label')}")
    print()
    from src.service.rag import retrieve
    hits = retrieve(p["claim"], top_k=top)
    print(f"RAG top-{len(hits)} 후보:")
    for i, h in enumerate(hits, 1):
        m = h.get("metadata", {}) or {}
        pmid = m.get("pmid", "?")
        title = (m.get("title") or h.get("text", ""))[:140]
        print(f"  {i:2d}. PMID:{pmid} ({m.get('year','?')}) score={h.get('score',0):.3f}")
        print(f"      {title}")
    print()
    print("★ mitto 작업:")
    print("  1) PubMed에서 1~2편 직접 읽기")
    print("  2) label 결정: 'supports' / 'contradicts' / 'neutral'")
    print("  3) evidence_pmids + label을 gold_set.json에 박기")


def status() -> None:
    d = _load()
    print("=" * 60)
    print(f"eval/gold_set.json 라벨 진척 (v{d.get('version','?')})")
    print("=" * 60)

    pairs = d.get("claim_evidence_pairs", [])
    labelled = [p for p in pairs
                  if p.get("evidence_pmids") and not str(p.get("label", "")).startswith("TODO")]
    print(f"\n📌 claim_evidence_pairs: {len(labelled)}/{len(pairs)} 라벨됨")
    for p in pairs:
        ok = bool(p.get("evidence_pmids")) and not str(p.get("label", "")).startswith("TODO")
        mark = "✓" if ok else "○"
        print(f"  {mark} {p['id']}: label={p.get('label','TODO')!r}, "
                f"evidence={len(p.get('evidence_pmids') or [])}편")

    queries = d.get("queries", [])
    with_pmids = [q for q in queries if q.get("expected_pmids")]
    print(f"\n📌 queries (retrieval@5): {len(with_pmids)}/{len(queries)} expected_pmids 박힘")
    for q in queries:
        n = len(q.get("expected_pmids") or [])
        mark = "✓" if n >= 2 else "○"
        print(f"  {mark} {q['id']}: expected={n}편, target={q.get('min_retrieval_at_5')}")

    print(f"\n📌 survey_design_test_cases: {len(d.get('survey_design_test_cases', []))}개 (자동 검증)")
    print(f"📌 style_targets: {len(d.get('style_targets', []))}개 (자동 측정)")
    print(f"📌 manuscript_targets: {len(d.get('manuscript_targets', []))}개 (자동 grep)")
    print()
    needed = len(pairs) - len(labelled) + len(queries) - len(with_pmids)
    if needed:
        print(f"★ 라벨 필요: {needed}건 (mitto 작업)")
        print(f"  다음 가이드: eval/LABELLING_GUIDE.md")
    else:
        print("✓ 라벨 완료 — python -m src.evolution.anchor 실행 가능")


def main() -> int:
    ap = argparse.ArgumentParser(description="mitto 라벨 도구 — 후보 제안만, 라벨 X")
    ap.add_argument("--query-id", help="query id (e.g. q_sleep_metabolic)")
    ap.add_argument("--pair-id", help="claim_evidence pair id (e.g. ce_caffeine_dep)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--status", action="store_true", help="현재 라벨 진척 보고")
    args = ap.parse_args()

    if args.status:
        status()
    elif args.query_id:
        suggest_for_query(args.query_id, top=args.top)
    elif args.pair_id:
        suggest_for_pair(args.pair_id, top=args.top)
    else:
        ap.print_help()
        print()
        status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
