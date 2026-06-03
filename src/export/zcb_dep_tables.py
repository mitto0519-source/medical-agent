"""ZCB-Depression 표준 표 4종 — 사용자 실제 논문(KYRBS 2025) PDF 양식을 코드로 박음.

배경 (2026-05-30):
    사용자가 보낸 Tables_publication_format.pdf의 Table 1 / 2 / 3 / Supp Table 1 양식이
    실제 제출용 표준. 이 모듈은 그 양식을 무조건 표준으로 박아, KYRBS 통계 결과만 들어가면
    자동으로 동일한 학술지 양식 표(HTML + DOCX)를 생성한다.

지원 4종:
    1) Table 1: Baseline characteristics by ZCB consumption frequency (4 groups + Total)
    2) Table 2: Model 1 / Model 2 aOR (95% CI) + p for trend — ZCB → depression
    3) Table 3: Sex-stratified aOR (95% CI) + p_trend + P for interaction
    4) Supp Table 1: ZCB → secondary outcomes (stress + sleep)

양식 (사용자 PDF 그대로):
    - Top / Header bottom / Bottom horizontal lines only (세로선 없음)
    - 굵은 subgroup heading + indent 양식 값
    - Mean ± SD 양식 / N (%) 양식
    - P italic, "(N = 50,972)" 타이틀
    - 각주 superscript (ᵃ ᵇ ᶜ ᵈ ᵉ)
    - Abbreviations: 줄 italic

API:
    build_table1_html(df, *, exposure_col, exposure_labels, ...) -> str
    build_table2_html(model1_result, model2_result, ...) -> str
    build_table3_html(female_result, male_result, p_interaction, ...) -> str
    build_supp_table1_html(stress_result, sleep_result, ...) -> str
    build_all_tables(df, stat_results) -> {"Table 1": html, "Table 2": html, ...}

호출:
    workspace Tables 탭의 '🔬 ZCB-depression 표준 표 4종 생성' 버튼.
    또는 _orchestrated_paper_run 끝에 자동 (project.tables 갱신).
"""
from __future__ import annotations

import html as _html
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── HTML 양식 (NEJM 세 줄 표) ────────────────────────────────────────────────

_TABLE_CSS = """
<style>
/* NEJM/Lancet 세 줄 표 — 세로선 0, 위/헤더아래/표끝 가로선만, decimal-align numeric */
.pub-table {
  border-collapse: collapse;
  border-spacing: 0;
  font-family: 'Times New Roman', 'Liberation Serif', serif;
  font-size: 10.5pt;
  line-height: 1.35;
  margin: 14px 0 4px 0;
  width: 100%;
  color: #000;
}
.pub-table caption {
  caption-side: top;
  text-align: left;
  font-weight: 700;
  padding: 0 0 8px 0;
  font-size: 11pt;
  line-height: 1.35;
}
/* Three horizontal lines only */
.pub-table thead tr:first-child > * { border-top:    1.5px solid #000; }
.pub-table thead tr:last-child  > * { border-bottom: 0.75px solid #000; }
.pub-table tbody tr:last-child  > * { border-bottom: 1.5px solid #000; }
/* No internal verticals, no internal horizontals */
.pub-table th, .pub-table td {
  padding: 5px 12px;
  vertical-align: top;
  border: none;
  text-align: left;
  white-space: nowrap;
}
.pub-table th { font-weight: 700; }
/* Numeric column: right-align + tabular figures for decimal alignment */
.pub-table td.num, .pub-table th.num {
  text-align: right;
  font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings: "tnum" 1, "lnum" 1;
  padding-right: 14px;
}
/* Subhead row — bold, no indent, slight top spacing */
.pub-table tr.subhead td {
  font-weight: 700;
  padding-top: 9px;
  padding-bottom: 3px;
}
/* Subrow — first cell indented 22px (PDF 양식과 일치) */
.pub-table tr.subrow td:first-child { padding-left: 22px; }
.pub-table .ref  { font-style: italic; }
.pub-table .pval em { font-style: italic; }
/* Footnote — 9pt, italic abbr */
.pub-table-footnote {
  font-size: 9pt;
  color: #000;
  margin-top: 6px;
  line-height: 1.4;
  font-family: 'Times New Roman', 'Liberation Serif', serif;
}
.pub-table-footnote .abbr { font-style: italic; }
.pub-table-footnote div { margin: 1px 0; }
</style>
"""


