"""Signal 2: 지식 증류 (Knowledge Distillation).

ChromaDB에 쌓인 논문들을 LLM이 실제로 읽고 핵심 인사이트를 압축.
매주 1회 실행, 결과를 캐시해 API 비용 최소화.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_CACHE = Path("data/agent_self/distilled_insights.json")
_REFRESH_DAYS = 7  # 최대 주 1회 재증류


def distill(force: bool = False) -> Dict:
    """ChromaDB 논문 → LLM 요약 → 핵심 인사이트 캐시."""
    # 캐시 유효성 확인 (비용 절감)
    if not force and _CACHE.exists():
        try:
            cached = json.loads(_CACHE.read_text(encoding="utf-8"))
            last = datetime.fromisoformat(cached.get("distilled_at", "2000-01-01"))
            if datetime.now() - last < timedelta(days=_REFRESH_DAYS):
                _log.info("[distiller] 캐시 유효 (%.1f일 전), 재사용.",
                          (datetime.now() - last).days)
                return cached
        except Exception:
            pass

    try:
        from src.rag.pipeline import RAGPipeline
        rag = RAGPipeline(persist_dir="data/chromadb_test")
    except Exception as e:
        _log.warning("[distiller] RAG 초기화 실패: %s", e)
        return _empty()

    # 핵심 주제별 대표 청크 수집
    queries = [
        "sleep adolescent Korea KYRBS depression",
        "obesity BMI Korean youth physical activity",
        "smoking alcohol mental health Korean population",
        "suicidal ideation stress Korean adolescent",
        "dietary pattern nutrition Korea chronic disease",
    ]

    all_chunks: List[str] = []
    for q in queries:
        try:
            result = rag.ask(q)
            for src in result.get("sources", [])[:3]:
                text = src.get("text", "")
                if text and len(text) > 100:
                    all_chunks.append(text[:500])
        except Exception as e:
            _log.warning("[distiller] RAG 쿼리 실패 '%s': %s", q[:30], e)

    if not all_chunks:
        return _empty()

    # LLM으로 인사이트 압축 (최대 20개 청크만 사용 — 비용 제한)
    chunks_for_llm = all_chunks[:20]
    context = "\n\n---\n\n".join(chunks_for_llm)

    try:
        from src.llm import get_llm_client
        llm = get_llm_client(task="standard")
        prompt = (
            "다음은 한국 공중보건 연구 논문들의 핵심 내용입니다.\n\n"
            f"{context}\n\n"
            "위 논문들에서 반복적으로 확인되는 핵심 통계적 사실과 연구 패턴을 "
            "10개 이하의 간결한 문장으로 추출하세요. "
            "각 항목은 '- ' 으로 시작하고, OR/RR 수치나 구체적 관계를 포함하세요. "
            "예: '- 청소년 수면 6시간 미만: 우울감 OR 1.8-2.4 (KYRBS 다수 연구 일관적)'"
        )
        raw = llm.generate(prompt, system_prompt="당신은 의학 문헌 분석 전문가입니다.")
        insights = [
            line.strip().lstrip("- ").strip()
            for line in raw.splitlines()
            if line.strip().startswith("-") and len(line.strip()) > 20
        ][:10]
    except Exception as e:
        _log.warning("[distiller] LLM 증류 실패: %s", e)
        insights = []

    result = {
        "source": "knowledge_distiller",
        "insights": insights,
        "confidence": min(0.85, 0.4 + len(all_chunks) * 0.01),
        "data_volume": len(all_chunks),
        "distilled_at": datetime.now().isoformat(),
    }
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info("[distiller] 증류 완료: %d개 인사이트 (청크 %d개 기반)",
              len(insights), len(all_chunks))
    return result


def _empty() -> Dict:
    return {"source": "knowledge_distiller", "insights": [], "confidence": 0.1,
            "data_volume": 0, "distilled_at": "2000-01-01"}
