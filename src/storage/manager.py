"""Unified storage manager — NotebookLM (primary) + ChromaDB (fallback).

기본값: NotebookLM MCP 서버에 저장/소싱
폴백: 서버 다운 시 로컬 ChromaDB 사용

사용 예:
    sm = StorageManager()
    sm.store_paper(paper, topic="청소년 비만")
    results = sm.search(query="수면 부족 청소년", topic="청소년 비만")
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """MCP 우선, 로컬 폴백 통합 스토리지."""

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        api_key: Optional[str] = None,
    ):
        # NotebookLM (primary)
        from src.notebooklm.paper_sync import PaperSync
        self._nlm_sync = PaperSync()

        # Vector store (Supabase if SUPABASE_DB_URL set, else ChromaDB)
        from src.vectordb.store import get_vector_store
        self._local = get_vector_store(persist_dir)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def nlm_available(self) -> bool:
        return self._nlm_sync.nlm.is_available()

    def status(self) -> dict:
        nlm_ok = self.nlm_available()
        local_count = 0
        try:
            local_count = self._local.count()
        except Exception:
            pass
        return {
            "notebooklm": "online" if nlm_ok else "offline",
            "local_chromadb_chunks": local_count,
            "active_storage": "NotebookLM" if nlm_ok else "ChromaDB (fallback)",
        }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_paper(self, paper: dict, topic: str = "") -> str:
        """논문 1건 저장. NLM 우선, 실패 시 ChromaDB.

        Returns: 'nlm' | 'local'
        """
        # Always write to local as backup
        try:
            text = self._paper_to_text(paper)
            chunk = {
                "text": text,
                "metadata": {
                    "source": paper.get("pmid") or paper.get("doi") or paper.get("title", "")[:80],
                    "filename": paper.get("title", "paper")[:80],
                    "topic": topic,
                },
            }
            self._local.add_chunks([chunk])
        except Exception as e:
            logger.warning(f"[Storage] Local write failed: {e}")

        # Try NLM as primary
        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    self._nlm_sync.add_pubmed_results(nb_id, [paper])
                    return "nlm"
            except Exception as e:
                logger.warning(f"[Storage] NLM write failed: {e}")

        return "local"

    def store_papers(self, papers: list[dict], topic: str = "") -> dict:
        """논문 목록 일괄 저장.

        Returns: {"nlm": N, "local": M}
        """
        nlm_count = 0
        local_count = 0

        # Always bulk-write to local
        try:
            chunks = [
                {
                    "text": self._paper_to_text(p),
                    "metadata": {
                        "source": p.get("pmid") or p.get("doi") or p.get("title", "")[:80],
                        "filename": p.get("title", "paper")[:80],
                        "topic": topic,
                    },
                }
                for p in papers
            ]
            self._local.add_chunks(chunks)
            local_count = len(papers)
        except Exception as e:
            logger.warning(f"[Storage] Local bulk write failed: {e}")

        # Try NLM
        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    nlm_count = self._nlm_sync.add_pubmed_results(nb_id, papers)
            except Exception as e:
                logger.warning(f"[Storage] NLM bulk write failed: {e}")

        return {"nlm": nlm_count, "local": local_count}

    def sync_pdf_dir(self, pdf_dir: str, topic: str) -> dict:
        """PDF 디렉토리를 NLM + 로컬 ChromaDB 모두에 동기화."""
        nlm_count = 0
        local_count = 0

        # Local ingest
        try:
            from src.ingestion.pdf_reader import PDFReader
            from src.ingestion.chunker import TextChunker
            from pathlib import Path
            reader = PDFReader()
            chunker = TextChunker()
            for pdf in Path(pdf_dir).glob("*.pdf"):
                pages = reader.read(str(pdf))
                text = " ".join(p.get("text", "") for p in pages)
                chunks = chunker.chunk(text, metadata={"filename": pdf.name, "source": str(pdf), "topic": topic})
                added = self._local.add_chunks(chunks)
                local_count += added
        except Exception as e:
            logger.warning(f"[Storage] Local PDF ingest failed: {e}")

        # NLM
        if self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    nlm_count = self._nlm_sync.add_local_pdfs_dir(nb_id, pdf_dir)
            except Exception as e:
                logger.warning(f"[Storage] NLM PDF sync failed: {e}")

        return {"nlm": nlm_count, "local": local_count}

    # ------------------------------------------------------------------
    # Read / Search
    # ------------------------------------------------------------------

    def search(self, query: str, topic: str = "", n_results: int = 5) -> dict:
        """쿼리 기반 관련 논문 검색. NLM 우선, 폴백 ChromaDB.

        Returns: {"source": "nlm"|"local", "answer": str, "chunks": [...]}
        """
        # Try NLM query first
        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    answer = self._nlm_sync.query_notebook(nb_id, query)
                    if answer and not answer.startswith("[NotebookLM query error"):
                        return {"source": "nlm", "answer": answer, "chunks": []}
            except Exception as e:
                logger.warning(f"[Storage] NLM search failed: {e}")

        # Fallback: local ChromaDB
        try:
            hits = self._local.search(query, n_results=n_results)
            answer = "\n\n".join(h["text"] for h in hits[:3]) if hits else ""
            return {
                "source": "local",
                "answer": answer,
                "chunks": hits,
            }
        except Exception as e:
            logger.warning(f"[Storage] Local search failed: {e}")
            return {"source": "none", "answer": "", "chunks": []}

    def analyze_topic(self, topic: str) -> dict:
        """NotebookLM으로 연구 주제 전방위 분석. NLM만 지원."""
        if not self.nlm_available():
            return {"error": "NotebookLM offline — analysis not available"}
        try:
            nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
            if not nb_id:
                return {"error": "Could not get/create notebook"}
            return self._nlm_sync.analyze_for_research(nb_id)
        except Exception as e:
            return {"error": str(e)}

    def get_topic_notebooks(self) -> list[dict]:
        """현재 관리 중인 주제-노트북 목록."""
        return self._nlm_sync.list_topic_notebooks()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _paper_to_text(paper: dict) -> str:
        from src.notebooklm.paper_sync import PaperSync
        return PaperSync._format_paper_text(paper)