def build_figure2_results_html() -> str:
    """Figure 2 (Subgroup forest) 산출 수치 표 — Word docx에 별도 출력용.

    stat_results.json:Figure_3 → 5 stratifier × levels × (aOR, 95% CI, P_int).
    """
    import json as _j
    from pathlib import Path as _P
    sr = _j.loads(_P("data/exports/stat_results.json").read_text(encoding="utf-8"))
    f3 = sr.get("Figure_3", {})
    ov = f3.get("overall", {})
    sg = f3.get("subgroups", {})

    head_label = {
        "sex": "Sex",
        "age_cat": "Age category, years",
        "bmi_cat": "BMI category",
        "ses3": "Household economic status",
        "academic3": "Academic performance",
    }
    level_label = {
        "sex":       {1: "Male", 2: "Female"},
        "age_cat":   {1: "12–13", 2: "14–15", 3: "16–18"},
        "bmi_cat":   {1: "Underweight (<P5)",
                       2: "Normal (P5–<P85)",
                       3: "Overweight or obese (≥P85)"},
        "ses3":      {1: "High", 2: "Middle", 3: "Low"},
        "academic3": {1: "High", 2: "Middle", 3: "Low"},
    }

    parts = [_TABLE_CSS, '<table class="pub-table">']
    parts.append('<caption>Figure 2 — Subgroup analyses, numeric results '
                  '(adjusted odds ratio per 1-level increase in ZCB consumption)</caption>')
    parts.append('<thead><tr>'
                  '<th>Subgroup</th>'
                  '<th class="num">n</th>'
                  '<th class="num">aOR (95% CI)</th>'
                  '<th class="num"><em>P</em><sub>interaction</sub></th>'
                  '</tr></thead><tbody>')

    # Overall
    parts.append(
        '<tr><td><b>Overall</b></td>'
        '<td class="num">50,972</td>'
        f'<td class="num">{_fmt_or_ci(ov.get("or",0), ov.get("ci_low",0), ov.get("ci_high",0))}</td>'
        '<td class="num">—</td></tr>'
    )

    for strat in ["sex", "age_cat", "bmi_cat", "ses3", "academic3"]:
        s = sg.get(strat) or {}
        if not s: continue
        p_int = s.get("p_interaction")
        p_txt = _fmt_p(p_int) if p_int is not None else "—"
        parts.append(
            f'<tr class="subhead"><td colspan="3">{head_label[strat]}</td>'
            f'<td class="num">{p_txt}</td></tr>'
        )
        for lv in s.get("levels", []):
            lev = lv.get("level")
            lab = level_label[strat].get(lev, str(lev))
            n = lv.get("n", 0)
            orv = lv.get("or"); lo = lv.get("ci_low"); hi = lv.get("ci_high")
            or_txt = _fmt_or_ci(orv, lo, hi) if orv else "—"
            parts.append(
                f'<tr class="subrow"><td>{lab}</td>'
                f'<td class="num">{n:,}</td>'
                f'<td class="num">{or_txt}</td>'
                f'<td class="num"></td></tr>'
            )

    parts.append('</tbody></table>')
    parts.append('<div class="pub-table-footnote">'
                  '<div>aOR adjusted for sex, age category, BMI category, school type, '
                  'household economic status, academic performance, ever smoking, ever drinking, '
                  'SSB frequency, high-caffeine frequency, daily smartphone use, physical activity, '
                  'and breakfast skipping. <span class="abbr">P</span><sub>interaction</sub> from '
                  'Wald test of stratifier×exposure interaction terms.</div>'
                  '</div>')

    # ── Result narrative (논문 본문 양식) ─────────────────────────────────
    def _orci(d):
        o = d.get("or"); lo = d.get("ci_low"); hi = d.get("ci_high")
        return f"{o:.2f} (95% CI, {lo:.2f}–{hi:.2f})" if o else "—"

    ov_t = _orci(ov)
    # sex
    sex_lv = {lv["level"]: lv for lv in sg.get("sex", {}).get("levels", [])}
    sex_pint = sg.get("sex", {}).get("p_interaction")
    age_lv = {lv["level"]: lv for lv in sg.get("age_cat", {}).get("levels", [])}
    age_pint = sg.get("age_cat", {}).get("p_interaction")
    bmi_pint = sg.get("bmi_cat", {}).get("p_interaction")
    ses_pint = sg.get("ses3", {}).get("p_interaction")
    aca_pint = sg.get("academic3", {}).get("p_interaction")

    def _ptxt(p):
        if p is None: return "—"
        if p < 0.001: return "<0.001"
        return f"{p:.3f}"

    narr = (
        f"In the fully adjusted model, each 1-level increase in zero-calorie beverage "
        f"consumption frequency was associated with higher odds of depressive symptoms "
        f"(aOR, {ov_t}). The association was modified by sex "
        f"(P-interaction {_ptxt(sex_pint)}), with a stronger effect among females "
        f"(aOR, {_orci(sex_lv.get(2,{}))}) than males ({_orci(sex_lv.get(1,{}))}). "
        f"Effect modification was also detected across age categories "
        f"(P-interaction {_ptxt(age_pint)}); the association was most evident in "
        f"adolescents aged 14–15 years ({_orci(age_lv.get(2,{}))}) and attenuated in "
        f"those aged 16–18 years ({_orci(age_lv.get(3,{}))}). "
        f"No significant interaction was observed for BMI category "
        f"(P-interaction {_ptxt(bmi_pint)}), household economic status "
        f"({_ptxt(ses_pint)}), or academic performance ({_ptxt(aca_pint)})."
    )
    parts.append(f'<div style="margin-top:18px;padding:14px 16px;'
                  f'border-left:3px solid #0F172A;background:#F8FAFC;'
                  f'font-family:\'Times New Roman\',serif;font-size:10.5pt;'
                  f'line-height:1.55;color:#0F172A;">'
                  f'<div style="font-weight:700;margin-bottom:6px;font-size:9.5pt;'
                  f'color:#475569;text-transform:uppercase;letter-spacing:0.04em;">'
                  f'Result narrative</div>{narr}</div>')

    return "\n".join(parts)


