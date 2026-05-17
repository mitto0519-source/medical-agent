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

        self._reader = DocumentReader(api_key=api_key)
        self._web_reader = WebReader()
        self._chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        self._store = get_vector_store(persist_dir=persist_dir)

        # LLM client selection: prefer explicit injection, then Claude, then OpenAI.
        if llm_client:
            self._llm = llm_client
        else:
            try:
                self._llm = ClaudeClient(api_key=api_key)
            except Exception:
                if OpenAIClient is not None and os.environ.get("OPENAI_API_KEY"):
                    self._llm = OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY"))
                else:
                    # last resort: instantiate ClaudeClient and let it raise for visibility
                    self._llm = ClaudeClient(api_key=api_key)

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
        answer = self._llm.answer_from_papers(
            question, context_chunks, context_prefix=context_prefix
        )

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

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        """Return a summary of the current index state."""
        return {
            "total_chunks": self._store.count(),
            "indexed_papers": self._store.list_sources(),
        }
