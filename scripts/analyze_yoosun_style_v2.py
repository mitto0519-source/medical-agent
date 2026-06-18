"""조유선 5편 abstract 마디(rhetorical move) 단위 정량 분석.

★ 사용자 명시 (2026-06-19): "초록 찌끄라기로 Graph db 하지 말고 마디별·스타일별 제대로".
data/yoosun_seed_papers/seed_5.json (마디별 추출 완료) → 정량 metric + persona inject.

산출:
  data/agent_self/yoosun_style_v2.json — 정량 + 정성 패턴
  data/agent_self/persona.json — yoosun_style_v2 키 갱신 (LLM 호출에 자동 inject)
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "yoosun_seed_papers" / "seed_5.json"
OUT = ROOT / "data" / "agent_self" / "yoosun_style_v2.json"
PERSONA = ROOT / "data" / "agent_self" / "persona.json"

HEDGE_WORDS = ["uncertain", "unknown", "may", "might", "suggest", "modestly",
                "remains unknown", "is unclear", "further studies are needed"]
PASSIVE_MARKERS = [r"\bwere\s+(?:used|measured|estimated|assessed|adjusted|"
                     r"identified|determined|categorized|stratified|"
                     r"followed\s+up)\b",
                    r"\bwas\s+(?:assessed|measured|used|determined|defined)\b"]
WE_INTROS = [r"^We\s+(?:investigated|examined|compared|studied|aimed)\b"]
EFFECT_MARKERS = ["p-interaction", "P for interaction", "effect modification",
                    "stronger in women", "differed by"]
CI_PATTERN = re.compile(r"(\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)\s*\)")
N_PATTERN = re.compile(r"\bn\s*=\s*([\d,]+)|(\d{3,}(?:,\d{3})*)\s+(?:Korean|adults|women|participants|individuals)")


def split_sentences(text: str) -> list[str]:
    # 단순 (. ?) 끝 분리 + 약식
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[\.\?])\s+(?=[A-Z(])", text)
    return [p.strip() for p in parts if len(p.strip()) > 8]


def sentence_lengths(sents: list[str]) -> list[int]:
    return [len(re.findall(r"\b\w+\b", s)) for s in sents]


def count_pattern(text: str, patterns: list[str]) -> int:
    text_l = text.lower()
    return sum(1 for p in patterns if p.lower() in text_l)


def regex_count(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)


def analyze() -> dict:
    d = json.loads(SEED.read_text(encoding="utf-8"))
    papers = d["papers"]
    assert len(papers) == 5, f"expected 5, got {len(papers)}"

    all_text_per_move = {f"M{i}": [] for i in range(1, 9)}
    all_sentences = []
    all_full_text = []
    ci_estimates = []   # (est, ci_low, ci_high)
    n_values = []
    follow_up_years = []
    designs = Counter()
    cohorts = Counter()
    models = Counter()
    exposures = []
    outcomes = []

    # 마디별 통합
    for p in papers:
        moves = p.get("moves", {})
        for k, txt in moves.items():
            if not isinstance(txt, str): continue
            mkey = k.split("_")[0]   # 'M1' / 'M2' / ...
            if mkey in all_text_per_move:
                all_text_per_move[mkey].append(txt)
            all_sentences.extend(split_sentences(txt))
            all_full_text.append(txt)
        # 메타
        n_values.append(p.get("n"))
        if p.get("follow_up_median_years"):
            follow_up_years.append(p["follow_up_median_years"])
        designs[p.get("design", "")] += 1
        cohorts[p.get("cohort", "")] += 1
        models[p.get("model", "")] += 1
        exposures.append(p.get("exposure", ""))
        outcomes.append(p.get("outcome", ""))

    full_text = "\n".join(all_full_text)
    lengths = sentence_lengths(all_sentences)

    # CI 추출
    for m in CI_PATTERN.finditer(full_text):
        try:
            ci_estimates.append({
                "estimate": float(m.group(1)),
                "ci_low": float(m.group(2)),
                "ci_high": float(m.group(3)),
            })
        except Exception:
            pass

    # 정량 metrics
    metrics = {
        "n_papers": len(papers),
        "n_sentences_total": len(all_sentences),
        "avg_sent_len_words": round(statistics.mean(lengths), 1) if lengths else 0,
        "median_sent_len_words": round(statistics.median(lengths), 1) if lengths else 0,
        "sent_len_p25_p75": [
            round(statistics.quantiles(lengths, n=4)[0], 1),
            round(statistics.quantiles(lengths, n=4)[2], 1),
        ] if len(lengths) >= 4 else None,

        "hedge_count": count_pattern(full_text, HEDGE_WORDS),
        "hedge_per_sentence": round(count_pattern(full_text, HEDGE_WORDS) / max(len(all_sentences), 1), 3),

        "passive_count": regex_count(full_text, PASSIVE_MARKERS),
        "passive_per_sentence": round(regex_count(full_text, PASSIVE_MARKERS) / max(len(all_sentences), 1), 3),

        "we_intro_count": regex_count(full_text, WE_INTROS),
        "effect_modification_signal": count_pattern(full_text, EFFECT_MARKERS),

        "n_CI_estimates": len(ci_estimates),
        "CI_estimates_sample": ci_estimates[:8],

        "design_distribution": dict(designs),
        "cohort_distribution": dict(cohorts),
        "model_distribution": dict(models),
        "sample_sizes": [p["n"] for p in papers],
        "median_n": int(statistics.median([p["n"] for p in papers])),
        "follow_up_years_range": [min(follow_up_years), max(follow_up_years)] if follow_up_years else None,

        "exposures": exposures,
        "outcomes": outcomes,
    }

    # 마디별 정성 패턴
    moves_pattern = {
        "M1_gap_template": "X effect of Y on Z is uncertain/unknown/remains unknown.",
        "M1_examples": all_text_per_move["M1"][:2],
        "M2_aim_template": "We investigated/examined/compared (a) whether X is...; and (b) whether X adds to...",
        "M2_examples": all_text_per_move["M2"][:2],
        "M3_methods_skeleton": [
            "n=<숫자> Korean adults/women without <outcome>",
            "<exposure> was measured using <ultrasonography/questionnaire>",
            "Cox proportional hazards models / Flexible parametric PH / Poisson PR",
            "Sex-specific adjusted hazard ratios (aHRs) with 95% CIs",
            "Adjusted for BMI / waist circumference / time-dependent covariates",
        ],
        "M4_result_template": "aHRs (95% CIs) for X comparing A versus B were E1 (Lo1-Hi1) and E2 (Lo2-Hi2) (p-interaction by sex < 0.001).",
        "M4_examples": all_text_per_move["M4"][:2],
        "M5_secondary_template": "These associations were also more pronounced in <subgroup> than <subgroup> (p-interaction < 0.001).",
        "M6_sensitivity_template": "Associations remained significant even after adjustment for <X>.",
        "M7_added_value_template": "The addition of X modestly improved risk prediction (C-index, NRI, IDI).",
        "M8_conclusion_template": "X is a complementary index / synergistically increases risk / association differed by <modifier>.",
        "M8_examples": all_text_per_move["M8"][:2],
    }

    style_rules = {
        "structure_4_para": "Background/Aims → Methods → Results → Conclusion (한 단락씩, 헤딩 X)",
        "opening": "갭부터 시작 — 'effect of X on Y is uncertain/unknown' 한 문장",
        "aim_voice": "We investigated/examined/compared — 능동 1인칭 복수",
        "method_voice": "Were measured / were used / were assessed — 수동, 압축",
        "estimate_format": "★ aHR/PR (95% CI) 양식 — '1.30 (1.18-1.43)' 정확히 (소수점 2자리, 하이픈 구분, 괄호 안 공백 X)",
        "interaction": "★ p-interaction by sex/menopause 명시 — effect modification은 거의 매 논문",
        "sample_size_emphasis": f"n 값 명시 (이 5편 중앙값 {int(statistics.median([p['n'] for p in papers])):,})",
        "follow_up_emphasis": f"median follow-up <Y> years 명시 (이 5편 범위 {min(follow_up_years)}-{max(follow_up_years)}년)",
        "covariate_adjustment": "BMI, waist circumference, time-dependent covariates 명시 — sensitivity까지",
        "lean_subgroup": "lean (BMI<23) vs overweight 별도 분석 — 1자수 분석 (이 5편 중 3편 명시)",
        "conclusion_style": "한 문장 (또는 두 문장). 'complementary index' / 'synergistically' / 'differed by'",
        "hedge_style": "uncertain/unknown (도입), modestly/may (결과), Further studies are needed (한계)",
        "forbidden_overclaim": ["causes", "definitely", "for the first time", "significantly improves" + " 단정"],
        "preferred_journals": ["Hepatology Communications", "European Journal of Epidemiology",
                                  "Liver International", "Breast Cancer Research and Treatment",
                                  "Nutrients", "JKMS"],
        "preferred_cohort_phrase": "Kangbuk Samsung Health Study (KSHS) — 51만+ 한국 성인 / 여성 코호트",
        "preferred_estimator": ["Cox proportional hazards", "Flexible parametric PH", "Weibull AFT",
                                  "Multivariable Poisson (PR)"],
        "ancillary_metrics": ["AUROC", "Net Reclassification Improvement (NRI)",
                                "Integrated Discrimination Improvement (IDI)", "C-index", "RERI"],
    }

    out = {
        "version": "2.0",
        "built_from": "data/yoosun_seed_papers/seed_5.json (5 papers 마디 정확 추출)",
        "built_at": "2026-06-19",
        "previous_version": "yoosun_seed (abstract 요약만, n=11/14)",
        "improvement": "★ abstract '찌끄라기' → 마디(M1~M8) 정확 추출 + 통계 양식 정량",
        "metrics": metrics,
        "moves_pattern": moves_pattern,
        "style_rules": style_rules,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def inject_into_persona(style_v2: dict) -> None:
    """persona.json에 yoosun_style_v2 키 갱신 → build_full_system에 자동 inject."""
    p = json.loads(PERSONA.read_text(encoding="utf-8")) if PERSONA.exists() else {}
    p["yoosun_style_v2"] = {
        "summary": "조유선 5편 마디 단위 정량 분석 (2026-06-19)",
        "rules": style_v2["style_rules"],
        "metrics_snapshot": {
            "avg_sent_len_words": style_v2["metrics"]["avg_sent_len_words"],
            "median_sent_len_words": style_v2["metrics"]["median_sent_len_words"],
            "hedge_per_sentence": style_v2["metrics"]["hedge_per_sentence"],
            "passive_per_sentence": style_v2["metrics"]["passive_per_sentence"],
            "n_CI_estimates": style_v2["metrics"]["n_CI_estimates"],
            "median_n": style_v2["metrics"]["median_n"],
        },
        "templates": style_v2["moves_pattern"],
    }
    PERSONA.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def report(style: dict) -> str:
    m = style["metrics"]
    lines = [
        "=" * 60,
        f"★ 조유선 5편 마디별 분석 (yoosun_style_v2)",
        "=" * 60,
        f"  논문 수            : {m['n_papers']}편",
        f"  추출 문장          : {m['n_sentences_total']}개",
        f"  평균 문장 길이      : {m['avg_sent_len_words']} 단어 (중앙값 {m['median_sent_len_words']})",
        f"  IQR(p25~p75)       : {m['sent_len_p25_p75']}",
        "",
        f"  헤지 표현 빈도     : {m['hedge_count']}회 / 문장당 {m['hedge_per_sentence']}",
        f"  수동태 빈도        : {m['passive_count']}회 / 문장당 {m['passive_per_sentence']}",
        f"  'We …' 1인칭 복수  : {m['we_intro_count']}회",
        f"  effect mod 신호    : {m['effect_modification_signal']}회",
        "",
        f"  추출 추정치(95% CI): {m['n_CI_estimates']}개",
        f"  샘플 N             : {m['sample_sizes']} (중앙값 {m['median_n']:,})",
        f"  추적 기간 범위      : {m['follow_up_years_range']}년",
        f"  설계 분포          : {m['design_distribution']}",
        f"  모델 분포          : {m['model_distribution']}",
        "",
        f"★ persona.json yoosun_style_v2 갱신 → 매 LLM 호출에 자동 inject",
        f"★ 정직 보고: 이건 본문 5편 전체가 아니라 abstract 마디 5편 (mitto가 본문 PDF는 별도 위치 필요).",
    ]
    return "\n".join(lines)


def main() -> int:
    style = analyze()
    inject_into_persona(style)
    print(report(style))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
