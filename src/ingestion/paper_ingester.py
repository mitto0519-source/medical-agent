"""Paper Ingester — 기존 논문 파일(DOCX/PDF/TXT) 파싱 → IMRAD 섹션 분리.

업로드된 논문을 읽어 세션 기본값으로 설정하는 진입점.

지원 형식:
  - .txt / .md     : 직접 파싱
  - .docx          : python-docx로 단락 추출
  - .pdf           : pdfminer / PyPDF2 fallback

IMRAD 섹션 자동 분리 기준:
  영문/한글 섹션 헤딩 패턴 매칭
  → {abstract, introduction, methods, results, discussion, conclusion}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_CACHE_DIR = Path("data/drafts/uploaded")


@dataclass
class IngestedPaper:
    """파싱 결과."""
    raw_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    title: str = ""
    journal: str = ""
    authors: str = ""
    file_name: str = ""
    char_count: int = 0

    def is_valid(self) -> bool:
        return bool(self.raw_text and len(self.raw_text) > 200)

    def to_draft_string(self) -> str:
        """전체 논문 텍스트 재조립."""
        if not self.sections:
            return self.raw_text
        order = ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]
        parts = []
        for key in order:
            if key in self.sections and self.sections[key]:
                heading = key.upper()
                parts.append(f"{heading}\n{self.sections[key]}")
        # 나머지 섹션 (기타)
        for key, val in self.sections.items():
            if key not in order and val:
                parts.append(f"{key.upper()}\n{val}")
        return "\n\n".join(parts) if parts else self.raw_text


# ── 섹션 헤딩 패턴 ──────────────────────────────────────────────────────────

_SECTION_PATTERNS = {
    "abstract": re.compile(
        r"(?:^|\n)\s*(?:Abstract|ABSTRACT|초록|요약)\s*\n", re.I
    ),
    "introduction": re.compile(
        r"(?:^|\n)\s*(?:Introduction|INTRODUCTION|서론|배경|1\.\s*Introduction)\s*\n", re.I
    ),
    "methods": re.compile(
        r"(?:^|\n)\s*(?:Methods?|Materials?\s*and\s*Methods?|METHODS?|방법론?|연구\s*방법|2\.\s*Methods?)\s*\n", re.I
    ),
    "results": re.compile(
        r"(?:^|\n)\s*(?:Results?|RESULTS?|결과|3\.\s*Results?)\s*\n", re.I
    ),
    "discussion": re.compile(
        r"(?:^|\n)\s*(?:Discussion|DISCUSSION|고찰|논의|4\.\s*Discussion)\s*\n", re.I
    ),
    "conclusion": re.compile(
        r"(?:^|\n)\s*(?:Conclusions?|CONCLUSIONS?|결론|결론\s*및\s*제언|5\.\s*Conclusions?)\s*\n", re.I
    ),
}


def _split_into_sections(text: str) -> Dict[str, str]:
    """전문 텍스트 → IMRAD 섹션 딕셔너리."""
    # 각 섹션 헤딩의 시작 위치 수집
    hits = []
    for name, pat in _SECTION_PATTERNS.items():
        for m in pat.finditer(text):
            hits.append((m.start(), name, m.end()))

    if not hits:
        return {}

    hits.sort(key=lambda x: x[0])
    sections: Dict[str, str] = {}

    for i, (start, name, content_start) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        content = text[content_start:end].strip()
        if content:
            sections[name] = content

    return sections


def _extract_metadata(text: str) -> Dict[str, str]:
    """논문 제목/저자/저널 간이 추출 (첫 20줄 기반)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:20]
    meta: Dict[str, str] = {"title": "", "authors": "", "journal": ""}

    # 첫 비어있지 않은 줄을 제목으로 간주
    if lines:
        meta["title"] = lines[0][:200]

    # 저널명 패턴
    journal_pat = re.compile(
        r"(?:Journal of|J\.|BMJ|Lancet|NEJM|JKMS|IJERPH|PLoS|Nutrients|"
        r"Preventive Medicine|Public Health|Epidemiology)\b.*", re.I
    )
    for ln in lines[1:8]:
        m = journal_pat.search(ln)
        if m:
            meta["journal"] = m.group(0)[:120]
            break

    return meta


# ── 파일 형식별 텍스트 추출 ──────────────────────────────────────────────────

def _read_txt(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp949", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    try:
        from docx import Document  # python-docx
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        _log.warning("python-docx 없음. pip install python-docx 필요.")
        return ""
    except Exception as e:
        _log.warning("DOCX 파싱 실패: %s", e)
        return ""


def _read_pdf(path: Path) -> str:
    # 1차 시도: pdfminer.six
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(path))
        if text and len(text.strip()) > 200:
            return text
    except ImportError:
        pass
    except Exception as e:
        _log.debug("pdfminer 실패: %s", e)

    # 2차 시도: PyPDF2
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        _log.debug("PyPDF2 실패: %s", e)

    _log.warning("PDF 텍스트 추출 실패 (%s). pdfminer 또는 PyPDF2 필요.", path.name)
    return ""


# ── 공개 API ─────────────────────────────────────────────────────────────────

class PaperIngester:
    """논문 파일 파서."""

    def ingest(self, file_path: str | Path) -> IngestedPaper:
        """파일 경로를 받아 IngestedPaper 반환."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        suffix = path.suffix.lower()
        if suffix in (".txt", ".md"):
            raw = _read_txt(path)
        elif suffix == ".docx":
            raw = _read_docx(path)
        elif suffix == ".pdf":
            raw = _read_pdf(path)
        else:
            raise ValueError(f"지원하지 않는 형식: {suffix}. .txt/.docx/.pdf만 지원.")

        if not raw or not raw.strip():
            raise ValueError(f"파일에서 텍스트를 추출할 수 없습니다: {path.name}")

        sections = _split_into_sections(raw)
        meta = _extract_metadata(raw)

        paper = IngestedPaper(
            raw_text=raw,
            sections=sections,
            title=meta.get("title", ""),
            journal=meta.get("journal", ""),
            authors=meta.get("authors", ""),
            file_name=path.name,
            char_count=len(raw),
        )

        # 캐시 저장
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _CACHE_DIR / f"{path.stem}_parsed.txt"
        cache_file.write_text(paper.to_draft_string(), encoding="utf-8")
        _log.info("논문 파싱 완료: %s (%d자, %d섹션)", path.name, len(raw), len(sections))

        return paper

    def ingest_bytes(self, file_bytes: bytes, file_name: str) -> IngestedPaper:
        """Streamlit UploadedFile.getvalue() 결과를 직접 받아 파싱."""
        suffix = Path(file_name).suffix.lower()
        tmp_path = _CACHE_DIR / file_name
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(file_bytes)
        try:
            return self.ingest(tmp_path)
        finally:
            # tmp는 유지 (캐시 겸용)
            pass


def ingest_paper(file_path: str | Path) -> IngestedPaper:
    """편의 함수."""
    return PaperIngester().ingest(file_path)
