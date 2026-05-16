"""Persistent vector store using ChromaDB"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Optional
import hashlib


class VectorStore:
    """Store and retrieve text chunks as embeddings via ChromaDB.

    Uses ChromaDB's built-in sentence-transformer embedding function so no
    separate embedding step is required at ingest time.
    """

    def __init__(self, persist_dir: str = "data/chromadb", collection_name: str = "papers"):
        """
        Args:
            persist_dir: Directory where ChromaDB persists its data
            collection_name: Name of the ChromaDB collection
        """
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        self._ef = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: List[Dict]) -> int:
        """Add text chunks to the collection.

        Skips chunks that are already stored (deduplication by content hash).

        Args:
            chunks: List of chunk dicts from TextChunker

        Returns:
            Number of chunks actually added (excluding duplicates)
        """
        if not chunks:
            return 0

        ids, documents, metadatas = [], [], []
        for chunk in chunks:
            text = chunk["text"]
            doc_id = hashlib.sha256(text.encode()).hexdigest()

            # Flatten metadata: ChromaDB only accepts str/int/float/bool values
            meta = {}
            for k, v in chunk.get("metadata", {}).items():
                meta[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v
            meta["word_start"] = chunk.get("word_start", 0)
            meta["word_end"] = chunk.get("word_end", 0)
            meta["chunk_id"] = chunk.get("chunk_id", 0)

            ids.append(doc_id)
            documents.append(text)
            metadatas.append(meta)

        # Check which IDs already exist
        existing = set(self._collection.get(ids=ids, include=[])["ids"])
        new_mask = [i for i, d in enumerate(ids) if d not in existing]

        if not new_mask:
            return 0

        self._collection.add(
            ids=[ids[i] for i in new_mask],
            documents=[documents[i] for i in new_mask],
            metadatas=[metadatas[i] for i in new_mask],
        )
        return len(new_mask)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, n_results: int = 5, where: Optional[Dict] = None) -> List[Dict]:
        """Semantic search for the most relevant chunks.

        Args:
            query: Natural-language question or statement
            n_results: How many top chunks to return
            where: Optional ChromaDB metadata filter, e.g. {"filename": "paper.pdf"}

        Returns:
            List of dicts with keys: text, score, metadata
        """
        kwargs = {"query_texts": [query], "n_results": n_results, "include": ["documents", "distances", "metadatas"]}
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        hits = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            hits.append(
                {
                    "text": doc,
                    "score": round(1 - dist, 4),  # cosine similarity
                    "metadata": meta,
                }
            )
        return hits

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return total number of stored chunks."""
        return self._collection.count()

    def list_sources(self) -> List[str]:
        """Return unique filenames indexed in the store."""
        if self.count() == 0:
            return []
        all_meta = self._collection.get(include=["metadatas"])["metadatas"]
        return sorted({m.get("filename", "") for m in all_meta if m.get("filename")})

    def delete_source(self, filename: str) -> int:
        """Remove all chunks belonging to a specific file.

        Args:
            filename: The filename as stored in metadata (e.g. "paper.pdf")

        Returns:
            Number of chunks deleted
        """
        results = self._collection.get(where={"filename": filename}, include=["metadatas"])
        ids = results["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)
