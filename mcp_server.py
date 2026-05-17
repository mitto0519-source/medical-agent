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
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root on path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

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
        mcp.run(transport="http", host=args.host, port=args.port)
