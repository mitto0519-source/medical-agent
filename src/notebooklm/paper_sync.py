"""Paper-to-NotebookLM sync for the Medical-Agent research pipeline.

YouTube 검색 → NotebookLM 패턴과 동일한 원리를
PubMed / Semantic Scholar / 로컬 PDF → NotebookLM 에 적용.

흐름:
  1. 연구 주제마다 NotebookLM 노트북 1개 생성 (이미 있으면 재사용)
  2. PubMed 검색 결과 / 로컬 PDF를 소스로 추가
  3. NotebookLM이 전체 소스를 AI로 합성 (Google 비용)
  4. 쿼리 결과를 로컬 ChromaDB에 캐시 (서버 다운 시 폴백)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.config.logging_config import get_logger

logger = get_logger(__name__)

# 주제 → 노트북 ID 매핑 파일
_MAP_PATH = Path("data/notebooklm_notebooks.json")


def _load_map() -> dict:
    if _MAP_PATH.exists():
        try:
            return json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_map(m: dict) -> None:
    _MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MAP_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


class PaperSync:
    """PubMed / 로컬 PDF 논문을 NotebookLM 노트북으로 동기화.

    사용 예:
        sync = PaperSync()
        if not sync.nlm.is_available():
            print("NotebookLM 오프라인 — 로컬 ChromaDB 사용")
            return

        nb_id = sync.get_or_create_topic_notebook("청소년 비만과 수면")
        sync.add_pubmed_results(nb_id, pubmed_papers)
        analysis = sync.query_notebook(nb_id, "핵심 연구 공백은?")
    """

    def __init__(self):
        from src.notebooklm.client import NLMClient
        self.nlm = NLMClient()
        self._map: dict = _load_map()

    # ------------------------------------------------------------------
    # 노트북 관리
    # ------------------------------------------------------------------

    def get_or_create_topic_notebook(self, topic: str) -> Optional[str]:
        """주제에 대한 NotebookLM 노트북 ID 반환 (없으면 생성)."""
        if not self.nlm.is_available():
            return None

        # 캐시 맵 먼저 확인
        if topic in self._map:
            return self._map[topic]

        title = f"[MA] {topic[:80]}"
        nb_id = self.nlm.get_or_create_notebook(title)
        self._map[topic] = nb_id
        _save_map(self._map)
        logger.info(f"[PaperSync] 노트북 '{title}' → {nb_id}")
        return nb_id

    def list_topic_notebooks(self) -> list[dict]:
        """로컬 맵 기준 주제-노트북 목록 반환."""
        return [{"topic": t, "notebook_id": nb_id} for t, nb_id in self._map.items()]

    # ------------------------------------------------------------------
    # 소스 추가
    # ------------------------------------------------------------------

    def add_pubmed_results(self, notebook_id: str, papers: list[dict]) -> int:
        """PubMed 검색 결과를 텍스트 소스로 추가.

        papers: [{"title": ..., "abstract": ..., "pmid": ..., "authors": ..., "year": ...}]
        Returns: 추가 성공 건수
        """
        count = 0
        for p in papers:
            title = p.get("title", "Paper")
            text = self._format_paper_text(p)
            if self.nlm.add_text_source(notebook_id, title[:100], text):
                count += 1
                logger.debug(f"[PaperSync] 추가: {title[:60]}")
        return count

    def add_pubmed_url(self, notebook_id: str, pmid: str) -> bool:
        """PubMed URL 소스 추가 (PMID 기반)."""
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        return self.nlm.add_url_source(notebook_id, url)

    def add_semantic_scholar_url(self, notebook_id: str, url: str) -> bool:
        """Semantic Scholar URL 소스 추가."""
        return self.nlm.add_url_source(notebook_id, url)

    def add_local_pdf(self, notebook_id: str, pdf_path: str) -> bool:
        """로컬 PDF 파일 업로드."""
        return self.nlm.add_file_source(notebook_id, pdf_path)

    def add_local_pdfs_dir(self, notebook_id: str, pdf_dir: str) -> int:
        """디렉토리 내 모든 PDF 일괄 업로드."""
        count = 0
        for pdf in Path(pdf_dir).glob("*.pdf"):
            if self.nlm.add_file_source(notebook_id, str(pdf)):
                count += 1
        return count

    # ------------------------------------------------------------------
    # 쿼리 / 분석
    # ------------------------------------------------------------------

    def query_notebook(self, notebook_id: str, question: str) -> str:
        """NotebookLM 노트북에 질문하고 답변 반환."""
        return self.nlm.query(notebook_id, question)

    def get_research_synthesis(self, notebook_id: str) -> dict:
        """NotebookLM AI 요약 + 제안 토픽 반환."""
        return self.nlm.get_summary(notebook_id)

    def analyze_for_research(self, notebook_id: str) -> dict:
        """연구 파이프라인용 표준 분석 질문 세트 실행."""
        questions = {
            "gap": "이 논문들에서 아직 연구되지 않은 주요 연구 공백은 무엇인가?",
            "methods": "가장 많이 사용된 연구 방법론과 통계 기법은 무엇인가?",
            "exposure_outcome": "주요 노출변수와 결과변수의 패턴을 정리해줘.",
            "novelty_angle": "신규 연구 각도로 가장 유망한 방향은 무엇인가?",
            "key_findings": "가장 일관되게 보고된 핵심 발견 3가지를 요약해줘.",
        }
        results = {}
        for key, q in questions.items():
            results[key] = self.nlm.query(notebook_id, q)
        return results

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    @staticmethod
    def _format_paper_text(paper: dict) -> str:
        parts = []
        if paper.get("title"):
            parts.append(f"Title: {paper['title']}")
        if paper.get("authors"):
            authors = paper["authors"]
            if isinstance(authors, list):
                authors = ", ".join(authors)
            parts.append(f"Authors: {authors}")
        if paper.get("year"):
            parts.append(f"Year: {paper['year']}")
        if paper.get("journal"):
            parts.append(f"Journal: {paper['journal']}")
        if paper.get("pmid"):
            parts.append(f"PMID: {paper['pmid']}")
        if paper.get("doi"):
            parts.append(f"DOI: {paper['doi']}")
        if paper.get("abstract"):
            parts.append(f"\nAbstract:\n{paper['abstract']}")
        if paper.get("keywords"):
            kw = paper["keywords"]
            if isinstance(kw, list):
                kw = ", ".join(kw)
            parts.append(f"\nKeywords: {kw}")
        return "\n".join(parts)
