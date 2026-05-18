"""Research Pipeline — 조유선 스타일 논문 생산 마스터 파이프라인

흐름:
  1. 데이터셋 + 방법론 라이브러리 참조
  2. 주제 생성
  3. 신규성 확인 (PubMed)
  4. 타당성 간이 검증
  5. 통계 수행 (외부 데이터 필요)
  6. 조유선 스타일 논문 작성
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.llm import get_llm_client
from src.memory import change_log
from src.profile.author_profile import AuthorProfile
from src.library.dataset_library import DatasetLibrary
from src.library.methods_library import MethodsLibrary
from src.research.novelty_checker import NoveltyChecker
from src.research.paper_writer import PaperWriter
from src.rag.pipeline import RAGPipeline
from src.ingestion.evidence_reader import EvidenceReader

_log = get_logger(__name__)


def _clean_llm_response(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            inner = parts[1].strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            text = inner
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text.strip().rstrip("```").strip()


class ResearchPipeline:
    """조유선 스타일 논문 생산 마스터 파이프라인.

    사용 예:
        rp = ResearchPipeline()
        rp.register_dataset("KYRBS", variables=[...])
        topics = rp.generate_topics("KYRBS", focus="sleep quality")
        novelty = rp.check_novelty(topics[0])
        draft = rp.write_paper(topics[0], study_info={...}, results={...})
    """

    def __init__(
        self,
        author_name: str = "Yoosun Cho",
        persist_dir: str = "data/chromadb",
        profile_dir: str = "data/author_profiles",
        library_dir: str = "data/libraries",
        api_key: Optional[str] = None,
    ):
        bootstrap()  # .env 단일 로드

        self._llm = get_llm_client(api_key=api_key, task="standard")

        self.author = AuthorProfile(author_name, profile_dir, api_key)
        self.datasets = DatasetLibrary(library_dir)
        self.methods = MethodsLibrary(library_dir)
        self.novelty = NoveltyChecker(api_key)
        self.rag = RAGPipeline(persist_dir=persist_dir, api_key=api_key)
        self.writer = PaperWriter(
            self.author, self.methods, self.datasets, self.rag, llm_client=self._llm
        )
        self.evidence = EvidenceReader()

        self._output_dir = Path("data/drafts")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1 — 저자 스타일 시드 구축 ───────────────────────────────────────

    def build_author_profile(self, paper_texts: List[Dict]) -> str:
        """논문 텍스트 목록으로 저자 스타일 시드 구축.

        paper_texts: [{"title": "...", "text": "..."}, ...]
        """
        _log.info("%s 스타일 시드 구축 시작...", self.author.author_name)
        for paper in paper_texts:
            title = paper.get("title", "")
            text = paper.get("text", "")
            if len(text) < 200:
                continue
            result = self.author.analyse_paper(text, title)
            status = "[완료]" if result["status"] == "analysed" else "[스킵]"
            _log.info("  %s %s", status, title[:60])

        return self.author.summary()

    # ── Step 2 — 데이터셋 라이브러리화 ──────────────────────────────────────

    def register_dataset(
        self,
        name: str,
        full_name: str = "",
        description: str = "",
        variables: Optional[List[Dict]] = None,
        confounders: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        """데이터셋과 변수를 라이브러리에 등록.

        variables: [{"name": "BMI", "label": "...", "type": "continuous", ...}]
        """
        self.datasets.add_dataset(name, full_name, description)
        for v in (variables or []):
            vname = v.pop("name", None)
            if vname:
                self.datasets.add_variable(name, vname, **v)
        for c in (confounders or []):
            self.datasets.add_confounder(name, c)
        for n in (notes or []):
            self.datasets.add_analysis_note(name, n)
        _log.info("데이터셋 '%s' 라이브러리 등록 완료.", name)

    # ── Step 3 — 주제 생성 ───────────────────────────────────────────────────

    def generate_topics(
        self,
        dataset_name: str,
        focus: str = "",
        n_topics: int = 5,
        reference_query: Optional[str] = None,
    ) -> List[Dict]:
        """데이터셋 + RAG 컨텍스트 기반 연구 주제 생성.

        Returns list of topic dicts:
            {"title", "exposure", "outcome", "population", "rationale",
             "suggested_design", "suggested_methods"}
        """
        dataset_ctx = self.datasets.get_context(dataset_name)

        rag_ctx = ""
        if reference_query or focus:
            hits = self.rag.ask(reference_query or focus)
            rag_ctx = "\n".join(h["text"] for h in hits.get("sources", [])[:3])
            ev_summary = self.evidence.search_and_summarise(reference_query or focus, n=5)
            rag_ctx = ev_summary + "\n\n--- LOCAL INDEX ---\n" + rag_ctx

        prompt = f"""You are a medical research strategist.
