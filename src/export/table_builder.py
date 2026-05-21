"""Table builder — 통계결과 딕셔너리 → python-docx Table 객체."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)

# Vancouver 스타일 헤더 색상
_HEADER_RGB = (0x1E, 0x3A, 0x5F)  # 짙은 네이비
_ALT_RGB = (0xF0, 0xF4, 0xFA)      # 연한 파랑


def _set_cell_bg(cell, rgb: Tuple[int, int, int]):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "%02X%02X%02X" % rgb)
    tcPr.append(shd)


def _bold_cell(cell, bold: bool = True):
    for para in cell.paragraphs:
        for run in para.runs:
            run.bold = bold


def _set_col_widths(table, widths_cm: List[float]):
    from docx.shared import Cm
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_cm):
                cell.width = Cm(widths_cm[i])


def baseline_characteristics_table(doc, data: List[Dict], caption: str = "Table 1. Baseline Characteristics"):
    """기준 특성 표 (변수, N, %, 평균±SD).

    data: [{"variable": str, "n": int, "pct": float, "mean": float, "sd": float}, ...]
    """
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc.add_paragraph(caption).runs[0].bold = True

    headers = ["Variable", "N", "%", "Mean ± SD"]
    table = doc.add_table(rows=1 + len(data), cols=len(headers))
    table.style = "Table Grid"

    # 헤더
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        _set_cell_bg(cell, _HEADER_RGB)
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # 데이터
    for row_idx, row_data in enumerate(data, start=1):
        row = table.rows[row_idx]
        row.cells[0].text = str(row_data.get("variable", ""))
        row.cells[1].text = str(row_data.get("n", ""))
        pct = row_data.get("pct")
        row.cells[2].text = f"{pct:.1f}" if pct is not None else ""
        mean = row_data.get("mean")
        sd = row_data.get("sd")
        row.cells[3].text = f"{mean:.2f} ± {sd:.2f}" if mean is not None else ""
        if row_idx % 2 == 0:
            for cell in row.cells:
                _set_cell_bg(cell, _ALT_RGB)

    doc.add_paragraph()
    return table


def regression_table(doc, results: List[Dict], caption: str = "Table 2. Regression Results"):
    """로지스틱/선형 회귀 결과 표.

    results: [{"variable": str, "or": float, "ci_low": float, "ci_high": float,
               "p_value": float, "beta": float}, ...]
    """
    from docx.shared import RGBColor

    doc.add_paragraph(caption).runs[0].bold = True

    has_or = any("or" in r for r in results)
    if has_or:
        headers = ["Variable", "OR", "95% CI", "p-value"]
    else:
        headers = ["Variable", "β", "95% CI", "p-value"]

    table = doc.add_table(rows=1 + len(results), cols=len(headers))
    table.style = "Table Grid"

    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        _set_cell_bg(cell, _HEADER_RGB)
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for row_idx, r in enumerate(results, start=1):
        row = table.rows[row_idx]
        row.cells[0].text = str(r.get("variable", ""))
        if has_or:
            row.cells[1].text = f"{r.get('or', ''):.2f}" if r.get("or") is not None else ""
        else:
            row.cells[1].text = f"{r.get('beta', ''):.3f}" if r.get("beta") is not None else ""
        ci_low = r.get("ci_low")
        ci_high = r.get("ci_high")
        row.cells[2].text = f"{ci_low:.2f} – {ci_high:.2f}" if ci_low is not None else ""
        p = r.get("p_value")
        row.cells[3].text = f"{'<0.001' if p and p < 0.001 else f'{p:.3f}'}" if p is not None else ""
        if row_idx % 2 == 0:
            for cell in row.cells:
                _set_cell_bg(cell, _ALT_RGB)

    doc.add_paragraph()
    return table


def cross_table(doc, contingency: List[List], row_labels: List[str],
                col_labels: List[str], caption: str = "Table 3. Cross Tabulation"):
    """교차표 (chi-square 결과용)."""
    from docx.shared import RGBColor

    doc.add_paragraph(caption).runs[0].bold = True

    table = doc.add_table(rows=1 + len(row_labels), cols=1 + len(col_labels))
    table.style = "Table Grid"

    # 헤더 행
    table.cell(0, 0).text = ""
    _set_cell_bg(table.cell(0, 0), _HEADER_RGB)
    for j, cl in enumerate(col_labels, start=1):
        cell = table.cell(0, j)
        cell.text = cl
        _set_cell_bg(cell, _HEADER_RGB)
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for i, rl in enumerate(row_labels, start=1):
        table.cell(i, 0).text = rl
        _set_cell_bg(table.cell(i, 0), _HEADER_RGB)
        for run in table.cell(i, 0).paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for j, val in enumerate(contingency[i - 1], start=1):
            table.cell(i, j).text = str(val)
            if i % 2 == 0:
                _set_cell_bg(table.cell(i, j), _ALT_RGB)

    doc.add_paragraph()
    return table


# ---------------------------------------------------------------------------
# StatBridge 결과 → Table 1 / Table 2 자동 변환
# ---------------------------------------------------------------------------

_VAR_LABELS: Dict[str, str] = {
    "sex": "Sex, female", "sex_2": "Sex, female",
    "sleep_hours": "Sleep duration (h/d)", "screen_time": "Screen time (h/d)",
    "smoking": "Current smoking", "alcohol": "Alcohol use",
    "physical_act": "Physical activity (d/wk)", "bmi": "BMI (kg/m²)",
    "grade": "School grade", "family_econ": "Socioeconomic status (low)",
    "academic_perf": "Academic performance (low)", "stress": "Perceived stress (high)",
    "depression": "Depressive mood", "suicidal": "Suicidal ideation",
    "obesity": "Obesity (BMI ≥ 25)", "hypertension": "Hypertension",
    "diabetes": "Diabetes", "metabolic_syn": "Metabolic syndrome",
}


def _prettify_var(col: str) -> str:
    if col in _VAR_LABELS:
        return _VAR_LABELS[col]
    return col.replace("_", " ").title()


def stat_result_to_table1_markdown(stat_result: dict) -> str:
    """StatBridge stat_result → Table 1 마크다운 문자열."""
    n_total = stat_result.get("n_total", 0)
    desc = stat_result.get("descriptive_stats", {})
    outcome_lbl = stat_result.get("outcome_label", stat_result.get("outcome", "Outcome"))

    lines = [
        f"**Table 1. Characteristics of Study Participants (N = {n_total:,})**",
        "",
        "| Variable | Value |",
        "|----------|-------|",
        f"| Total N | {n_total:,} |",
        f"| {outcome_lbl}, n (%) | "
        f"{stat_result.get('n_outcome', 0):,} ({stat_result.get('outcome_rate', 0.0):.1f}%) |",
    ]

    for col, stats in desc.items():
        label = _prettify_var(col)
        if "mean" in stats:
            m, s = stats["mean"], stats["std"]
            lines.append(f"| {label}, mean ± SD | {m:.2f} ± {s:.2f} |")
        elif "categories" in stats:
            cats = stats["categories"]
            first = True
            for cat_val, pct in cats.items():
                if first:
                    lines.append(f"| {label} |  |")
                    first = False
                lines.append(f"|   — {cat_val} | {pct * 100:.1f}% |")

    return "\n".join(lines)


def stat_result_to_table2_markdown(stat_result: dict) -> str:
    """StatBridge stat_result → Table 2 마크다운 문자열."""
    outcome_lbl = stat_result.get("outcome_label", stat_result.get("outcome", "Outcome"))
    model_vars = stat_result.get("model_vars", [])

    lines = [
        f"**Table 2. Logistic Regression Results — Odds Ratios for {outcome_lbl}**",
        "",
        "| Variable | aOR | 95% CI | p-value |",
        "|----------|-----|--------|---------|",
    ]

    for v in model_vars:
        label = v.get("label") or _prettify_var(v.get("variable", ""))
        or_f = v.get("or_formatted", "")
        ci_f = v.get("ci_formatted", "")
        if not ci_f and v.get("ci_lower") is not None:
            ci_f = f"{v['ci_lower']:.2f} – {v['ci_upper']:.2f}"
        p_f = v.get("p_formatted", "")
        sig = " *" if v.get("significant") else ""
        lines.append(f"| {label}{sig} | {or_f} | {ci_f} | {p_f} |")

    lines += ["", "*p < 0.05; aOR, adjusted odds ratio; CI, confidence interval"]
    return "\n".join(lines)


def stat_result_to_tables_docx_bytes(stat_result: dict) -> bytes:
    """StatBridge stat_result → Tables DOCX 바이트 반환 (Streamlit 다운로드용).

    Table 1: 기술통계, Table 2: 로지스틱 회귀 결과
    """
    import io
    try:
        from docx import Document
    except ImportError:
        _log.error("python-docx 미설치")
        return b""

    doc = Document()
    n_total = stat_result.get("n_total", 0)
    outcome_lbl = stat_result.get("outcome_label", stat_result.get("outcome", "Outcome"))
    desc = stat_result.get("descriptive_stats", {})
    outcome_key = stat_result.get("outcome", "")

    # ── Table 1 ─────────────────────────────────────────────────────────
    table1_data = [
        {"variable": "Total N", "n": n_total, "pct": None, "mean": None, "sd": None},
        {"variable": outcome_lbl,
         "n": stat_result.get("n_outcome", 0),
         "pct": stat_result.get("outcome_rate", 0.0),
         "mean": None, "sd": None},
    ]
    for col, stats in desc.items():
        if col == outcome_key:
            continue
        label = _prettify_var(col)
        if "mean" in stats:
            table1_data.append({"variable": label, "n": n_total,
                                 "pct": None, "mean": stats["mean"], "sd": stats["std"]})
        elif "categories" in stats:
            for cat_val, pct in list(stats["categories"].items())[:3]:
                table1_data.append({"variable": f"  {label} — {cat_val}",
                                     "n": round(pct * n_total),
                                     "pct": pct * 100, "mean": None, "sd": None})

    baseline_characteristics_table(
        doc, table1_data,
        caption=f"Table 1. Characteristics of Study Participants (N = {n_total:,})"
    )
    doc.add_paragraph()

    # ── Table 2 ─────────────────────────────────────────────────────────
    model_vars = stat_result.get("model_vars", [])
    table2_data = []
    for v in model_vars:
        label = v.get("label") or _prettify_var(v.get("variable", ""))
        table2_data.append({
            "variable": label,
            "or": v.get("or_value"),
            "ci_low": v.get("ci_lower"),
            "ci_high": v.get("ci_upper"),
            "p_value": v.get("p_value"),
        })

    if table2_data:
        regression_table(
            doc, table2_data,
            caption=f"Table 2. Logistic Regression Results — Adjusted Odds Ratios for {outcome_lbl}"
        )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
