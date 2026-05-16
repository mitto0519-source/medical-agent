"""Supabase pgvector adapter — ChromaDB VectorStore와 동일한 인터페이스.

환경변수 SUPABASE_DB_URL 이 설정된 경우에만 활성화.
미설정 시 로컬 ChromaDB 자동 사용.

Supabase 설정 방법:
  1. supabase.com 에서 프로젝트 생성
  2. SQL Editor: CREATE EXTENSION IF NOT EXISTS vector;
  3. Settings > Database > Connection string (URI) 복사
  4. .env 에 SUPABASE_DB_URL=postgresql://... 추가

Streamlit Cloud 배포 시:
  Settings > Secrets 에 SUPABASE_DB_URL 추가
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

import numpy as np


def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 출력 차원
_model = None


def _embed(texts: list[str]) -> list[list[float]]:
    global _model
    if _model is None:
        _model = _get_embedding_model()
    vecs = _model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


class SupabaseVectorStore:
    """Supabase pgvector 기반 벡터 스토어.

    VectorStore(ChromaDB)와 동일한 public 인터페이스를 제공합니다.
    """

    COLLECTION = "medical_papers"

    def __init__(self, db_url: Optional[str] = None):
        import vecs
        self._db_url = db_url or os.environ.get("SUPABASE_DB_URL")
        if not self._db_url:
            raise RuntimeError("SUPABASE_DB_URL 환경변수가 필요합니다.")
        self._vx = vecs.create_client(self._db_url)
        self._col = self._vx.get_or_create_collection(
            name=self.COLLECTION,
            dimension=_EMBEDDING_DIM,
        )
        # 인덱스 없으면 생성 (처음 한 번만 실행됨)
        try:
            self._col.create_index()
        except Exception:
            pass  # 이미 존재

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[dict]) -> int:
        """ChromaDB VectorStore.add_chunks() 호환."""
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = _embed(texts)

        records = []
        for chunk, emb in zip(chunks, embeddings):
            text = chunk["text"]
            doc_id = hashlib.sha256(text.encode()).hexdigest()
            meta = {k: str(v) for k, v in chunk.get("metadata", {}).items()}
            meta["text"] = text  # 텍스트도 메타데이터로 보관
            records.append((doc_id, emb, meta))

        # upsert = 중복 무시
        self._col.upsert(records=records)
        return len(records)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, n_results: int = 5, where: Optional[dict] = None) -> list[dict]:
        """ChromaDB VectorStore.search() 호환."""
        q_emb = _embed([query])[0]

        filters = None
        if where:
            # vecs 필터 형식: {"key": {"$eq": "value"}}
            filters = {k: {"$eq": str(v)} for k, v in where.items()}

        results = self._col.query(
            data=q_emb,
            limit=n_results,
            filters=filters,
            include_value=True,   # similarity score
            include_metadata=True,
        )

        hits = []
        for rec_id, score, meta in results:
            text = meta.pop("text", rec_id)
            hits.append({
                "text": text,
                "score": round(float(score), 4),
                "metadata": meta,
            })
        return hits

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def count(self) -> int:
        try:
            import sqlalchemy as sa
            with self._vx._engine.connect() as conn:
                row = conn.execute(
                    sa.text(f'SELECT COUNT(*) FROM vecs."{self.COLLECTION}"')
                ).fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def list_sources(self) -> list[str]:
        try:
            import sqlalchemy as sa
            with self._vx._engine.connect() as conn:
                rows = conn.execute(
                    sa.text(
                        f"SELECT DISTINCT metadata->>'filename' "
                        f'FROM vecs."{self.COLLECTION}" '
                        f"WHERE metadata->>'filename' IS NOT NULL"
                    )
                ).fetchall()
                return sorted(r[0] for r in rows if r[0])
        except Exception:
            return []

    def delete_source(self, filename: str) -> int:
        try:
            import sqlalchemy as sa
            with self._vx._engine.connect() as conn:
                result = conn.execute(
                    sa.text(
                        f'DELETE FROM vecs."{self.COLLECTION}" '
                        f"WHERE metadata->>'filename' = :fn"
                    ),
                    {"fn": filename},
                )
                conn.commit()
                return result.rowcount or 0
        except Exception:
            return 0

    def close(self):
        try:
            self._vx.disconnect()
        except Exception:
            pass
