"""Backlog queue — 즉시 처리 못하는 작업을 큐에 쌓고, heartbeat가 budget 보면서 처리.

설계 (사용자 요구):
  · 러버블 모드의 무거운 작업(논문 학습, 5만편 PMC 수집, 파일 첨부 vision 분석 등)을
    즉시 동기 처리하지 않고 백로그에 등록 → 별도 worker가 시간 들여 처리
  · API limit/budget 80% 초과 시 PENDING 유지 + retry_after 설정 → 다음날 자동 재개
  · /backlog 페이지에서 PENDING/RUNNING/DONE/FAILED 시각화

기존 인프라 재사용:
  · `src.runtime.tasks.TaskRun` — durable state machine
  · `src.runtime.events`         — append-only audit
  · `src.llm.budget`             — 한도/사용량 체크
  · `src.runtime.heartbeat`      — 정기 drain job 등록

JobKind (확장 가능):
  - "paper_ingest"     : 첨부 PDF/DOCX → 청킹 → ChromaDB
  - "oa_bulk_fetch"    : Europe PMC OA bulk (단일 query → N편)
  - "vision_check"     : 첨부 이미지 → figure_validator
  - "novelty"          : PubMed 신규성 (heavy)
  - "kyrbs_stat"       : StatBridge 회귀 (중간)
  - "rag_reindex"      : ChromaDB 재구축 (heavy)

호출 양식:
    from src.runtime.backlog import enqueue, drain_once, status
    job_id = enqueue("paper_ingest", {"path": "/app/data/uploads/foo.pdf"},
                      owner="me@x.com")
    drain_once(max_jobs=5)          # heartbeat가 매분 호출
    status(owner="me@x.com")        # /backlog 페이지가 호출
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events
from src.runtime.tasks import TaskRun, _conn as _tasks_conn

_log = get_logger(__name__)


# JobKind → 처리 함수 (모듈 lazy import — 순환 의존 회피)
_HANDLERS: Dict[str, Callable[[dict], Any]] = {}

# JobKind 메타: "예상 비용" — drain이 budget 확인 시 사용
JOB_COST: Dict[str, str] = {
    "paper_ingest":  "medium",
    "oa_bulk_fetch": "high",
    "vision_check":  "medium",
    "novelty":       "medium",
    "kyrbs_stat":    "low",
    "rag_reindex":   "high",
}


# ── Public API ──────────────────────────────────────────────────────────────

def register_handler(kind: str, fn: Callable[[dict], Any]) -> None:
    """JobKind에 처리 함수 등록. 새 worker 추가 시 호출."""
    _HANDLERS[kind] = fn
    _log.debug("backlog handler 등록: %s", kind)


def enqueue(kind: str, payload: dict, *, owner: str = "",
             granularity: str = "minute") -> str:
    """백로그에 작업 등록 (TaskRun CREATED 상태). 같은 입력은 idempotency로 중복 방지.
    Returns: task_id"""
    if kind not in JOB_COST:
        _log.warning("미등록 JobKind 등록 시도: %s", kind)
    run = TaskRun.get_or_create(f"backlog.{kind}", owner, payload, granularity=granularity)
    _events.append("backlog_enqueue",
                    {"kind": kind, "owner": owner, "payload_keys": list(payload.keys())},
                    task_id=run.id, actor="backlog")
    return run.id


def drain_once(*, max_jobs: int = 5, owner: Optional[str] = None) -> dict:
    """대기 중 PENDING/CREATED/RETRYING 작업을 max_jobs개까지 처리.
    budget 80% 초과면 high-cost job은 skip (PENDING 유지). heartbeat가 매분 호출."""
    from src.llm.budget import remaining
    rem = remaining("day")
    pct_used = rem.get("pct_used", 0)
    high_budget_ok = pct_used < 80

    c = _tasks_conn()
    rows = c.execute(
        "SELECT id FROM task_runs WHERE status IN ('CREATED','RETRYING','WAITING') "
        "AND task_type LIKE 'backlog.%' ORDER BY created_at ASC LIMIT ?",
        (max_jobs * 3,),
    ).fetchall()

    processed: list = []
    skipped: list = []
    for (tid,) in rows:
        try:
            run = TaskRun.get_by_id(tid)
        except KeyError:
            continue
        kind = run.task_type.replace("backlog.", "", 1)
        if not high_budget_ok and JOB_COST.get(kind) == "high":
            skipped.append({"id": tid, "kind": kind, "reason": "budget_high"})
            continue
        handler = _HANDLERS.get(kind)
        if handler is None:
            skipped.append({"id": tid, "kind": kind, "reason": "no_handler"})
            continue
        if len(processed) >= max_jobs:
            break

        # 실행
        try:
            run._set_status("RUNNING")
            _events.append("backlog_start", {"kind": kind}, task_id=tid, actor="backlog")
            result = handler(run.input or {})
            run.set_output(result if isinstance(result, dict) else {"result": result})
            run._set_status("COMPLETED")
            run.commit_step(name="drain", output=result if isinstance(result, dict) else {"result": str(result)[:500]})
            _events.append("backlog_done", {"kind": kind}, task_id=tid, actor="backlog")
            processed.append({"id": tid, "kind": kind, "status": "COMPLETED"})
        except Exception as e:
            try:
                run._set_status("FAILED", error=str(e)[:500])
                run.commit_step(name="drain", error=str(e)[:500])
                _events.append("backlog_failed", {"kind": kind, "error": str(e)[:200]},
                               task_id=tid, actor="backlog")
            except Exception:
                pass
            processed.append({"id": tid, "kind": kind, "status": "FAILED", "error": str(e)[:200]})

    return {
        "processed": processed, "skipped": skipped,
        "pct_used_today": pct_used, "high_budget_ok": high_budget_ok,
    }


def status(*, owner: Optional[str] = None, limit: int = 50) -> dict:
    """현재 백로그 상태 — /backlog 페이지가 호출."""
    c = _tasks_conn()
    sql = ("SELECT id, task_type, owner_email, status, input_json, output_json, "
            "error, created_at, updated_at FROM task_runs WHERE task_type LIKE 'backlog.%' ")
    params: list = []
    if owner:
        sql += "AND owner_email=? "
        params.append(owner)
    sql += "ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = c.execute(sql, tuple(params)).fetchall()

    counts: dict = {}
    items: list = []
    for r in rows:
        st = r[3]
        counts[st] = counts.get(st, 0) + 1
        items.append({
            "id": r[0],
            "kind": r[1].replace("backlog.", "", 1),
            "owner": r[2],
            "status": st,
            "input": json.loads(r[4]) if r[4] else None,
            "output": json.loads(r[5]) if r[5] else None,
            "error": r[6],
            "created_at": r[7],
            "updated_at": r[8],
        })
    return {"counts": counts, "items": items}


# ── Built-in handlers (모듈 import-time에 등록) ──────────────────────────────

def _h_paper_ingest(payload: dict) -> dict:
    """첨부 PDF/DOCX/TXT → 청킹 → RAG 인덱싱."""
    from pathlib import Path as _P
    from src.ingestion.paper_ingester import PaperIngester
    from src.rag.pipeline import RAGPipeline
    path = payload.get("path") or payload.get("file_path")
    if not path or not _P(path).exists():
        return {"error": "file not found", "path": str(path)}
    p = PaperIngester().ingest(_P(path))
    n_chunks = 0
    try:
        rag = RAGPipeline()
        if hasattr(rag, "ingest_file"):
            n_chunks = rag.ingest_file(str(path)) or 0
    except Exception as e:
        _log.warning("RAG ingest 실패: %s", e)
    return {"file": _P(path).name, "title": getattr(p, "title", ""),
            "sections": list(getattr(p, "sections", {}).keys()) if hasattr(p, "sections") else [],
            "n_chunks": n_chunks}


def _h_oa_bulk_fetch(payload: dict) -> dict:
    """Europe PMC OA Subset bulk fetch — 한 배치 처리."""
    try:
        from src.ingestion.oa_bulk_fetcher import fetch_oa_batch
        q = payload.get("query", "")
        n = int(payload.get("n_target", 100))
        return fetch_oa_batch(q, n_target=n)
    except Exception as e:
        return {"error": str(e)}


def _h_vision_check(payload: dict) -> dict:
    """첨부 이미지 → Claude Vision figure_validator."""
    from src.safety.figure_validator import validate_figure
    img = payload.get("path")
    expected = payload.get("expected")
    rep = validate_figure(img, expected=expected)
    return rep.to_dict()


def _h_novelty(payload: dict) -> dict:
    from src.research.novelty_checker import NoveltyChecker
    return NoveltyChecker().check(payload.get("query", ""),
                                    max_results=int(payload.get("n", 10)),
                                    years=int(payload.get("years", 5)))


def _h_kyrbs_stat(payload: dict) -> dict:
    from pathlib import Path as _P
    from src.data.kyrbs_raw_loader import KYRBSLoader
    from src.data.stat_bridge import StatBridge
    df, _m = KYRBSLoader().load(_P("data/raw/kyrbs2025.sav"))
    return StatBridge().run(df, payload).to_dict()


def _h_rag_reindex(payload: dict) -> dict:
    """RAG 전체 재인덱싱 (heavy). budget high 시 skip 대상."""
    from src.rag.pipeline import RAGPipeline
    rag = RAGPipeline()
    if hasattr(rag, "rebuild"):
        return {"rebuilt": rag.rebuild()}
    return {"error": "RAGPipeline.rebuild() 없음"}


# 등록
register_handler("paper_ingest", _h_paper_ingest)
register_handler("oa_bulk_fetch", _h_oa_bulk_fetch)
register_handler("vision_check", _h_vision_check)
register_handler("novelty", _h_novelty)
register_handler("kyrbs_stat", _h_kyrbs_stat)
register_handler("rag_reindex", _h_rag_reindex)
