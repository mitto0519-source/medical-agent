"""RAG (Retrieval-Augmented Generation) pipeline

Ties together: document reading → chunking → vector storage → Claude generation.
Supports PDF, Word, PowerPoint, Excel, text, and images.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional

from src.ingestion.document_reader import DocumentReader
from src.ingestion.web_reader import WebReader
from src.ingestion.chunker import TextChunker
from src.vectordb.store import get_vector_store
from src.llm.claude_client import ClaudeClient
try:
    from src.llm.openai_client import OpenAIClient
except Exception:
    OpenAIClient = None

# Standard logger
try:
    from src.config.logging_config import get_logger
    _log = get_logger(__name__)
except Exception:
    import logging as _logging
    _log = _logging.getLogger(__name__)


class RAGPipeline:
    """Full RAG pipeline for medical research papers.

    Workflow
    --------
    1. ingest_pdf()   — read PDF → chunk → embed → store in ChromaDB
    2. ask()          — embed query → retrieve top-k chunks → Claude answers
    3. summarize()    — retrieve all chunks for a paper → Claude summarises
    """

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        papers_dir: str = "data/papers",
        chunk_size: int = 500,
        overlap: int = 100,
        top_k: int = 5,
        api_key: Optional[str] = None,
        llm_client: Optional[object] = None,
    ):
        """
        Args:
            persist_dir: ChromaDB storage directory
            papers_dir: Default directory to scan for PDFs
            chunk_size: Words per chunk
            overlap: Overlapping words between adjacent chunks
            top_k: Number of chunks to retrieve per query
            api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var)
        """
        self.papers_dir = papers_dir
        self.top_k = top_k
        self._persist_dir = persist_dir
        self._store_obj = None  # lazy: loaded on first access

        self._reader = DocumentReader(api_key=api_key)
        self._web_reader = WebReader()
        self._chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)

        # LLM client: 명시 주입이 없으면 get_llm_client로 — 자동 최적화 + 3중 폴백
        # (Claude→OpenAI→Gemini)을 모든 RAG LLM 호출(summarize/ask)에 일관 적용.
        if llm_client is not None:
            self._llm = llm_client
        else:
            try:
                from src.llm import get_llm_client
                self._llm = get_llm_client(api_key=api_key, task="standard")
            except Exception:
                # 폴백: 팩토리 실패 시 직접 ClaudeClient (가시성 위해 raise 허용)
                self._llm = ClaudeClient(api_key=api_key)

    @property
    def _store(self):
        if self._store_obj is None:
            self._store_obj = get_vector_store(persist_dir=self._persist_dir)
        return self._store_obj

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_url(self, url: str) -> Dict:
        """Fetch a URL and store its content in the vector DB.

        Supports: general web pages, arXiv, PubMed, direct PDF links.

        Args:
            url: Full URL, arXiv ID (e.g. "2401.12345"), or PMID

        Returns:
            Summary dict: {title, filename, file_type, chunks_added}
        """
        doc = self._web_reader.read(url)
        chunks = self._chunker.chunk_document(doc)
        added = self._store.add_chunks(chunks)
        return {
            "title": doc["title"],
            "filename": doc["filename"],
            "file_type": doc.get("file_type", "web"),
            "source_url": doc["metadata"].get("source_url", url),
            "chunks_total": len(chunks),
            "chunks_added": added,
        }

    def ingest_file(self, file_path: str) -> Dict:
        """Read any supported file, chunk it, and store in the vector DB.

        Supports: PDF, Word, PowerPoint, Excel, text, images.

        Args:
            file_path: Path to the file

        Returns:
            Summary dict: {title, filename, file_type, page_count, chunks_added}
        """
        doc = self._reader.read(file_path)
        chunks = self._chunker.chunk_document(doc)
        added = self._store.add_chunks(chunks)

        return {
            "title": doc["title"],
            "filename": doc["filename"],
            "file_type": doc.get("file_type", "unknown"),
            "page_count": doc["page_count"],
            "chunks_total": len(chunks),
            "chunks_added": added,
        }

    def ingest_pdf(self, pdf_path: str) -> Dict:
        """Alias for ingest_file — kept for backwards compatibility."""
        return self.ingest_file(pdf_path)

    def ingest_directory(self, directory: Optional[str] = None, recursive: bool = False) -> List[Dict]:
        """Ingest all supported files in a directory.

        Args:
            directory: Path to scan. Defaults to self.papers_dir.
            recursive: If True, scan subdirectories too.

        Returns:
            List of ingest summary dicts
        """
        target = directory or self.papers_dir
        if recursive:
            docs = self._reader.read_directory_recursive(target)
        else:
            docs = self._reader.read_directory(target)
        results = []
        for doc in docs:
            chunks = self._chunker.chunk_document(doc)
            added = self._store.add_chunks(chunks)
            results.append(
                {
                    "title": doc["title"],
                    "filename": doc["filename"],
                    "page_count": doc["page_count"],
                    "chunks_total": len(chunks),
                    "chunks_added": added,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        filename_filter: Optional[str] = None,
        context_prefix: str = "",
    ) -> Dict:
        """Answer a question grounded in indexed papers.

        Args:
            question: Natural-language question about the research
            filename_filter: Limit search to a specific paper (by filename)
            context_prefix: Prepend this text to the system prompt (e.g. continuity preamble)

        Returns:
            {answer, sources}  where sources is a list of {text, score, metadata}
        """
        where = {"filename": filename_filter} if filename_filter else None
        hits = self._store.search(question, n_results=self.top_k, where=where)

        if not hits:
            return {
                "answer": "No relevant content found in the indexed papers. Please ingest papers first.",
                "sources": [],
            }

        context_chunks = [h["text"] for h in hits]
        try:
            answer = self._llm.answer_from_papers(
                question, context_chunks, context_prefix=context_prefix
            )
        except Exception as exc:
            _log.warning("RAG answer_from_papers 실패: %s", exc, exc_info=True)
            return {
                "answer": "RAG 기반 응답 생성 중 오류가 발생했습니다. 인덱스 또는 LLM 상태를 확인하세요.",
                "sources": hits,
            }

        return {"answer": answer, "sources": hits}

    # ------------------------------------------------------------------
    # Summarisation
    # ------------------------------------------------------------------

    def summarize(self, filename: str, n_chunks: int = 10) -> str:
        """Generate a structured summary of an indexed paper.

        Args:
            filename: PDF filename as stored in metadata (e.g. "paper.pdf")
            n_chunks: How many representative chunks to send to Claude

        Returns:
            Structured summary text
        """
        hits = self._store.search(
            "main findings methods results conclusion",
            n_results=n_chunks,
            where={"filename": filename},
        )
        if not hits:
            return f"'{filename}' not found in the index. Please ingest it first."

        paper_text = "\n\n".join(h["text"] for h in hits)
        return self._llm.summarize_paper(paper_text)

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        """벡터 스토어에서 관련 청크를 검색해 반환.

        Returns:
            List of {text, score, metadata} dicts (빈 리스트 가능)
        """
        return self._store.search(query, n_results=n_results) or []

    # ------------------------------------------------------------------
    # Multi-stage retrieval (B-7) — dense + lexical rerank + context compression
    # ------------------------------------------------------------------

    def search_multistage(self, query: str, *, n_final: int = 5, n_pool: int = 20,
                          recency_boost: float = 0.1,
                          must_cite: Optional[List[str]] = None) -> List[Dict]:
        """확장된 retrieval — dense top-N → lexical/메타 rerank → 최종 n_final.

        Args:
            n_final: 최종 반환 개수
            n_pool: dense 후보 풀 크기 (>= n_final)
            recency_boost: 최근 PubMed pub_year에 가산점 (0~0.5)
            must_cite: 반드시 포함되어야 할 PMID/DOI 리스트 (있으면 강제 합집합)

        Returns:
            List of dicts with: text, score, score_dense, score_lex, score_recency,
            final_score, metadata.
        """
        pool = self._store.search(query, n_results=n_pool) or []
        if not pool:
            return []
        # Lexical overlap (Jaccard token) — query token vs chunk token
        q_tokens = set(_simple_tokens(query))

        scored: list = []
        for hit in pool:
            text = hit.get("text", "") or ""
            md = hit.get("metadata", {}) or {}
            score_dense = float(hit.get("score", 0.0) or 0.0)
            score_lex = _jaccard(q_tokens, set(_simple_tokens(text[:600])))
            score_recency = 0.0
            year = md.get("year") or md.get("pub_year")
            if year:
                try:
                    y = int(str(year)[:4])
                    if 2020 <= y <= 2030:
                        score_recency = recency_boost * (y - 2020) / 10.0
                except Exception:
                    pass
            # Final score = 0.6 dense + 0.3 lex + recency
            final = 0.6 * score_dense + 0.3 * score_lex + score_recency
            scored.append({**hit, "score_dense": score_dense, "score_lex": score_lex,
                           "score_recency": score_recency, "final_score": final})

        # must_cite 강제 포함 (앞쪽)
        forced: list = []
        if must_cite:
            keep = set(str(x).strip().lower() for x in must_cite)
            for it in scored:
                md = it.get("metadata", {}) or {}
                key = str(md.get("pmid") or md.get("doi") or "").lower()
                if key and key in keep:
                    forced.append(it)
                    keep.discard(key)

        rest = [it for it in scored if it not in forced]
        rest.sort(key=lambda x: x["final_score"], reverse=True)
        return forced + rest[: max(0, n_final - len(forced))]


def _simple_tokens(s: str) -> List[str]:
    import re
    return [t for t in re.findall(r"[A-Za-z가-힣]{3,}", (s or "").lower())]


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        """Return a summary of the current index state."""
        return {
            "total_chunks": self._store.count(),
            "indexed_papers": self._store.list_sources(),
        }