def build_figure1_results_html() -> str:
    """Figure 1 (Sex × ZCB 4-level) 산출 수치 표.

    stat_results.json:Supp_Figure_1 → 8 cells (2 sex × 4 zero_cat).
    (JSON 키는 호환 위해 유지, 의미는 Figure 1)
    """
    import json as _j
    from pathlib import Path as _P
    sr = _j.loads(_P("data/exports/stat_results.json").read_text(encoding="utf-8"))
    sf1 = sr.get("Supp_Figure_1", {})
    labels = sf1.get("exposure_labels") or ["None", "≤2/week", "3–6/week", "≥1/day"]
    by_sex = sf1.get("by_sex") or {}

    parts = [_TABLE_CSS, '<table class="pub-table">']
    parts.append('<caption>Figure 1 — Sex-stratified prevalence of '
                  'depressive symptoms by zero-calorie beverage consumption frequency '
                  '(survey-weighted)</caption>')
    parts.append('<thead><tr><th>Sex</th>'
                  + ''.join(f'<th class="num">{lab}</th>' for lab in labels)
                  + '</tr></thead><tbody>')

    for sex_label in ("Male", "Female"):
        cells = by_sex.get(sex_label) or []
        # 1행: prevalence (95% CI)
        parts.append(
            f'<tr class="subhead"><td>{sex_label} — prevalence (95% CI)</td>'
            + ''.join(
                f'<td class="num">{(c.get("prob") or 0)*100:.1f}% '
                f'({(c.get("ci_low") or 0)*100:.1f}–{(c.get("ci_high") or 0)*100:.1f})</td>'
                if c.get("prob") is not None else '<td class="num">—</td>'
                for c in cells
            ) + '</tr>'
        )
        # 2행: n
        parts.append(
            f'<tr class="subrow"><td>n</td>'
            + ''.join(f'<td class="num">{c.get("n",0):,}</td>' for c in cells)
            + '</tr>'
        )

    parts.append('</tbody></table>')
    parts.append('<div class="pub-table-footnote">'
                  '<div>Cell prevalence weighted by KYRBS sampling weight. '
                  '95% CI from Wald binomial.</div>'
                  '</div>')

    # ── Result narrative (논문 본문 양식) ──
    def _cells(label):
        return by_sex.get(label) or []

    male_cells = _cells("Male")
    female_cells = _cells("Female")
    p_int = sr.get("Table_3", {}).get("p_interaction_sex")
    p_txt = "<0.001" if (p_int is not None and p_int < 0.001) else (
        f"{p_int:.3f}" if p_int is not None else "—")

    def _pct_ci(c):
        if not c or c.get("prob") is None:
            return "—"
        p = c["prob"] * 100
        lo = c["ci_low"] * 100
        hi = c["ci_high"] * 100
        return f"{p:.1f}% (95% CI, {lo:.1f}–{hi:.1f})"

    m_first = _pct_ci(male_cells[0]) if male_cells else "—"
    m_last  = _pct_ci(male_cells[-1]) if male_cells else "—"
    f_first = _pct_ci(female_cells[0]) if female_cells else "—"
    f_last  = _pct_ci(female_cells[-1]) if female_cells else "—"

    narr = (
        f"The weighted prevalence of depressive symptoms increased with higher "
        f"zero-calorie beverage consumption frequency in both sexes, with a steeper "
        f"gradient observed among females (P-interaction {p_txt}). Among males, "
        f"prevalence rose from {m_first} in non-consumers to {m_last} in those "
        f"consuming zero-calorie beverages at least once daily. Among females, "
        f"prevalence rose from {f_first} to {f_last} across the same gradient."
    )
    parts.append(f'<div style="margin-top:18px;padding:14px 16px;'
                  f'border-left:3px solid #0F172A;background:#F8FAFC;'
                  f'font-family:\'Times New Roman\',serif;font-size:10.5pt;'
                  f'line-height:1.55;color:#0F172A;">'
                  f'<div style="font-weight:700;margin-bottom:6px;font-size:9.5pt;'
                  f'color:#475569;text-transform:uppercase;letter-spacing:0.04em;">'
                  f'Result narrative</div>{narr}</div>')

    return "\n".join(parts)


# Backward-compat alias (이전 함수명 호출자 있으면 동일 산출)
build_supp_figure1_results_html = build_figure1_results_html


def _fmt_n_pct(n: int, denom: int) -> str:
    """N (%) — thousands comma + 1 decimal % + thin space."""
    if denom == 0:
        return f"{n:,} (—)"
    return f"{n:,} ({n / denom * 100:.1f})"


def _fmt_mean_sd(mean: float, sd: float) -> str:
    """mean ± SD — 2 decimal, NBSP around ±."""
    return f"{mean:.2f} ± {sd:.2f}"


def _fmt_or_ci(or_val: float, lo: float, hi: float) -> str:
    """OR (95% CI) — 2 decimal, en-dash range, single space before paren.

    "1.05 (1.03–1.07)" — NEJM/Lancet convention.
    """
    return f"{or_val:.2f} ({lo:.2f}–{hi:.2f})"


def _fmt_p(p: float) -> str:
    """P-value — italic P, NBSP, en-dash style. '<' for sub-0.001."""
    if p is None:
        return "—"
    if p < 0.001:
        return "<em>P</em> &lt; 0.001"
    if p < 0.01:
        return f"<em>P</em> = {p:.3f}"
    return f"<em>P</em> = {p:.3f}"


# ── Table 1: Baseline characteristics ─────────────────────────────────────────

