"""FastAPI 백엔드 진입 — service 함수를 HTTP/SSE로 노출.

FRONTEND_MIGRATION_SPEC §5 + FRONTEND_NEXTJS_SPEC §8/§9.

핵심 엔드포인트:
  POST /auth/login           — JWT 발급
  GET  /me                   — 현재 사용자
  GET  /projects             — 프로젝트 목록 (RECENT)
  POST /projects             — 새 프로젝트
  GET  /projects/{id}        — 프로젝트 단건
  POST /chat (SSE)           — ChatEvent 스트림 (src.service.chat.stream_turn)
  POST /rag/search           — RAG 검색
  POST /stats/run            — 통계 실행
  POST /figures              — 그림 생성
  POST /references           — refs CRUD
  GET  /export/docx          — Word + EndNote 묶음 zip

원칙: 로직 0. 모든 호출 = src.service.*.
실행: uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import io
import json
import time
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, JSONResponse
from pydantic import BaseModel

from src.config.env import bootstrap
from src.config.logging_config import get_logger

bootstrap()
_log = get_logger(__name__)

from api.auth import create_token, get_current_email, verify_user

app = FastAPI(
    title="Medical-Agent API",
    version="0.1.0",
    description="FastAPI backend — service 함수를 HTTP/SSE로 노출 (Phase 2)",
)

# CORS — 개발 시 모든 origin 허용, 프로덕션은 Vercel/HF 도메인만
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 인증 의존성 ───────────────────────────────────────────────────────────

def require_email(
    authorization: Optional[str] = Header(None),
    ma_token: Optional[str] = Cookie(None, alias="ma_token"),
) -> str:
    email = get_current_email(authorization or "", ma_token or "")
    if not email:
        raise HTTPException(status_code=401, detail="authentication required")
    return email


# ── 헬스체크 ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": app.version, "ts": int(time.time())}


# ── /auth ────────────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
def auth_login(body: LoginIn):
    if not verify_user(body.email, body.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_token(body.email)
    resp = JSONResponse({"email": body.email, "token": token})
    resp.set_cookie(
        key="ma_token", value=token, httponly=True, secure=False,
        samesite="lax", max_age=7 * 24 * 3600,
    )
    return resp


@app.post("/auth/logout")
def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("ma_token")
    return resp


@app.get("/me")
def me(email: str = Depends(require_email)):
    return {"email": email}


# ── /projects (CRUD) ─────────────────────────────────────────────────────

class ProjectCreateIn(BaseModel):
    title: str = "새 작업"


@app.get("/projects")
def list_projects(email: str = Depends(require_email)):
    """ez_home._load_projects의 service 양식. Supabase 우선 → 로컬 폴백."""
    try:
        from src.cloud.db import cloud_available, get_engine
        from sqlalchemy import text as _sql
        if cloud_available():
            with get_engine().begin() as conn:
                rows = conn.execute(_sql(
                    "SELECT id, title, updated_at, data_json "
                    "FROM ma_working_papers WHERE owner_email=:e "
                    "ORDER BY updated_at DESC LIMIT 50"
                ), {"e": email}).all()
                items = []
                for r in rows:
                    pid, title, ts, dj = r[0], r[1] or "", r[2], r[3] or {}
                    if not title or title.startswith("chat_") or title == pid:
                        msgs = (dj if isinstance(dj, dict) else json.loads(dj)).get("messages", [])
                        for m in msgs:
                            if m.get("role") == "user":
                                title = m.get("content", "")[:60]
                                break
                    items.append({"id": pid, "title": title or "제목 없음",
                                    "updated_at": ts})
                return items
    except Exception as e:
        _log.warning("list_projects fail: %s", e)
    return []


@app.post("/projects")
def create_project(body: ProjectCreateIn, email: str = Depends(require_email)):
    from src.research.research_state import new_project, project_save
    rp = new_project(owner_email=email, title=body.title)
    project_save(rp, cloud=True)
    return {"id": rp.id, "title": rp.title}


@app.get("/projects/{pid}")
def get_project(pid: str, email: str = Depends(require_email)):
    from src.research.research_state import project_load
    rp = project_load(pid)
    if rp is None:
        raise HTTPException(status_code=404, detail="not found")
    if rp.owner_email and rp.owner_email != email:
        raise HTTPException(status_code=403, detail="forbidden")
    return rp.project_to_dict()


# ── /chat (SSE — ChatEvent 스트림) ───────────────────────────────────────

class ChatIn(BaseModel):
    project_id: Optional[str] = None
    message: str
    max_tokens: int = 2048


def _sse_serialize(ev) -> str:
    """ChatEvent → SSE frame. FRONTEND_MIGRATION_SPEC §5.5.6."""
    try:
        return ev.to_sse()
    except Exception:
        return f"data: {json.dumps({'type': 'error', 'data': {'msg': 'serialize_fail'}})}\n\n"


@app.post("/chat")
def chat_stream(body: ChatIn, email: str = Depends(require_email)):
    """SSE stream — service.chat.stream_turn ChatEvent generator를 그대로 흘림.

    클라이언트(Next.js)는 EventSource로 소비. 각 ChatEvent는 SSE frame.
    """
    from src.research.research_state import project_load
    from src.service.chat import stream_turn

    project = None
    if body.project_id:
        rp = project_load(body.project_id)
        if rp is not None:
            from src.research.research_state import to_project_dict
            project = to_project_dict(rp)
    if project is None:
        project = {"id": body.project_id or "chat_tmp",
                    "owner_email": email, "messages": [], "sections": {}}

    def event_stream():
        try:
            for ev in stream_turn(project, body.message, owner_email=email,
                                    max_tokens=body.max_tokens):
                yield _sse_serialize(ev)
        except Exception as e:
            _log.warning("chat_stream fail: %s", e)
            yield f"data: {json.dumps({'type':'error','data':{'msg':str(e)[:200]}})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── /rag/search ──────────────────────────────────────────────────────────

class RagIn(BaseModel):
    query: str
    top_k: int = 5
    use_hyde: bool = False


@app.post("/rag/search")
def rag_search(body: RagIn, email: str = Depends(require_email)):
    from src.service.rag import retrieve
    hits = retrieve(body.query, top_k=body.top_k, use_hyde=body.use_hyde)
    return {"hits": hits}


# ── /stats/run ───────────────────────────────────────────────────────────

class StatsIn(BaseModel):
    spec: dict
    dataset_path: Optional[str] = None


@app.post("/stats/run")
def stats_run(body: StatsIn, email: str = Depends(require_email)):
    from src.service.stats import analyze
    result = analyze(body.spec, dataset_path=body.dataset_path)
    return result


# ── /figures ─────────────────────────────────────────────────────────────

class FigureIn(BaseModel):
    project_id: str
    kind: str  # forest|subgroup|coef|roc|prev|table1|table2


@app.post("/figures")
def figures_gen(body: FigureIn, email: str = Depends(require_email)):
    from src.research.research_state import project_load, to_project_dict
    from src.service.figures import generate_figure
    rp = project_load(body.project_id)
    if rp is None:
        raise HTTPException(status_code=404, detail="project not found")
    project = to_project_dict(rp)
    result = generate_figure(project, body.kind)
    if result is None:
        raise HTTPException(status_code=400, detail="figure generation failed (no stat_result?)")
    png_bytes, caption = result
    return Response(content=png_bytes, media_type="image/png",
                      headers={"X-Caption": caption[:200]})


# ── /references ──────────────────────────────────────────────────────────

class RefAddIn(BaseModel):
    pmids: list[str]
    fetch_pubmed: bool = False


@app.post("/references/from_pmids")
def references_from_pmids(body: RefAddIn, email: str = Depends(require_email)):
    from src.service.references import references_from_pmid_list
    refs = references_from_pmid_list(body.pmids, fetch_pubmed=body.fetch_pubmed)
    return {"refs": [
        {"pmid": getattr(r, "pmid", None), "title": getattr(r, "title", ""),
         "citation_key": getattr(r, "citation_key", "")}
        for r in refs
    ]}


# ── /export/docx (Word + EndNote 묶음) ───────────────────────────────────

@app.get("/export/docx")
def export_docx_bundle(
    project_id: str = Query(...),
    journal: Optional[str] = Query(None),
    email: str = Depends(require_email),
):
    """FRONTEND_NEXTJS_SPEC §5.3 §8: Word + EndNote zip 묶음 다운로드."""
    from src.research.research_state import project_load, to_project_dict
    from src.service.export import bundle_for_download

    rp = project_load(project_id)
    if rp is None:
        raise HTTPException(status_code=404, detail="not found")
    project = to_project_dict(rp)
    try:
        result = bundle_for_download(project, with_endnote=True, journal_slug=journal)
    except Exception as e:
        _log.warning("export fail: %s", e)
        raise HTTPException(status_code=500, detail=f"export failed: {e}")

    if isinstance(result, (bytes, bytearray)):
        return Response(content=bytes(result), media_type="application/zip",
                          headers={"Content-Disposition":
                                     f'attachment; filename="paper_{project_id}.zip"'})
    if isinstance(result, dict) and "zip_bytes" in result:
        return Response(content=result["zip_bytes"], media_type="application/zip",
                          headers={"Content-Disposition":
                                     f'attachment; filename="paper_{project_id}.zip"'})
    raise HTTPException(status_code=500, detail="export: unexpected result shape")


# ── /research /concept (FRONTEND_NEXTJS_SPEC §3 — (public) 데이터 소스) ──

@app.get("/research/{slug}")
def get_research_topic(slug: str):
    """Phase 3 web (public) /research/[slug] → ScholarlyArticle JSON-LD 데이터 공급.

    graph.json에서 paper 노드 검색 (slug=pmid 또는 slugified title).
    """
    import json as _json
    from pathlib import Path as _P
    try:
        g = _json.loads((_P("data/knowledge_graph/graph.json")).read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {e}")
    paper = None
    # 1) slug == pmid
    for n in g.get("nodes", []):
        if n.get("type") == "paper":
            if str(n.get("pmid")) == slug or n.get("id") == slug:
                paper = n
                break
    if paper is None:
        raise HTTPException(status_code=404, detail=f"research topic '{slug}' not found")
    # 인용/관련 concepts
    pmid = str(paper.get("pmid") or slug)
    related = []
    for e in g.get("edges", [])[:10000]:
        if e.get("source") == f"paper:{pmid}" or e.get("from") == f"paper:{pmid}":
            tgt = e.get("target") or e.get("to") or ""
            if tgt.startswith("concept:") or tgt.startswith("C_"):
                related.append(tgt.replace("concept:", ""))
            if len(related) >= 8:
                break
    return {
        "slug": slug,
        "pmid": pmid,
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract", "")[:1500],
        "year": paper.get("year"),
        "journal": paper.get("journal", ""),
        "related_concepts": related,
        "modified_at": paper.get("updated_at"),
    }


@app.get("/concept/{cui}")
def get_concept(cui: str):
    """Phase 3 web (public) /concept/[cui] → MedicalCondition JSON-LD 데이터 공급.

    medical_ontology에서 concept 검색.
    """
    try:
        from src.knowledge.medical_ontology import MedicalOntology
        ont = MedicalOntology()
        c = None
        for axis_concepts in (ont.concepts() if hasattr(ont, "concepts") else []):
            if axis_concepts.get("concept_id") == cui or axis_concepts.get("cui") == cui:
                c = axis_concepts
                break
    except Exception:
        c = None
    if c is None:
        # graph.json fallback
        import json as _json
        from pathlib import Path as _P
        try:
            g = _json.loads(_P("data/knowledge_graph/graph.json").read_text(encoding="utf-8"))
            for n in g.get("nodes", []):
                if n.get("type") == "concept" and (
                    str(n.get("id", "")) == cui or str(n.get("cui", "")) == cui
                ):
                    c = n
                    break
        except Exception:
            pass
    if c is None:
        raise HTTPException(status_code=404, detail=f"concept '{cui}' not found")
    return {
        "cui": cui,
        "label": c.get("label") or c.get("name") or cui,
        "domain": c.get("domain_label") or c.get("axis") or c.get("domain") or "",
        "definition": c.get("definition") or c.get("description") or "",
        "mesh": c.get("mesh"),
        "umls": c.get("umls"),
        "keywords": c.get("keywords") or [],
    }


# ── /pipeline (RESEARCH_PIPELINE_SPEC orchestrator 노출) ─────────────────

class PipelineAdvanceIn(BaseModel):
    project_id: str
    auto: bool = False


@app.post("/pipeline/advance")
def pipeline_advance(body: PipelineAdvanceIn, email: str = Depends(require_email)):
    """orchestrator.advance — SSE로 ChatEvent 흘림.

    auto=True면 STATS gate까지 연속 진행 후 휴먼 확인 대기.
    """
    from src.research.research_state import project_load
    from src.research.pipeline_orchestrator import advance

    rp = project_load(body.project_id)
    if rp is None:
        raise HTTPException(status_code=404, detail="not found")
    if rp.owner_email and rp.owner_email != email:
        raise HTTPException(status_code=403, detail="forbidden")

    def event_stream():
        try:
            for ev in advance(rp, auto=body.auto):
                yield _sse_serialize(ev)
        except Exception as e:
            _log.warning("pipeline_advance fail: %s", e)
            yield f"data: {json.dumps({'type':'error','data':{'msg':str(e)[:200]}})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class PipelineConfirmIn(BaseModel):
    project_id: str


@app.post("/pipeline/confirm_stats")
def pipeline_confirm_stats(body: PipelineConfirmIn, email: str = Depends(require_email)):
    """STATS gate 휴먼 확인 — '이 숫자/해석으로 갈까요?' 승인."""
    from src.research.research_state import project_load
    from src.research.pipeline_orchestrator import confirm_stats_human

    rp = project_load(body.project_id)
    if rp is None:
        raise HTTPException(status_code=404, detail="not found")
    if rp.owner_email and rp.owner_email != email:
        raise HTTPException(status_code=403, detail="forbidden")
    confirm_stats_human(rp)
    return {"ok": True, "stage": rp.stage}