Given this dataset and research context, generate {n_topics} original, publishable research topics.

DATASET CONTEXT:
{dataset_ctx}

RESEARCH FOCUS: {focus}

EXISTING LITERATURE CONTEXT:
{rag_ctx[:2000] if rag_ctx else 'Not provided'}

Generate {n_topics} research topics as JSON array:
[
  {{
    "title": "concise study title",
    "exposure": "main exposure variable",
    "outcome": "primary outcome",
    "population": "target population",
    "rationale": "why this is important and feasible with this dataset",
    "suggested_design": "cross-sectional / cohort / etc.",
    "suggested_methods": ["logistic_regression", ...]
  }},
  ...
]
Return JSON only."""

        raw = self._llm.generate(prompt, max_tokens=3000, task="topic_generation")
        raw = _clean_llm_response(raw)

        try:
            topics = json.loads(raw)
        except Exception as exc:
            raise ValueError(
                f"주제 생성 결과를 JSON으로 파싱할 수 없습니다: {exc}\n원본:\n{raw}"
            )
        if not isinstance(topics, list):
            raise ValueError(f"JSON 배열이 아닙니다:\n{raw}")

        _log.info("주제 %d개 생성 완료.", len(topics))
        change_log.log(
            title=f"주제 생성: {dataset_name} / {focus[:40]}",
            action_type="topic_generate",
            description=f"{dataset_name} 데이터셋 기반 연구 주제 {len(topics)}개 생성",
            inputs={"dataset_name": dataset_name, "focus": focus, "n_topics": n_topics},
            outputs={"topic_count": len(topics), "titles": [t.get("title", "") for t in topics]},
            impact={"affected_modules": ["research_pipeline"]},
        )

        from src.memory.auto_learn import reflect_and_record
        reflect_and_record(
            action="generate_topics",
            inputs={"dataset": dataset_name, "focus": focus, "n_topics": n_topics},
            outputs={"count": len(topics), "titles": [t.get("title", "") for t in topics[:3]]},
        )

        # 페르소나 자동 진화 — 연구 주제로부터 관점 학습
        try:
            from src.agent.persona import get_persona
            rag_hits = []
            if rag_ctx:
                rag_hits = [{"text": rag_ctx[:500]}]
            for t in topics[:2]:
                get_persona().evolve_from_research(topic=t, rag_hits=rag_hits)
        except Exception:
            pass

        return topics

    # ── Step 4 — 신규성 확인 ─────────────────────────────────────────────────

    def check_novelty(self, topic: Dict) -> Dict:
        """주제 신규성 PubMed 검증."""
        _log.info("신규성 확인: %s", topic.get("title", "")[:60])
        result = self.novelty.check(
            topic=topic.get("title", ""),
            exposure=topic.get("exposure", ""),
            outcome=topic.get("outcome", ""),
            population=topic.get("population", ""),
        )
        change_log.log(
            title=f"신규성 확인: {topic.get('title', '')[:60]}",
            action_type="novelty_check",
            description=f"PubMed 신규성 검증 완료. 점수: {result.get('novelty_score', '?')}/10",
            inputs={"topic_title": topic.get("title", ""), "exposure": topic.get("exposure", "")},
            outputs={"novelty_score": result.get("novelty_score"), "verdict": result.get("verdict", "")[:100]},
            impact={"affected_modules": ["novelty_checker"]},
        )

        from src.memory.auto_learn import reflect_and_record
        reflect_and_record(
            action="check_novelty",
            inputs={"topic": topic.get("title", ""), "exposure": topic.get("exposure", "")},
            outputs={
                "novelty_score": result.get("novelty_score"),
                "recommendation": result.get("recommendation", ""),
                "gap": result.get("gap_identified", "")[:200],
            },
        )

        return result

    # ── Step 5 — 타당성 간이 검증 ────────────────────────────────────────────

    def validate_feasibility(self, topic: Dict, dataset_name: str) -> Dict:
        """데이터셋 변수 기반 연구 타당성 빠른 검증."""
        dataset_ctx = self.datasets.get_context(dataset_name)
        prompt = f"""Evaluate the feasibility of this research topic given the available dataset.

TOPIC: {json.dumps(topic, ensure_ascii=False)}

AVAILABLE DATASET:
{dataset_ctx}

