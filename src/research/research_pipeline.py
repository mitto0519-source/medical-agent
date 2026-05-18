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

    # ── Step 5b — 실제 통계 분석 ─────────────────────────────────────────────

    def run_stat_analysis(
        self,
        topic: Dict,
        dataset: str = "KYRBS",
        n_synthetic: int = 5000,
        df=None,
    ) -> dict:
        """StatBridge로 실제 통계 분석 수행.

        df: 실제 데이터프레임이 있으면 사용, 없으면 합성 데이터 생성.
        Returns: AnalysisResult.to_dict()
        """
        from src.data.survey_loader import SurveyLoader
        from src.data.stat_bridge import StatBridge

        if df is None:
            loader = SurveyLoader()
            df = loader.generate_synthetic(dataset.upper(), n=n_synthetic)
            _log.info("합성 데이터 %d건 생성 (%s)", n_synthetic, dataset)

        spec = self._build_stat_spec(topic, dataset)
        result = StatBridge().run(df, spec)

        _log.info(
            "통계 분석 완료: n=%d, OR변수=%d개, 유의=%d개",
            result.n_total, len(result.model_vars), len(result.get_significant()),
        )
        change_log.log(
            title=f"통계분석: {topic.get('title', '')[:60]}",
            action_type="stat_analysis",
            description=f"LogisticRegression 완료. 유의 변수 {len(result.get_significant())}개",
            inputs={"topic": topic.get("title", ""), "dataset": dataset, "spec": spec},
            outputs={"n_total": result.n_total, "n_sig": len(result.get_significant())},
            impact={"affected_modules": ["stat_bridge", "research_pipeline"]},
        )
        return result.to_dict()

    def _build_stat_spec(self, topic: Dict, dataset: str) -> dict:
        """주제 dict → StatBridge spec 자동 생성."""
        outcome_map = {
            "depression": {"outcome": "depression", "label": "우울감 경험"},
            "suicidal": {"outcome": "suicidal", "label": "자살 생각"},
            "obesity": {"outcome": "obesity", "label": "비만"},
            "smoking": {"outcome": "smoking", "label": "흡연"},
            "alcohol": {"outcome": "alcohol", "label": "음주"},
            "sleep": {"outcome": "sleep_hours", "label": "수면 시간"},
            "physical": {"outcome": "physical_act", "label": "신체 활동"},
            "diabetes": {"outcome": "diabetes", "label": "당뇨"},
            "hypertension": {"outcome": "hypertension", "label": "고혈압"},
            "metabolic": {"outcome": "metabolic_syn", "label": "대사 증후군"},
        }
        outcome_raw = topic.get("outcome", "depression").lower()
        matched = next(
            (v for k, v in outcome_map.items() if k in outcome_raw),
            {"outcome": "depression", "label": "우울감 경험"},
        )

        if dataset.lower() == "kyrbs":
            predictors = ["sex", "sleep_hours", "screen_time", "smoking"]
            covariates = ["grade", "family_econ", "academic_perf"]
        else:
            predictors = ["sex", "age", "bmi", "smoking", "physical_act"]
            covariates = ["edu", "income"]

        exposure = topic.get("exposure", "").lower()
        exposure_var_map = {
            "sleep": "sleep_hours",
            "screen": "screen_time",
            "smoking": "smoking",
            "alcohol": "alcohol",
            "physical": "physical_act",
            "bmi": "bmi",
            "stress": "stress",
        }
        exposure_var = next((v for k, v in exposure_var_map.items() if k in exposure), None)
        if exposure_var and exposure_var not in predictors:
            predictors = [exposure_var] + [p for p in predictors if p != exposure_var]

        return {
            "outcome": matched["outcome"],
            "outcome_label": matched["label"],
            "predictors": predictors,
            "covariates": covariates,
            "analysis": "logistic",
            "weight_var": "weight_var",
            "subgroups": ["sex"],
        }

    # ── Step 6b — 동료 심사 ──────────────────────────────────────────────────

    def run_peer_review(self, paper_text: str, topic: Dict, stat_result: dict | None = None) -> dict:
        """PeerReviewer로 논문 품질 평가.

        Returns: ReviewResult.to_dict()
        """
        from src.research.peer_reviewer import PeerReviewer
        reviewer = PeerReviewer(llm_client=self._llm)
        dataset = topic.get("dataset", "KYRBS/KNHANES")
        result = reviewer.review(paper_text, topic.get("title", ""), dataset=dataset, stat_result=stat_result)
        _log.info(
            "동료 심사 완료: %d/100 (%s) — %s",
            result.total_score, result.grade, result.accept_recommendation,
        )
        change_log.log(
            title=f"동료심사: {topic.get('title', '')[:60]}",
            action_type="peer_review",
            description=f"논문 품질 평가: {result.total_score}/100 ({result.grade}) — {result.accept_recommendation}",
            inputs={"topic": topic.get("title", "")},
            outputs={"score": result.total_score, "grade": result.grade, "rec": result.accept_recommendation},
            impact={"affected_modules": ["peer_reviewer", "research_pipeline"]},
        )
        return result.to_dict()

    # ── Step 6c — 통계 주입 논문 작성 + DOCX 저장 ────────────────────────────

    def write_paper_with_stats(
        self,
        topic: Dict,
        study_info: Dict,
        stat_result: dict,
        use_rag_references: bool = True,
        export_docx: bool = True,
    ) -> tuple[str, str | None]:
        """StatBridge 결과를 주입해 논문 생성 + DOCX 저장.

        Returns: (paper_text, docx_path_or_None)
        """
        reference_context = None
        if use_rag_references:
            query = f"{topic.get('exposure', '')} {topic.get('outcome', '')} {topic.get('population', '')}"
            hits = self.rag.ask(query)
            if hits.get("sources"):
                reference_context = "\n\n".join(h["text"] for h in hits["sources"][:5])

        _log.info("통계 주입 논문 작성 시작: %s", topic.get("title", "")[:60])
        draft = self.writer.write_full_paper_with_stats(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            stat_result=stat_result,
            reference_context=reference_context,
        )

        safe_title = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in topic.get("title", "draft")
        )[:60]

        txt_path = self._output_dir / f"{safe_title}.txt"
        txt_path.write_text(draft, encoding="utf-8")
        _log.info("논문 저장(txt): %s", txt_path)

        docx_path = None
        if export_docx:
            try:
                out = self.writer.export_docx(draft, self._output_dir / safe_title, title=topic.get("title", ""))
                docx_path = str(out)
                _log.info("DOCX 저장: %s", docx_path)
            except Exception as e:
                _log.warning("DOCX export 실패: %s", e)

        change_log.log(
            title=f"통계주입 논문 작성: {topic.get('title', 'Untitled')[:80]}",
            action_type="paper_write",
            description=f"StatBridge 통계 주입 논문 초안 생성 완료. DOCX: {docx_path is not None}",
            why_better="실제 OR/CI 통계값이 논문 본문에 직접 주입되어 정확도 향상",
            inputs={"topic_title": topic.get("title", ""), "n_total": stat_result.get("n_total", 0)},
            outputs={"draft_word_count": len(draft.split()), "docx_path": docx_path},
            impact={"affected_modules": ["paper_writer", "stat_bridge", "research_pipeline"]},
        )

        return draft, docx_path

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

    def run_full(
        self,
        dataset_name: str,
        focus: str,
        study_info_template: Optional[Dict] = None,
        n_synthetic: int = 5000,
        export_docx: bool = True,
    ) -> Dict:
        """완전 자동화 파이프라인: 주제 → 신규성 → 타당성 → 통계 → 논문 → 동료심사.

        Returns complete pipeline result with draft + review + stat_result.
        """
        _log.info("Full pipeline 시작: %s / %s", focus, dataset_name)

        # Step 1: 주제 선택
        run_result = self.run(dataset_name, focus, study_info_template)
        best = run_result["recommended"]
        topic = best["topic"]

        # Step 2: 통계 분석
        _log.info("[2/4] 통계 분석 중...")
        stat_result = self.run_stat_analysis(topic, dataset=dataset_name.lower(), n_synthetic=n_synthetic)

        # Step 3: 논문 작성 (통계 주입)
        _log.info("[3/4] 논문 작성 중...")
        si = study_info_template or {}
        study_info = {
            "dataset": dataset_name,
            "design": topic.get("suggested_design", "cross-sectional"),
            "population": topic.get("population", ""),
            "exposure": topic.get("exposure", ""),
            "outcome": topic.get("outcome", ""),
            "sample_size": stat_result.get("n_total", n_synthetic),
            "journal": si.get("journal", "J Korean Med Sci"),
            "methods_list": topic.get("suggested_methods", ["logistic_regression"]),
            **si,
        }
        draft, docx_path = self.write_paper_with_stats(
            topic, study_info, stat_result, export_docx=export_docx
        )

        # Step 4: 동료 심사
        _log.info("[4/4] 동료 심사 중...")
        review = self.run_peer_review(draft, topic, stat_result=stat_result)

        _log.info(
            "Full pipeline 완료: score=%d/100 (%s), DOCX=%s",
            review.get("total_score", 0), review.get("grade", "?"), docx_path,
        )

        return {
            "topic": topic,
            "novelty": best["novelty"],
            "feasibility": best["feasibility"],
            "stat_result": stat_result,
            "draft": draft,
            "docx_path": docx_path,
            "review": review,
            "all_topics": run_result["all_topics"],
        }