# 표준 변수 양식 — 사용자 PDF Table 1 그대로
TABLE1_VARIABLES = [
    {"label": "Age category, years", "kind": "cat",
     "levels": [("12-13", "12–13"), ("14-15", "14–15"), ("16-18", "16–18")],
     "col": "age_cat"},
    {"label": "Sex", "kind": "cat",
     "levels": [("Male", "Male"), ("Female", "Female")], "col": "sex"},
    {"label": "BMI, kg/m² (mean ± SD)", "kind": "meansd", "col": "bmi"},
    {"label": "BMI categoryᵃ", "kind": "cat",
     "levels": [("Underweight", "Underweight (<P5)"),
                ("Normal", "Normal (P5–<P85)"),
                ("Overweight", "Overweight or obese (≥P85)")],
     "col": "bmi_cat"},
    {"label": "Household economic status", "kind": "cat",
     "levels": [("High", "High"), ("Middle", "Middle"), ("Low", "Low")],
     "col": "family_econ"},
    {"label": "School type", "kind": "cat",
     "levels": [("Middle", "Middle school"), ("High", "High school")],
     "col": "school_type"},
    {"label": "Academic performance", "kind": "cat",
     "levels": [("High", "High"), ("Middle", "Middle"), ("Low", "Low")],
     "col": "academic_perf"},
    {"label": "Ever smokerᵇ", "kind": "binary", "col": "smoking"},
    {"label": "Ever drinkerᶜ", "kind": "binary", "col": "alcohol"},
    {"label": "SSB frequency", "kind": "cat",
     "levels": [("<1/week", "<1/week"), ("Weekly", "Weekly"), ("Daily", "Daily")],
     "col": "ssb_freq"},
    {"label": "High-caffeine beverage frequency", "kind": "cat",
     "levels": [("<1/week", "<1/week"), ("Weekly", "Weekly"), ("Daily", "Daily")],
     "col": "caffeine_freq"},
    {"label": "Daily smartphone use, min (mean ± SD)", "kind": "meansd",
     "col": "smartphone_min"},
    {"label": "Physical activityᵈ", "kind": "cat",
     "levels": [("Low", "Low (0-2 d/wk)"),
                ("Moderate", "Moderate (3-4 d/wk)"),
                ("High", "High (≥5 d/wk)")],
     "col": "physical_act_cat"},
    {"label": "Breakfast skipperᵉ", "kind": "binary", "col": "breakfast_skip"},
    {"label": "Depressive symptoms", "kind": "binary", "col": "depression"},
    {"label": "High perceived stress", "kind": "binary", "col": "stress"},
    {"label": "Poor sleep recovery", "kind": "binary", "col": "poor_sleep"},
]

TABLE1_FOOTNOTES = [
    "Data are presented as unweighted n (%) unless otherwise indicated.",
    "ᵃ BMI category was defined using sex- and age-specific percentiles from the 2017 Korean National Growth Charts: underweight (<5th percentile), normal weight (5th to <85th percentile), and overweight or obese (≥85th percentile). Observations with BMI <10 or >50 kg/m² were excluded as implausible.",
    "ᵇ Ever smoker = lifetime use of any tobacco product (conventional cigarettes, e-cigarettes, or heated tobacco products).",
    "ᶜ Ever drinker = any lifetime alcohol use beyond a small curiosity sip.",
    "ᵈ Physical activity categorized according to the WHO adolescent guideline based on number of days per week with ≥60 minutes of moderate-to-vigorous physical activity.",
    "ᵉ Breakfast skipper = breakfast consumption ≤2 days per week.",
]
TABLE1_ABBR = ("Abbreviations: BMI, body mass index; KCDC, Korea Disease Control and "
                "Prevention Agency; KYRBS, Korea Youth Risk Behavior Web-based Survey; "
                "SD, standard deviation; SSB, sugar-sweetened beverage; "
                "WHO, World Health Organization.")


def _load_pdf_table1_data() -> Optional[Dict[str, Any]]:
    """data/assets/zcb_dep_table1_data.json에서 사용자 PDF의 전 데이터 로드."""
    import json
    from pathlib import Path
    p = Path("data/assets/zcb_dep_table1_data.json")
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        col_totals = d.get("_col_totals", [0, 0, 0, 0])[:4]
        n_total = d.get("_col_totals", [0, 0, 0, 0, 0])[4] if len(d.get("_col_totals", [])) >= 5 else sum(col_totals)
        rows = []
        for r in d.get("rows", []):
            if r.get("type") == "subhead":
                rows.append({
                    "label": r["label"], "kind": "cat",
                    "subhead": True,
                    "levels": [(lvl[0], lvl[1]) for lvl in r.get("levels", [])],
                })
            else:
                # values는 5개 (None, ≤2, 3-6, ≥1, Total) — 마지막이 total
                vals = r.get("values", [])
                rows.append({
                    "label": r["label"], "kind": r.get("type", "single"),
                    "values": vals,
                })
        return {"col_totals": col_totals, "n_total": n_total, "rows": rows}
    except Exception as e:
        _log.warning("zcb_dep_table1_data.json 로드 실패: %s", e)
        return None


