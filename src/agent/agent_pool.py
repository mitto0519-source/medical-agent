"""Phase B — 멀티에이전트 병렬 풀 (Google A2A 프로토콜 근접).

Google 대비 격차 해소:
- 단일 순차 파이프라인 → StatAgent/LitAgent/WritingAgent/ReviewAgent 동시 실행
- ThreadPoolExecutor 기반 병렬화
- 각 에이전트는 독립 LLM 클라이언트 + 전용 도구 보유
- 에이전트 간 결과를 collect하여 파이프라인에 통합

Usage:
    pool = AgentPool()
    result = pool.run_paper_pipeline(topic, study_info, stat_result)
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger
from src.llm import get_llm_client

_log = get_logger(__name__)


@dataclass
class AgentTask:
    name: str
    fn: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    name: str
    result: Any = None
    error: Optional[str] = None
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


# ─────────────────────────────────────────────────────────────────────
# 전문화 에이전트
# ─────────────────────────────────────────────────────────────────────

class StatAgent:
    """통계 분석 전담 에이전트."""

    def run(self, df, spec: dict) -> dict:
        from src.data.stat_bridge import StatBridge
        _log.info("[StatAgent] 통계 분석 시작: %s", spec.get("outcome", ""))
        result = StatBridge().run(df, spec)
        _log.info("[StatAgent] 완료: n=%d, 유의변수=%d",
                  result.n_total, len(result.get_significant()))
        return result.to_dict()


class LitAgent:
    """문헌 검색 + RAG 전담 에이전트."""

    def run(self, query: str, top_k: int = 10) -> dict:
        from src.rag.pipeline import RAGPipeline
        from src.ingestion.evidence_reader import EvidenceReader
        _log.info("[LitAgent] 문헌 검색 시작: %s", query[:60])
        rag_hits = RAGPipeline().search(query, top_k=top_k) or []
        try:
            ev = EvidenceReader().search(query, max_results=5)
            pubmed_hits = ev if ev else []
        except Exception as e:
            _log.debug("[LitAgent] EvidenceReader 실패: %s", e)
            pubmed_hits = []
        _log.info("[LitAgent] 완료: RAG %d개, PubMed %d개", len(rag_hits), len(pubmed_hits))
        return {"rag_hits": rag_hits, "pubmed_hits": pubmed_hits}


class WritingAgent:
    """논문 작성 전담 에이전트."""

    def run(self, topic: dict, study_info: dict, stat_result: dict,
            reference_context: str = "") -> str:
        from src.research.paper_writer import PaperWriter
        from src.profile.author_profile import AuthorProfile
        from src.library.methods_library import MethodsLibrary
        from src.library.dataset_library import DatasetLibrary
        from src.rag.pipeline import RAGPipeline
        _log.info("[WritingAgent] 논문 작성 시작: %s", topic.get("title", "")[:50])
        writer = PaperWriter(
            AuthorProfile("Yoosun Cho"), MethodsLibrary(), DatasetLibrary(), RAGPipeline()
        )
        draft = writer.write_full_paper_with_stats(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            stat_result=stat_result,
            reference_context=reference_context or None,
        )
        _log.info("[WritingAgent] 완료: %d자", len(draft))
        return draft


class ReviewAgent:
    """동료 심사 전담 에이전트."""

    def run(self, draft: str, topic: dict) -> dict:
        from src.research.peer_reviewer import PeerReviewer
        _log.info("[ReviewAgent] 동료 심사 시작")
        result = PeerReviewer().review(draft, topic)
        score = getattr(result, "total_score", None) or result.get("total_score", 0)
        _log.info("[ReviewAgent] 완료: 점수 %s/100", score)
        if hasattr(result, "__dict__"):
            return vars(result)
        return result if isinstance(result, dict) else {"total_score": score}


class NoveltyAgent:
    """신규성 확인 전담 에이전트."""

    def run(self, topic: dict) -> dict:
        from src.research.novelty_checker import NoveltyChecker
        _log.info("[NoveltyAgent] 신규성 확인: %s", topic.get("title", "")[:50])
        result = NoveltyChecker().check(
            topic=topic.get("title", ""),
            exposure=topic.get("exposure", ""),
            outcome=topic.get("outcome", ""),
            population=topic.get("population", ""),
        )
        _log.info("[NoveltyAgent] 신규성 점수: %s/10", result.get("novelty_score", "?"))
        return result


# ─────────────────────────────────────────────────────────────────────
# 에이전트 풀 — 병렬 실행 오케스트레이터
# ─────────────────────────────────────────────────────────────────────

class AgentPool:
    """멀티에이전트 병렬 실행 풀.

    각 에이전트를 별도 스레드에서 동시 실행하여 3~5배 속도 향상.
    """

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers

    def run_tasks(self, tasks: List[AgentTask]) -> Dict[str, AgentResult]:
        """태스크 목록을 병렬 실행."""
        results: Dict[str, AgentResult] = {}

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(tasks))) as pool:
            futures: Dict[Future, AgentTask] = {
                pool.submit(self._safe_run, task): task
                for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    agent_result = future.result(timeout=300)
                    results[task.name] = agent_result
                except Exception as e:
                    results[task.name] = AgentResult(name=task.name, error=str(e))
                    _log.error("[AgentPool] %s 실패: %s", task.name, e)

        return results

    @staticmethod
    def _safe_run(task: AgentTask) -> AgentResult:
        t0 = time.time()
        try:
            result = task.fn(*task.args, **task.kwargs)
            return AgentResult(name=task.name, result=result, elapsed=time.time() - t0)
        except Exception as e:
            return AgentResult(name=task.name, error=str(e), elapsed=time.time() - t0)

    # ── 논문 파이프라인 병렬 실행 ────────────────────────────────────────

    def run_paper_pipeline(
        self,
        topic: dict,
        study_info: dict,
        stat_result: dict,
        df=None,
        spec: dict = None,
    ) -> Dict[str, Any]:
        """논문 생성 병렬 파이프라인.

        Phase 1 (병렬): 통계 재분석 + 문헌 검색 + 신규성 확인
        Phase 2 (순차): 논문 작성 (Phase 1 결과 사용)
        Phase 3 (병렬): 동료 심사 + 그림 생성
        """
        _log.info("[AgentPool] 논문 파이프라인 시작: %s", topic.get("title", "")[:50])
        t_total = time.time()

        # ── Phase 1: 병렬 실행 ─────────────────────────────────────────
        phase1_tasks = []

        if df is not None and spec:
            phase1_tasks.append(AgentTask(
                name="stat",
                fn=StatAgent().run,
                args=(df, spec),
            ))

        query = (
            f"{topic.get('exposure', '')} {topic.get('outcome', '')} "
            f"{topic.get('population', '')}"
        )
        phase1_tasks.append(AgentTask(
            name="lit",
            fn=LitAgent().run,
            args=(query,),
        ))
        phase1_tasks.append(AgentTask(
            name="novelty",
            fn=NoveltyAgent().run,
            args=(topic,),
        ))

        phase1_results = self.run_tasks(phase1_tasks)
        _log.info("[AgentPool] Phase 1 완료: %s", {k: v.ok for k, v in phase1_results.items()})

        # 통계 결과 병합
        final_stat = stat_result
        if "stat" in phase1_results and phase1_results["stat"].ok:
            final_stat = phase1_results["stat"].result

        # 참조 컨텍스트 조합
        reference_context = ""
        if "lit" in phase1_results and phase1_results["lit"].ok:
            lit = phase1_results["lit"].result
            rag_texts = [h.get("text", h.get("content", "")) for h in (lit.get("rag_hits") or [])[:5]]
            reference_context = "\n\n".join(t for t in rag_texts if t)

        # ── Phase 2: 논문 작성 (순차) ─────────────────────────────────────
        draft = ""
        try:
            draft = WritingAgent().run(
                topic=topic,
                study_info=study_info,
                stat_result=final_stat,
                reference_context=reference_context,
            )
        except Exception as e:
            _log.error("[AgentPool] WritingAgent 실패: %s", e)

        # ── Phase 3: 병렬 실행 ─────────────────────────────────────────
        phase3_tasks = []
        if draft:
            phase3_tasks.append(AgentTask(
                name="review",
                fn=ReviewAgent().run,
                args=(draft, topic),
            ))
        phase3_tasks.append(AgentTask(
            name="figures",
            fn=self._generate_figures,
            args=(final_stat, topic.get("title", "paper")),
        ))

        phase3_results = self.run_tasks(phase3_tasks) if phase3_tasks else {}
        _log.info("[AgentPool] Phase 3 완료: %s", {k: v.ok for k, v in phase3_results.items()})

        total_elapsed = time.time() - t_total
        _log.info("[AgentPool] 전체 파이프라인 완료: %.1fs", total_elapsed)

        return {
            "draft": draft,
            "stat_result": final_stat,
            "novelty": phase1_results.get("novelty", AgentResult(name="novelty")).result,
            "review": phase3_results.get("review", AgentResult(name="review")).result,
            "figures": phase3_results.get("figures", AgentResult(name="figures")).result or {},
            "elapsed": total_elapsed,
        }

    @staticmethod
    def _generate_figures(stat_result: dict, title: str) -> dict:
        try:
            from src.export.publication_figure_generator import generate_figures_for_paper
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:60]
            return generate_figures_for_paper(stat_result, safe_title=safe_title)
        except Exception as e:
            _log.warning("[AgentPool] Figure generation 실패: %s", e)
            return {}


def get_agent_pool(max_workers: int = 4) -> AgentPool:
    return AgentPool(max_workers=max_workers)
