"""Universal document reader — PDF, Word, PowerPoint, Excel, text, images

Supported formats
-----------------
PDF     .pdf            → PyMuPDF
Word    .docx           → python-docx
PPT     .pptx           → python-pptx
Excel   .xlsx .xls .csv → openpyxl / pandas
Text    .txt .md .rst   → plain read
Image   .jpg .jpeg .png .webp .bmp .gif → Claude Vision (text + interpretation)
"""

import base64
import os
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_pdf(path: Path) -> tuple[str, dict]:
    import fitz
    doc = fitz.open(str(path))
    meta = doc.metadata or {}
    pages = []
    for page in doc:
        text = page.get_text("text").strip()
        if text:
            pages.append(text)
    doc.close()
    return "\n\n".join(pages), meta


def _read_docx(path: Path) -> tuple[str, dict]:
    from docx import Document
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    return "\n\n".join(paragraphs), {}


def _read_pptx(path: Path) -> tuple[str, dict]:
    from pptx import Presentation
    prs = Presentation(str(path))
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())
        if texts:
            slides.append(f"[Slide {i}]\n" + "\n".join(texts))
    return "\n\n".join(slides), {}


def _read_excel(path: Path) -> tuple[str, dict]:
    import pandas as pd
    ext = path.suffix.lower()
    if ext == ".csv":
        df_dict = {"Sheet1": pd.read_csv(str(path))}
    else:
        df_dict = pd.read_excel(str(path), sheet_name=None, engine="openpyxl")
    sheets = []
    for sheet_name, df in df_dict.items():
        sheets.append(f"[Sheet: {sheet_name}]\n{df.to_string(index=False)}")
    return "\n\n".join(sheets), {}


def _read_text(path: Path) -> tuple[str, dict]:
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return path.read_text(encoding=enc), {}
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="replace"), {}


def _read_image(path: Path, api_key: Optional[str] = None) -> tuple[str, dict]:
    """Send image to Claude Vision and extract text + interpretation."""
    import anthropic

    ext_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/png",
    }
    media_type = ext_map.get(path.suffix.lower(), "image/png")

    image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Please extract ALL text visible in this image (OCR). "
                            "Then provide a concise interpretation of what the image shows "
                            "(charts, diagrams, tables, figures, etc.). "
                            "Format: first the extracted text, then '--- Interpretation ---', "
                            "then your interpretation."
                        ),
                    },
                ],
            }
        ],
    )
    text = response.content[0].text if response.content else ""
    return text, {"vision_processed": True}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf", ".docx", ".pptx",
    # Spreadsheets
    ".xlsx", ".xls", ".csv",
    # Plain text
    ".txt", ".md", ".rst",
    # Images
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


class DocumentReader:
    """Read any supported file and return a unified document dict."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def read(self, file_path: str) -> Dict:
        """Extract text and metadata from a file.

        Returns
        -------
        {
            path, filename, title, full_text, page_count,
            file_type, metadata
        }
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported extension '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        if ext == ".pdf":
            full_text, meta = _read_pdf(path)
            file_type = "pdf"
        elif ext == ".docx":
            full_text, meta = _read_docx(path)
            file_type = "word"
        elif ext == ".pptx":
            full_text, meta = _read_pptx(path)
            file_type = "powerpoint"
        elif ext in {".xlsx", ".xls", ".csv"}:
            full_text, meta = _read_excel(path)
            file_type = "spreadsheet"
        elif ext in {".txt", ".md", ".rst"}:
            full_text, meta = _read_text(path)
            file_type = "text"
        elif ext in IMAGE_EXTENSIONS:
            full_text, meta = _read_image(path, self._api_key)
            file_type = "image"
        else:
            raise ValueError(f"Unhandled extension: {ext}")

        title = meta.get("title") or path.stem
        word_count = len(full_text.split())
        page_count = max(1, word_count // 400)  # rough estimate for non-PDF

        return {
            "path": str(path),
            "filename": path.name,
            "title": title,
            "full_text": full_text,
            "page_count": page_count,
            "file_type": file_type,
            "metadata": meta,
        }

    def read_directory(self, directory: str) -> List[Dict]:
        """Read all supported files in a directory (non-recursive)."""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        results = []
        for f in sorted(dir_path.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    results.append(self.read(str(f)))
                except Exception as exc:
                    print(f"[DocumentReader] Skipping {f.name}: {exc}")

        return results

    def read_directory_recursive(self, directory: str) -> List[Dict]:
        """Read all supported files recursively."""
        dir_path = Path(directory)
        results = []
        for f in sorted(dir_path.rglob("*")):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    results.append(self.read(str(f)))
                except Exception as exc:
                    print(f"[DocumentReader] Skipping {f.name}: {exc}")
        return results