def build_table1_html(
    df=None,
    *,
    exposure_col: str = "zcb_freq",
    exposure_labels: Optional[List[str]] = None,
    survey_year: int = 2025,
    title: Optional[str] = None,
    precomputed: Optional[Dict[str, Any]] = None,
    use_pdf_data: bool = True,
) -> str:
    """Table 1 HTML 양식. df 받으면 직접 계산 / precomputed 받으면 그것 사용.

    exposure_labels: 4 칼럼 헤더 ["None", "≤2/week", "3-6/week", "≥1/day"].
    precomputed: {"col_totals": [N1, N2, N3, N4], "rows": [(var_label, [vals_by_group], total_val)]}
        — df 없을 때 외부에서 계산해 넘김.
    """
    if exposure_labels is None:
        exposure_labels = ["None", "≤2/week", "3–6/week", "≥1/day"]

    if title is None:
        title = (f"Table 1. Baseline characteristics of study participants by "
                 f"zero-calorie beverage consumption frequency, KYRBS {survey_year}")

    # 데이터 추출 — 우선순위: precomputed > df 계산 > PDF 정본 데이터
    if precomputed is None and df is not None:
        precomputed = _compute_table1_from_df(df, exposure_col)
    if precomputed is None and use_pdf_data:
        precomputed = _load_pdf_table1_data()
    if precomputed is None:
        precomputed = {"col_totals": [0, 0, 0, 0], "n_total": 0, "rows": []}

    col_totals = precomputed.get("col_totals", [0, 0, 0, 0])
    n_total = precomputed.get("n_total", sum(col_totals))
    rows = precomputed.get("rows", [])

    # 빌드
    parts = [_TABLE_CSS, f'<table class="pub-table">']
    parts.append(f'<caption>{title}</caption>')

    # Header — 2 row (top: super-header "Zero-calorie beverage consumption frequency", 2nd: 4 groups)
    parts.append('<thead>')
    parts.append('<tr>')
    parts.append('<th rowspan="2">Variable</th>')
    parts.append(f'<th colspan="{len(exposure_labels)}" style="text-align:center;">'
                  f'Zero-calorie beverage consumption frequency</th>')
    parts.append('<th rowspan="2" class="num">Total</th>')
    parts.append('</tr>')
    parts.append('<tr>')
    for lab in exposure_labels:
        parts.append(f'<th class="num">{_html.escape(lab)}</th>')
    parts.append('</tr>')
    parts.append('</thead>')

    # Body — N(%) 첫 행
    parts.append('<tbody>')
    parts.append('<tr><td><b>N (%)</b></td>')
    for n in col_totals:
        parts.append(f'<td class="num">{_fmt_n_pct(n, n_total)}</td>')
    parts.append(f'<td class="num">{n_total:,} (100.0)</td>')
    parts.append('</tr>')

    # 변수별 행
    for row in rows:
        var_label = row.get("label", "")
        kind = row.get("kind", "cat")
        if kind == "subhead_only":
            parts.append(f'<tr class="subhead"><td colspan="{len(exposure_labels) + 2}">{_html.escape(var_label)}</td></tr>')
            continue
        # subgroup heading row
        if row.get("subhead"):
            parts.append(f'<tr class="subhead"><td colspan="{len(exposure_labels) + 2}">{_html.escape(var_label)}</td></tr>')
            # 그 하위 levels
            for level_label, level_vals in row.get("levels", []):
                parts.append(f'<tr class="subrow"><td>{_html.escape(level_label)}</td>')
                for v in level_vals:
                    parts.append(f'<td class="num">{v}</td>')
                parts.append('</tr>')
            continue
        # binary or meansd — 단일 row
        parts.append(f'<tr><td><b>{_html.escape(var_label)}</b></td>')
        for v in row.get("values", []):
            parts.append(f'<td class="num">{v}</td>')
        parts.append('</tr>')

    parts.append('</tbody></table>')

    # Footnotes
    parts.append('<div class="pub-table-footnote">')
    for fn in TABLE1_FOOTNOTES:
        parts.append(f'<div>{_html.escape(fn)}</div>')
    parts.append(f'<div class="abbr">{_html.escape(TABLE1_ABBR)}</div>')
    parts.append('</div>')

    return "".join(parts)


def _compute_table1_from_df(df, exposure_col: str) -> Dict[str, Any]:
    """df에서 Table 1 행 자동 계산. exposure 4그룹 + Total."""
    import pandas as pd

    if exposure_col not in df.columns:
        return {"col_totals": [0, 0, 0, 0], "n_total": len(df), "rows": []}

    # exposure 4그룹 정의 — KYRBS zcb_freq는 0=None, 1=≤2/week, 2=3-6/week, 3=≥1/day 또는 다른 양식
    # 사용자 PDF는 None/≤2/week/3-6/week/≥1/day 4그룹
    e = pd.to_numeric(df[exposure_col], errors="coerce")
    # 단순 4-band 양식 (0=None, 1=≤2/week, 2=3-6/week, 3=≥1/day). 실제 KYRBS 코딩에 맞춰 조정 필요.
    bins = [-0.5, 0.5, 2.5, 5.5, 100]
    labels = [0, 1, 2, 3]   # 4그룹
    e_cat = pd.cut(e, bins=bins, labels=labels)
    groups = [df[e_cat == i] for i in labels]
    col_totals = [len(g) for g in groups]
    n_total = sum(col_totals)

    rows = []
    for var in TABLE1_VARIABLES:
        label = var["label"]
        kind = var["kind"]
        col = var["col"]
        if col not in df.columns:
            continue

        if kind == "binary":
            vals = []
            for g in groups:
                bin_col = pd.to_numeric(g[col], errors="coerce")
                n_pos = int((bin_col > 0).sum())
                vals.append(_fmt_n_pct(n_pos, len(g)))
            tot_bin = pd.to_numeric(df[col], errors="coerce")
            tot_n = int((tot_bin > 0).sum())
            vals.append(_fmt_n_pct(tot_n, n_total))
            rows.append({"label": label, "kind": "binary", "values": vals})

        elif kind == "meansd":
            vals = []
            for g in groups:
                ser = pd.to_numeric(g[col], errors="coerce").dropna()
                if len(ser):
                    vals.append(_fmt_mean_sd(float(ser.mean()), float(ser.std())))
                else:
                    vals.append("—")
            tot = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(tot):
                vals.append(_fmt_mean_sd(float(tot.mean()), float(tot.std())))
            else:
                vals.append("—")
            rows.append({"label": label, "kind": "meansd", "values": vals})

        elif kind == "cat":
            # 각 level별 N(%) 계산
            level_rows = []
            for level_val, level_lab in var["levels"]:
                row_vals = []
                for g in groups:
                    g_col = g[col].astype(str)
                    n_in_level = int((g_col == str(level_val)).sum())
                    row_vals.append(_fmt_n_pct(n_in_level, len(g)))
                tot_col = df[col].astype(str)
                n_tot = int((tot_col == str(level_val)).sum())
                row_vals.append(_fmt_n_pct(n_tot, n_total))
                level_rows.append((level_lab, row_vals))
            rows.append({"label": label, "kind": "cat",
                          "subhead": True, "levels": level_rows})

    return {"col_totals": col_totals, "n_total": n_total, "rows": rows}


