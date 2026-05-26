"""Memory Scorer — 메모리 후보 항목의 importance/novelty/recurrence/trust 점수.

LLM-무관(쿼터 영향 없음). 임베딩 유사도는 sentence-transformers를 닫힌-stderr 가드로 감싸 사용.

API:
  score(text, type, source, candidates=[]) -> dict
  gate(scores, type) -> "store" | "review" | "quarantine" | "skip"

설계:
  - novelty: 1 - max cosine(text, candidates) → 이미 알고 있는 정도와 반비례
  - recurrence: 최근 N일 내 의미상 유사 항목 등장 횟수 (높을수록 진짜 패턴)
  - importance: type/source 기반 + 길이/구조 가중
  - trust: source별 사전값 (user 최고, auto_learn 최저)
"""
from __future__ import annotations

import contextlib
import io
import os
import warnings
from typing import Iterable

# HF 진행바·경고 사전 차단(Streamlit 스레드 닫힌 stderr 보호)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_MODEL = None


@contextlib.contextmanager
def _quiet():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            yield


def _embed(text: str):
    global _MODEL
    if _MODEL is None:
        with _quiet():
            from sentence_transformers import SentenceTransformer
            from src.config.models import get_embedding_model
            _MODEL = SentenceTransformer(get_embedding_model())
    with _quiet():
        return _MODEL.encode((text or "")[:1500])


def _cos(a, b) -> float:
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    d = (float(np.linalg.norm(a)) * float(np.linalg.norm(b))) or 1.0
    return float(a @ b / d)


_TRUST = {
    "user": 1.00,
    "human": 1.00,
    "verified": 0.95,
    "reflection": 0.85,
    "observation": 0.75,
    "rule": 0.95,
    "llm": 0.55,
    "auto_learn": 0.45,
    "trend": 0.45,
    "pubmed": 0.80,    # 외부 검증된 출처
    "crossref": 0.85,
}

_IMPORTANCE_BASE = {
    "goal": 0.85,
    "procedural": 0.75,   # 행동 규칙
    "semantic": 0.55,
    "episodic": 0.45,
}


def score(text: str, type: str = "episodic", source: str = "observation",
          candidates: Iterable[str] = ()) -> dict:
    """단일 후보에 대한 점수 산출."""
    text = (text or "").strip()
    if not text:
        return {"novelty": 0.0, "recurrence": 0.0, "importance": 0.0, "trust": 0.0,
                "composite": 0.0, "embedding_used": False}

    # 길이/구조 가중 — 너무 짧으면 importance 페널티
    length_factor = min(1.0, len(text) / 80.0)

    # 신뢰도
    trust = _TRUST.get(source, 0.5)

    # 중요도 base + 길이 + (대문자 약어/숫자 풍부도 가중 — 통계·고유명사 신호)
    base = _IMPORTANCE_BASE.get(type, 0.5)
    info_density = min(0.2, (sum(1 for c in text if c.isdigit()) / max(len(text), 1)) * 3)
    importance = min(1.0, base * (0.6 + 0.4 * length_factor) + info_density)

    # 신규성 / 재출현 — 후보가 있을 때만 임베딩 사용
    novelty = 1.0
    recurrence = 0.0
    used_emb = False
    cand_list = [c for c in candidates if (c or "").strip()]
    if cand_list:
        try:
            tv = _embed(text)
            sims = [_cos(tv, _embed(c)) for c in cand_list[:8]]
            max_sim = max(sims) if sims else 0.0
            novelty = max(0.0, 1.0 - max_sim)
            # 재출현: 0.6 이상 유사한 후보 개수 / 후보수
            recurrence = (sum(1 for s in sims if s >= 0.6) / len(sims)) if sims else 0.0
            used_emb = True
        except Exception:
            pass

    # composite: trust × importance × (novelty^0.6 + 0.3·recurrence)
    composite = trust * importance * (novelty ** 0.6 + 0.3 * recurrence)
    composite = max(0.0, min(1.0, composite))

    return {
        "novelty": round(novelty, 3), "recurrence": round(recurrence, 3),
        "importance": round(importance, 3), "trust": round(trust, 3),
        "composite": round(composite, 3), "embedding_used": used_emb,
    }


def gate(scores: dict, type: str = "episodic") -> str:
    """점수 → 라우팅 판정.

    skip: 학습 가치 없음(저신뢰 + 저신규성)
    quarantine: 격리(검토 후 승인)
    review: 일단 저장하지만 약한 신뢰
    store: 정상 저장
    """
    t, i, n, c = scores["trust"], scores["importance"], scores["novelty"], scores["composite"]

    # 저신뢰 자동 출처는 신규성도 낮으면 버림 (이미 있는 정보를 양산하는 trend/auto_learn 방지)
    if t < 0.5 and n < 0.3:
        return "skip"
    # 너무 약한 신호 (composite 매우 낮음)
    if c < 0.10:
        return "quarantine"
    # 자동 출처 + 보통 신호 → review (사람 검토 후 승격 가능)
    if t < 0.6 and c < 0.30:
        return "review"
    return "store"
