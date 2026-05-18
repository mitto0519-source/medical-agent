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