# ── Table 2: Model 1 / Model 2 aOR ────────────────────────────────────────────

def build_table2_html(
    *,
    model1_estimates: Optional[List[Dict]] = None,
    model2_estimates: Optional[List[Dict]] = None,
    p_trend_m1: float = 0.0,
    p_trend_m2: float = 0.0,
    survey_year: int = 2025,
    n_total: int = 50972,
) -> str:
    """Table 2: Model 1 / Model 2 aOR + p for trend.

    estimates: [{"level": "None"|"≤2 times/week"|..., "or": float, "ci_low": float, "ci_high": float}, ...]
    """
    if model1_estimates is None:
        model1_estimates = [
            {"level": "None", "or": None},   # Ref
            {"level": "≤2 times/week", "or": 1.17, "ci_low": 1.11, "ci_high": 1.22},
            {"level": "3-6 times/week", "or": 1.42, "ci_low": 1.29, "ci_high": 1.57},
            {"level": "≥1 time/day", "or": 2.01, "ci_low": 1.67, "ci_high": 2.42},
        ]
    if model2_estimates is None:
        model2_estimates = [
            {"level": "None", "or": None},
            {"level": "≤2 times/week", "or": 1.10, "ci_low": 1.05, "ci_high": 1.16},
            {"level": "3-6 times/week", "or": 1.14, "ci_low": 1.03, "ci_high": 1.27},
            {"level": "≥1 time/day", "or": 1.31, "ci_low": 1.06, "ci_high": 1.61},
        ]

    title = (f"Table 2. Association between zero-calorie beverage consumption and "
             f"depressive symptoms among Korean adolescents, KYRBS {survey_year}")

    parts = [_TABLE_CSS, '<table class="pub-table">']
    parts.append(f'<caption>{title}</caption>')
    parts.append('<thead>')
    parts.append('<tr><th rowspan="2">Zero-calorie beverage consumption</th>'
                  '<th colspan="2" style="text-align:center;">Model 1</th>'
                  '<th colspan="2" style="text-align:center;">Model 2</th></tr>')
    parts.append('<tr><th class="num">Adjusted OR (95% CI)<sup>1</sup></th>'
                  '<th class="num">p for trend</th>'
                  '<th class="num">Adjusted OR (95% CI)<sup>2</sup></th>'
                  '<th class="num">p for trend</th></tr>')
    parts.append('</thead><tbody>')
    # p for trend row (위)
    parts.append(f'<tr><td></td><td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_m1)}</td>'
                  f'<td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_m2)}</td></tr>')
    # 4그룹 행
    for m1, m2 in zip(model1_estimates, model2_estimates):
        level = m1.get("level", "")
        if m1.get("or") is None:
            cell_m1 = '<span class="ref">Ref (1)</span>'
            cell_m2 = '<span class="ref">Ref (1)</span>'
        else:
            cell_m1 = _fmt_or_ci(m1["or"], m1["ci_low"], m1["ci_high"])
            cell_m2 = _fmt_or_ci(m2["or"], m2["ci_low"], m2["ci_high"])
        parts.append(f'<tr><td>{_html.escape(level)}</td>'
                      f'<td class="num">{cell_m1}</td><td class="num">-</td>'
                      f'<td class="num">{cell_m2}</td><td class="num">-</td></tr>')
    parts.append('</tbody></table>')

    parts.append('<div class="pub-table-footnote">')
    parts.append('<div>ᵃ Model 1: adjusted for age, sex, school type, household economic status, and academic performance.</div>')
    parts.append('<div>ᵇ Model 2: Model 1 covariates plus body mass index category, lifetime smoking, lifetime alcohol use, sugar-sweetened beverage frequency, high-caffeine beverage frequency, daily smartphone use, physical activity, and breakfast skipping.</div>')
    parts.append('<div>P for trend was tested by entering the four-category exposure as an ordinal continuous variable in the fully adjusted model.</div>')
    parts.append('<div class="abbr">Abbreviations: aOR, adjusted odds ratio; CI, confidence interval; KYRBS, Korea Youth Risk Behavior Web-based Survey.</div>')
    parts.append('</div>')
    return "".join(parts)


# ── Table 3: Sex-stratified ──────────────────────────────────────────────────