Return JSON:
{{
  "is_feasible": true/false,
  "confidence": "high/medium/low",
  "available_variables": ["list of needed variables that ARE in dataset"],
  "missing_variables": ["list of needed variables NOT in dataset"],
  "sample_size_concern": true/false,
  "confounding_concern": "description of main confounders to adjust",
  "verdict": "one sentence go/no-go recommendation",
  "modifications_needed": ["list of adjustments to make it feasible"]
}}
Return JSON only."""

        raw = self._llm.generate(prompt, task="feasibility")
        raw = _clean_llm_response(raw)

        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw, "is_feasible": None}

    # ── Step 6 — 논문 작성 ───────────────────────────────────────────────────

    def write_paper(
        self,
        topic: Dict,
        study_info: Dict,
        results: Dict,
        use_rag_references: bool = True,
    ) -> str:
        """조유선 스타일로 논문 초안 생성 및 파일 저장."""
        reference_context = None
        if use_rag_references:
            query = (
                f"{topic.get('exposure', '')} "
                f"{topic.get('outcome', '')} "
                f"{topic.get('population', '')}"
            )
            hits = self.rag.ask(query)
            if hits.get("sources"):
                reference_context = "\n\n".join(h["text"] for h in hits["sources"][:5])

        _log.info("논문 작성 시작: %s", topic.get("title", "")[:60])
        draft = self.writer.write_full_paper(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            results=results,
            reference_context=reference_context,
        )

        safe_title = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in topic.get("title", "draft")
        )[:60]
        out_path = self._output_dir / f"{safe_title}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(draft)
        _log.info("논문 저장: %s", out_path)

        try:
            from src.cloud.db import cloud_available, get_engine
            if cloud_available():
                from sqlalchemy import text
                with get_engine().begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO ma_drafts (safe_title, topic_title, content) "
                            "VALUES (:safe_title, :topic_title, :content)"
                        ),
                        {
                            "safe_title": safe_title,
                            "topic_title": topic.get("title", ""),
                            "content": draft,
                        },
                    )
                _log.info("클라우드 저장 완료: ma_drafts/%s", safe_title)
        except Exception as e:
            _log.warning("클라우드 저장 실패 (로컬만 저장됨): %s", e)

        from src.memory.auto_learn import reflect_and_record
        reflect_and_record(
            action="write_paper",
            inputs={
                "topic": topic.get("title", ""),
                "exposure": topic.get("exposure", ""),
                "outcome": topic.get("outcome", ""),
            },
            outputs={
                "word_count": len(draft.split()),
                "output_path": str(out_path),
                "used_rag": use_rag_references,
            },
        )

        change_log.log(
            title=f"논문 작성: {topic.get('title', 'Untitled')[:80]}",
            action_type="paper_write",
            description=f"조유선 스타일 논문 초안 생성 완료. 파일: {out_path}",
            why_better="RAG 참조 컨텍스트 + 저자 프로파일 적용으로 일관된 스타일 유지",
            inputs={
                "topic_title": topic.get("title", ""),
                "exposure": topic.get("exposure", ""),
                "outcome": topic.get("outcome", ""),
                "population": topic.get("population", ""),
                "use_rag_references": use_rag_references,
                "study_info_keys": list(study_info.keys()),
            },
            outputs={
                "draft_word_count": len(draft.split()),
                "output_path": str(out_path),
                "safe_title": safe_title,
            },
            impact={"affected_modules": ["research_pipeline", "paper_writer", "rag"]},
        )

        return draft

    # ── Full automated run ────────────────────────────────────────────────────

    def run(
        self,
        dataset_name: str,
        focus: str,
        study_info_template: Optional[Dict] = None,
        auto_select_topic: bool = True,
    ) -> Dict:
        """데이터셋 + 주제 → 주제 생성 → 신규성 → 타당성 → 자동 실행.

        Returns: {"all_topics": [...], "recommended": {...}}
        """
        _log.info("Research Pipeline 시작: %s / %s", focus, dataset_name)

        topics = self.generate_topics(dataset_name, focus=focus)

        scored = []
        for t in topics:
            novelty = self.check_novelty(t)
            feasibility = self.validate_feasibility(t, dataset_name)
            score = (novelty.get("novelty_score", 0) or 0)
            viable = feasibility.get("is_feasible", False)
            scored.append({
                "topic": t,
                "novelty": novelty,
                "feasibility": feasibility,
                "combined_score": score * (1.5 if viable else 0.5),
            })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        best = scored[0]

        _log.info(
            "최우선 주제: %s (신규성 %s/10)",
            best["topic"]["title"],
            best["novelty"].get("novelty_score", "?"),
        )

        return {"all_topics": scored, "recommended": best}
