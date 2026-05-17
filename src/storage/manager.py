"""Unified storage manager — NotebookLM (primary, 선택적) + ChromaDB/Supabase (fallback).

NotebookLM은 선택 사항: 미설치 또는 미인증 시 로컬 벡터 스토어만 사용.
두 스토리지는 항상 동시 쓰기 (NLM에도 + 로컬에도).
"""
from __future__ import annotations

import logging
from typing import Optional

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def _try_load_paper_sync():
    """NotebookLM PaperSync를 안전하게 로드. 없으면 None 반환."""
    try:
        from src.notebooklm.paper_sync import PaperSync
        return PaperSync()
    except ImportError:
        logger.debug("notebooklm_tools 미설치 — NLM 없이 동작합니다.")
        return None
    except Exception as e:
        logger.debug(f"PaperSync 초기화 실패 — NLM 없이 동작합니다: {e}")
        return None


class StorageManager:
    """NLM 우선, 로컬(ChromaDB/Supabase) 폴백 통합 스토리지."""

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        api_key: Optional[str] = None,
    ):
        # NotebookLM (선택적 — 없어도 정상 동작)
        self._nlm_sync = _try_load_paper_sync()

        # 로컬 벡터 스토어 (ChromaDB 또는 Supabase pgvector)
        from src.vectordb.store import get_vector_store
        self._local = get_vector_store(persist_dir)

    # ── Status ────────────────────────────────────────────────────────────────

    def nlm_available(self) -> bool:
        if self._nlm_sync is None:
            return False
        try:
            return self._nlm_sync.nlm.is_available()
        except Exception:
            return False

    def status(self) -> dict:
        nlm_ok = self.nlm_available()
        local_count = 0
        try:
            local_count = self._local.count()
        except Exception:
            pass

        cloud_ok = False
        try:
            from src.cloud.db import cloud_available
            cloud_ok = cloud_available()
        except Exception:
            pass

        return {
            "notebooklm": "online" if nlm_ok else "offline",
            "supabase": "online" if cloud_ok else "offline",
            "vector_chunks": local_count,
            "active_storage": "NotebookLM + Local" if nlm_ok else "Local Only",
            "cloud": "connected" if cloud_ok else "disconnected",
        }

    # ── Write ─────────────────────────────────────────────────────────────────

    def store_paper(self, paper: dict, topic: str = "") -> str:
        """논문 1건 저장. 항상 로컬에 쓰고, NLM이 가능하면 추가로 NLM에도 저장."""
        # 로컬 항상 저장
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
            logger.warning(f"[Storage] 로컬 저장 실패: {e}")

        # NLM 추가 저장
        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    self._nlm_sync.add_pubmed_results(nb_id, [paper])
                    return "nlm+local"
            except Exception as e:
                logger.warning(f"[Storage] NLM 저장 실패: {e}")

        return "local"

    def store_papers(self, papers: list[dict], topic: str = "") -> dict:
        """논문 목록 일괄 저장."""
        nlm_count = 0
        local_count = 0

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
            logger.warning(f"[Storage] 로컬 일괄 저장 실패: {e}")

        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    nlm_count = self._nlm_sync.add_pubmed_results(nb_id, papers)
            except Exception as e:
                logger.warning(f"[Storage] NLM 일괄 저장 실패: {e}")

        return {"nlm": nlm_count, "local": local_count}

    def sync_pdf_dir(self, pdf_dir: str, topic: str) -> dict:
        """PDF 디렉토리를 로컬 + NLM에 동기화."""
        nlm_count = 0
        local_count = 0

        try:
            from src.ingestion.pdf_reader import PDFReader
            from src.ingestion.chunker import TextChunker
            from pathlib import Path
            reader = PDFReader()
            chunker = TextChunker()
            for pdf in Path(pdf_dir).glob("*.pdf"):
                pages = reader.read(str(pdf))
                text = " ".join(p.get("text", "") for p in pages)
                chunks = chunker.chunk(
                    text,
                    metadata={"filename": pdf.name, "source": str(pdf), "topic": topic},
                )
                added = self._local.add_chunks(chunks)
                local_count += added
        except Exception as e:
            logger.warning(f"[Storage] 로컬 PDF 수집 실패: {e}")

        if self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    nlm_count = self._nlm_sync.add_local_pdfs_dir(nb_id, pdf_dir)
            except Exception as e:
                logger.warning(f"[Storage] NLM PDF 동기화 실패: {e}")

        return {"nlm": nlm_count, "local": local_count}

    # ── Read / Search ─────────────────────────────────────────────────────────

    def search(self, query: str, topic: str = "", n_results: int = 5) -> dict:
        """쿼리 기반 검색. NLM 우선, 폴백 로컬."""
        if topic and self.nlm_available():
            try:
                nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
                if nb_id:
                    answer = self._nlm_sync.query_notebook(nb_id, query)
                    if answer and not answer.startswith("[NotebookLM query error"):
                        return {"source": "nlm", "answer": answer, "chunks": []}
            except Exception as e:
                logger.warning(f"[Storage] NLM 검색 실패: {e}")

        try:
            hits = self._local.search(query, n_results=n_results)
            answer = "\n\n".join(h["text"] for h in hits[:3]) if hits else ""
            return {"source": "local", "answer": answer, "chunks": hits}
        except Exception as e:
            logger.warning(f"[Storage] 로컬 검색 실패: {e}")
            return {"source": "none", "answer": "", "chunks": []}

    def analyze_topic(self, topic: str) -> dict:
        """NLM 전방위 분석 (NLM 가용 시에만)."""
        if not self.nlm_available():
            # 로컬 폴백: 간단한 청크 기반 요약
            try:
                hits = self._local.search(topic, n_results=5)
                if hits:
                    return {
                        "source": "local",
                        "summary": "\n\n".join(h["text"] for h in hits[:3]),
                        "note": "NotebookLM offline — 로컬 벡터 검색 결과입니다.",
                    }
            except Exception:
                pass
            return {"error": "NotebookLM offline — 분석 불가. 로컬 데이터도 없습니다."}
        try:
            nb_id = self._nlm_sync.get_or_create_topic_notebook(topic)
            if not nb_id:
                return {"error": "노트북을 가져오거나 생성할 수 없습니다."}
            return self._nlm_sync.analyze_for_research(nb_id)
        except Exception as e:
            return {"error": str(e)}

    def get_topic_notebooks(self) -> list[dict]:
        """주제-노트북 목록 (NLM 없으면 빈 리스트)."""
        if self._nlm_sync is None:
            return []
        try:
            return self._nlm_sync.list_topic_notebooks()
        except Exception:
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _paper_to_text(paper: dict) -> str:
        parts = []
        if paper.get("title"):
            parts.append(f"Title: {paper['title']}")
        if paper.get("authors"):
            a = paper["authors"]
            parts.append(f"Authors: {', '.join(a) if isinstance(a, list) else a}")
        if paper.get("year"):
            parts.append(f"Year: {paper['year']}")
        if paper.get("journal"):
            parts.append(f"Journal: {paper['journal']}")
        if paper.get("pmid"):
            parts.append(f"PMID: {paper['pmid']}")
        if paper.get("abstract"):
            parts.append(f"\nAbstract:\n{paper['abstract']}")
        return "\n".join(parts)
