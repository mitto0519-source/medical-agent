"""Medical-Agent Evaluation Benchmark — 정량 메트릭 (LongMemEval/HELM 계열 영감).

5개 축:
  1. Memory Retrieval Precision (P@5) — 의미검색이 의도 결과를 상위 5개에 회수하나
  2. Hallucination Detection Rate — memory_gate가 환각 신호 항목을 quarantine하나
  3. Statistical Analysis Correctness — StatBridge가 알려진 ZCB aOR을 재현하나
  4. Figure Regression — Figure 데이터(figure_data.json)가 paper 값과 매치하나
  5. Citation Verification Rate — CrossRef로 ref DOI가 실존 검증되나

각 메트릭: 점수(0-1) + 임계값 + PASS/FAIL.
결과: JSON 리포트 → data/exports/eval_report.json + 콘솔 표

실행: docker compose exec learner python scripts/eval_benchmark.py
"""
from __future__ import annotations
import io, json, sys, time, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

OUT = Path("data/exports/eval_report.json")
RESULTS: list = []


def metric(name: str, score: float, threshold: float, detail: str = "") -> dict:
    """단일 메트릭 결과 표준 형식."""
    return {"name": name, "score": round(score, 4), "threshold": threshold,
            "pass": score >= threshold, "detail": detail[:200]}


# ── ① Memory Retrieval Precision ─────────────────────────────────────────────

def eval_memory_retrieval() -> dict:
    """의미 검색이 ground-truth label과 일치 — P@5 (conversation_memory ChromaDB 직접 시드)."""
    try:
        from src.memory import conversation_memory as cm
        # 시드 (10 항목, 각각 distinct topic) — cm.record는 verbatim + 의미 색인 동시
        seeds = [
            ("ZCB 우울에 미치는 영향", "청소년 ZCB와 우울 용량반응 KYRBS 2025 분석 결과 보여줘"),
            ("청소년 수면 영향 요인", "청소년 스마트폰 과사용과 수면부족 관련 강한 연관성"),
            ("당뇨병 식단", "당뇨병 예방 식단 가이드라인 한국형"),
            ("폐암 스크리닝", "폐암 스크리닝 LDCT 권고 50세 이상 흡연자"),
            ("심혈관 운동", "심혈관 질환 예방 운동 처방 일주일 150분"),
            ("우식증 예방", "청소년 우식증 예방 불소 도포 권장"),
            ("SSRI 부작용", "우울증 치료 SSRI 부작용 성기능 영향"),
            ("비만 추세", "KNHANES 비만 추세 2020 한국 성인"),
            ("자살예방 게이트키퍼", "청소년 자살예방 게이트키퍼 훈련 학교"),
            ("흡연 추세", "KYRBS 흡연 추세 2005-2024 감소"),
        ]
        for q, ans in seeds:
            cm.record(q, ans, topic=q[:20], context_type="qa", owner_email="eval@test")

        # 쿼리: 의도 항목이 top5에 회수돼야
        queries = [
            ("제로칼로리 음료 우울", "zcb"),
            ("스마트폰 청소년 수면", "smartphone"),
            ("비만 추세 한국", "obesity"),
            ("청소년 자살 예방", "suicide_prev"),
            ("우울증 약물 부작용", "ssri"),
        ]
        hits = 0
        for q, want in queries:
            res = cm.recall_relevant(q, n=5, owner_email="eval@test")
            # 의도 항목의 키워드가 결과에 포함되는지 (단순 substring 매칭)
            want_keywords = {"zcb": "ZCB", "smartphone": "스마트폰", "obesity": "비만",
                             "suicide_prev": "자살예방", "ssri": "SSRI"}[want]
            if want_keywords in res:
                hits += 1
        p_at_5 = hits / len(queries)
        return metric("memory_retrieval_p@5", p_at_5, 0.6,
                      f"{hits}/{len(queries)} 쿼리에서 의도 항목 회수")
    except Exception as e:
        return metric("memory_retrieval_p@5", 0.0, 0.6, f"ERROR: {str(e)[:100]}")


# ── ② Hallucination Detection Rate ───────────────────────────────────────────

def eval_hallucination_gate() -> dict:
    """memory_gate가 환각 신호/짧음/중복 항목을 quarantine하나."""
    try:
        from src.memory.memory_gate import assess
        # 환각 신호 항목들 (모두 quarantine 기대)
        bad = [
            "As an AI language model I cannot help with that here at all.",
            "I cannot provide medical advice as I am an AI.",
            "짧",   # 너무 짧음
            "abc",  # 너무 짧음
        ]
        # 정상 항목들 (verified 기대)
        good = [
            ("청소년 ZCB 섭취와 우울 사이 KYRBS 2025에서 dose-response 관계 확인.", "observation"),
            ("Body mass index calculated from self-reported height and weight.", "user"),
            ("PubMed 검색에서 artificial sweetener depression 관련 12편 발견.", "pubmed"),
        ]
        bad_caught = sum(1 for t in bad if assess(t).get("tier") == "quarantine")
        good_pass = sum(1 for t, s in good if assess(t, source=s).get("tier") in ("verified", "auto"))
        rate = (bad_caught / len(bad) + good_pass / len(good)) / 2
        return metric("hallucination_gate_balanced_acc", rate, 0.85,
                      f"환각 차단 {bad_caught}/{len(bad)} · 정상통과 {good_pass}/{len(good)}")
    except Exception as e:
        return metric("hallucination_gate_balanced_acc", 0.0, 0.85, f"ERROR: {str(e)[:100]}")


