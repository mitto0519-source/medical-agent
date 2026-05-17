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

    return {
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
    """PubMed 기반 연구 주제 신규성 검증.

    Args:
        topic_title: 연구 제목
        exposure: 주요 노출변수 (예: "smartphone use")
        outcome: 주요 결과변수 (예: "sleep quality")
        population: 대상 집단 (예: "Korean adolescents")
    """
    from src.research.novelty_checker import NoveltyChecker
    checker = NoveltyChecker()
    return checker.check(
        topic=topic_title,
        exposure=exposure,
        outcome=outcome,
        population=population,
    )


@mcp.tool
def generate_research_topics(
    dataset: str = "KYRBS",
    focus: str = "",
    n_topics: int = 5,
    ctx=None,
) -> dict:
    """데이터셋 + RAG 기반 연구 주제 생성.

    Args:
        dataset: 사용 데이터셋 (기본: KYRBS)
        focus: 연구 포커스 키워드
        n_topics: 생성할 주제 수
    """
    from src.research.research_pipeline import ResearchPipeline
    rp = ResearchPipeline()
    topics = rp.generate_topics(dataset_name=dataset, focus=focus, n_topics=n_topics)
    return {"topics": topics, "count": len(topics)}


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