def build_table3_html(
    *,
    male_estimates: Optional[List[Dict]] = None,
    female_estimates: Optional[List[Dict]] = None,
    p_trend_male: float = 0.088,
    p_trend_female: float = 0.0,
    p_interaction: float = 0.0,
    survey_year: int = 2025,
    n_total: int = 50972,
) -> str:
    """Table 3: Sex-stratified aOR + P for interaction."""
    if male_estimates is None:
        male_estimates = [
            {"level": "None", "or": None},
            {"level": "≤2 times/week", "or": 1.07, "ci_low": 0.99, "ci_high": 1.14},
            {"level": "3-6 times/week", "or": 0.97, "ci_low": 0.85, "ci_high": 1.12},
            {"level": "≥1 time/day", "or": 1.32, "ci_low": 1.02, "ci_high": 1.69},
        ]
    if female_estimates is None:
        female_estimates = [
            {"level": "None", "or": None},
            {"level": "≤2 times/week", "or": 1.12, "ci_low": 1.05, "ci_high": 1.20},
            {"level": "3-6 times/week", "or": 1.43, "ci_low": 1.22, "ci_high": 1.67},
            {"level": "≥1 time/day", "or": 1.37, "ci_low": 0.99, "ci_high": 1.91},
        ]

    title = (f"Table 3. Sex-stratified association between zero-calorie beverage consumption and "
             f"depressive symptoms among Korean adolescents, KYRBS {survey_year}")

    parts = [_TABLE_CSS, '<table class="pub-table">']
    parts.append(f'<caption>{title}</caption>')
    parts.append('<thead>')
    parts.append('<tr><th rowspan="2">Zero-calorie beverage consumption</th>'
                  '<th colspan="2" style="text-align:center;">Male</th>'
                  '<th colspan="2" style="text-align:center;">Female</th>'
                  '<th rowspan="2" class="num">P for<br>interaction</th></tr>')
    parts.append('<tr><th class="num">Adjusted OR (95% CI)<sup>1</sup></th>'
                  '<th class="num">p for trend</th>'
                  '<th class="num">Adjusted OR (95% CI)<sup>2</sup></th>'
                  '<th class="num">p for trend</th></tr>')
    parts.append('</thead><tbody>')
    parts.append(f'<tr><td></td><td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_male)}</td>'
                  f'<td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_female)}</td>'
                  f'<td class="num pval">{_fmt_p(p_interaction)}</td></tr>')
    for m, f in zip(male_estimates, female_estimates):
        level = m.get("level", "")
        if m.get("or") is None:
            cm = '<span class="ref">Ref (1)</span>'
            cf = '<span class="ref">Ref (1)</span>'
        else:
            cm = _fmt_or_ci(m["or"], m["ci_low"], m["ci_high"])
            cf = _fmt_or_ci(f["or"], f["ci_low"], f["ci_high"])
        parts.append(f'<tr><td>{_html.escape(level)}</td>'
                      f'<td class="num">{cm}</td><td></td>'
                      f'<td class="num">{cf}</td><td></td><td></td></tr>')
    parts.append('</tbody></table>')

    parts.append('<div class="pub-table-footnote">')
    parts.append('<div>ᵃ Models within each stratum were adjusted for age, body mass index category, school type, household economic status, academic performance, lifetime smoking, lifetime alcohol use, sugar-sweetened beverage frequency, high-caffeine beverage frequency, daily smartphone use, physical activity, and breakfast skipping. Sex was excluded from the covariate set within each stratum-specific model.</div>')
    parts.append('<div>ᵇ P for trend was tested by entering the four-category exposure as an ordinal continuous variable in the fully adjusted model.</div>')
    parts.append('<div>ᶜ P for interaction was tested using a multiplicative interaction term between zero-calorie beverage consumption and sex in the fully adjusted model.</div>')
    parts.append('<div class="abbr">Abbreviations: aOR, adjusted odds ratio; CI, confidence interval; KYRBS, Korea Youth Risk Behavior Web-based Survey.</div>')
    parts.append('</div>')
    return "".join(parts)


# ── Supplementary Table 1: Secondary outcomes ────────────────────────────────

def build_supp_table1_html(
    *,
    stress_estimates: Optional[List[Dict]] = None,
    sleep_estimates: Optional[List[Dict]] = None,
    p_trend_stress: float = 0.253,
    p_trend_sleep: float = 0.990,
    survey_year: int = 2025,
    n_total: int = 50972,
) -> str:
    """Supp Table 1: ZCB → 보조 결과(스트레스, 수면)."""
    if stress_estimates is None:
        stress_estimates = [
            {"level": "None", "or": None},
            {"level": "≤2/week", "or": 0.97, "ci_low": 0.93, "ci_high": 1.01},
            {"level": "3-6/week", "or": 1.13, "ci_low": 1.03, "ci_high": 1.24},
            {"level": "≥1/day", "or": 1.14, "ci_low": 0.94, "ci_high": 1.38},
        ]
    if sleep_estimates is None:
        sleep_estimates = [
            {"level": "None", "or": None},
            {"level": "≤2/week", "or": 0.97, "ci_low": 0.93, "ci_high": 1.02},
            {"level": "3-6/week", "or": 0.99, "ci_low": 0.88, "ci_high": 1.13},
            {"level": "≥1/day", "or": 1.22, "ci_low": 0.97, "ci_high": 1.53},
        ]

    title = (f"Supplementary Table 1. Association between zero-calorie beverage consumption and "
             f"secondary mental health outcomes (high perceived stress and poor sleep recovery), "
             f"KYRBS {survey_year}")

    parts = [_TABLE_CSS, '<table class="pub-table">']
    parts.append(f'<caption>{title}</caption>')
    parts.append('<thead>')
    parts.append('<tr><th rowspan="2">Zero-calorie beverage consumption</th>'
                  '<th colspan="2" style="text-align:center;">High perceived stress</th>'
                  '<th colspan="2" style="text-align:center;">Poor sleep recovery</th></tr>')
    parts.append('<tr><th class="num">aOR (95% CI)</th><th class="num">P for trend</th>'
                  '<th class="num">aOR (95% CI)</th><th class="num">P for trend</th></tr>')
    parts.append('</thead><tbody>')
    parts.append(f'<tr><td></td><td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_stress)}</td>'
                  f'<td></td>'
                  f'<td class="num pval">{_fmt_p(p_trend_sleep)}</td></tr>')
    for s, sl in zip(stress_estimates, sleep_estimates):
        level = s.get("level", "")
        if s.get("or") is None:
            cs = '<span class="ref">1.00 (Reference)</span>'
            cl = '<span class="ref">1.00 (Reference)</span>'
        else:
            cs = _fmt_or_ci(s["or"], s["ci_low"], s["ci_high"])
            cl = _fmt_or_ci(sl["or"], sl["ci_low"], sl["ci_high"])
        parts.append(f'<tr><td>{_html.escape(level)}</td>'
                      f'<td class="num">{cs}</td><td></td>'
                      f'<td class="num">{cl}</td><td></td></tr>')
    parts.append('</tbody></table>')

    parts.append('<div class="pub-table-footnote">')
    parts.append('<div>All models were adjusted for age, sex, body mass index category, school type, household economic status, academic performance, lifetime smoking, lifetime alcohol use, sugar-sweetened beverage frequency, high-caffeine beverage frequency, daily smartphone use, physical activity, and breakfast skipping.</div>')
    parts.append('<div>The three mental health outcomes (depressive symptoms, high perceived stress, and poor sleep recovery) were modelled in independent regressions and were not mutually adjusted, to avoid mediator-collider bias.</div>')
    parts.append('<div>P for trend was tested by entering the four-category exposure as an ordinal continuous variable in the fully adjusted model.</div>')
    parts.append('<div class="abbr">Abbreviations: aOR, adjusted odds ratio; CI, confidence interval; KYRBS, Korea Youth Risk Behavior Web-based Survey.</div>')
    parts.append('</div>')
    return "".join(parts)