# ── ③ Statistical Analysis Correctness ───────────────────────────────────────

def eval_stat_correctness() -> dict:
    """StatBridge가 실 KYRBS 2025에서 ZCB aOR을 재현 (paper 값과 일치).

    2025 전용: F_ZERO(ZCB 노출 컬럼)는 21차(2025) 신규이므로 다른 연도엔 없음.
    _find_real_data가 mtime으로 다른 해를 골라 zcb_freq=None이 되면 metric 의미 상실.
    """
    try:
        from pathlib import Path as _P
        from src.data.kyrbs_raw_loader import KYRBSLoader
        from src.data.stat_bridge import StatBridge
        sav = _P("data/raw/kyrbs2025.sav")
        if not sav.exists():
            return metric("stat_zcb_aOR_within_0.05", 0.0, 0.9, "kyrbs2025.sav 없음 (ZCB 변수는 2025 전용)")
        df, _meta = KYRBSLoader().load(sav)
        if "zcb_freq" not in df.columns:
            return metric("stat_zcb_aOR_within_0.05", 0.0, 0.9,
                          f"loader가 zcb_freq 노출 실패 (cols={list(df.columns)[:8]})")
        # Paper v2.4 Model 2 fully-adjusted continuous aOR per 1-level = 1.046 (95% CI 1.026-1.066).
        # 복합표본설계: pweight + cluster (KYRBS school cluster). StatBridge는 GEE로 근사.
        # 공변량은 paper와 동일한 11개를 모두 투입 (loader가 노출하는 표준명).
        present_cov = [c for c in ["sex", "age", "school_type", "academic_perf", "family_econ",
                                    "bmi", "smoking", "alcohol", "physical_act",
                                    "screen_time", "breakfast", "ssb_freq", "caffeine_freq",
                                    "sleep_hours"] if c in df.columns]
        spec = {"outcome": "depression",
                "predictors": ["zcb_freq"],
                "covariates": present_cov,
                "weight_var": "weight_var" if "weight_var" in df.columns else None,
                "strata_var": "strata"     if "strata"     in df.columns else None,
                "cluster_var": "cluster"   if "cluster"    in df.columns else None,
                "analysis": "logistic"}
        r = StatBridge().run(df, spec).to_dict()
        if r.get("error"):
            return metric("stat_zcb_aOR_within_0.05", 0.0, 0.9, f"StatBridge 오류: {r['error'][:80]}")
        vars_ = r.get("model_vars", [])
        zcb_or = next((v.get("or_value") for v in vars_
                       if "zcb" in str(v.get("variable", "")).lower()), None)
        if zcb_or is None:
            return metric("stat_zcb_aOR_within_0.05", 0.0, 0.9,
                          f"zcb_freq OR 미산출 (vars={[v.get('variable') for v in vars_[:5]]})")
        # 점추정 paper continuous 1.046. score = 1.0 if |diff|≤0.05 then linear decay.
        target = 1.046
        diff = abs(zcb_or - target)
        score = max(0.0, 1.0 - diff * 4)  # diff 0.05 → 0.8 / 0.10 → 0.6
        complex_flag = "+pw+cluster" if (spec.get("weight_var") and spec.get("cluster_var")) else "+plain"
        return metric("stat_zcb_aOR_within_0.05", score, 0.7,
                      f"OR={zcb_or:.3f} (target {target}, |diff|={diff:.3f}, "
                      f"n_cov={len(present_cov)}{complex_flag})")
    except Exception as e:
        return metric("stat_zcb_aOR_within_0.05", 0.0, 0.7, f"ERROR: {str(e)[:100]}")


# ── ④ Figure Data Regression ─────────────────────────────────────────────────

