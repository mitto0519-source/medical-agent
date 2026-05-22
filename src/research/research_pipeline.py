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
import re
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


def _find_real_data(dataset: str):
    """data/raw/ 폴더에서 실제 원시자료를 자동 탐색해 DataFrame 반환.

    파일명에 'kyrbs' 또는 'knhanes'가 포함된 .sav/.csv를 우선 선택.
    없으면 None 반환.
    """
    import pandas as pd
    raw_dir = Path("data/raw")
    if not raw_dir.exists():
        return None
    keyword = dataset.lower()
    candidates = []
    for ext in ("*.sav", "*.csv", "*.xlsx"):
        for f in raw_dir.glob(ext):
            if keyword in f.name.lower():
                candidates.append(f)
    if not candidates:
        # 폴더 내 아무 파일이나
        for ext in ("*.sav", "*.csv", "*.xlsx"):
            candidates.extend(raw_dir.glob(ext))
    if not candidates:
        return None

    chosen = sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    _log.info("실제 원시자료 발견: %s", chosen.name)

    if chosen.suffix.lower() == ".sav":
        from src.data.kyrbs_raw_loader import KYRBSLoader, KNHANESLoader
        loader = KNHANESLoader() if "knhanes" in keyword else KYRBSLoader()
        df, _ = loader.load(chosen)
    else:
        try:
            df = pd.read_csv(chosen, encoding="utf-8-sig", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(chosen, encoding="euc-kr", low_memory=False)
    _log.info("원시자료 로드 완료: %d행 × %d열", len(df), len(df.columns))
    return df


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
        user_email: str = "",
        session_id: str = "",
    ):
        bootstrap()  # .env 단일 로드

        self.user_email = user_email
        self.session_id = session_id

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
            user_email=self.user_email,
            session_id=self.session_id,
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
        except Exception as exc:
            _log.warning("Persona 진화 실패: %s", exc, exc_info=True)

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
            user_email=self.user_email,
            session_id=self.session_id,
        )

        # found_papers를 인스턴스에 누적 (참고문헌 빌더에서 활용)
        found = result.get("found_papers", [])
        if found:
            if not hasattr(self, "_novelty_papers"):
                self._novelty_papers = []
            self._novelty_papers = (self._novelty_papers + found)[-30:]  # 최근 30편만 보관
            _log.info("NoveltyChecker 논문 %d편 참고문헌 풀에 추가 (누적 %d편)", len(found), len(self._novelty_papers))

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
        ref_lib = None
        if use_rag_references:
            query = (
                f"{topic.get('exposure', '')} "
                f"{topic.get('outcome', '')} "
                f"{topic.get('population', '')}"
            )
            reference_context, ref_lib = self._build_reference_context(query)

        _log.info("논문 작성 시작: %s", topic.get("title", "")[:60])
        draft = self.writer.write_full_paper(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            results=results,
            reference_context=reference_context,
            ref_lib=ref_lib,
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
            user_email=self.user_email,
            session_id=self.session_id,
        )

        return draft

    # ── Step 5b — 실제 통계 분석 ─────────────────────────────────────────────

    def run_stat_analysis(
        self,
        topic: Dict,
        dataset: str = "KYRBS",
        df=None,
    ) -> dict:
        """StatBridge로 실제 통계 분석 수행.

        df: 실제 데이터프레임. None이면 data/raw/ 에서 자동 탐색.
        Returns: AnalysisResult.to_dict()
        """
        from src.data.stat_bridge import StatBridge

        if df is None:
            # 실제 원시자료 자동 탐색 (data/raw/ 폴더)
            df = _find_real_data(dataset)
            if df is None:
                raise FileNotFoundError(
                    f"'{dataset}' 원시자료를 찾을 수 없습니다.\n"
                    f"data/raw/ 폴더에 .sav 또는 .csv 파일을 넣거나 "
                    f"Streamlit '원시자료 업로드' 페이지에서 업로드하세요."
                )

        spec = self._build_stat_spec(topic, dataset)
        # G1: ColNameResolver — 실제 컬럼명으로 자동 매핑
        try:
            from src.data.col_name_resolver import resolve_spec_columns
            spec = resolve_spec_columns(df, spec)
        except Exception as _cnr_err:
            _log.warning("ColNameResolver 실패 (원본 spec 사용): %s", _cnr_err)
        result = StatBridge().run(df, spec)

        # P2-3: 민감도 분석 자동화 — E-value + 역전 임계값 자동 추가
        try:
            sens_spec = {**spec, "analysis": "sensitivity"}
            sens_result = StatBridge().run(df, sens_spec)
            if not sens_result.error and sens_result.model_metrics.get("sensitivity"):
                result.model_metrics["sensitivity"] = sens_result.model_metrics["sensitivity"]
                _log.info("P2-3 민감도 분석 자동 완료")
        except Exception as _se:
            _log.debug("P2-3 sensitivity 자동 실행 실패: %s", _se)

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
            user_email=self.user_email,
            session_id=self.session_id,
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

    # ── 참고문헌 컨텍스트 빌더 (RAG + EvidenceReader → ReferenceLibrary) ────────

    def _build_reference_context(self, query: str) -> tuple:
        """RAG + EvidenceReader로 실제 참고문헌 컨텍스트 생성.

        Returns: (context_str, ReferenceLibrary | None)
        context_str: LLM 프롬프트에 주입할 문자열 (Vancouver 인용 목록 + RAG 텍스트)
        """
        from src.export.reference_library import ReferenceLibrary, Reference

        ref_lib = None
        formatted_refs = ""
        rag_text = ""

        # 1. 로컬 RAG 인덱스에서 텍스트 조각 수집
        #    PMC 전문이 인덱싱되어 있으므로 충분히 활용하도록 8개까지 수집
        try:
            hits = self.rag.ask(query)
            rag_sources = hits.get("sources", [])[:8]
            if rag_sources:
                rag_text = "\n\n".join(h["text"] for h in rag_sources)
        except Exception as e:
            _log.warning("RAG 검색 실패: %s", e)

        # 2. EvidenceReader + NoveltyChecker 누적 논문 → ReferenceLibrary
        try:
            papers = [r for r in self.evidence.search(query, max_per_source=6)[:10] if r]
            # NoveltyChecker가 이미 찾은 논문 병합 (중복 제거)
            novelty_papers = getattr(self, "_novelty_papers", [])
            existing_pmids = {p.get("pmid", "") for p in papers if p.get("pmid")}
            for np_paper in novelty_papers:
                if np_paper.get("pmid") and np_paper["pmid"] not in existing_pmids:
                    papers.append(np_paper)
                    existing_pmids.add(np_paper["pmid"])
            papers = papers[:15]  # 최대 15편
            if papers:
                slug = re.sub(r"[^\w]", "_", query[:40])
                ref_lib = ReferenceLibrary(slug)
                for p in papers:
                    authors = p.get("authors") or []
                    if not isinstance(authors, list):
                        authors = [str(authors)]
                    ref = Reference(
                        pmid=str(p.get("pmid", "")),
                        doi=p.get("doi", ""),
                        title=p.get("title", ""),
                        authors=authors,
                        journal=p.get("journal", "") or p.get("source", ""),
                        year=str(p.get("year", "") or ""),
                        abstract=p.get("abstract", "") or "",
                    )
                    ref_lib.add_manual(ref)
                formatted_refs = ref_lib.format_list("Vancouver")
                _log.info("참고문헌 %d개 수집 완료 (RAG+EvidenceReader)", len(papers))
        except Exception as e:
            _log.warning("EvidenceReader 참고문헌 구축 실패: %s", e)

        # 3. 텍스트 컨텍스트 조합
        parts = []
        if formatted_refs:
            parts.append(
                f"CITED REFERENCES — use these Vancouver citations in your text "
                f"(e.g. [1], [2,3]) where appropriate:\n{formatted_refs}"
            )
        if rag_text:
            parts.append(f"ADDITIONAL CONTEXT FROM KNOWLEDGE BASE:\n{rag_text}")

        ctx = "\n\n".join(parts)
        return ctx, ref_lib

    # ── P1-1 — 동료 심사 후 자동 재작성 루프 ────────────────────────────────────

    # rubric dimension → 논문 섹션명 매핑
    _RUBRIC_TO_SECTION = {
        "originality": "INTRODUCTION",
        "methodology": "METHODS",
        "results_clarity": "RESULTS",
        "clinical_relevance": "DISCUSSION",
        "writing_quality": "ABSTRACT",
    }

    def review_and_revise(
        self,
        paper_text: str,
        topic: Dict,
        study_info: Dict,
        stat_result: Optional[dict] = None,
        max_iterations: int = 2,
        score_threshold: int = 70,
    ) -> tuple:
        """동료 심사 → score<threshold면 worst section 자동 재작성 → 재심사.

        Returns: (final_paper_text, final_review_dict)
        최대 max_iterations회 반복 후 중단.
        """
        from src.research.peer_reviewer import PeerReviewer
        reviewer = PeerReviewer(llm_client=self._llm)
        topic_title = topic.get("title", "") if isinstance(topic, dict) else str(topic)

        current_paper = paper_text
        review = reviewer.review(current_paper, topic_title, stat_result=stat_result)
        _log.info(
            "초기 동료 심사: %d/100 (%s)", review.total_score, review.accept_recommendation
        )

        for iteration in range(max_iterations):
            if review.total_score >= score_threshold:
                _log.info("점수 %d ≥ %d — 재작성 루프 종료", review.total_score, score_threshold)
                break

            # 가장 낮은 점수의 rubric 차원 찾기
            worst_dim = min(
                review.section_scores,
                key=lambda k: review.section_scores[k].pct,
                default=None,
            )
            if not worst_dim:
                break

            worst_fb = review.section_scores[worst_dim]
            section_name = self._RUBRIC_TO_SECTION.get(worst_dim, "INTRODUCTION")
            _log.info(
                "재작성 시도 %d: %s (점수 %d/%d, %.0f%%) → 섹션 %s",
                iteration + 1, worst_dim, worst_fb.score, worst_fb.max_score,
                worst_fb.pct, section_name,
            )

            # 해당 섹션 텍스트 추출
            current_paper = self._rewrite_section(
                current_paper, section_name, worst_fb, topic, study_info
            )

            # 재심사
            review = reviewer.review(current_paper, topic_title, stat_result=stat_result)
            _log.info(
                "재심사 %d 결과: %d/100 (%s)",
                iteration + 1, review.total_score, review.accept_recommendation,
            )

        # G4: 방법론 저조 → suggested_analyses 자동 보충 주석
        meth_fb = review.section_scores.get("methodology")
        if meth_fb and meth_fb.pct < 50 and review.suggested_analyses:
            suggested = review.suggested_analyses[:3]
            method_note = (
                "\n\n[METHODOLOGICAL NOTE — Reviewer-Suggested Analyses: "
                + "; ".join(suggested)
                + "]"
            )
            current_paper += method_note
            _log.info("G4: 방법론 보완 제안 %d개 주석 삽입", len(suggested))

        change_log.log(
            title=f"동료심사+재작성: {topic_title[:60]}",
            action_type="peer_review",
            description=f"최종 점수: {review.total_score}/100 ({review.grade})",
            inputs={"topic": topic_title, "max_iter": max_iterations},
            outputs={"final_score": review.total_score, "grade": review.grade},
            impact={"affected_modules": ["peer_reviewer", "research_pipeline"]},
        )
        return current_paper, review.to_dict()

    def _rewrite_section(
        self,
        paper_text: str,
        section_name: str,
        feedback,
        topic: Dict,
        study_info: Dict,
    ) -> str:
        """페이퍼 텍스트에서 section_name 섹션을 피드백 기반으로 재작성 후 대체."""
        sep = "=" * 70
        # 섹션 경계 파싱
        pattern = re.compile(
            rf"({re.escape(sep)}\n{re.escape(section_name)}\n{re.escape(sep)}\n)(.*?)(?={re.escape(sep)}|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        m = pattern.search(paper_text)
        if not m:
            _log.warning("섹션 '%s' 를 텍스트에서 찾을 수 없음 — 재작성 건너뜀", section_name)
            return paper_text

        old_body = m.group(2).strip()
        header = m.group(1)

        weaknesses = "\n".join(f"- {w}" for w in (feedback.weaknesses or []))
        suggestions = "\n".join(f"- {s}" for s in (feedback.suggestions or []))

        prompt = f"""You are revising the {section_name} section of a Korean public health paper.

TOPIC: {topic.get("title", "") if isinstance(topic, dict) else str(topic)}
DATASET: {study_info.get("dataset", "KYRBS")}
STUDY DESIGN: {study_info.get("design", "Cross-sectional")}

CURRENT {section_name} SECTION:
{old_body[:3000]}

REVIEWER WEAKNESSES IDENTIFIED:
{weaknesses or "(none specified)"}

REVIEWER SUGGESTIONS:
{suggestions or "(none specified)"}

Rewrite the {section_name} section addressing all weaknesses and implementing all suggestions.
Keep the same data and statistics. Output ONLY the revised section text, no headers."""

        try:
            new_body = self._llm.generate(
                user_message=prompt,
                max_tokens=2000,
                task="paper_writing",
            ).strip()
        except Exception as e:
            _log.warning("섹션 재작성 LLM 호출 실패: %s", e)
            return paper_text

        # 텍스트에서 해당 섹션 대체
        new_section = f"{header}{new_body}\n\n"
        return paper_text[:m.start()] + new_section + paper_text[m.end():]

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
            user_email=self.user_email,
            session_id=self.session_id,
        )

        # AI 동료심사 약점을 FeedbackStore에 누적 → 다음 논문 작성 프롬프트에 자동 학습
        # (실 리뷰어 피드백과 같은 루프에 합류 — 심사→약점학습→개선 루프 완성)
        try:
            if result.major_concerns or result.suggested_analyses:
                from src.memory.user_feedback_store import FeedbackStore
                fb_lines = []
                if result.major_concerns:
                    fb_lines.append("Major concerns:\n" + "\n".join(f"- {c}" for c in result.major_concerns))
                if result.suggested_analyses:
                    fb_lines.append("Suggested analyses:\n" + "\n".join(f"- {s}" for s in result.suggested_analyses))
                FeedbackStore().add(
                    feedback_text="\n\n".join(fb_lines),
                    journal=topic.get("journal", ""),
                    topic_keywords=f"{topic.get('exposure', '')} {topic.get('outcome', '')} {topic.get('population', '')}".strip(),
                    source="ai_reviewer",
                    paper_title=topic.get("title", ""),
                    decision=result.accept_recommendation,
                )
                _log.info("동료심사 약점 FeedbackStore 누적 — 다음 작성에 학습됨")
        except Exception as _fb_e:
            _log.debug("동료심사 FeedbackStore 누적 실패(비치명): %s", _fb_e)

        return result.to_dict()

    # ── Phase A/B 통합 헬퍼 ──────────────────────────────────────────────────

    def _run_deep_research(self, topic: Dict) -> str:
        """Phase A — AutonomousResearchLoop로 자율 반복 탐색. 근거 컨텍스트 문자열 반환.

        주제(topic)는 변경하지 않고(통계 일관성 유지), 모은 증거만 반환한다.
        """
        try:
            from src.research.autonomous_research_loop import AutonomousResearchLoop
            _refined, evidence_list, dr_novelty = AutonomousResearchLoop(
                max_rounds=3, novelty_threshold=7.0,
            ).run(topic)
            if not evidence_list:
                return ""
            # 중복 제거 (pmid 기준)
            seen, uniq = set(), []
            for p in evidence_list:
                pid = p.get("pmid", "") or p.get("title", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    uniq.append(p)
            ev_lines = [
                f"- [{p.get('year', '')}] {p.get('title', '')}: {p.get('abstract', '')[:200]}"
                for p in uniq[:15]
            ]
            self.last_deep_novelty = dr_novelty  # UI/로깅용
            _log.info("[deep_research] 고유 증거 %d개 수집, novelty=%.1f", len(uniq), dr_novelty)
            return "AUTONOMOUS RESEARCH EVIDENCE (deep iterative PubMed search):\n" + "\n".join(ev_lines)
        except Exception as e:
            _log.warning("[deep_research] 실패(비치명): %s", e)
            return ""

    def _parallel_pre_collect(self, query: str, topic: Dict) -> None:
        """Phase B — AgentPool로 PMC 다운로드(I/O) + 신규성 확인(LLM) 동시 실행.

        PMC 전문은 RAG 인덱싱이 목적(부수효과), 신규성 결과는 _novelty_papers에 누적.
        """
        try:
            from src.agent.agent_pool import AgentPool, AgentTask, NoveltyAgent
            from src.ingestion.pmc_downloader import download_pmc_for_topic

            tasks = [
                AgentTask(name="pmc", fn=download_pmc_for_topic, args=(query, 6)),
                AgentTask(name="novelty", fn=NoveltyAgent().run, args=(topic,)),
            ]
            results = AgentPool(max_workers=2).run_tasks(tasks)

            pmc_res = results.get("pmc")
            if pmc_res and pmc_res.ok:
                _log.info("[parallel] PMC 전문 %s편 준비 (%.1fs)", pmc_res.result, pmc_res.elapsed)

            nov_res = results.get("novelty")
            if nov_res and nov_res.ok and isinstance(nov_res.result, dict):
                found = nov_res.result.get("found_papers", [])
                if found:
                    if not hasattr(self, "_novelty_papers"):
                        self._novelty_papers = []
                    self._novelty_papers = (self._novelty_papers + found)[-30:]
                _log.info("[parallel] 신규성 %.1f/10 (%.1fs)",
                          nov_res.result.get("novelty_score", 0), nov_res.elapsed)
        except Exception as e:
            _log.warning("[parallel] 병렬 사전수집 실패(비치명) — 순차 폴백: %s", e, exc_info=True)
            try:
                from src.ingestion.pmc_downloader import download_pmc_for_topic
                download_pmc_for_topic(query, max_papers=6)
            except Exception as fallback_exc:
                _log.error("[parallel] PMC 자동 다운로드 순차 폴백 실패: %s", fallback_exc, exc_info=True)

    # ── Step 6c — 통계 주입 논문 작성 + DOCX 저장 ────────────────────────────

    def write_paper_with_stats(
        self,
        topic: Dict,
        study_info: Dict,
        stat_result: dict,
        use_rag_references: bool = True,
        export_docx: bool = True,
        journal_id: str = "jkms",
        auto_revise: bool = False,
        revise_threshold: int = 70,
        revise_max_iter: int = 2,
        deep_research: bool = False,
        parallel: bool = False,
    ) -> tuple[str, str | None]:
        """StatBridge 결과를 주입해 논문 생성 + 저널 스타일 DOCX 저장.

        journal_id: 'jkms' | 'kjpm' | 'ijerph' | 'plos_one' | 'bmj_open' | 기타(자동 생성)
        auto_revise: True면 동료 심사 후 score<revise_threshold 섹션 자동 재작성
        deep_research: True면 AutonomousResearchLoop로 자율 반복 탐색 → 근거 보강 (Phase A)
        parallel: True면 PMC 다운로드 + 신규성 확인을 AgentPool로 병렬 실행 (Phase B)
        Returns: (paper_text, docx_path_or_None)
        """
        reference_context = None
        ref_lib = None
        query = (
            f"{topic.get('exposure', '')} "
            f"{topic.get('outcome', '')} "
            f"{topic.get('population', '')}"
        )

        # ── Phase A: 자율 연구 루프 (deep_research=True) ─────────────────────
        # 통계 일관성을 위해 주제(topic)는 유지하고, 자율 탐색으로 모은 근거만 보강
        deep_evidence_context = ""
        if deep_research:
            deep_evidence_context = self._run_deep_research(topic)

        # ── Phase B: 병렬 사전수집 (parallel=True) ───────────────────────────
        # PMC 전문 다운로드(I/O) + 신규성 확인(LLM)을 AgentPool로 동시 실행
        if parallel:
            self._parallel_pre_collect(query, topic)
        else:
            # PMC 오픈액세스 전문 자동 다운로드 + RAG 인덱싱 (순차)
            try:
                from src.ingestion.pmc_downloader import download_pmc_for_topic
                _pmc_count = download_pmc_for_topic(query, max_papers=6)
                _log.info("PMC 전문 %d편 준비 완료", _pmc_count)
            except Exception as _pmc_err:
                _log.debug("PMC 자동 다운로드 실패(비치명): %s", _pmc_err)

        if use_rag_references:
            reference_context, ref_lib = self._build_reference_context(query)
        self.last_ref_lib = ref_lib  # DOCX export에서 접근 가능하도록 보관

        # Phase A 증거를 reference_context에 보강
        if deep_evidence_context:
            reference_context = (
                (reference_context + "\n\n" + deep_evidence_context)
                if reference_context else deep_evidence_context
            )

        # P2-2: 의미론적 기억 검색 — 관련 과거 인사이트 컨텍스트 주입
        try:
            from src.memory.semantic_search import SemanticMemorySearch
            _sms_ctx = SemanticMemorySearch().build_context(query, top_k=3)
            if _sms_ctx:
                reference_context = (
                    (reference_context + "\n\n" + _sms_ctx) if reference_context else _sms_ctx
                )
        except Exception as _sms_err:
            _log.debug("SemanticMemorySearch 실패: %s", _sms_err)

        # 실 리뷰어 피드백 컨텍스트 빌드 (저장된 피드백 있으면 자동 주입)
        feedback_context = None
        try:
            from src.memory.user_feedback_store import get_feedback_context
            _fb_ctx = get_feedback_context(
                query=query,
                journal=study_info.get("journal", ""),
            )
            if _fb_ctx:
                feedback_context = _fb_ctx
                _log.info("리뷰어 피드백 컨텍스트 주입 완료 (%d자)", len(_fb_ctx))
        except Exception as _fb_err:
            _log.debug("FeedbackStore 조회 실패(비치명): %s", _fb_err)

        _log.info("통계 주입 논문 작성 시작: %s", topic.get("title", "")[:60])
        draft = self.writer.write_full_paper_with_stats(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            stat_result=stat_result,
            reference_context=reference_context,
            ref_lib=ref_lib,
            feedback_context=feedback_context,
        )

        # G3: 인라인 인용 [n] 자동 삽입
        if ref_lib is not None:
            try:
                from src.export.reference_library import insert_inline_citations
                draft = insert_inline_citations(draft, ref_lib)
            except Exception as _ic_err:
                _log.debug("인라인 인용 삽입 실패: %s", _ic_err)

        # ── 동료 심사 후 자동 재작성 루프 ──────────────────────────────────
        if auto_revise:
            self.pre_revise_draft = draft    # Before/After 비교 UI용
            draft, _ = self.review_and_revise(
                draft, topic, study_info,
                stat_result=stat_result,
                max_iterations=revise_max_iter,
                score_threshold=revise_threshold,
            )
            self.post_revise_draft = draft   # Before/After 비교 UI용

        # 통계 자기검증: 본문 OR 값이 실제 분석결과와 일치하는지 (환각/누락 탐지)
        self.last_stat_consistency = None
        try:
            from src.diagnostics.stat_consistency import verify_stat_consistency
            self.last_stat_consistency = verify_stat_consistency(draft, stat_result)
            _sc = self.last_stat_consistency
            if _sc["missing"] or _sc["hallucinated"]:
                _log.warning("[통계검증] 일치율 %.0f%% — %s", _sc["score"], _sc["note"])
            else:
                _log.info("[통계검증] 본문 통계값이 실제 분석결과와 일치 (%.0f%%)", _sc["score"])
        except Exception as _sc_e:
            _log.debug("통계 일치 검증 실패(비치명): %s", _sc_e)

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
                from src.export.journal_docx_exporter import JournalDocxExporter
                sections = getattr(self.writer, "last_sections", None) or {}
                exporter = JournalDocxExporter(journal_id)
                docx_out = str(self._output_dir / f"{safe_title}_{journal_id}.docx")
                exporter.export(
                    title=topic.get("title", "Untitled"),
                    sections=sections,
                    references=getattr(self, "last_ref_lib", None),
                    authors=[study_info.get("authors", "Yoosun Cho")],
                    affiliation=study_info.get("affiliation", ""),
                    keywords=topic.get("keywords", []),
                    output_path=docx_out,
                )
                docx_path = docx_out
                _log.info("저널 DOCX 저장 (%s): %s", journal_id, docx_path)
            except Exception as e:
                _log.warning("DOCX export 실패: %s", e)

        # ── STATA do-file 자동 생성 ─────────────────────────────────────────────
        stata_path = None
        try:
            from src.export.stata_exporter import save_stata_do_file
            stata_spec = self._build_stat_spec(topic, study_info.get("dataset", "KYRBS"))
            stata_path = save_stata_do_file(
                topic=topic,
                stat_spec=stata_spec,
                study_info=study_info,
                data_path="",
                output_path=str(self._output_dir / "stata" / f"{safe_title}.do"),
                use_complex_survey="kyrbs" in study_info.get("dataset", "").lower(),
            )
            _log.info("STATA do-file 저장: %s", stata_path)
        except Exception as e:
            _log.warning("STATA do-file 생성 실패: %s", e)

        # ── Table 1 / Table 2 자동 생성 ───────────────────────────────────────
        tables_docx_path = None
        try:
            from src.export.table_builder import (
                stat_result_to_table1_markdown,
                stat_result_to_table2_markdown,
                stat_result_to_tables_docx_bytes,
            )
            tables_dir = Path("data/drafts/tables")
            tables_dir.mkdir(parents=True, exist_ok=True)
            tables_docx_path = str(tables_dir / f"{safe_title}_tables.docx")
            tables_bytes = stat_result_to_tables_docx_bytes(stat_result)
            if tables_bytes:
                with open(tables_docx_path, "wb") as f:
                    f.write(tables_bytes)
                _log.info("Tables DOCX 저장: %s", tables_docx_path)

            # 마크다운 표를 txt 파일 끝에 추가
            t1_md = stat_result_to_table1_markdown(stat_result)
            t2_md = stat_result_to_table2_markdown(stat_result)
            tables_block = f"\n\n{'='*70}\nTABLES\n{'='*70}\n\n{t1_md}\n\n{t2_md}\n"
            draft += tables_block
            txt_path.write_text(draft, encoding="utf-8")
        except Exception as e:
            _log.warning("Table 생성 실패: %s", e)

        # G2: Forest Plot 자동 생성 + PNG 저장
        # G2 + FigureLabs: 전체 논문용 그림/표 자동 생성
        forest_plot_path = None
        self.last_figures: dict = {}
        try:
            from src.export.publication_figure_generator import generate_figures_for_paper
            self.last_figures = generate_figures_for_paper(
                stat_result, safe_title=safe_title,
            )
            if "forest_plot" in self.last_figures:
                forest_plot_path = self.last_figures["forest_plot"]["png_path"]
        except Exception as e:
            _log.warning("Publication figure generator 실패, 기본 forest plot 시도: %s", e)
            try:
                from src.export.figure_builder import stat_result_to_forest_plot
                figures_dir = Path("data/drafts/figures")
                fp_out = str(figures_dir / f"{safe_title}_forest.png")
                fp_bytes = stat_result_to_forest_plot(stat_result, save_path=fp_out)
                if fp_bytes:
                    forest_plot_path = fp_out
            except Exception as e2:
                _log.warning("Forest plot 생성 실패: %s", e2)

        # G5: Cover Letter 자동 생성
        cover_letter_path = None
        try:
            from src.export.cover_letter_writer import CoverLetterWriter
            _cl_writer = CoverLetterWriter(llm_client=self._llm)
            try:
                from src.export.journal_registry import get_registry as _jreg_fn
                _jinfo = _jreg_fn().get(journal_id)
                _journal_name = _jinfo.get("name", journal_id) if isinstance(_jinfo, dict) else journal_id
            except Exception:
                _journal_name = journal_id
            _cl_text = _cl_writer.generate(
                topic=topic, study_info=study_info, journal_name=_journal_name,
            )
            cover_letter_path = _cl_writer.save(_cl_text, safe_title)
            _log.info("Cover letter 저장: %s", cover_letter_path)
        except Exception as e:
            _log.warning("Cover letter 생성 실패: %s", e)

        # Phase C: 역량 자기평가 벤치마크 (비동기 — 파이프라인 블로킹 없음)
        try:
            from src.diagnostics.capability_bench import run_capability_bench
            _novelty_score = getattr(self, "_last_novelty_score", 0.0)
            _bench = run_capability_bench(
                draft=draft,
                stat_result=stat_result,
                topic=topic,
                figures=self.last_figures,
                novelty_score=_novelty_score,
            )
            _log.info("[CapabilityBench] 종합 점수: %.1f/100, 약점: %s",
                      _bench.overall, _bench.weak_areas)
        except Exception as _bench_e:
            _log.debug("역량 벤치마크 실패: %s", _bench_e)

        change_log.log(
            title=f"통계주입 논문 작성: {topic.get('title', 'Untitled')[:80]}",
            action_type="paper_write",
            description=f"StatBridge 통계 주입 논문 초안 생성 완료. DOCX: {docx_path is not None}, Tables: {tables_docx_path is not None}",
            why_better="실제 OR/CI 통계값이 논문 본문에 직접 주입되어 정확도 향상",
            inputs={"topic_title": topic.get("title", ""), "n_total": stat_result.get("n_total", 0)},
            outputs={"draft_word_count": len(draft.split()), "docx_path": docx_path, "tables_docx_path": tables_docx_path},
            impact={"affected_modules": ["paper_writer", "stat_bridge", "research_pipeline", "table_builder"]},
            user_email=self.user_email,
            session_id=self.session_id,
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
        df=None,
        export_docx: bool = True,
        journal_id: str = "jkms",
        deep_research: bool = False,
        parallel: bool = False,
        auto_revise: bool = False,
    ) -> Dict:
        """완전 자동화 파이프라인: 주제 → 신규성 → 타당성 → 통계 → 논문 → 동료심사.

        df: 실제 원시자료 DataFrame (없으면 data/raw/ 자동 탐색).
        deep_research: Phase A 자율 연구 루프 활성화
        parallel: Phase B 병렬 사전수집 활성화
        auto_revise: 동료 심사 후 약점 섹션 자동 재작성
        Returns complete pipeline result with draft + review + stat_result.
        """
        _log.info("Full pipeline 시작: %s / %s", focus, dataset_name)

        # Step 1: 주제 선택
        run_result = self.run(dataset_name, focus, study_info_template)
        best = run_result["recommended"]
        topic = best["topic"]

        # Step 2: 통계 분석 (실제 원시자료 사용)
        _log.info("[2/4] 통계 분석 중 (실제 원시자료)...")
        stat_result = self.run_stat_analysis(topic, dataset=dataset_name.lower(), df=df)

        # Step 3: 논문 작성 (통계 주입)
        _log.info("[3/4] 논문 작성 중...")
        si = study_info_template or {}
        study_info = {
            "dataset": dataset_name,
            "design": topic.get("suggested_design", "cross-sectional"),
            "population": topic.get("population", ""),
            "exposure": topic.get("exposure", ""),
            "outcome": topic.get("outcome", ""),
            "sample_size": stat_result.get("n_total", 0),
            "journal": si.get("journal", "J Korean Med Sci"),
            "methods_list": topic.get("suggested_methods", ["logistic_regression"]),
            **si,
        }
        draft, docx_path = self.write_paper_with_stats(
            topic, study_info, stat_result, export_docx=export_docx, journal_id=journal_id,
            deep_research=deep_research, parallel=parallel, auto_revise=auto_revise,
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
