"""Europe PMC 차집합 fetch — 부족분을 의학 query 셋으로 채움.

이미 ChromaDB에 있는 PMID는 자동 skip (manifest.sqlite).
20+ 의학 query × 500편 = 약 10,000편 신규 fetch.
heartbeat backlog와 충돌하지 않음 — query별 idempotent.

실행: python scripts/fetch_oa_diff.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# 도메인 우선순위 → 일반 → 종합
QUERIES = [
    # 한국 데이터셋 도메인
    "KYRBS adolescent Korea",
    "KNHANES Korea adult survey",
    "ultra-processed food depression",
    "ultra-processed food obesity adolescent",
    "MASLD MetALD steatotic liver",
    "NAFLD metabolic syndrome Asian",
    "caffeine consumption mental health adolescent",
    "sleep duration cardiovascular outcome",
    "sleep duration suicide ideation adolescent",
    "screen time depression youth",
    # 만성질환
    "diabetes type 2 Korean cohort",
    "hypertension elderly Korea",
    "dyslipidemia treatment outcome",
    "metabolic syndrome IDF Asian",
    "CKD chronic kidney disease eGFR",
    # 영양·운동
    "physical activity vigorous moderate",
    "Mediterranean diet cardiovascular",
    "DASH diet hypertension",
    "sodium intake blood pressure",
    "dietary pattern depression",
    # 정신건강
    "depression anxiety adolescent screening",
    "suicide ideation risk factor",
    "perceived stress quality of life",
    "anxiety disorder elderly",
    "alcohol use disorder prevalence",
    # 인구·역학
    "survey weighted analysis epidemiology",
    "cross-sectional study Korea adult",
    "longitudinal cohort follow-up",
    "STROBE observational study",
    "PRISMA systematic review meta-analysis",
]


def main() -> int:
    from src.ingestion.oa_bulk_fetcher import fetch_oa_batch, manifest_stats
    print("=" * 60)
    print(f"Europe PMC OA 차집합 fetch — {len(QUERIES)} queries × 500편 max")
    print("=" * 60)

    s0 = manifest_stats()
    print(f"\n시작 상태: total={s0.get('total_papers', 0):,} chunked={s0.get('chunked_papers', 0):,}")

    total_fetched = 0
    total_skipped = 0
    total_failed = 0
    for i, q in enumerate(QUERIES, 1):
        print(f"\n[{i}/{len(QUERIES)}] query: {q!r}")
        try:
            r = fetch_oa_batch(q, n_target=500, skip_if_exists=True)
            print(f"  → fetched={r.get('fetched', 0)} skipped={r.get('skipped', 0)} failed={r.get('failed', 0)}")
            total_fetched += r.get("fetched", 0)
            total_skipped += r.get("skipped", 0)
            total_failed += r.get("failed", 0)
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")
            total_failed += 1
        time.sleep(2)  # query 사이 rate limit courtesy

    print()
    print("=" * 60)
    print(f"종료: fetched={total_fetched:,} skipped={total_skipped:,} failed={total_failed:,}")

    s1 = manifest_stats()
    delta = s1.get("total_papers", 0) - s0.get("total_papers", 0)
    print(f"manifest 변화: {s0.get('total_papers', 0):,} → {s1.get('total_papers', 0):,} (+{delta:,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
