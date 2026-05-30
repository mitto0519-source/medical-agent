"""Parallel sub-agent — 의학 논문 4섹션을 ThreadPoolExecutor로 동시 작성.

배경 (2026-05-30):
    paper_writer는 Introduction → Methods → Results → Discussion → Abstract 순차 양식이라
    5섹션 양식 100초가 소요됨. Discussion만 Results의 결과를 일부 참조하는 약한 의존성이고,
    Introduction/Methods는 study_info만으로 독립 가능. ThreadPoolExecutor로 4섹션 동시 작성
    → 약 30~40초로 단축.

흐름:
    1) Introduction + Methods + Results + Discussion 4개 동시 worker
    2) Abstract는 4섹션 텍스트를 input으로 단일 worker (합성)

API:
    write_sections_parallel(topic, study_info, results_dict,
                            *, author="Yoosun Cho", n_workers=4, paper_writer=None)
        → {"Introduction": ..., "Methods": ..., "Results": ..., "Discussion": ..., "Abstract": ...}

호출:
    _orchestrated_paper_run에서 옵션 (`parallel=True`)으로 활성화.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)


def _make_paper_writer(author_name: str = "Yoosun Cho"):
    """PaperWriter + 보조 라이브러리 한 묶음."""
    from src.research.paper_writer import PaperWriter
    from src.profile.author_profile import AuthorProfile
    try:
        from src.library.methods_library import MethodsLibrary
        ml = MethodsLibrary()
    except Exception:
        ml = None
    try:
        from src.library.dataset_library import DatasetLibrary
        dl = DatasetLibrary("data/libraries")
    except Exception:
        dl = None
    return PaperWriter(
        author_profile=AuthorProfile(author_name),
        methods_library=ml, dataset_library=dl,
    )


def write_sections_parallel(
    topic: str,
    study_info: Dict[str, Any],
    results_dict: Dict[str, Any],
    *,
    author: str = "Yoosun Cho",
    n_workers: int = 4,
    paper_writer: Optional[Any] = None,
    reference_context: Optional[str] = None,
) -> Dict[str, str]:
    """4섹션 동시 작성 → Abstract 합성. 단일 PaperWriter 인스턴스를 thread-safe하게 공유.

    Returns:
        {"Abstract", "Introduction", "Methods", "Results", "Discussion"} 5섹션 dict.
        섹션별 실패 시 placeholder 텍스트와 함께 반환 (전체 흐름 중단 안 함).
    """
    t0 = time.time()
    pw = paper_writer or _make_paper_writer(author)

    # 4섹션 task 정의 — PaperWriter는 write_introduction/methods/results/discussion API 보유
    def _intro():
        return pw.write_introduction(
            topic=topic, study_info=study_info,
            reference_context=reference_context)

    def _methods():
        return pw.write_methods(topic=topic, study_info=study_info)

    def _results():
        return pw.write_results(
            topic=topic, study_info=study_info, results=results_dict,
            methods_summary="")

    def _discussion():
        return pw.write_discussion(
            topic=topic, study_info=study_info, results=results_dict,
            reference_context=reference_context)

    tasks = {
        "Introduction": _intro,
        "Methods":      _methods,
        "Results":      _results,
        "Discussion":   _discussion,
    }

    sections: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="sect") as ex:
        futures = {ex.submit(fn): name for name, fn in tasks.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                sections[name] = fut.result()
                _log.info("[parallel] %s 완료 (+%.1fs)", name, time.time() - t0)
            except Exception as e:
                sections[name] = f"[{name} 작성 실패: {type(e).__name__}: {str(e)[:200]}]"
                _log.warning("[parallel] %s 실패: %s", name, e)

    # Abstract는 4섹션 다 끝난 후 단일 worker로
    try:
        abstract = pw.write_abstract(
            topic=topic,
            background=str(sections.get("Introduction", ""))[-1500:],
            objective=topic[:200],
            methods_summary=str(sections.get("Methods", ""))[:1500],
            results_summary=str(sections.get("Results", ""))[:1500],
        )
        sections["Abstract"] = abstract
    except Exception as e:
        sections["Abstract"] = f"[Abstract 합성 실패: {type(e).__name__}: {str(e)[:200]}]"

    elapsed = time.time() - t0
    try:
        _events.append("parallel_sections_done",
                        {"elapsed_sec": round(elapsed, 1),
                         "n_workers": n_workers,
                         "sections": list(sections.keys()),
                         "chars": {k: len(str(v)) for k, v in sections.items()}},
                        actor="parallel_sections")
    except Exception:
        pass

    _log.info("[parallel] 5섹션 완성 — %.1fs (%d workers)", elapsed, n_workers)
    return sections


__all__ = ["write_sections_parallel"]
