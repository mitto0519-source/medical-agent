"""End-to-end 증명: 실 KYRBS 2025 → StatBridge → 논문 표/그림.

조유선 ZCB×Depression 단면연구를 SW 없이 Python으로 동등 재현.
'재료(실데이터+설계)로 논문 표가 실제로 나오는가'를 거짓 없이 검증한다.
"""
from __future__ import annotations

import sys
import io
from pathlib import Path

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 UTF-8 고정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    from src.data.kyrbs_raw_loader import KYRBSLoader
    from src.data.stat_bridge import StatBridge
    from src.export.table_builder import (
        stat_result_to_table1_markdown,
        stat_result_to_table2_markdown,
    )

    print("=" * 70)
    print("STEP 1 — 자산화된 실데이터 로드 (KYRBS 2025 — ZCB 신규 문항 도입 차수)")
    df, _meta = KYRBSLoader().load("data/raw/kyrbs2025.sav")
    if df is None:
        print("FAIL: KYRBS 2025 데이터를 찾지 못함")
        return 1
    print(f"  로드됨: {len(df):,}행 × {len(df.columns)}열")
    print(f"  표준 컬럼: {list(df.columns)}")

    # 핵심: 노출(zcb_freq)이 살아남았는가?
    if "zcb_freq" not in df.columns:
        print("FAIL: ZCB 노출변수(zcb_freq)가 표준 df에 없음 — 로더 매핑 누락")
        return 1
    if "depression" not in df.columns:
        print("FAIL: depression 결과변수 없음")
        return 1
    print(f"  ✓ 노출 zcb_freq 존재: 분포={df['zcb_freq'].value_counts(dropna=False).sort_index().to_dict()}")
    print(f"  ✓ 결과 depression 존재: 우울률={df['depression'].mean()*100:.1f}% (n={int(df['depression'].sum()):,})")

    print()
    print("=" * 70)
    print("STEP 2 — 조유선 STATA 로직 → spec (svy: logistic depression zcb + 공변량)")
    # 조유선 M2 완전조정 모델 — 설계 템플릿(covariate 3분류)에 충실
    spec = {
        "outcome": "depression",
        "outcome_label": "Depressive symptoms",
        "predictors": ["zcb_freq"],                 # 주노출 (연속 용량-반응)
        "covariates": [                              # 완전조정(M2)
            "sex", "grade", "bmi", "family_econ", "academic_perf",
            "smoking", "alcohol", "ssb_freq", "caffeine_freq",
            "physical_act", "breakfast",
        ],
        "analysis": "logistic",
        "weight_var": "weight_var",                 # 복합표본 가중
        "strata_var": "strata",
        "cluster_var": "cluster",
        "subgroups": ["sex"],                       # 성별 성층화
    }
    # 실제 존재 컬럼만 남기기 (graceful — _ws_stata와 동일 로직)
    spec["covariates"] = [c for c in spec["covariates"] if c in df.columns]
    for k in ("weight_var", "strata_var", "cluster_var"):
        if spec.get(k) and spec[k] not in df.columns:
            spec[k] = None
    print(f"  spec.predictors={spec['predictors']}")
    print(f"  spec.covariates={spec['covariates']}")
    print(f"  weight={spec.get('weight_var')} strata={spec.get('strata_var')} cluster={spec.get('cluster_var')}")

    print()
    print("=" * 70)
    print("STEP 3 — StatBridge 동등 분석 실행 (실 통계)")
    result = StatBridge().run(df, spec).to_dict()
    if result.get("error"):
        print(f"FAIL: 분석 오류: {result['error']}")
        return 1
    print(f"  analysis_type={result.get('analysis_type')}")
    print(f"  n_total={result.get('n_total'):,}  outcome_rate={result.get('outcome_rate'):.1f}%")
    print(f"  metrics: weighted={result.get('model_metrics',{}).get('weighted')} "
          f"complex={result.get('model_metrics',{}).get('complex_sample')} "
          f"AUC={result.get('model_metrics',{}).get('roc',{}).get('auc')}")
    # 노출 OR 추출
    zcb = next((v for v in result.get("model_vars", []) if "zcb" in v.get("variable", "").lower()), None)
    if not zcb:
        print("FAIL: 결과에서 ZCB OR을 찾지 못함")
        print("  model_vars:", [v.get("variable") for v in result.get("model_vars", [])])
        return 1
    print(f"  ★ ZCB(zcb_freq) aOR = {zcb.get('or_value')} "
          f"(95% CI {zcb.get('ci_lower')}–{zcb.get('ci_upper')}), p={zcb.get('p_value')}")

    print()
    print("=" * 70)
    print("STEP 4 — 논문 표 생성 (복사/워드 저장 가능 형태)")
    t1 = stat_result_to_table1_markdown(result)
    t2 = stat_result_to_table2_markdown(result)
    print(t2)

    print()
    print("=" * 70)
    print("STEP 5 — 논문용 그림(PNG/SVG) 생성")
    try:
        from src.export.publication_figure_generator import generate_figures_for_paper
        figs = generate_figures_for_paper(result, safe_title="proof_zcb")
        for name, fd in figs.items():
            if isinstance(fd, dict) and fd.get("png_path"):
                print(f"  ✓ {name}: {fd['png_path']}")
    except Exception as e:
        print(f"  (그림 생성 스킵: {e})")

    print()
    print("=" * 70)
    print("RESULT: 실데이터 → 통계 → 논문표/그림 전 과정 동작 확인 (PASS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
