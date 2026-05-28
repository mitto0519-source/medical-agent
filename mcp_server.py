"""Medical-Agent MCP Server

외부 에이전트 (Claude Desktop, 다른 AI 에이전트 등) 에서 접근 가능한 MCP 서버.

인증: Bearer API 키 (email 기반)
슈퍼 어드민: mitto0519@gmail.com / misslonghorn46@gmail.com

실행:
    python mcp_server.py              # 기본 포트 8765
    python mcp_server.py --port 9000  # 포트 지정

Claude Desktop 연결 (~/.config/claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "medical-agent": {
          "url": "http://localhost:8765/mcp",
          "headers": { "Authorization": "Bearer ma-YOUR_API_KEY" }
        }
      }
    }
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root on path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Windows CP949 → UTF-8 강제 (한글 로그 깨짐 방지)
os.environ['PYTHONIOENCODING'] = 'utf-8'
for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, 'buffer'):
        try:
            if _s is sys.stdout:
                sys.stdout = io.TextIOWrapper(_s.buffer, encoding='utf-8', errors='replace', line_buffering=True)
            else:
                sys.stderr = io.TextIOWrapper(_s.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        except Exception:
            pass

from src.config.env import bootstrap
bootstrap()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import fastmcp
from fastmcp.server.auth import TokenVerifier, AccessToken

from src.auth.users import get_user_by_key, is_super_admin


# ════════════════════════════════════════════════════════════════════════
# Auth — API 키 → email 검증
# ════════════════════════════════════════════════════════════════════════

class EmailKeyVerifier(TokenVerifier):
    """Bearer API 키를 검증하고 email/role을 AccessToken에 담아 반환."""

    async def verify_token(self, token: str) -> AccessToken | None:
        user = get_user_by_key(token)
        if not user:
            return None
        scopes = ["read", "write"]
        if user.get("role") == "super_admin":
            scopes += ["admin", "sync"]
        return AccessToken(
            token=token,
            client_id=user["email"],
            scopes=scopes,
            claims={
                "email": user["email"],
                "name": user.get("name", ""),
                "role": user.get("role", "viewer"),
            },
        )


# ════════════════════════════════════════════════════════════════════════
# Server
# ════════════════════════════════════════════════════════════════════════

mcp = fastmcp.FastMCP(
    name="Medical-Agent",
    instructions=(
        "의학 연구 논문 파이프라인 MCP 서버. "
        "PubMed 검색, NotebookLM 동기화, 신규성 확인, 연구 주제 생성, 논문 초안 작성을 지원합니다. "
        "모든 요청은 Bearer API 키 인증이 필요합니다."
    ),
    auth=EmailKeyVerifier(),
)

# ── Railway / Uptime health check — 인증 불필요 ──────────────────────────────

import time as _time
_START_TIME = _time.time()

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    from src.cloud.db import cloud_available
    uptime = int(_time.time() - _START_TIME)
    return JSONResponse({
        "status": "ok",
        "service": "medical-agent-mcp",
        "uptime_seconds": uptime,
        "cloud": cloud_available(),
    })

@mcp.custom_route("/", methods=["GET"])
async def root(request):
    from starlette.responses import JSONResponse
    return JSONResponse({
        "service": "Medical-Agent MCP Server",
        "mcp_endpoint": "/mcp",
        "health_endpoint": "/health",
    })


def _caller_email(ctx) -> str:
    """현재 요청 사용자 이메일 반환."""
    try:
        return ctx.auth.claims.get("email", "unknown") if ctx and ctx.auth else "unknown"
    except Exception:
        return "unknown"


def _log_tool(ctx, tool_name: str, inputs: dict, result_summary: str = "") -> None:
    """MCP tool 호출을 change_log에 기록."""
    try:
        from src.memory import change_log
        change_log.log(
            title=f"[MCP] {tool_name}",
            description=result_summary[:200],
            action_type="mcp_tool",
            user_email=_caller_email(ctx),
            inputs=inputs,
            outputs={"summary": result_summary[:200]},
        )
    except Exception:
        pass


def _require_admin(ctx):
    email = _caller_email(ctx)
    if not is_super_admin(email):
        raise PermissionError(f"'{email}' does not have admin privileges.")


# ════════════════════════════════════════════════════════════════════════
# Tools — 공개 (read + write)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool
def get_status(ctx=None) -> dict:
    """스토리지 상태 및 현재 사용자 정보 반환."""
    from src.storage.manager import StorageManager
    sm = StorageManager()
    stat = sm.status()
    stat["caller"] = _caller_email(ctx)
    return stat


@mcp.tool
def search_papers(
    query: str,
    topic: str,
    max_results: int = 10,
    sync_to_notebooklm: bool = True,
    ctx=None,
) -> dict:
    """PubMed에서 논문을 검색하고 NotebookLM + ChromaDB에 동기화.

    Args:
        query: PubMed 검색어 (예: "adolescent obesity sleep Korea")
        topic: 연구 주제 레이블 (노트북 이름으로 사용)
        max_results: 최대 논문 수 (3~20)
        sync_to_notebooklm: NotebookLM에 동기화 여부
    """
    from src.research.novelty_checker import NoveltyChecker
    from src.storage.manager import StorageManager

    checker = NoveltyChecker()
    papers = checker.search_papers(query, max_results=max_results)

    if not papers:
        return {"status": "no_results", "count": 0, "papers": []}

    sm = StorageManager()
    if sync_to_notebooklm:
        result = sm.store_papers(papers, topic=topic)
    else:
        result = {"nlm": 0, "local": len(papers)}

    out = {
        "status": "ok",
        "count": len(papers),
        "stored": result,
        "papers": [
            {
                "title": p.get("title", ""),
                "year": p.get("year", ""),
                "pmid": p.get("pmid", ""),
                "authors": p.get("authors", [])[:3],
            }
            for p in papers
        ],
    }
    _log_tool(ctx, "search_papers", {"query": query, "topic": topic},
              f"PubMed '{query}' → {len(papers)}편 수집")
    return out


@mcp.tool
def query_topic(
    topic: str,
    question: str,
    ctx=None,
) -> dict:
    """저장된 논문을 기반으로 연구 주제 질문에 답변.
    NotebookLM 우선, 오프라인 시 ChromaDB 폴백.

    Args:
        topic: 쿼리할 연구 주제
        question: 자유 형식 질문
    """
    from src.storage.manager import StorageManager
    sm = StorageManager()
    return sm.search(question, topic=topic)


@mcp.tool
def analyze_topic(topic: str, ctx=None) -> dict:
    """NotebookLM으로 연구 주제 전방위 분석.
    연구 공백 / 방법론 / 노출·결과변수 / 신규 각도 / 핵심 발견을 반환.

    Args:
        topic: 분석할 연구 주제 (이미 논문이 동기화되어 있어야 함)
    """
    from src.storage.manager import StorageManager
    sm = StorageManager()
    return sm.analyze_topic(topic)


@mcp.tool
def check_novelty(
    topic_title: str,
    exposure: str,
    outcome: str,
    population: str = "",
    ctx=None,
) -> dict:
    """PubMed 기반 연구 주제 신규성 검증. 결과를 Supabase에 저장해 다른 사용자와 공유.

    Args:
        topic_title: 연구 제목
        exposure: 주요 노출변수 (예: "smartphone use")
        outcome: 주요 결과변수 (예: "sleep quality")
        population: 대상 집단 (예: "Korean adolescents")
    """
    from src.research.novelty_checker import NoveltyChecker
    checker = NoveltyChecker()
    result = checker.check(
        topic=topic_title,
        exposure=exposure,
        outcome=outcome,
        population=population,
    )

    caller = _caller_email(ctx)
    _save_novelty_cloud(caller, topic_title, exposure, outcome, population, result)
    _log_tool(ctx, "check_novelty",
              {"topic_title": topic_title, "exposure": exposure, "outcome": outcome},
              f"신규성 점수 {result.get('novelty_score', '?')}/10: {topic_title}")
    return result


def _save_novelty_cloud(
    user_email: str, topic_title: str, exposure: str,
    outcome: str, population: str, result: dict,
) -> None:
    from datetime import datetime
    import json as _json
    entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text
            with get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_novelty_results
                        (id, user_email, topic_title, exposure, outcome, population, result)
                    VALUES
                        (:id, :user_email, :topic_title, :exposure, :outcome, :population,
                         CAST(:result AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": entry_id,
                    "user_email": user_email,
                    "topic_title": topic_title,
                    "exposure": exposure,
                    "outcome": outcome,
                    "population": population,
                    "result": _json.dumps(result, ensure_ascii=False),
                })
    except Exception as e:
        _log.warning("ma_novelty_results 저장 실패: %s", e)


@mcp.tool
def generate_research_topics(
    dataset: str = "KYRBS",
    focus: str = "",
    n_topics: int = 5,
    ctx=None,
) -> dict:
    """데이터셋 + RAG 기반 연구 주제 생성. 결과를 Supabase에 저장해 다른 사용자와 공유.

    Args:
        dataset: 사용 데이터셋 (기본: KYRBS)
        focus: 연구 포커스 키워드
        n_topics: 생성할 주제 수
    """
    from src.research.research_pipeline import ResearchPipeline
    rp = ResearchPipeline()
    topics = rp.generate_topics(dataset_name=dataset, focus=focus, n_topics=n_topics)

    caller = _caller_email(ctx)
    entry_id = _save_topics_cloud(caller, dataset, focus, topics)
    _log_tool(ctx, "generate_research_topics",
              {"dataset": dataset, "focus": focus, "n_topics": n_topics},
              f"{dataset}/{focus} → {len(topics)}개 주제 생성")
    return {"topics": topics, "count": len(topics), "saved_id": entry_id}


def _save_topics_cloud(user_email: str, dataset: str, focus: str, topics: list) -> str:
    """생성된 주제를 ma_topics에 저장. 저장된 id 반환."""
    from datetime import datetime
    import json as _json
    entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text
            with get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_topics (id, user_email, dataset, focus, n_topics, topics)
                    VALUES (:id, :user_email, :dataset, :focus, :n_topics, CAST(:topics AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": entry_id,
                    "user_email": user_email,
                    "dataset": dataset,
                    "focus": focus,
                    "n_topics": len(topics),
                    "topics": _json.dumps(topics, ensure_ascii=False),
                })
    except Exception as e:
        _log.warning("ma_topics 저장 실패: %s", e)
    return entry_id


@mcp.tool
def list_topic_notebooks(ctx=None) -> dict:
    """관리 중인 연구 주제 - NotebookLM 노트북 목록 반환."""
    from src.storage.manager import StorageManager
    sm = StorageManager()
    return {"notebooks": sm.get_topic_notebooks()}


@mcp.tool
def sync_local_pdfs(
    pdf_dir: str,
    topic: str,
    ctx=None,
) -> dict:
    """로컬 PDF 폴더를 NotebookLM + ChromaDB에 동기화.

    Args:
        pdf_dir: PDF 파일이 있는 폴더 경로
        topic: 연구 주제 레이블
    """
    from src.storage.manager import StorageManager
    sm = StorageManager()
    return sm.sync_pdf_dir(pdf_dir, topic)


# ════════════════════════════════════════════════════════════════════════
# Tools — 공유 데이터 조회 (모든 사용자)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool
def get_topics(
    dataset: str = "",
    limit: int = 20,
    ctx=None,
) -> dict:
    """저장된 연구 주제 목록 조회 (Supabase 공유 DB).

    Args:
        dataset: 데이터셋 필터 (빈 문자열이면 전체)
        limit: 최대 반환 수
    """
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text
            conditions, params = [], {"lim": limit}
            if dataset:
                conditions.append("dataset = :dataset")
                params["dataset"] = dataset
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text(f"SELECT id, timestamp, user_email, dataset, focus, n_topics, topics FROM ma_topics {where} ORDER BY timestamp DESC LIMIT :lim"),
                    params,
                ).mappings().all()
            return {"source": "supabase", "count": len(rows), "results": [dict(r) for r in rows]}
    except Exception as e:
        _log.warning("get_topics cloud failed: %s", e)
    return {"source": "local_unavailable", "count": 0, "results": []}


@mcp.tool
def get_novelty_results(
    limit: int = 20,
    ctx=None,
) -> dict:
    """저장된 신규성 검증 결과 목록 조회 (Supabase 공유 DB).

    Args:
        limit: 최대 반환 수
    """
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT id, timestamp, user_email, topic_title, exposure, outcome, population, result FROM ma_novelty_results ORDER BY timestamp DESC LIMIT :lim"),
                    {"lim": limit},
                ).mappings().all()
            return {"source": "supabase", "count": len(rows), "results": [dict(r) for r in rows]}
    except Exception as e:
        _log.warning("get_novelty_results cloud failed: %s", e)
    return {"source": "local_unavailable", "count": 0, "results": []}


@mcp.tool
def get_drafts(
    limit: int = 10,
    ctx=None,
) -> dict:
    """저장된 논문 초안 목록 조회 (Supabase 공유 DB).

    Args:
        limit: 최대 반환 수
    """
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT id, safe_title, topic_title, author_email, created_at, LEFT(content, 500) AS preview FROM ma_drafts ORDER BY created_at DESC LIMIT :lim"),
                    {"lim": limit},
                ).mappings().all()
            return {"source": "supabase", "count": len(rows), "drafts": [dict(r) for r in rows]}
    except Exception as e:
        _log.warning("get_drafts cloud failed: %s", e)
    return {"source": "local_unavailable", "count": 0, "drafts": []}


@mcp.tool
def get_change_log(
    action_type: str = "",
    user_email: str = "",
    limit: int = 30,
    ctx=None,
) -> dict:
    """전체 작업 이력 조회 (Supabase 공유 DB — 모든 사용자의 작업 포함).

    Args:
        action_type: 필터 (topic_generate / novelty_check / paper_write / mcp_tool / general 등)
        user_email: 특정 사용자 필터
        limit: 최대 반환 수
    """
    from src.memory.change_log import get_recent
    entries = get_recent(n=limit, user_email=user_email or None, action_type=action_type or None)
    return {
        "source": "supabase" if _cloud_ok() else "local",
        "count": len(entries),
        "entries": entries,
    }


@mcp.tool
def get_insights(
    category: str = "",
    limit: int = 50,
    ctx=None,
) -> dict:
    """에이전트 자체 학습 인사이트 조회 (Supabase 공유 DB).

    Args:
        category: pattern / mistake / optimization / next_action / decision / reference
        limit: 최대 반환 수
    """
    from src.memory.agent_insight import get_all
    entries = get_all(category=category or None, n=limit)
    return {
        "source": "supabase" if _cloud_ok() else "local",
        "count": len(entries),
        "insights": entries,
    }


def _cloud_ok() -> bool:
    try:
        from src.cloud.db import cloud_available
        return cloud_available()
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════════
# Tools — 슈퍼 어드민 전용
# ════════════════════════════════════════════════════════════════════════

@mcp.tool
def list_users(ctx=None) -> dict:
    """[슈퍼 어드민] 전체 사용자 목록 조회."""
    _require_admin(ctx)
    from src.auth.users import list_users as _list
    users = _list()
    # API 키는 마스킹
    for u in users:
        key = u.get("api_key", "")
        u["api_key"] = key[:6] + "****" + key[-4:] if len(key) > 10 else "****"
    return {"users": users, "count": len(users)}


@mcp.tool
def add_user(
    email: str,
    name: str = "",
    role: str = "viewer",
    ctx=None,
) -> dict:
    """[슈퍼 어드민] 신규 사용자 추가. API 키 자동 발급.

    Args:
        email: 사용자 이메일
        name: 표시 이름
        role: 역할 (viewer / admin / super_admin)
    """
    _require_admin(ctx)
    from src.auth.users import add_user as _add
    user = _add(email=email, name=name, role=role)
    return {
        "status": "created",
        "email": user["email"],
        "role": user["role"],
        "api_key": user["api_key"],
    }


@mcp.tool
def remove_user(email: str, ctx=None) -> dict:
    """[슈퍼 어드민] 사용자 비활성화 (슈퍼 어드민 이메일은 삭제 불가).

    Args:
        email: 비활성화할 사용자 이메일
    """
    _require_admin(ctx)
    from src.auth.users import remove_user as _remove
    ok = _remove(email)
    return {"status": "deactivated" if ok else "not_found", "email": email}


@mcp.tool
def rotate_api_key(email: str, ctx=None) -> dict:
    """[슈퍼 어드민] 사용자 API 키 재발급.

    Args:
        email: 키를 재발급할 사용자 이메일
    """
    _require_admin(ctx)
    from src.auth.users import rotate_key
    new_key = rotate_key(email)
    return {"status": "rotated", "email": email, "new_api_key": new_key}


@mcp.tool
def sync_between_admins(ctx=None) -> dict:
    """[슈퍼 어드민] 두 슈퍼 어드민 간 데이터 동기화 상태 확인.
    두 계정은 동일한 NotebookLM 계정과 ChromaDB를 공유합니다.
    """
    _require_admin(ctx)
    from src.storage.manager import StorageManager
    sm = StorageManager()
    stat = sm.status()
    notebooks = sm.get_topic_notebooks()
    return {
        "storage": stat,
        "shared_notebooks": notebooks,
        "sync_note": (
            "두 슈퍼 어드민은 동일한 NotebookLM 계정(Google)과 ChromaDB를 공유합니다. "
            "NotebookLM online 시 실시간 공유, offline 시 로컬 ChromaDB 기준으로 동기화됩니다."
        ),
    }


# ════════════════════════════════════════════════════════════════════════
# Tools — 지식 베이스 자가발전 (trend_learn)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool
def get_knowledge_graph_stats(ctx=None) -> dict:
    """지식 그래프 + 주기적 학습 상태 조회.

    반환: 그래프 노드/엣지 수, 마지막 실행 시간, 누적 수집 논문 수.
    """
    from src.knowledge.medical_graph import get_graph
    from src.knowledge.trend_learner import get_last_run_info
    graph_stats = get_graph().stats()
    run_info = get_last_run_info()
    return {
        "graph": graph_stats,
        "periodic_learn": run_info,
    }


@mcp.tool
def trigger_self_audit(quick: bool = False, ctx=None) -> dict:
    """[슈퍼 어드민] 자가 진단 + 자동 개선 즉시 실행.

    Args:
        quick: True이면 LLM 아키텍처 평가 제외 (빠른 진단, ~30초)
    """
    _require_admin(ctx)
    from src.diagnostics.self_auditor import SelfAuditor
    from src.diagnostics.improvement_engine import ImprovementEngine

    result = SelfAuditor().run_full_audit(with_llm_eval=not quick)
    improvements = ImprovementEngine().run(result.to_dict())

    _log_tool(ctx, "trigger_self_audit", {"quick": quick},
              f"score={result.overall_score}, gaps={len(result.llm_gaps)}, auto={len(improvements.get('auto_applied', []))}")

    return {
        "overall_score": result.overall_score,
        "duration_sec": result.duration_sec,
        "code_issues_count": len(result.code_issues),
        "rag_health": result.rag_health.get("status"),
        "llm_health": result.llm_health.get("status"),
        "gaps_found": len(result.llm_gaps),
        "auto_applied": improvements.get("auto_applied", []),
        "queued_count": improvements.get("queued_count", 0),
    }


@mcp.tool
def get_self_audit_report(ctx=None) -> dict:
    """마지막 자가 진단 결과 + 승인 대기 항목 조회."""
    from src.diagnostics.self_auditor import get_last_audit, get_audit_history
    from src.diagnostics.improvement_engine import get_approval_queue

    last = get_last_audit()
    history = get_audit_history(5)
    scores = [h["overall_score"] for h in history]
    pending = get_approval_queue()

    return {
        "last_audit": last,
        "score_history": scores,
        "pending_approvals": pending,
        "trend": "improving" if len(scores) > 1 and scores[0] > scores[-1] else
                 "degrading" if len(scores) > 1 and scores[0] < scores[-1] else "stable",
    }


@mcp.tool
def trigger_periodic_learn(days: int = 60, ctx=None) -> dict:
    """[슈퍼 어드민] 주기적 학습 즉시 실행.

    PubMed에서 최근 N일 논문 수집 → 그래프/RAG 갱신 → 자가학습 기록.
    Args:
        days: 수집할 최근 일수 (기본 60)
    """
    _require_admin(ctx)
    from src.knowledge.trend_learner import run_trend_learn
    summary = run_trend_learn(days=days, max_per_query=30)
    return {"status": "completed", "summary": summary}


# ── 24시간 주기 백그라운드 학습 루프 ──────────────────────────────────────────

import threading as _threading

_LEARN_INTERVAL_H = 24  # 24시간마다 자동 실행


def _background_learn_loop():
    """서버 시작 후 1시간 딜레이 → 이후 24시간마다 주기적 학습."""
    import time as _t
    from src.config.logging_config import get_logger
    _bg_log = get_logger("bg_learn")

    _bg_log.info("[bg_learn] 대기 중 — 1시간 후 첫 번째 주기적 학습 시작")
    _t.sleep(3600)

    while True:
        try:
            _bg_log.info("[bg_learn] 주기적 학습 시작")
            from src.knowledge.trend_learner import run_trend_learn
            summary = run_trend_learn(days=60, max_per_query=30)
            _bg_log.info("[bg_learn] 완료: 신규 %d편, 그래프 %d→%d 노드",
                         summary.get("new_papers", 0),
                         summary.get("graph_nodes_before", 0),
                         summary.get("graph_nodes_after", 0))
        except Exception as e:
            _bg_log.error("[bg_learn] 실패 (다음 주기에 재시도): %s", e)
        _t.sleep(_LEARN_INTERVAL_H * 3600)


_AUDIT_INTERVAL_H = 12  # 12시간마다 자가 진단


def _background_self_evolution_loop():
    """서버 시작 후 2시간 딜레이 → 이후 12시간마다 자가 진단 + 자동 개선."""
    import time as _t
    from src.config.logging_config import get_logger
    _bg_log = get_logger("bg_evolve")

    _bg_log.info("[bg_evolve] 대기 중 — 2시간 후 첫 자가 진단 시작")
    _t.sleep(7200)  # 학습 루프와 시간차 두기

    while True:
        try:
            _bg_log.info("[bg_evolve] 자가 진단 + 자동 개선 시작")
            from src.diagnostics.self_auditor import SelfAuditor
            from src.diagnostics.improvement_engine import ImprovementEngine

            result = SelfAuditor().run_full_audit(with_llm_eval=True)
            improvements = ImprovementEngine().run(result.to_dict())

            _bg_log.info(
                "[bg_evolve] 완료: score=%d, auto=%d건, 큐=%d건",
                result.overall_score,
                len(improvements.get("auto_applied", [])),
                improvements.get("queued_count", 0),
            )
        except Exception as e:
            _bg_log.error("[bg_evolve] 실패 (다음 주기에 재시도): %s", e)
        _t.sleep(_AUDIT_INTERVAL_H * 3600)


# ════════════════════════════════════════════════════════════════════════
# Runtime Layer Exposure (memory router + tasks + events + budget + lifecycle)
# Added 2026-05-27 — VS Code agent ↔ Streamlit ↔ MCP 공통 runtime backend
# ════════════════════════════════════════════════════════════════════════

# ── 메모리 ────────────────────────────────────────────────────────────────────

@mcp.tool
def memory_write(text: str, type: str = "episodic", source: str = "user",
                 related_to: list = None, extra_meta: dict = None,
                 ctx=None) -> dict:
    """타입형 메모리 쓰기 단일 진입(router 경유). gate + scorer + lifecycle audit 통과.

    type: 'episodic' | 'semantic' | 'procedural' | 'goal'
    source: 'user' | 'observation' | 'reflection' | 'auto_learn' | 'llm' | 'pubmed' | ...
    """
    try:
        from src.memory import router
        owner = _caller_email(ctx)
        r = router.write(text, type=type, source=source, owner_email=owner,
                         related_to=related_to or [], extra_meta=extra_meta)
        _log_tool(ctx, "memory_write", {"type": type, "source": source, "len": len(text)},
                  f"decision={r.get('decision')}")
        return r
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def memory_recall(query: str, n: int = 5, ctx=None) -> dict:
    """의미적 회수 — conversation_memory + research_wiki 의미검색 통합."""
    try:
        from src.memory import conversation_memory as cm
        owner = _caller_email(ctx)
        out = cm.recall_relevant(query, n=n, owner_email=owner)
        return {"query": query, "n": n, "results": out[:5000]}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def memory_lifecycle_tick(ctx=None) -> dict:
    """수동 lifecycle 트리거(decay/expire/archive). 정기 실행은 heartbeat에서."""
    _require_admin(ctx)
    try:
        from src.memory.lifecycle import tick, stats
        out = tick()
        out["stats_after"] = stats()
        return out
    except Exception as e:
        return {"error": str(e)[:200]}


# ── 작업 ─────────────────────────────────────────────────────────────────────

@mcp.tool
def task_list_unfinished(ctx=None) -> dict:
    """미완료 작업 목록(crash 후 이어쓰기 후보)."""
    try:
        from src.runtime.tasks import TaskRun
        owner = _caller_email(ctx)
        runs = TaskRun.list_unfinished(owner_email=owner, limit=20)
        return {"runs": [{"id": r.id, "type": r.task_type, "status": r.status,
                          "created_at": r.created_at, "updated_at": r.updated_at,
                          "input": r.input} for r in runs]}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def task_status(task_id: str, ctx=None) -> dict:
    """단일 작업의 상태 + steps 조회."""
    try:
        from src.runtime.tasks import TaskRun
        run = TaskRun.get_by_id(task_id)
        return {"id": run.id, "type": run.task_type, "status": run.status,
                "input": run.input, "output": run.output, "error": run.error,
                "created_at": run.created_at, "updated_at": run.updated_at,
                "steps": run.steps()}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── 이벤트 / 감사 ────────────────────────────────────────────────────────────

@mcp.tool
def events_recent(type: str = None, n: int = 50, ctx=None) -> dict:
    """최근 이벤트(LLM 호출/메모리쓰기/작업전이/cache 히트 등) 감사 조회."""
    try:
        from src.runtime import events
        return {"events": events.recent(n=n, type=type)}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def events_replay(task_id: str, ctx=None) -> dict:
    """특정 작업의 전체 이벤트 replay (환각 추적·디버깅용)."""
    try:
        from src.runtime import events
        return {"task_id": task_id, "events": events.replay(task_id)}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── 예산 / 비용 ──────────────────────────────────────────────────────────────

@mcp.tool
def budget_status(window: str = "day", ctx=None) -> dict:
    """LLM 비용 사용량 + 남은 한도."""
    try:
        from src.llm import budget
        return {"snapshot": budget.snapshot(),
                "remaining": budget.remaining(window),
                "recommended_anthropic": budget.recommended_provider("paper_writing", requested="anthropic")}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def budget_set_caps(day_cost_usd: float = None, week_cost_usd: float = None,
                    ctx=None) -> dict:
    """일/주 cap 조정(admin). cap 도달 시 자동 google 다운그레이드 발동."""
    _require_admin(ctx)
    try:
        from src.llm import budget
        return {"new_caps": budget.set_caps(day_cost_usd=day_cost_usd,
                                            week_cost_usd=week_cost_usd)}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def budget_latency(window: str = "day", ctx=None) -> dict:
    """provider별 p50/p95/max latency (ms) — events.llm_usage 집계."""
    try:
        from src.llm.budget import latency_summary
        return latency_summary(window)
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def rag_search_multistage(query: str, n_final: int = 5, n_pool: int = 20,
                            must_cite_csv: str = "", ctx=None) -> dict:
    """다단계 RAG 검색 — dense + Jaccard lexical + recency_boost rerank.
    must_cite_csv: PMID/DOI csv (강제 포함)."""
    try:
        from src.rag.pipeline import RAGPipeline
        must = [x.strip() for x in must_cite_csv.split(",") if x.strip()] if must_cite_csv else None
        hits = RAGPipeline().search_multistage(query, n_final=n_final,
                                                  n_pool=n_pool, must_cite=must)
        return {"n": len(hits), "hits": [{"text": h.get("text", "")[:300],
                                            "final_score": h.get("final_score"),
                                            "metadata": h.get("metadata", {})}
                                           for h in hits]}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def citation_graph_analyze(refs_csv: str, ctx=None) -> dict:
    """ref list(PMID/DOI csv)로 citation graph 빌드 → co-citation + bridging + missing seminal."""
    try:
        from src.knowledge.citation_graph import (
            build_citation_graph, find_co_citations, find_bridging_refs, find_missing_seminal
        )
        refs = [x.strip() for x in refs_csv.split(",") if x.strip()]
        if not refs:
            return {"error": "refs_csv가 비어있음"}
        g = build_citation_graph(refs, depth=1, max_per_ref=10)
        if g is None:
            return {"error": "networkx 미설치 또는 그래프 구축 실패"}
        return {
            "nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
            "co_citations": find_co_citations(g)[:5],
            "bridging": find_bridging_refs(g, top_n=5),
            "missing_seminal": find_missing_seminal(g, refs, top_n=10),
        }
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def llm_with_tools(message: str, tool_names_csv: str = "search_papers,check_novelty",
                    max_iters: int = 4, ctx=None) -> dict:
    """★ Agentic tool-use loop — Claude가 직접 도구를 호출하며 task 수행.
    tool_names_csv: TOOLS 레지스트리에서 노출할 도구 이름 csv."""
    try:
        from src.llm import get_llm_client
        from src.tools import TOOLS, run_tool
        names = [n.strip() for n in tool_names_csv.split(",") if n.strip()]
        tools_spec = []
        for n in names:
            t = TOOLS.get(n)
            if not t:
                continue
            tools_spec.append({
                "name": n,
                "description": getattr(t, "description", n),
                "input_schema": getattr(t, "input_schema", {"type": "object", "properties": {}}),
            })
        client = get_llm_client(task="standard")
        # ClaudeClient 우회 (failover wrapper) — 직접 anthropic이 필요
        from src.llm.claude_client import ClaudeClient
        cc = client if isinstance(client, ClaudeClient) else ClaudeClient(task="standard")
        result = cc.generate_with_tools(message, tools=tools_spec,
                                          tool_handler=lambda n, i: str(run_tool(n, i)),
                                          max_iters=max_iters)
        return result
    except Exception as e:
        return {"error": str(e)[:300]}


@mcp.tool
def consistency_check_paper(paper_text: str, ctx=None) -> dict:
    """본문 정형 모순 검사 (n/OR-CI/p값/연도). LLM이 못 잡는 것을 정규식으로."""
    try:
        from src.safety.consistency_checker import check_consistency
        sections = {"Paper": paper_text}
        rep = check_consistency(sections)
        return rep.to_dict()
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def trigger_analyze(text: str, ctx=None) -> dict:
    """사용자 메시지 → intent/topic/sentiment/priority/urgency 분류 (vision 트리거 분석기)."""
    try:
        from src.agent.trigger_analyzer import analyze
        return analyze(text).to_dict()
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def cognitive_activate(user_msg: str, owner: str = "", ctx=None) -> dict:
    """5-layer Cognitive Activation (vision 인지 활성화 엔진).
    fragments → propagation → routing → flow → policy."""
    try:
        from src.agent.cognitive_activation import activate
        return activate(user_msg, owner=owner or None)
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def memory_recall_5layers(query: str, owner: str = "", n: int = 3, ctx=None) -> dict:
    """5층 메모리 동시 recall (working/episodic/semantic/procedural/goal)."""
    try:
        from src.memory import recall_all_layers
        return recall_all_layers(query, owner=owner or None, n_per_layer=n)
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def memory_stats_5layers(ctx=None) -> dict:
    """5층 메모리 누적 통계 (Dashboard용)."""
    try:
        from src.memory import stats
        return stats()
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def notify_list(unread_only: bool = True, limit: int = 50, ctx=None) -> dict:
    """알림 시스템 — 읽지 않은/전체 알림 목록."""
    try:
        from src.runtime.notifier import list_unread, list_all, stats
        items = list_unread(limit=limit) if unread_only else list_all(limit=limit)
        return {"stats": stats(), "items": items}
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def longitudinal_summary(days: int = 30, ctx=None) -> dict:
    """eval metric의 시계열 trend + regression alert. 'agent가 좋아졌나' 측정."""
    try:
        from src.diagnostics.longitudinal_eval import summary
        return summary(days=days)
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def causal_check_paper(paper_text: str, study_design: str = "cross_sectional",
                         ctx=None) -> dict:
    """본문 causal claim 추출 + design 적합성 평가 (STROBE 위반 검출)."""
    try:
        from src.safety.causal_checker import check_causal_claims
        rep = check_causal_claims(paper_text, study_design=study_design)
        return rep.to_dict()
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def sandbox_python(code: str, timeout_sec: int = 30, ctx=None) -> dict:
    """격리 subprocess에서 Python 코드 실행. autonomous debug용."""
    try:
        from src.runtime.sandbox import run_python
        return run_python(code, timeout_sec=timeout_sec)
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def list_agent_roles(ctx=None) -> dict:
    """multi-agent roles 레지스트리 + action→role mapping."""
    try:
        from src.agent.roles import role_stats
        return role_stats()
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def plan_section_dag(section: str, goal: str = "", outcome: str = "depression",
                       exposure: str = "zcb_freq", ctx=None) -> dict:
    """Planner DAG 생성 (실행은 안 함) — 어떤 노드/엣지가 만들어지는지 미리보기."""
    try:
        from src.agent.planner import get_planner
        g = get_planner().plan(goal or section,
                                  context={"section": section, "outcome": outcome,
                                            "exposure": exposure})
        return {
            "graph_id": g.id, "goal": g.goal,
            "n_nodes": len(g.nodes),
            "topological_order": g.topological_order(),
            "nodes": {nid: {"action": n.action, "deps": n.deps,
                              "rationale": n.rationale}
                       for nid, n in g.nodes.items()},
        }
    except Exception as e:
        return {"error": str(e)[:200]}


@mcp.tool
def reporting_checklist_strobe(sections_json: str, ctx=None) -> dict:
    """STROBE 22항목 자동 체크 — sections_json은 {"Introduction": "...", ...} dict."""
    try:
        import json as _json
        from src.research.reporting_checklist import check_strobe
        sections = _json.loads(sections_json)
        return check_strobe(sections)
    except Exception as e:
        return {"error": str(e)[:200]}


# ════════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medical-Agent MCP Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)), help="HTTP port (default: 8765)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode (Claude Code)")
    args = parser.parse_args()

    if args.stdio:
        print("[MCP] Running in stdio mode (no auth enforcement)")
        mcp.run()
    else:
        print(f"[MCP] Medical-Agent MCP Server starting on http://{args.host}:{args.port}")
        print(f"[MCP] Claude Desktop: set URL to http://localhost:{args.port}/mcp")
        # 백그라운드 학습 루프 (24h 주기)
        bg_learn = _threading.Thread(target=_background_learn_loop, daemon=True, name="bg_learn")
        bg_learn.start()
        print("[MCP] 백그라운드 학습 루프 시작됨 (1h 딜레이 후 첫 실행, 이후 24h 주기)")

        # 백그라운드 자가 진단 루프 (12h 주기)
        bg_evolve = _threading.Thread(target=_background_self_evolution_loop, daemon=True, name="bg_evolve")
        bg_evolve.start()
        print("[MCP] 자가 진단 루프 시작됨 (2h 딜레이 후 첫 실행, 이후 12h 주기)")

        mcp.run(transport="http", host=args.host, port=args.port)