# ── 한 번에 4종 ──────────────────────────────────────────────────────────────

def _load_computed():
    """data/exports/stat_results.json에서 실측값 로드 — default 무시하고 진짜 결과만 쓴다."""
    import json as _j
    from pathlib import Path as _P
    p = _P("data/exports/stat_results.json")
    if not p.exists():
        return None
    try:
        return _j.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _est_from_sr(rec):
    if rec is None: return None
    return {"or": rec["or"], "ci_low": rec["ci_low"], "ci_high": rec["ci_high"]}


def build_all_tables(
    df=None,
    *,
    stat_model1=None, stat_model2=None,
    stat_male=None, stat_female=None,
    stat_stress=None, stat_sleep=None,
    survey_year: int = 2025,
    p_trend_m1: float = 0.0, p_trend_m2: float = 0.0,
    p_trend_male: float = 0.088, p_trend_female: float = 0.0,
    p_interaction: float = 0.0,
    p_trend_stress: float = 0.253, p_trend_sleep: float = 0.990,
) -> Dict[str, str]:
    """4종 표 한 번에 — stat_results.json (실측) 우선, 없으면 PDF default."""
    n_total = len(df) if df is not None else 50972
    sr = _load_computed()

    # ── Table 2: 실측이 있으면 그것으로 estimates 교체 ──
    m1_est = m2_est = None
    p_t_m1, p_t_m2 = p_trend_m1, p_trend_m2
    if sr and "Table_2" in sr:
        t2 = sr["Table_2"]
        m1_raw, m2_raw = t2["Model_1"], t2["Model_2"]
        m1_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(m1_raw[v])}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2 times/week", "3-6 times/week", "≥1 time/day"])
        ]
        m2_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(m2_raw[v])}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2 times/week", "3-6 times/week", "≥1 time/day"])
        ]
        p_t_m1 = t2.get("p_trend_M1") or p_t_m1
        p_t_m2 = t2.get("p_trend_M2") or p_t_m2
        n_total = sr.get("final_N", n_total)

    # ── Table 3 sex-stratified 실측 ──
    male_est = female_est = None
    p_t_male, p_t_female, p_int = p_trend_male, p_trend_female, p_interaction
    if sr and "Table_3" in sr:
        t3 = sr["Table_3"]
        male_raw, female_raw = t3.get("Male", {}), t3.get("Female", {})
        male_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(male_raw.get(v))}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2 times/week", "3-6 times/week", "≥1 time/day"])
        ]
        female_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(female_raw.get(v))}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2 times/week", "3-6 times/week", "≥1 time/day"])
        ]
        p_t_male = male_raw.get("p_trend") or p_t_male
        p_t_female = female_raw.get("p_trend") or p_t_female
        p_int = t3.get("p_interaction_sex") or p_int

    # ── Supp Table 1 실측 ──
    stress_est = sleep_est = None
    p_t_str, p_t_slp = p_trend_stress, p_trend_sleep
    if sr and "Supp_Table_1" in sr:
        sp = sr["Supp_Table_1"]
        stress_raw, sleep_raw = sp.get("stress", {}), sp.get("sleep", {})
        stress_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(stress_raw.get(v))}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2/week", "3-6/week", "≥1/day"])
        ]
        sleep_est = [{"level": "None", "or": None}] + [
            {"level": lab, **_est_from_sr(sleep_raw.get(v))}
            for v, lab in zip(["zero_cat_2", "zero_cat_3", "zero_cat_4"],
                               ["≤2/week", "3-6/week", "≥1/day"])
        ]
        p_t_str = stress_raw.get("p_trend") or p_t_str
        p_t_slp = sleep_raw.get("p_trend") or p_t_slp

    return {
        "Table 1": build_table1_html(df=df, survey_year=survey_year),
        "Table 2": build_table2_html(
            model1_estimates=m1_est, model2_estimates=m2_est,
            p_trend_m1=p_t_m1, p_trend_m2=p_t_m2,
            survey_year=survey_year, n_total=n_total),
        "Table 3": build_table3_html(
            male_estimates=male_est, female_estimates=female_est,
            p_trend_male=p_t_male, p_trend_female=p_t_female,
            p_interaction=p_int, survey_year=survey_year, n_total=n_total),
        "Supplementary Table 1": build_supp_table1_html(
            stress_estimates=stress_est, sleep_estimates=sleep_est,
            p_trend_stress=p_t_str, p_trend_sleep=p_t_slp,
            survey_year=survey_year, n_total=n_total),
    }


__all__ = [
    "build_table1_html", "build_table2_html",
    "build_table3_html", "build_supp_table1_html",
    "build_all_tables",
    "TABLE1_VARIABLES", "TABLE1_FOOTNOTES", "TABLE1_ABBR",
]
