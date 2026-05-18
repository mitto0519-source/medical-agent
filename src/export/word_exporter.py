"""Word 논문 출력 엔진 — python-docx 기반 Vancouver 스타일 .docx 생성."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_OUTPUT_DIR = Path("data/drafts/word")


def _ensure_dir():
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── 스타일 헬퍼 ──────────────────────────────────────────────────────────────

def _apply_base_styles(doc):
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)


def _add_title(doc, title: str, authors: List[str], affiliation: str = ""):
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(14)

    if authors:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.add_run(", ".join(authors)).font.size = Pt(11)

    if affiliation:
        p3 = doc.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p3.add_run(affiliation)
        r.font.size = Pt(10)
        r.italic = True

    doc.add_paragraph()


def _add_section_heading(doc, text: str):
    from docx.shared import Pt, RGBColor

    p = doc.add_paragraph()
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)


def _add_body_text(doc, text: str):
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if not text or not text.strip():
        return
    p = doc.add_paragraph(text.strip())
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = None


def _embed_figure(doc, img_bytes: bytes, caption: str = "", width_cm: float = 14.0):
    from docx.shared import Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    buf = io.BytesIO(img_bytes)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(buf, width=Cm(width_cm))

    if caption:
        cp = doc.add_paragraph(caption)
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in cp.runs:
            run.italic = True
        cp.paragraph_format.space_after = Pt(8)


def _add_page_break(doc):
    from docx.enum.text import WD_BREAK
    doc.add_page_break()


# ── 메인 익스포터 ─────────────────────────────────────────────────────────────

class WordExporter:
    """논문 전체를 Word .docx 파일로 출력."""

    def export(
        self,
        topic: Dict,
        sections: Dict[str, str],
        figures: Optional[List[Dict]] = None,
        tables: Optional[List[Dict]] = None,
        references: Optional[List[Dict]] = None,
        authors: Optional[List[str]] = None,
        affiliation: str = "",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Args:
            topic: {"title": str, "exposure": str, "outcome": str}
            sections: {"Abstract": str, "Introduction": str, "Methods": str,
                       "Results": str, "Discussion": str}
            figures: [{"bytes": bytes, "caption": str}, ...]
            tables: [{"type": str, "data": ..., "caption": str}, ...]
            references: [{"citation_key": str, "formatted": str}, ...]
            output_path: 저장 경로 (None이면 data/drafts/word/ 자동 생성)

        Returns:
            저장된 .docx 파일 경로
        """
        from docx import Document
        from docx.shared import Pt

        _ensure_dir()
        doc = Document()
        _apply_base_styles(doc)

        title = topic.get("title", "Untitled")
        _add_title(doc, title, authors or ["Yoosun Cho"], affiliation)

        section_order = ["Abstract", "Introduction", "Methods", "Results", "Discussion"]

        for sec_name in section_order:
            text = sections.get(sec_name, "")
            if not text:
                continue
            _add_section_heading(doc, sec_name)
            _add_body_text(doc, text)

            # Results 뒤에 그림/테이블 삽입
            if sec_name == "Results":
                self._insert_figures(doc, figures or [])
                self._insert_tables(doc, tables or [])

        # References
        if references:
            _add_section_heading(doc, "References")
            for i, ref in enumerate(references, start=1):
                p = doc.add_paragraph(style="List Number")
                p.text = f"{i}. {ref.get('formatted', '')}"

        # 저장
        if not output_path:
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title[:60])
            output_path = str(_OUTPUT_DIR / f"{safe_title}.docx")

        doc.save(output_path)
        _log.info(f"Word 저장 완료: {output_path}")
        return output_path

    def _insert_figures(self, doc, figures: List[Dict]):
        for fig in figures:
            img_bytes = fig.get("bytes")
            if img_bytes:
                _embed_figure(doc, img_bytes, fig.get("caption", ""))

    def _insert_tables(self, doc, tables: List[Dict]):
        from src.export.table_builder import (
            baseline_characteristics_table,
            regression_table,
            cross_table,
        )
        for t in tables:
            ttype = t.get("type", "baseline")
            caption = t.get("caption", "")
            data = t.get("data", [])
            if ttype == "baseline":
                baseline_characteristics_table(doc, data, caption)
            elif ttype == "regression":
                regression_table(doc, data, caption)
            elif ttype == "cross":
                row_labels = t.get("row_labels", [])
                col_labels = t.get("col_labels", [])
                cross_table(doc, data, row_labels, col_labels, caption)

    def export_bytes(self, **kwargs) -> bytes:
        """파일 저장 없이 바이트스트림으로 반환 (Streamlit 다운로드용)."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.export(output_path=tmp_path, **kwargs)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
