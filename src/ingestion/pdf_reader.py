"""PDF text extraction using PyMuPDF"""

import fitz  # PyMuPDF
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


class PDFReader:
    """Extract text and metadata from PDF files"""

    def read(self, pdf_path: str) -> Dict:
        """Extract full text and metadata from a PDF file.

        Args:
            pdf_path: Absolute or relative path to the PDF file

        Returns:
            Dictionary with keys:
              - path: resolved file path
              - filename: basename
              - title: metadata title (or filename if empty)
              - pages: list of {page_num, text} dicts
              - full_text: concatenated text of all pages
              - page_count: total number of pages
        """
        path = Path(pdf_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        doc = fitz.open(str(path))
        meta = doc.metadata or {}

        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            pages.append({"page_num": page_num + 1, "text": text.strip()})

        doc.close()

        full_text = "\n\n".join(p["text"] for p in pages if p["text"])
        title = meta.get("title") or path.stem

        return {
            "path": str(path),
            "filename": path.name,
            "title": title,
            "pages": pages,
            "full_text": full_text,
            "page_count": len(pages),
        }

    def read_directory(self, directory: str) -> List[Dict]:
        """Read all PDFs in a directory.

        Args:
            directory: Path to directory containing PDF files

        Returns:
            List of document dicts (same shape as read())
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        results = []
        for pdf_file in sorted(dir_path.glob("*.pdf")):
            try:
                results.append(self.read(str(pdf_file)))
            except Exception as exc:
                _log.warning("[PDFReader] Skipping %s: %s", pdf_file.name, exc)

        return results