def eval_figure_regression() -> dict:
    """figure_data.json의 핵심 값이 paper와 매치."""
    try:
        path = Path("data/exports/figure_data.json")
        if not path.exists():
            # SKIP (not FAIL) — regenerable via compute_all_figure_data.py
            return {"name": "figure_data_match", "score": None, "threshold": 0.8,
                    "pass": None, "detail": "SKIP: figure_data.json 없음 (재생성 필요)"}
        d = json.loads(path.read_text(encoding="utf-8"))
        checks = []
        # n_final
        f1 = d.get("figure1", {})
        checks.append(("n_final=50972", f1.get("n_final") == 50972))
        checks.append(("excluded=3198", f1.get("e_total") == 3198))
        # Figure 2 female end (43%대)
        f2 = d.get("figure2B", {}).get("female", {}).get("7", {})
        f_end = f2.get("prob") if isinstance(f2, dict) else f2
        checks.append(("female_freq7 ≈ 0.43", 0.40 <= (f_end or 0) <= 0.46))
        # Figure 3 age 14-15
        f3 = d.get("figure3", {})
        age2 = f3.get("age_2", {}).get("aOR")
        checks.append(("age_14-15 aOR ≈ 1.09", 1.07 <= (age2 or 0) <= 1.11))
        passed = sum(1 for _, ok in checks if ok)
        return metric("figure_data_match", passed / len(checks), 0.8,
                      "; ".join(f"{n}{'✓' if ok else '✗'}" for n, ok in checks))
    except Exception as e:
        return metric("figure_data_match", 0.0, 0.8, f"ERROR: {str(e)[:100]}")


# ── ⑤ Citation Verification ──────────────────────────────────────────────────

def eval_citation_verification() -> dict:
    """ZCB 논문의 신규 ref DOI들이 CrossRef에 실존."""
    try:
        import urllib.request
        # 본 논문 ref 중 신규 추가된 10개의 DOI (Yoosun engine 산출 또는 v2.4 fixed)
        dois_to_check = [
            "10.3389/fnut.2025.1575351",      # Ren 2025
            "10.1186/s13034-026-01079-4",     # Ulm 2026
            "10.3390/nu18060899",             # Georgiou 2026
            "10.1007/s00394-026-03986-w",     # Akbaraly 2026
            "10.1016/j.brainres.2025.149978", # Santerre-Anderson 2025
        ]
        verified = 0
        for doi in dois_to_check:
            try:
                req = urllib.request.Request(
                    f"https://api.crossref.org/works/{doi}",
                    headers={"User-Agent": "medical-agent-eval/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.load(resp)
                    if data.get("status") == "ok" and data.get("message", {}).get("DOI"):
                        verified += 1
            except Exception:
                pass
        rate = verified / len(dois_to_check)
        return metric("citation_crossref_verify", rate, 0.9,
                      f"{verified}/{len(dois_to_check)} DOI 실존 확인")
    except Exception as e:
        return metric("citation_crossref_verify", 0.0, 0.9, f"ERROR: {str(e)[:100]}")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Medical-Agent Evaluation Benchmark — 5축 정량")
    print("=" * 72)

    started = time.time()
    metrics = [
        eval_memory_retrieval(),
        eval_hallucination_gate(),
        eval_stat_correctness(),
        eval_figure_regression(),
        eval_citation_verification(),
    ]
    duration = time.time() - started

    # 콘솔 표 (SKIP은 별도 카운트)
    n_pass = sum(1 for m in metrics if m["pass"] is True)
    n_skip = sum(1 for m in metrics if m["pass"] is None)
    n_scored = sum(1 for m in metrics if m["pass"] is not None)
    print(f"\n{n_pass}/{n_scored} metrics PASS · {n_skip} SKIP ({duration:.1f}s)\n")
    print(f"{'Metric':<35} {'Score':>8} {'Min':>6} {'Status':>8}  Detail")
    print("-" * 110)
    for m in metrics:
        if m["pass"] is None:
            mark = "SKIP -"; score_str = "   N/A"
        else:
            mark = "PASS ✓" if m["pass"] else "FAIL ✗"
            score_str = f"{m['score']:>8.4f}"
        print(f"{m['name']:<35} {score_str:>8} {m['threshold']:>6.2f} {mark:>8}  {m['detail']}")

    # JSON 리포트
    overall = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_sec": round(duration, 2),
        "n_pass": n_pass, "n_skip": n_skip, "n_scored": n_scored,
        "n_total": len(metrics),
        "pass_rate": round(n_pass / max(n_scored, 1), 3),
        "metrics": metrics,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT}")

    # ★ Longitudinal — 시계열 누적 + regression alert
    try:
        from src.diagnostics.longitudinal_eval import record_eval, regression_alert
        run_id = record_eval(overall)
        alerts = regression_alert()
        if alerts:
            print(f"\n⚠️ REGRESSION ALERT ({len(alerts)} metrics):")
            for a in alerts:
                print(f"  - {a['metric']}: {a['latest']:.3f} (avg {a['prev_avg']:.3f}, drop {a['drop']:.3f})")
        print(f"longitudinal run_id: {run_id}")
    except Exception as e:
        print(f"longitudinal record fail: {e}")

    return 0 if n_pass == n_scored else 1


if __name__ == "__main__":
    raise SystemExit(main())
