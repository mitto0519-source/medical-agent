"""조유선 1저자 본문 풀텍스트 (5편) + 메타 (2편) 마디 정량 분석 v3.

★ v2 폐기 사유 (사용자 2026-06-19): "abstract 찌끄라기 X — 본문 마디·스타일별 제대로".
v3 = data/yoosun_seed_papers/seed_full.json (mitto 직접 첨부 PDF 추출) 기반.

산출:
  data/agent_self/yoosun_style_v3.json
  data/agent_self/persona.json (yoosun_style_v3 키 갱신)
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "yoosun_seed_papers" / "seed_full.json"
OUT = ROOT / "data" / "agent_self" / "yoosun_style_v3.json"
PERSONA = ROOT / "data" / "agent_self" / "persona.json"

HEDGE = ["may", "might", "could", "however", "although", "while", "suggest",
          "possibly", "uncertain", "unknown", "remains unknown", "remains uncertain",
          "modestly", "tend to", "further studies"]
WE_INTRO = [r"\bWe\s+(?:investigated|examined|compared|aimed|hypothesized|"
              r"showed|demonstrated|found|considered|stratified|conducted|evaluated)\b"]
PASSIVE = [r"\b(?:were|was|been)\s+(?:adjusted|measured|used|estimated|assessed|"
            r"determined|categorized|stratified|defined|followed|identified|collected|"
            r"calculated|matched|included|excluded|obtained|classified)\b"]
CI_REGEX = re.compile(r"(\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)\s*\)")
FIRST_SECOND = ["First,", "Second,", "Third,", "Fourth,", "Fifth,",
                  "Sixth,", "Finally,", "Lastly,"]


def split_sents(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[\.\?])\s+(?=[A-Z(\[])", text)
    return [p.strip() for p in parts if len(p.strip()) > 10]


def word_count(s: str) -> int:
    return len(re.findall(r"\b\w+\b", s))


def main() -> int:
    d = json.loads(SEED.read_text(encoding="utf-8"))
    papers = [p for p in d["papers"] if isinstance(p, dict) and p.get("pmid")]
    fulltext = [p for p in papers if p.get("fulltext_available")]
    metaonly = [p for p in papers if p.get("metadata_only")]
    print(f"★ 1저자 논문: {len(papers)}편 (풀텍스트 {len(fulltext)} + 메타 {len(metaonly)})")

    # 본문 모든 마디 통합
    full_text_chunks = []
    intro_openings = []
    discussion_openings = []
    limitations_texts = []
    conclusions_openings = []
    results_templates = []
    gap_paragraphs = []
    methods_skeletons = []
    mechanism_paragraphs = []

    for p in fulltext:
        for k in ("introduction_opening", "hypothesis_pattern", "gap_paragraph",
                   "aim_pattern", "methods_skeleton", "stats_methods_pattern",
                   "primary_result_template", "discussion_opening",
                   "discussion_mechanism_pattern", "limitations_pattern",
                   "limitations_pattern_6items", "strengths_pattern",
                   "conclusions_opening", "pathophysiology_pattern"):
            v = p.get(k)
            if v: full_text_chunks.append(v)
        if p.get("introduction_opening"): intro_openings.append(p["introduction_opening"])
        if p.get("discussion_opening"): discussion_openings.append(p["discussion_opening"])
        if p.get("limitations_pattern"): limitations_texts.append(p["limitations_pattern"])
        if p.get("limitations_pattern_6items"): limitations_texts.append(p["limitations_pattern_6items"])
        if p.get("conclusions_opening"): conclusions_openings.append(p["conclusions_opening"])
        if p.get("primary_result_template"): results_templates.append(p["primary_result_template"])
        if p.get("gap_paragraph"): gap_paragraphs.append(p["gap_paragraph"])
        if p.get("methods_skeleton"): methods_skeletons.append(p["methods_skeleton"])
        if p.get("discussion_mechanism_pattern"): mechanism_paragraphs.append(p["discussion_mechanism_pattern"])

    blob = "\n".join(full_text_chunks)
    sents = split_sents(blob)
    lens = [word_count(s) for s in sents]

    # 정량
    hedge_count = sum(1 for w in HEDGE if w.lower() in blob.lower())
    we_count = sum(len(re.findall(pat, blob)) for pat in WE_INTRO)
    passive_count = sum(len(re.findall(pat, blob, re.IGNORECASE)) for pat in PASSIVE)
    cis = [{"est": float(m.group(1)), "lo": float(m.group(2)), "hi": float(m.group(3))}
            for m in CI_REGEX.finditer(blob)]
    first_second_count = sum(blob.count(t) for t in FIRST_SECOND)

    # 표본 N
    ns = [p.get("n") for p in papers if p.get("n")]
    follow_up_years = []
    designs = Counter()
    journals = Counter()
    for p in papers:
        designs[p.get("design", "")] += 1
        journals[p.get("journal", "")] += 1

    metrics = {
        "n_papers_first_author": len(papers),
        "n_fulltext": len(fulltext),
        "n_metadata_only": len(metaonly),
        "n_sentences_extracted": len(sents),
        "avg_sent_len_words": round(statistics.mean(lens), 1) if lens else 0,
        "median_sent_len_words": round(statistics.median(lens), 1) if lens else 0,
        "sent_len_iqr": [round(statistics.quantiles(lens, n=4)[0], 1),
                           round(statistics.quantiles(lens, n=4)[2], 1)] if len(lens) >= 4 else None,
        "hedge_total": hedge_count,
        "we_active_count": we_count,
        "passive_count": passive_count,
        "ci_estimates_extracted": len(cis),
        "sample_ci_estimates": cis[:6],
        "first_second_third_count": first_second_count,
        "sample_sizes": ns,
        "median_n": int(statistics.median(ns)) if ns else 0,
        "max_n": max(ns) if ns else 0,
        "min_n": min(ns) if ns else 0,
        "designs": dict(designs),
        "journals": dict(journals),
    }

    moves_v3 = {
        "M0_journal_pool": "Hepatology Communications · Breast Cancer Res Treat · Eur J Epidemiol · "
                                 "Liver International · Nutrients · Eur J Endocrinol · Archives of Osteoporosis",
        "M1_intro_opening": {
            "template": "X is a Y disease / X is becoming an emerging pandemic / X affect approximately Y% of population / Burden of X is an increasing concern",
            "examples": intro_openings[:3],
        },
        "M2_gap": {
            "template": "Despite ... / Unlike ... / While X has been well studied / Since there are subjects with X, it is unclear whether ...",
            "examples": gap_paragraphs[:2],
        },
        "M3_aim": {
            "template": "Thus, we aimed to / We hypothesized that / Therefore, our aim was to investigate",
        },
        "M4_methods_skeleton": {
            "template": "표본 정의 (n=숫자 Korean adults/women) → 제외 기준 → 변수 측정 (US/questionnaire) → 통계 모델 (Cox PH / Poisson PR) → 보정 (BMI/WC/time-varying)",
            "examples": methods_skeletons[:2],
        },
        "M5_results_inline": {
            "template": "Multivariable-adjusted aHRs/PRs (95% CIs) comparing X to reference were E (Lo-Hi) ... (p-interaction by sex < 0.001).",
            "examples": results_templates[:3],
        },
        "M6_discussion_opening": {
            "template": "In this study, we demonstrated/showed that X. / In the present cross-sectional study of N adults, X was associated with Y.",
            "examples": discussion_openings[:3],
        },
        "M7_mechanism_3steps": {
            "template": "Several hypotheses ... First, X. Secondly, Y. Thirdly, Z.",
            "examples": mechanism_paragraphs[:1],
        },
        "M8_limitations_6items": {
            "template": "Our study has several limitations. First, ... Second, ... Third, ... Fourth, ... Fifth, ... Finally, generalizability ...",
            "examples": limitations_texts[:2],
        },
        "M9_strengths": {
            "template": "Despite these limitations, our study has several strengths. To our knowledge, this is the first study ... We used a nationally representative cohort ...",
        },
        "M10_conclusions": {
            "template": "In conclusion, individuals with X / This cohort study demonstrated / Our findings showed that — 단정 X, 'demonstrated/showed/suggested'",
            "examples": conclusions_openings[:3],
        },
    }

    style_rules = {
        "structure_imrad_strict": "Introduction → Methods → Results → Discussion (Limitations + Strengths + Conclusions).",
        "intro_opening_rule": "갭 도입 첫 문장은 '문제 크기 + 통계' (예: 'NAFLD accounts for 25% of the adult global population').",
        "gap_transition_rule": "기존 연구 인정 + 'However/Despite/Unlike' 전환 + 'remains unknown/uncertain' 종결.",
        "aim_active_rule": "1인칭 복수 능동: 'We aimed to / We hypothesized that / Therefore, our aim was'.",
        "method_passive_rule": "Methods는 수동태 압축: 'were measured/used/adjusted/categorized'.",
        "stats_reporting": "aHR/PR (95% CI) — '1.30 (1.18-1.43)' 소수점 2자리, 하이픈 구분, 괄호 안 공백 X.",
        "effect_modification": "p-interaction by sex/menopause/lean — 명시. 거의 매 논문에 등장.",
        "limitations_first_sixth": "Our study has several limitations. First, ... Second, ... Third, ... Fourth, ... Fifth/Sixth, ... Finally, generalizability — 5~6 항목 정형.",
        "strengths_first_second": "Despite these limitations, ... To our knowledge, this is the first study ... We used a nationally representative cohort.",
        "conclusion_voice": "'demonstrated/showed/suggested' (단정 'proved/causes' 절대 X).",
        "forbidden_overclaim": ["proves", "causes", "definitely", "for the first time without 'to our knowledge'",
                                  "significantly improves (without CI)"],
        "preferred_cohorts": ["Kangbuk Samsung Health Study (KSHS)", "NHIS-HEALS",
                                "Total Healthcare Center cohort"],
        "preferred_estimators": ["Cox proportional hazards (time-dependent)",
                                     "Flexible parametric PH", "Weibull AFT",
                                     "Multivariable Poisson PR", "Multivariable logistic OR"],
        "common_confounders": ["age", "sex", "BMI", "waist circumference",
                                  "education", "physical activity (IPAQ)", "smoking",
                                  "alcohol intake", "menopause", "parity", "age at menarche",
                                  "hypertension", "diabetes", "dyslipidemia medication"],
        "sample_size_typical_range": f"{min(ns):,} ~ {max(ns):,} (중앙값 {int(statistics.median(ns)):,})" if ns else "",
        "follow_up_years_common": "3.7 ~ 5.5 years median",
    }

    out = {
        "version": "3.0-fulltext",
        "built_from": "data/yoosun_seed_papers/seed_full.json (mitto 첨부 PDF 본문 추출)",
        "built_at": "2026-06-19",
        "v2_status": "deprecated (abstract 마디 + 14편 truncated 1500-char)",
        "improvement": "1저자 풀텍스트 5편 (PMID 34529194/33839996/35889762/37387519/36651159) "
                          "+ 메타 2편 (PMID 35503803/37253998) — Introduction/Methods/Results/Discussion/"
                          "Limitations/Strengths/Conclusions 마디별 본문 추출",
        "excluded": "공저자 2편 (사용자 명시 2026-06-19): 공저자는 1저자 stylometry 대상 아님",
        "metrics": metrics,
        "moves": moves_v3,
        "style_rules": style_rules,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # persona inject
    if PERSONA.exists():
        p = json.loads(PERSONA.read_text(encoding="utf-8"))
    else:
        p = {}
    p["yoosun_style_v3"] = {
        "summary": "조유선 1저자 7편 본문 마디 분석 (2026-06-19) — v2(abstract 14편) 폐기",
        "rules": style_rules,
        "metrics_snapshot": {k: metrics[k] for k in
                                ("avg_sent_len_words", "median_sent_len_words",
                                 "ci_estimates_extracted", "we_active_count",
                                 "passive_count", "median_n", "max_n")},
        "templates": {k: v.get("template") for k, v in moves_v3.items() if isinstance(v, dict)},
    }
    # v2 폐기 표시
    if "yoosun_style_v2" in p:
        p["yoosun_style_v2"]["DEPRECATED"] = "v3 대체 — abstract 찌끄라기 X (mitto 2026-06-19)"
    PERSONA.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    # 보고
    print("=" * 60)
    print(f"★ 1저자 풀텍스트 분석 (v3) 완료")
    print(f"  논문 7편 (풀텍스트 5 + 메타 2) — 공저자 2 제외")
    print(f"  추출 문장: {len(sents)} (평균 {metrics['avg_sent_len_words']} 단어)")
    print(f"  헤지 어휘: {hedge_count}회")
    print(f"  수동태: {passive_count}회")
    print(f"  'We' 능동: {we_count}회")
    print(f"  95% CI 추출: {len(cis)}개")
    print(f"  'First/Second/Third/Finally': {first_second_count}회 (Limitations 정형 강도)")
    print(f"  샘플 N: {min(ns):,} ~ {max(ns):,} (중앙값 {int(statistics.median(ns)):,})")
    print(f"  → data/agent_self/yoosun_style_v3.json")
    print(f"  → persona.json yoosun_style_v3 갱신 + v2 DEPRECATED 표시")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
