"""Supabase pgvector 어댑터 — VectorStore와 동일한 인터페이스.

환경변수 SUPABASE_DB_URL 설정 시에만 활성화.
임베딩 모델: src.config.models.get_embedding_model() (중앙 설정)
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

import numpy as np

from src.config.logging_config import get_logger
from src.config.models import get_embedding_model, get_embedding_dim

_log = get_logger(__name__)

_model = None
_model_unavailable = False


def _get_embedding_model():
    model_name = get_embedding_model()
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception as e:
        _log.warning(f"SentenceTransformer 로드 실패: {e}")
        return None


def _embed(texts: list[str]) -> list[list[float]]:
    global _model, _model_unavailable
    if _model_unavailable:
        return _embed_fallback(texts)
    if _model is None:
        _model = _get_embedding_model()
        if _model is None:
            _model_unavailable = True
            return _embed_fallback(texts)
    vecs = _model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def _embed_fallback(texts: list[str]) -> list[list[float]]:
    """sentence_transformers 없을 때 해시 기반 폴백 (검색 품질 낮음)."""
    dim = get_embedding_dim()
    result = []
    for text in texts:
        h = hashlib.sha256(text.lower().encode()).digest()
        vec = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
        vec = np.resize(vec, dim)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        result.append(vec.tolist())
    return result


class SupabaseVectorStore:
    """Supabase pgvector 기반 벡터 스토어 (VectorStore 호환 인터페이스)."""

    COLLECTION = "medical_papers"

    def __init__(self, db_url: Optional[str] = None):
        import vecs
        self._db_url = db_url or os.environ.get("SUPABASE_DB_URL")
        if not self._db_url:
            raise RuntimeError("SUPABASE_DB_URL 환경변수가 필요합니다.")

        dim = get_embedding_dim()
        _log.debug(f"SupabaseVectorStore 초기화: dim={dim}, model={get_embedding_model()}")

        self._vx = vecs.create_client(self._db_url)
        self._col = self._vx.get_or_create_collection(
            name=self.COLLECTION,
            dimension=dim,
        )
        try:
            self._col.create_index()
        except Exception:
            pass  # 이미 존재

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = _embed(texts)

        records = []
        for chunk, emb in zip(chunks, embeddings):
            text = chunk["text"]
            doc_id = hashlib.sha256(text.encode()).hexdigest()
            meta = {k: str(v) for k, v in chunk.get("metadata", {}).items()}
            meta["text"] = text
            records.append((doc_id, emb, meta))

        self._col.upsert(records=records)
        return len(records)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def search(
        self, query: str, n_results: int = 5, where: Optional[dict] = None,
    ) -> list[dict]:
        q_emb = _embed([query])[0]

        filters = None
        if where:
            filters = {k: {"$eq": str(v)} for k, v in where.items()}

        results = self._col.query(
            data=q_emb,
            limit=n_results,
            filters=filters,
            include_value=True,
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

    # ── Info ──────────────────────────────────────────────────────────────────

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
