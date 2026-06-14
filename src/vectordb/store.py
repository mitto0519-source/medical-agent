"""Persistent vector store — ChromaDB (local) or Supabase pgvector (cloud).

SUPABASE_DB_URL 환경변수 설정 시 → Supabase 자동 사용
미설정 시 → 로컬 ChromaDB

임베딩 모델: src.config.models.get_embedding_model() (중앙 설정)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import hashlib

from src.config.logging_config import get_logger
from src.config.models import get_embedding_model

_log = get_logger(__name__)


class VectorStore:
    """ChromaDB 기반 로컬 벡터 스토어."""

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        collection_name: str | None = None,
    ):
        # ★ Phase-Next: 임베딩 모델별 collection 분리 (차원 충돌 방지)
        # 예: papers_minilm_384d, papers_pubmedbert_768d, papers_medcpt_768d
        # 같은 ChromaDB 인스턴스에서 여러 모델 collection 공존 가능.
        if collection_name is None:
            import os, re
            model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            from src.config.models import get_embedding_dim
            dim = get_embedding_dim()
            # 모델 이름 단축
            tag = re.sub(r"[^a-z0-9]", "", model.lower().split("/")[-1])[:24]
            collection_name = f"papers_{tag}_{dim}d"
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError(
                "chromadb가 설치되지 않았습니다.\n"
                "  pip install chromadb\n"
                "또는 SUPABASE_DB_URL 환경변수를 설정하여 Supabase를 사용하세요."
            )

        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection_name = collection_name
        self._embedding_model = get_embedding_model()
        _log.debug(f"VectorStore 임베딩 모델: {self._embedding_model}")
        self._col = None  # lazy: embedding model loaded on first use

    @property
    def _collection(self):
        """Collection with embedding function — loaded lazily on first use."""
        if self._col is None:
            import chromadb
            try:
                ef = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self._embedding_model
                )
            except Exception as e:
                _log.warning(f"sentence_transformers 없음 — DefaultEmbeddingFunction 사용: {e}")
                ef = chromadb.utils.embedding_functions.DefaultEmbeddingFunction()
            self._col = self._client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        return self._col

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: List[Dict]) -> int:
        """청크 추가. 중복(내용 해시 기준) 자동 스킵.

        Returns: 실제로 추가된 청크 수
        """
        if not chunks:
            return 0

        ids, documents, metadatas = [], [], []
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text:
                continue
            doc_id = hashlib.sha256(text.encode()).hexdigest()

            meta: Dict = {}
            for k, v in chunk.get("metadata", {}).items():
                meta[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v
            meta["word_start"] = chunk.get("word_start", 0)
            meta["word_end"] = chunk.get("word_end", 0)
            meta["chunk_id"] = chunk.get("chunk_id", 0)

            ids.append(doc_id)
            documents.append(text)
            metadatas.append(meta)

        if not ids:
            return 0

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

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """의미 기반 유사도 검색.

        Returns: [{text, score, metadata}, ...]
        """
        count = self._collection.count()
        if count == 0:
            return []

        n = min(n_results, count)
        kwargs: Dict = {
            "query_texts": [query],
            "n_results": n,
            "include": ["documents", "distances", "metadatas"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        hits = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            hits.append({
                "text": doc,
                "score": round(1 - dist, 4),
                "metadata": meta,
            })
        return hits

    # ── Info ──────────────────────────────────────────────────────────────────

    def count(self) -> int:
        return self._collection.count()

    def list_sources(self) -> List[str]:
        if self.count() == 0:
            return []
        all_meta = self._collection.get(include=["metadatas"])["metadatas"]
        return sorted({m.get("filename", "") for m in all_meta if m.get("filename")})

    def delete_source(self, filename: str) -> int:
        results = self._collection.get(
            where={"filename": filename}, include=["metadatas"]
        )
        ids = results["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)


class NoOpVectorStore:
    """ChromaDB/Supabase 모두 없을 때의 무동작 폴백."""

    def add_chunks(self, chunks):
        return 0

    def search(self, query, n_results=5, where=None):
        return []

    def count(self):
        return 0

    def list_sources(self):
        return []

    def delete_source(self, filename):
        return 0

    def close(self):
        pass


def get_vector_store(persist_dir: str = "data/chromadb"):
    """환경에 따라 적절한 VectorStore 반환.

    SUPABASE_DB_URL → SupabaseVectorStore
    미설정           → VectorStore (ChromaDB)
    둘 다 실패       → NoOpVectorStore (경고 출력)
    """
    import os
    if os.environ.get("SUPABASE_DB_URL"):
        try:
            from src.vectordb.supabase_store import SupabaseVectorStore
            return SupabaseVectorStore()
        except Exception as e:
            _log.warning(f"SupabaseVectorStore 초기화 실패, ChromaDB로 폴백: {e}")
            # fall through to ChromaDB

    try:
        return VectorStore(persist_dir=persist_dir)
    except ImportError as e:
        _log.warning(
            f"ChromaDB 없음 — NoOpVectorStore 사용 (RAG 비활성화): {e}\n"
            "  pip install chromadb  으로 설치하세요."
        )
        return NoOpVectorStore()
    except Exception as e:
        _log.error(f"VectorStore 초기화 실패: {e}")
        return NoOpVectorStore()
