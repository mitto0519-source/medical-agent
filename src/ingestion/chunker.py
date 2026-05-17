"""Split long text into overlapping chunks for embedding"""

from typing import List


class TextChunker:
    """Split text into fixed-size chunks with overlap.

    Overlap preserves context across chunk boundaries so that a sentence
    split at the end of one chunk still appears at the start of the next.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        """
        Args:
            chunk_size: Target number of words per chunk
            overlap: Number of words shared between consecutive chunks
        """
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: dict | None = None) -> List[dict]:
        """Split text into chunks.

        Args:
            text: Raw text to split
            metadata: Optional key-value pairs attached to every chunk
                      (e.g. {"source": "paper.pdf", "title": "..."})

        Returns:
            List of dicts: {chunk_id, text, word_start, word_end, metadata}
        """
        words = text.split()
        if not words:
            return []

        meta = metadata or {}
        step = self.chunk_size - self.overlap
        chunks = []
        chunk_id = 0

        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "word_start": start,
                    "word_end": end,
                    "metadata": meta,
                }
            )
            chunk_id += 1
            if end == len(words):
                break
            start += step

        return chunks

    def chunk(self, text: str, metadata: dict | None = None) -> List[dict]:
        """Alias for chunk_text() — used by app/streamlit_app.py."""
        return self.chunk_text(text, metadata=metadata)

    def chunk_document(self, doc: dict) -> List[dict]:
        """Chunk a document dict produced by PDFReader.

        Each chunk inherits: source path, filename, title, and page count.
        """
        metadata = {
            "source": doc.get("path", ""),
            "filename": doc.get("filename", ""),
            "title": doc.get("title", ""),
            "page_count": doc.get("page_count", 0),
        }
        return self.chunk_text(doc.get("full_text", ""), metadata=metadata)
