"""프로젝트 워크스페이스 — EZ 양식의 split 화면.

좌측 (38%): chat
  · 과거 대화 + 현재 어시스턴트 응답
  · 하단 입력바 (sg-big-input 글래스 양식)

우측 (62%): preview tab bar (chip 양식)
  · Manuscript  — Word 양식 1:1 사파이어 글라스 위 화이트 페이퍼
  · Figures     — 생성된 figure (썸네일 그리드)
  · Tables      — 학술지 세 줄 표 (HTML 미리보기)
  · Supplement  — 부록 / Stata do-file / raw stats

기존 working_paper_store + paper_writer + StatBridge를 그대로 사용,
새 UI는 표면 — 핵심 로직은 침범 안 함.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Optional

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

# ── Page-level config + 즉시 chrome_hide micro-CSS (2026-05-30, ez_home과 동일) ──
try:
    st.set_page_config(
        page_title="Medical-Agent · Workspace",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except Exception:
    pass
st.markdown(
    "<style>"
    "#MainMenu{visibility:hidden!important;display:none!important;}"
    "header[data-testid='stHeader']{background:transparent!important;}"
    "[data-testid='stToolbar']{display:none!important;}"
    "[data-testid='stToolbarActions']{display:none!important;}"
    "[data-testid='stDecoration']{display:none!important;}"
    "[data-testid='stStatusWidget']{display:none!important;}"
    "[data-testid='stAppDeployButton']{display:none!important;}"
    ".stDeployButton{display:none!important;}"
    "button[kind='header']{display:none!important;}"
    "footer{visibility:hidden!important;display:none!important;}"
    "html,body,[data-testid='stApp']{background:#1E1B4B!important;color:#F5F5FA!important;}"
    "</style>",
    unsafe_allow_html=True,
)

from app.styles.sapphire_glass import (
    inject_sapphire_glass, message_bubble, manuscript_preview_html, action_card,
)
from src.utils.text_sanitize import safe_json_dumps, sanitize_obj, strip_lone_surrogates


_WP_DIR = Path("data/working_papers")
_FIG_DIR = Path("data/exports")


def _load_project(pid: str) -> dict:
    """working_papers/{pid}.json (로컬) 또는 Supabase ma_working_papers (클라우드).
    2026-05-30: 클라우드 fallback 추가 — 로컬에 없으면 Supabase에서 자동 로드.
    KYRBS .sav 데이터 없어도 sections/messages/references 다 보고 chat 첨삭 가능.
    """
    if pid == "new":
        return {"title": "New manuscript",
                "topic": {}, "sections": {}, "messages": [], "figures": [], "tables": []}

    # 1) 로컬 우선
    for p in (_WP_DIR / f"{pid}.json",
              *(_WP_DIR.glob(f"*/{pid}.json"))):  # user-scoped subdir도 탐색
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass

    # 2) Supabase 폴백 — 클라우드에서 동기된 프로젝트 로드
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text as _sql
            with get_engine().connect() as conn:
                row = conn.execute(_sql(
                    "SELECT title, sections, meta FROM ma_working_papers WHERE id=:id"),
                    {"id": pid}).mappings().first()
            if row:
                sec_lower = row["sections"] or {}
                if isinstance(sec_lower, str):
                    try: sec_lower = json.loads(sec_lower)
                    except Exception: sec_lower = {}
                meta = row["meta"] or {}
                if isinstance(meta, str):
                    try: meta = json.loads(meta)
                    except Exception: meta = {}
                # lowercase → PascalCase 변환
                sec_pascal = {
                    "Abstract": sec_lower.get("abstract", ""),
                    "Introduction": sec_lower.get("introduction", ""),
                    "Methods": sec_lower.get("methods", ""),
                    "Results": sec_lower.get("results", ""),
                    "Discussion": sec_lower.get("discussion", ""),
                }
                return {
                    "title": row["title"] or pid,
                    "topic": (meta.get("topic") or {"title": row["title"]}),
                    "sections": sec_pascal,
                    "messages": [],   # Supabase에는 messages 미저장 → 빈 list (첨삭 시작 가능)
                    "references": meta.get("references") or [],
                    "figures": [],
                    "tables": [],
                    "_loaded_from": "supabase",
                }
    except Exception:
        pass

    # 3) 진짜 없음
    return {"title": pid, "sections": {}, "messages": [], "figures": [], "tables": []}


def _save_project(pid: str, data: dict, *, msg_cap: int = 200,
                   archive_after: int = 300) -> None:
    """working_papers/{pid}.json. messages 무한 누적으로 write 실패 방지:
    archive_after 초과 시 오래된 메시지 archive 파일로 분리 → main은 최근 msg_cap만."""
    if pid == "new":
        return
    _WP_DIR.mkdir(parents=True, exist_ok=True)
    p = _WP_DIR / f"{pid}.json"

    # messages cap + archive
    msgs = data.get("messages") or []
    if isinstance(msgs, list) and len(msgs) > archive_after:
        archive_dir = _WP_DIR / "_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{pid}_msgs.jsonl"
        keep = msgs[-msg_cap:]
        drop = msgs[:-msg_cap]
        try:
            with archive_path.open("a", encoding="utf-8") as af:
                for m in drop:
                    af.write(json.dumps(m, ensure_ascii=False, default=str) + "\n")
            data["messages"] = keep
            data["_archived_msgs_count"] = (data.get("_archived_msgs_count", 0)
                                              + len(drop))
        except Exception as e:
            # archive 실패해도 본 저장은 시도 — 가장 최근 msg_cap만 강제
            data["messages"] = keep
            try:
                from src.runtime import events as _events
                _events.append("project_archive_fail",
                                {"pid": pid, "err": str(e)[:160]},
                                actor="project_workspace")
            except Exception:
                pass

    # 단일 message 자체가 거대한 경우(예: tool_result 거대 JSON) 잘라내기 + lone surrogate 제거
    # (2026-05-30 API 6.6MB no-low-surrogate 사고 방어)
    if isinstance(data.get("messages"), list):
        for m in data["messages"]:
            c = m.get("content")
            if isinstance(c, str):
                c = strip_lone_surrogates(c)
                if len(c) > 8000:
                    c = c[:8000] + "\n…[truncated]"
                m["content"] = c

    try:
        # sanitize: dict 안 모든 str의 lone surrogate / nasty ctrl 제거 → JSON 직렬화 안전
        text = safe_json_dumps(data, indent=2)
        # 5MB 이상이면 indent 제거하고 재시도
        if len(text) > 5_000_000:
            text = safe_json_dumps(data)
        p.write_text(text, encoding="utf-8")

        # ★ Supabase 자동 동기 (2026-05-30) — 로컬 docker → 클라우드 자동 sync,
        # 클라우드에서 같은 user_email로 로그인하면 같은 프로젝트 자동 표시.
        try:
            from src.storage.working_paper_store import save_paper as _wp_save
            owner = str(data.get("owner") or
                          st.session_state.get("user", {}).get("email") or
                          st.session_state.get("user_email", "") or "anonymous")
            sec_in = data.get("sections") or {}
            sec_out = {
                "title": (data.get("topic") or {}).get("title") or data.get("title", ""),
                "abstract": str(sec_in.get("Abstract") or sec_in.get("abstract", ""))[:30000],
                "introduction": str(sec_in.get("Introduction") or sec_in.get("introduction", ""))[:30000],
                "methods": str(sec_in.get("Methods") or sec_in.get("methods", ""))[:30000],
                "results": str(sec_in.get("Results") or sec_in.get("results", ""))[:30000],
                "discussion": str(sec_in.get("Discussion") or sec_in.get("discussion", ""))[:30000],
            }
            meta_out = {
                "topic": data.get("topic"),
                "references": data.get("references"),
                "messages_count": len(data.get("messages") or []),
                "raw_pid": pid,
            }
            _wp_save(owner, sec_out, meta=meta_out, paper_id=pid)
        except Exception as _sync_e:
            try:
                from src.runtime import events as _ev
                _ev.append("project_supabase_sync_fail",
                            {"pid": pid, "err": str(_sync_e)[:160]},
                            actor="project_workspace")
            except Exception:
                pass
    except Exception as e:
        try:
            from src.runtime import events as _events
            _events.append("project_save_fail",
                            {"pid": pid, "err": str(e)[:200],
                             "size_attempt": len(text) if "text" in dir() else 0},
                            actor="project_workspace")
        except Exception:
            pass
        # 마지막 시도 — messages 완전 비우고 메타만 저장
        try:
            backup = {**data}
            backup["messages"] = (backup.get("messages") or [])[-20:]
            p.write_text(safe_json_dumps(backup), encoding="utf-8")
        except Exception:
            pass


def _render_topbar(project: dict):
    title = project.get("title", "Untitled")
    cols = st.columns([5, 1, 1, 1])
    with cols[0]:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:12px;padding:6px 0;'>"
            f"<div style='width:32px;height:32px;border-radius:10px;"
            f"background:linear-gradient(135deg,#3B82F6,#8B5CF6);'></div>"
            f"<div><div style='font-weight:600;font-size:1.0rem;'>{title}</div>"
            f"<div style='color:#A3A3B8;font-size:0.78rem;'>Previewing last saved version</div>"
            f"</div></div>", unsafe_allow_html=True)
    with cols[1]:
        # Comments — inline note 양식은 Phase 2. 지금은 회의록/메모 download 양식.
        if st.button("💬 Notes", use_container_width=True, key="ws_comments"):
            st.session_state["ws_show_notes"] = not st.session_state.get("ws_show_notes", False)
    with cols[2]:
        # Share — working_paper JSON download (link 기반 share는 Phase 2 multi-user)
        try:
            payload = safe_json_dumps(project, indent=2)
            st.download_button(
                "🔗 Share", data=payload.encode("utf-8"),
                file_name=f"{project.get('title','manuscript').replace(' ','_')[:40]}.json",
                mime="application/json", use_container_width=True, key="ws_share_dl",
                help="현재 프로젝트 상태(JSON)를 다운로드. 공유 링크는 multi-user 단계에서.")
        except Exception as e:
            if st.button("🔗 Share", use_container_width=True, key="ws_share"):
                st.error(f"Share export 실패: {e}")
    with cols[3]:
        # ── Export: Word / PDF / EndNote XML / BibTeX 한큐 (2026-05-30) ──
        with st.popover("⬇ Export", use_container_width=True):
            st.caption("4가지 포맷 한 번에")
            # 1) Word (docx)
            if st.button("📄 Word (.docx)", use_container_width=True, key="ws_exp_docx"):
                _export_docx(project)
            # 2) PDF
            if st.button("📑 PDF (.pdf)", use_container_width=True, key="ws_exp_pdf"):
                _export_pdf(project)
            # 3) EndNote XML
            refs = project.get("references", []) or []
            if refs:
                try:
                    from src.export.reference_library import ReferenceLibrary
                    slug = (project.get("topic") or {}).get("title", "manuscript")[:60]
                    lib = ReferenceLibrary(paper_slug=slug)
                    for r in refs:
                        lib.add_from_dict(r)
                    st.download_button(
                        "🔖 EndNote (.xml)",
                        data=lib.export_endnote_xml().encode("utf-8"),
                        file_name=f"{slug}.xml", mime="application/xml",
                        use_container_width=True, key="ws_exp_endnote")
                    # 4) BibTeX
                    st.download_button(
                        "📚 BibTeX (.bib)",
                        data=lib.export_bibtex().encode("utf-8"),
                        file_name=f"{slug}.bib", mime="text/plain",
                        use_container_width=True, key="ws_exp_bib")
                except Exception as _e:
                    st.warning(f"인용 export 실패: {_e}")
            else:
                st.caption("인용이 없어 EndNote/BibTeX 비활성")

    # Notes panel — 짧은 메모 적어 working_paper.notes 로 저장 (inline comment의 단순 양식)
    if st.session_state.get("ws_show_notes"):
        with st.container():
            current_notes = project.get("notes", "")
            new_notes = st.text_area(
                "📝 작업 메모 (이 프로젝트에만 저장)", value=current_notes, height=100,
                key="ws_notes_text",
                placeholder="예: TODO Discussion 강화 / 사용자 피드백 / 통계 재검토 항목…")
            if new_notes != current_notes:
                project["notes"] = strip_lone_surrogates(new_notes)
                # 호출자(render)가 pid를 갖고 있음 — 여기는 정적 함수라 즉시 저장은 다음 rerun에 맡김.
                st.session_state["ws_notes_pending_save"] = True
                st.caption("✓ 다음 메시지 전송 시 함께 저장됩니다.")


def _export_docx(project: dict):
    try:
        from src.export.word_exporter import WordExporter
        sections = project.get("sections", {})
        topic = project.get("topic") or {"title": project.get("title", "Untitled")}
        path = WordExporter().export(
            topic=topic, sections=sections,
            references=project.get("references", []),
            back_matter=project.get("back_matter", {}),
            keywords=project.get("keywords", []),
            figures=project.get("figures_bin", []),
            tables=project.get("tables", []),
        )
        st.session_state["sg_last_export"] = path
        st.toast(f"docx 저장: {Path(path).name}", icon="✅")
        # 즉시 download_button 제공
        try:
            with open(path, "rb") as f:
                st.download_button(
                    "⬇ docx 다운로드", data=f.read(),
                    file_name=Path(path).name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"dl_docx_{Path(path).stem}")
        except Exception:
            pass
    except Exception as e:
        st.error(f"Export 실패: {e}")


def _export_pdf(project: dict):
    """PDF export — reportlab 또는 docx2pdf 폴백.

    1순위: docx → LibreOffice headless 변환 (docker container 안 가능)
    2순위: reportlab으로 직접 PDF 생성 (간단한 한국어 양식)
    3순위: 'PDF는 Word에서 Save As로 변환하세요' 안내
    """
    sections = project.get("sections", {})
    topic = project.get("topic") or {"title": project.get("title", "Untitled")}
    refs = project.get("references", []) or []

    # 우선 reportlab 직접 생성 시도 (가장 안정적)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

        # 한국어 폰트 등록 (docker에 fonts-nanum 설치됨)
        try:
            pdfmetrics.registerFont(TTFont("NanumGothic", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"))
            base_font = "NanumGothic"
        except Exception:
            base_font = "Helvetica"

        from pathlib import Path as _PP
        out_dir = _PP("data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        out_path = out_dir / f"{topic.get('title', 'manuscript')[:50].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                                 leftMargin=2.5*cm, rightMargin=2.5*cm,
                                 topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title", parent=styles["Title"],
                                       fontName=base_font, fontSize=18, alignment=1)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                              fontName=base_font, fontSize=13, spaceBefore=12)
        body = ParagraphStyle("Body", parent=styles["BodyText"],
                                fontName=base_font, fontSize=10.5, leading=15)

        story = []
        story.append(Paragraph(str(topic.get("title", "Untitled")), title_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Yoosun Cho", body))
        story.append(Spacer(1, 16))

        for name in ("Abstract", "Introduction", "Methods", "Results", "Discussion"):
            content = sections.get(name)
            if not content:
                continue
            story.append(Paragraph(name, h2))
            if isinstance(content, dict):
                for k, v in content.items():
                    story.append(Paragraph(f"<b>{k}</b>: {str(v)}", body))
                    story.append(Spacer(1, 4))
            else:
                # 줄바꿈 보존
                for para in str(content).split("\n\n"):
                    if para.strip():
                        story.append(Paragraph(para.replace("\n", "<br/>"), body))
                        story.append(Spacer(1, 6))
            story.append(Spacer(1, 10))

        # References
        if refs:
            story.append(PageBreak())
            story.append(Paragraph("References", h2))
            try:
                from src.export.reference_library import (
                    ReferenceLibrary, format_reference, Reference,
                )
                for i, r in enumerate(refs, 1):
                    ref = Reference.from_dict(r) if isinstance(r, dict) else r
                    line = format_reference(ref, "Vancouver", i)
                    story.append(Paragraph(line, body))
                    story.append(Spacer(1, 4))
            except Exception:
                for i, r in enumerate(refs, 1):
                    story.append(Paragraph(
                        f"{i}. {r.get('title', '?') if isinstance(r, dict) else str(r)}",
                        body))

        doc.build(story)
        st.session_state["sg_last_export"] = str(out_path)
        st.toast(f"PDF 저장: {out_path.name}", icon="✅")
        with open(out_path, "rb") as f:
            st.download_button(
                "⬇ PDF 다운로드", data=f.read(),
                file_name=out_path.name, mime="application/pdf",
                key=f"dl_pdf_{out_path.stem}")
        return
    except ImportError:
        pass
    except Exception as e:
        st.warning(f"reportlab PDF 실패: {e}")

    # 폴백: docx만 만들고 안내
    try:
        _export_docx(project)
        st.info("PDF 직접 export는 docker container에 reportlab 설치가 필요합니다. "
                "현재 docx로 저장됐으니 Word에서 'PDF로 저장'을 사용하세요.")
    except Exception as e:
        st.error(f"PDF/docx 모두 실패: {e}")


def _figures_list() -> list[dict]:
    """data/exports의 Figure*.png 자동 수집."""
    items = []
    if not _FIG_DIR.exists():
        return items
    for p in sorted(_FIG_DIR.glob("Figure*.png")):
        items.append({"path": str(p), "name": p.name})
    return items


def _render_chat_event(m: dict, *, idx: int = 0):
    """user/assistant/tool_use/tool_result/system — rich content 양식 분기 렌더.
    VS Code less/more 양식: 긴 콘텐츠는 collapsible <details>로 접고 펴기.
    짧은 것(<300자, default tool_use)은 그대로 표시."""
    role = m.get("role", "system")
    if role == "user":
        _collapsible_bubble("user", m.get("content", ""), idx=idx, threshold=400)
        return
    if role == "assistant":
        if m.get("content"):
            _collapsible_bubble("assistant", m["content"], idx=idx, threshold=400)
        return
    if role == "tool_use":
        _render_tool_use(m)   # 자체로 짧음 — 그대로
        return
    if role == "tool_result":
        _render_tool_result(m, idx=idx)
        return
    if role == "system":
        _render_system_event(m, idx=idx)


def _collapsible_bubble(role: str, text: str, *, idx: int, threshold: int = 400):
    """긴 메시지는 <details> 양식으로 접기 (less/more 토글)."""
    import html as _html
    if not text:
        return
    cls = "sg-msg-user" if role == "user" else "sg-msg-assistant"
    safe = _html.escape(text).replace("\n", "<br/>")
    if len(text) <= threshold:
        st.markdown(f"<div class='{cls}'>{safe}</div>", unsafe_allow_html=True)
        return
    head = _html.escape(text[:threshold].rstrip()).replace("\n", "<br/>")
    body = _html.escape(text[threshold:]).replace("\n", "<br/>")
    st.markdown(
        f"<div class='{cls}'>"
        f"<details><summary style='cursor:pointer;list-style:none;'>"
        f"{head}<span style='color:#A78BFA;font-size:0.78rem;'> …more ▾</span>"
        f"</summary>"
        f"<div style='margin-top:6px;'>{body}</div>"
        f"</details></div>", unsafe_allow_html=True)


def _render_tool_use(m: dict):
    tool = m.get("tool", "?")
    inputs = m.get("input", {}) or {}
    icon_map = {"patch_preview": "📝", "kyrbs_stat": "📊",
                 "pubmed_search": "🔬", "strobe_check": "📑",
                 "consistency_check": "🔍", "rag_search": "🧠"}
    icon = icon_map.get(tool, "🛠️")
    # 짧은 핵심 input만 헤더에
    head = ""
    if tool == "patch_preview":
        tgt = (inputs.get("section") or inputs.get("abstract_field")
                or inputs.get("supplement_block") or "?")
        head = f"→ {tgt}"
    elif tool == "kyrbs_stat":
        head = f"{inputs.get('exposure', '?')} → {inputs.get('outcome', '?')}"
    elif tool == "pubmed_search":
        head = inputs.get("query", "")[:60]
    elif tool == "rag_search":
        head = inputs.get("query", "")[:60]
    st.markdown(
        f"<div class='sg-action-card' style='border-color:rgba(6,182,212,0.45);"
        f"background:rgba(6,182,212,0.10);margin:6px 0;'>"
        f"<div class='sg-icon'>{icon}</div>"
        f"<div class='sg-detail'>"
        f"<div class='sg-title'>tool_use · <code style='color:#06B6D4;'>{tool}</code> "
        f"<span style='color:#A3A3B8;font-weight:400;'>{head}</span></div>"
        f"<div class='sg-sub'><code style='font-size:0.74rem;color:#6B6B7E;'>"
        f"{json.dumps(inputs, ensure_ascii=False)[:260]}</code></div>"
        f"</div></div>", unsafe_allow_html=True)


def _render_tool_result(m: dict, *, idx: int = 0):
    """tool 종류별 rich 시각화 — metric card / figure thumb / paper list / raw.
    raw fallback은 collapsible (긴 결과 less/more)."""
    import html as _html
    tool = m.get("tool", "")
    raw = m.get("content", "") or ""
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        pass

    if tool == "kyrbs_stat" and isinstance(parsed, dict) and parsed.get("aOR") is not None:
        _render_metric_stat(parsed)
        return
    if tool == "pubmed_search" and isinstance(parsed, dict) and parsed.get("similar_papers"):
        _render_paper_list(parsed)
        return
    if tool == "rag_search" and isinstance(parsed, list):
        _render_rag_hits(parsed)
        return

    # default — collapsible if long
    head = raw[:300]
    tail = raw[300:1500]
    body_html = (
        f"<div class='sg-sub' style='white-space:pre-wrap;'>{_html.escape(head)}</div>"
        if len(raw) <= 300 else
        f"<div class='sg-sub' style='white-space:pre-wrap;'>"
        f"<details><summary style='cursor:pointer;list-style:none;color:#10B981;'>"
        f"{_html.escape(head)}<span style='color:#A78BFA;font-size:0.78rem;'> …more ▾</span>"
        f"</summary><div style='margin-top:6px;'>{_html.escape(tail)}</div></details>"
        f"</div>"
    )
    st.markdown(
        f"<div class='sg-action-card' style='border-color:rgba(16,185,129,0.40);"
        f"background:rgba(16,185,129,0.08);margin:6px 0;'>"
        f"<div class='sg-icon'>📥</div>"
        f"<div class='sg-detail'>"
        f"<div class='sg-title'>tool_result · <code style='color:#10B981;'>{tool or '?'}</code></div>"
        f"{body_html}"
        f"</div></div>", unsafe_allow_html=True)


def _render_metric_stat(d: dict):
    """kyrbs_stat 결과 — 메트릭 카드 (aOR + 95% CI + P)."""
    aor = d.get("aOR")
    lo = d.get("ci_low")
    hi = d.get("ci_high")
    p = d.get("p_value")
    n = d.get("n", 0)
    exposure = d.get("exposure", "?")
    outcome = d.get("outcome", "?")
    design = d.get("design", "")
    p_fmt = "< 0.001" if (p is not None and p < 0.001) else (f"= {p:.3f}" if p is not None else "?")
    st.markdown(
        f"<div class='sg-card' style='border:1px solid rgba(59,130,246,0.50);"
        f"background:linear-gradient(135deg, rgba(59,130,246,0.10), rgba(139,92,246,0.10));'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;'>"
        f"<div style='color:#A3A3B8;font-size:0.78rem;'>📊 KYRBS stat — {exposure} → {outcome}</div>"
        f"<div style='color:#6B6B7E;font-size:0.72rem;'>n={n:,} · {design}</div></div>"
        f"<div style='margin-top:10px;color:#F5F5FA;font-size:1.6rem;font-weight:700;'>"
        f"aOR {aor:.3f} "
        f"<span style='color:#A78BFA;font-size:0.85rem;font-weight:500;'>"
        f"(95% CI {lo:.3f}–{hi:.3f}; <i>P</i> {p_fmt})</span></div>"
        f"</div>", unsafe_allow_html=True)


def _render_paper_list(d: dict):
    """pubmed_search 결과 — 논문 카드 리스트."""
    score = d.get("novelty_score", "?")
    summary = (d.get("summary") or "")[:300]
    papers = d.get("similar_papers", [])[:6]
    rows = "".join(
        f"<div style='border-top:1px solid rgba(255,255,255,0.08);padding:8px 0;'>"
        f"<div style='font-weight:600;color:#F5F5FA;font-size:0.88rem;'>"
        f"{p.get('title', '?')[:120]}</div>"
        f"<div style='color:#A3A3B8;font-size:0.76rem;'>"
        f"{p.get('year', '?')} · {(p.get('authors') or '')[:80]}</div>"
        f"</div>" for p in papers)
    st.markdown(
        f"<div class='sg-card' style='border:1px solid rgba(167,139,250,0.40);'>"
        f"<div style='display:flex;justify-content:space-between;'>"
        f"<div style='font-weight:600;color:#F5F5FA;'>🔬 PubMed novelty</div>"
        f"<div style='color:#A78BFA;font-weight:600;'>score: {score}</div></div>"
        f"<div style='color:#A3A3B8;font-size:0.86rem;margin:8px 0;'>{summary}</div>"
        f"{rows}</div>", unsafe_allow_html=True)


def _render_rag_hits(hits: list):
    """rag_search 결과 — 상위 hit 미니 카드."""
    rows = ""
    for h in hits[:5]:
        text = (h.get("text") or "")[:180]
        score = h.get("score") or h.get("final_score") or 0
        md = h.get("metadata") or {}
        src = md.get("source") or md.get("doi") or md.get("pmid") or "—"
        rows += (
            f"<div style='border-top:1px solid rgba(255,255,255,0.08);padding:8px 0;'>"
            f"<div style='font-size:0.84rem;color:#F5F5FA;'>{text}…</div>"
            f"<div style='color:#A3A3B8;font-size:0.72rem;'>score={score:.3f} · {src}</div>"
            f"</div>")
    st.markdown(
        f"<div class='sg-card' style='border:1px solid rgba(6,182,212,0.40);'>"
        f"<div style='font-weight:600;color:#F5F5FA;'>🧠 RAG retrieval (top {len(hits)})</div>"
        f"{rows}</div>", unsafe_allow_html=True)


def _render_system_event(m: dict, *, idx: int = 0):
    """system event — preview_patched 시 before/after diff (이미 collapsible 내장)."""
    import html as _html
    event = m.get("event", "system")
    detail = m.get("detail", "")
    parsed = None
    if isinstance(detail, str):
        try:
            parsed = json.loads(detail)
        except Exception:
            parsed = None

    if event == "preview_patched" and isinstance(parsed, dict):
        _render_patch_diff(parsed)
        return

    s = str(detail or "")
    body = (f"<div class='sg-sub' style='white-space:pre-wrap;'>{_html.escape(s[:300])}</div>"
             if len(s) <= 300 else
             f"<div class='sg-sub' style='white-space:pre-wrap;'>"
             f"<details><summary style='cursor:pointer;list-style:none;color:#A78BFA;'>"
             f"{_html.escape(s[:300])}<span style='font-size:0.78rem;'> …more ▾</span>"
             f"</summary><div style='margin-top:6px;'>{_html.escape(s[300:2000])}</div>"
             f"</details></div>")
    st.markdown(
        f"<div class='sg-action-card' style='border-color:rgba(124,58,237,0.40);"
        f"background:rgba(124,58,237,0.08);margin:6px 0;'>"
        f"<div class='sg-icon'>⚙️</div>"
        f"<div class='sg-detail'>"
        f"<div class='sg-title'>{event}</div>"
        f"{body}"
        f"</div></div>", unsafe_allow_html=True)


def _render_patch_diff(d: dict):
    """patch_preview의 before/after diff — VS Code 양식 (added 강조)."""
    import html as _html
    target = d.get("target", "?")
    before = (d.get("before") or "").strip()
    after = (d.get("after") or "").strip()
    added = (d.get("added") or "").strip()
    head = (
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;'>"
        f"<div style='font-weight:600;color:#F5F5FA;'>📝 Preview patched · "
        f"<code style='color:#A78BFA;'>{target}</code></div>"
        f"<div style='color:#A3A3B8;font-size:0.74rem;'>"
        f"before {len(before)} → after {len(after)} chars</div></div>")

    body = ""
    if added:
        body += (
            f"<div style='margin-top:8px;background:rgba(16,185,129,0.10);"
            f"border-left:3px solid #10B981;padding:8px 12px;border-radius:6px;"
            f"font-family:Consolas,monospace;font-size:0.80rem;color:#A7F3D0;"
            f"white-space:pre-wrap;'>+ {_html.escape(added[:600])}</div>")
    if before and before != after:
        body += (
            f"<details style='margin-top:6px;'><summary style='cursor:pointer;color:#A3A3B8;"
            f"font-size:0.78rem;'>Before/After 전체 보기</summary>"
            f"<div style='margin-top:6px;background:rgba(244,63,94,0.06);"
            f"border-left:3px solid #FB7185;padding:8px 12px;border-radius:6px;"
            f"font-family:Consolas,monospace;font-size:0.76rem;color:#FECDD3;"
            f"white-space:pre-wrap;'>- {_html.escape(before[-500:])}</div>"
            f"<div style='margin-top:4px;background:rgba(16,185,129,0.06);"
            f"border-left:3px solid #10B981;padding:8px 12px;border-radius:6px;"
            f"font-family:Consolas,monospace;font-size:0.76rem;color:#A7F3D0;"
            f"white-space:pre-wrap;'>+ {_html.escape(after[-500:])}</div>"
            f"</details>")

    st.markdown(
        f"<div class='sg-card' style='border:1px solid rgba(124,58,237,0.40);'>"
        f"{head}{body}</div>", unsafe_allow_html=True)


def _render_chat_left(project: dict, pid: str):
    """좌측 chat panel — VS Code/Claude Code 양식.
    user/assistant/tool_use/tool_result/system 모두 시간순 표시."""
    st.markdown("<div style='font-size:0.78rem;color:#A3A3B8;margin:4px 0 8px 4px;'>"
                f"{project.get('updated', 'today')}</div>", unsafe_allow_html=True)

    messages = project.get("messages", [])
    initial = st.session_state.pop("sg_initial_prompt", None)
    # ★ 유기적 흐름 (2026-05-30): ez_home에서 prompt 받고 workspace 진입 시 자동으로 agentic loop
    # 실행해서 첫 응답까지 한 번에. 사용자가 두 번 입력할 필요 없음. [[feedback-vibe-paper]] 정신.
    if initial and not messages:
        messages.append({"role": "user", "content": initial})
        project["messages"] = messages
        _save_project(pid, project)
        st.session_state["_ws_auto_run_pending"] = initial   # 이번 rerun에서 agentic step 실행
    # 미완 작업: 직전 rerun에 _ws_auto_run_pending이 set돼 있으면 양식 자동 실행
    # _orchestrated_paper_run 호출 — KYRBS 로드 → StatBridge → 5섹션 자동 작성 → safety 게이트
    auto_run = st.session_state.pop("_ws_auto_run_pending", None)
    if auto_run:
        with st.spinner("✨ 논문 초안 생성 중… (KYRBS 로드 → StatBridge 회귀 → 5섹션 작성 → safety 게이트)"):
            try:
                _orchestrated_paper_run(auto_run, project, pid)
            except Exception as _e:
                import traceback as _tb
                project["messages"].append({"role": "system", "event": "auto_run_error",
                                              "detail": f"{_e}\n{_tb.format_exc()[:400]}"})
                _save_project(pid, project)
        st.rerun()

    # 너무 많으면 앞쪽은 expander 안에 — 페이지 길이/렌더 시간 제어
    _RECENT_CAP = 80
    if len(messages) > _RECENT_CAP:
        older = messages[:-_RECENT_CAP]
        recent = messages[-_RECENT_CAP:]
        archived = project.get("_archived_msgs_count", 0)
        with st.expander(f"📁 이전 메시지 {len(older):,}개 + archive {archived:,}개 (펼치기)"):
            st.caption("archive: data/working_papers/_archive/{pid}_msgs.jsonl")
            for i, m in enumerate(older):
                _render_chat_event(m, idx=i)
        st.markdown("---")
        for i, m in enumerate(recent, start=len(older)):
            _render_chat_event(m, idx=i)
    else:
        for i, m in enumerate(messages):
            _render_chat_event(m, idx=i)

    # 입력 form — 파일 첨부 포함
    with st.form(key="ws_form", clear_on_submit=True):
        prompt = st.text_area("ask",
                               placeholder="Ask Medical-Agent… (LLM이 tool을 직접 호출해 preview를 갱신합니다)\n"
                                           "💡 파일 첨부 시 자동으로 백로그에 등록됩니다.",
                               label_visibility="collapsed", height=80)
        uploaded = st.file_uploader(
            "📎 파일 첨부 (참고 논문/이미지) — heavy 작업은 백로그 처리",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "sav", "csv", "xlsx"],
            accept_multiple_files=True, key="ws_files",
            label_visibility="visible")
        c1, c2, c3 = st.columns([5, 2, 1])
        with c1:
            mode = st.selectbox("mode",
                                 ["✨ Build (자유 작성)",
                                  "🔬 Yoosun 스타일 재작성",
                                  "📊 KYRBS 통계 보강",
                                  "📑 STROBE 체크"],
                                 label_visibility="collapsed")
        with c2:
            use_tools = st.checkbox("🛠️ Tool-use", value=True,
                                     help="LLM이 직접 patch_preview/kyrbs_stat 등 tool을 호출")
        with c3:
            sent = st.form_submit_button("➤", use_container_width=True, type="primary")

    if sent and (prompt or uploaded):
        # 1) 첨부 → 백로그 (비동기 처리)
        if uploaded:
            _enqueue_workspace_uploads(uploaded, prompt_hint=prompt)
        # 2) prompt 가 있으면 agentic loop 실행
        if prompt:
            # ★ 무의식 임프린트 — 사용자 prompt 진입 시점에 intent 발화 (이후 모든 LLM 호출 자동 픽업)
            try:
                from src.agent.intent_sensor import sense_and_imprint
                _owner = (st.session_state.get("user") or {}).get("email") or \
                          st.session_state.get("user_email", "")
                sense_and_imprint(prompt,
                                   prior_messages=messages,
                                   project=project, owner_email=_owner)
            except Exception:
                pass
            messages.append({"role": "user", "content": prompt})
            project["messages"] = messages
            _save_project(pid, project)
            if use_tools:
                _run_agentic_step(prompt, project, pid, mode)
            else:
                reply = _delegate_to_writer(prompt, project, mode)
                messages.append({"role": "assistant",
                                  "content": reply.get("content", "")})
                project["messages"] = messages
                _save_project(pid, project)
        st.rerun()


def _enqueue_workspace_uploads(uploaded_files, prompt_hint: str = "") -> None:
    """workspace 첨부 → backlog. lovable_home의 _enqueue_uploaded_files 와 동일 동작."""
    from pathlib import Path as _P
    upload_dir = _P("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        from src.runtime.backlog import enqueue
    except Exception as e:
        st.error(f"backlog import 실패: {e}")
        return
    owner = st.session_state.get("user_email", "")
    n_p, n_v = 0, 0
    for f in uploaded_files:
        target = upload_dir / f.name
        try:
            target.write_bytes(f.getbuffer())
        except Exception as e:
            st.warning(f"저장 실패 {f.name}: {e}")
            continue
        ext = target.suffix.lower()
        if ext in (".pdf", ".docx", ".txt"):
            enqueue("paper_ingest",
                     {"path": str(target), "filename": f.name, "hint": prompt_hint[:300]},
                     owner=owner)
            n_p += 1
        elif ext in (".png", ".jpg", ".jpeg"):
            enqueue("vision_check",
                     {"path": str(target), "filename": f.name},
                     owner=owner)
            n_v += 1
    if n_p or n_v:
        st.toast(f"📥 백로그 등록: 논문 {n_p}편 · 이미지 {n_v}장", icon="✅")


def _build_prior_context(messages: list, k: int = 8) -> str:
    """직전 K개 user/assistant/tool 메시지를 압축해 LLM 컨텍스트로 묶음.
    시스템 이벤트는 압축 표시. (2026-05-30 — 세션 흐름 끊김 차단)
    """
    if not messages:
        return ""
    recent = messages[-k:]
    lines = ["# PRIOR CONVERSATION IN THIS PROJECT (직전 대화 — 흐름 유지)",
             ""]
    for m in recent:
        role = m.get("role", "system")
        if role == "user":
            lines.append(f"USER: {str(m.get('content',''))[:600]}")
        elif role == "assistant":
            c = str(m.get("content", "") or "")
            if c.strip():
                lines.append(f"ASSISTANT: {c[:800]}")
        elif role == "tool_use":
            t = m.get("tool", "?")
            inp = json.dumps(m.get("input", {}), ensure_ascii=False, default=str)[:200]
            lines.append(f"TOOL_USE [{t}]: {inp}")
        elif role == "tool_result":
            t = m.get("tool", "?")
            res = str(m.get("content", ""))[:300]
            lines.append(f"TOOL_RESULT [{t}]: {res}")
        elif role == "system":
            ev = m.get("event", "system")
            det = str(m.get("detail", ""))[:200]
            lines.append(f"SYSTEM [{ev}]: {det}")
    lines.append("")
    return "\n".join(lines)


def _run_agentic_step(prompt: str, project: dict, pid: str, mode: str):
    """★ Agentic loop — LLM이 tool을 직접 호출해 preview를 갱신.
    각 step(assistant text / tool_use / tool_result / system)을 chat에 시간순 기록.
    실패해도 UX는 살아있게 system 이벤트로 남김.

    2026-05-30 fix — 세션 흐름 끊김 차단:
      (a) build_system_with_preview에 user_msg 전달 → trigger/cognitive/5층메모리 활성
      (b) 직전 N개 messages를 prior_ctx로 묶어 user_message에 주입 → ClaudeClient single-turn 한계 우회
    """
    try:
        from src.llm.claude_client import ClaudeClient
        from src.agent.prompt_loader import load_prompt
        from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler, build_system_with_preview

        messages = project["messages"]

        def get_project():
            return project

        def set_project(p):
            project.update(p)
            _save_project(pid, project)

        def append_chat_event(ev_type: str, payload: dict):
            messages.append({"role": "system", "event": ev_type,
                              "detail": json.dumps(payload, ensure_ascii=False)[:280]})

        handler = make_tool_handler(get_project, set_project, append_chat_event)

        base_system = load_prompt("paper_write")
        # ★ user_msg 전달 — build_system_with_preview의 trigger_analyzer/cognitive_activation/
        #   recall_all_layers/conversation_memory.recall_relevant 활성화 (이전엔 다 skip됐음)
        system = build_system_with_preview(
            base_system + f"\n\nMode: {mode}.", project, user_msg=prompt)

        cc = ClaudeClient(task="paper_writing")
        # ★ 직전 대화를 user_message에 묶어 주입 — ClaudeClient single-turn 한계 우회
        prior_ctx = _build_prior_context(messages[:-1], k=8)  # 방금 추가된 user 메시지 제외
        user_msg = (prior_ctx + "\n\n# CURRENT REQUEST\n" + prompt) if prior_ctx else prompt

        result = cc.generate_with_tools(
            user_message=user_msg, tools=TOOL_SCHEMAS,
            tool_handler=handler, system_prompt=system,
            max_tokens=3000, max_iters=10, task="paper_writing",
        )
        # ★ patch_preview가 0회 호출됐으면 폴백: _delegate_to_writer로 한 번 더 시도해 본문 보강
        trace = result.get("trace") or []
        patch_calls = sum(1 for s in trace if s.get("tool") == "patch_preview")
        if patch_calls == 0:
            messages.append({"role": "system", "event": "no_patch_fallback",
                              "detail": "patch_preview 0회 → 폴백 본문 보강 시도"})
            try:
                fallback = _delegate_to_writer(prompt, project, mode)
                # 폴백 응답을 Discussion에 append (가장 무난한 곳)
                sections = project.get("sections") or {}
                old = sections.get("Discussion") or ""
                new_text = str(fallback.get("content", ""))
                if new_text.strip():
                    sections["Discussion"] = (str(old) + "\n\n" + new_text).strip()
                    project["sections"] = sections
                    _save_project(pid, project)
            except Exception:
                pass

        # trace를 chat에 시간순 기록
        for step in result.get("trace", []):
            messages.append({"role": "tool_use",
                              "tool": step.get("tool"),
                              "input": step.get("input", {})})
            messages.append({"role": "tool_result",
                              "tool": step.get("tool"),
                              "content": step.get("result_preview", "")})
        # 최종 assistant text
        text = (result.get("text") or "").strip()
        if text:
            messages.append({"role": "assistant", "content": text})
        else:
            messages.append({"role": "system", "event": "no_text",
                              "detail": f"stop_reason={result.get('stop_reason')} iters={result.get('iters')}"})
        project["messages"] = messages
        _save_project(pid, project)

        # ★ 자가학습 — chat의 user/assistant 교환을 memory.router로 흘려보냄
        _wire_memory(prompt, text, project)
    except Exception as e:
        import traceback
        project["messages"].append({"role": "system", "event": "agentic_error",
                                      "detail": f"{e}\n\n{traceback.format_exc()[:500]}"})
        _save_project(pid, project)


def _wire_memory(user_msg: str, assistant_text: str, project: dict) -> None:
    """chat 교환을 자가학습 파이프라인에 연결:
    1) `conversation_memory.record` — ChromaDB 의미검색 색인 (recall_relevant)
    2) `memory.router.write` — typed memory (gate + scorer + lifecycle)
    """
    owner = str(project.get("owner") or "anonymous")
    title = str(project.get("title") or "")[:80]
    try:
        from src.memory import conversation_memory as cm
        if user_msg or assistant_text:
            cm.record(
                user_message=(user_msg or "")[:600],
                agent_response=(assistant_text or "")[:1500],
                topic=title or "paper",
                context_type="research",
                owner_email=owner,
            )
    except Exception:
        pass
    try:
        from src.memory.router import write as mem_write
        if assistant_text and len(assistant_text) > 60:
            mem_write(
                text=assistant_text[:1500],
                kind="episodic",
                source="paper_agentic",
                owner=owner,
                extra_meta={"project_title": title,
                             "grounded_in_data": True},
            )
    except Exception:
        pass


def _delegate_to_writer(prompt: str, project: dict, mode: str) -> dict:
    """단순 one-shot LLM 호출 (tool-use OFF일 때). 실패 시 graceful.
    2026-05-30 — build_system_with_preview에 user_msg + 직전 대화 컨텍스트 함께 주입."""
    try:
        from src.llm import get_llm_client
        from src.agent.prompt_loader import load_prompt
        from app.agentic_loop import build_system_with_preview
        base = load_prompt("paper_write")
        sys_prompt = build_system_with_preview(
            base + f"\n\nMode: {mode}.", project, user_msg=prompt)
        prior_ctx = _build_prior_context(project.get("messages", [])[:-1], k=8)
        user_msg = (prior_ctx + "\n\n# CURRENT REQUEST\n" + prompt) if prior_ctx else prompt
        client = get_llm_client(task="paper_writing")
        out = client.generate(user_msg, system_prompt=sys_prompt, max_tokens=1500)
        return {"content": out[:2000]}
    except Exception as e:
        return {"content": f"⚠️ LLM 호출 실패: {e}"[:300]}


def _render_preview_right(project: dict):
    """우측 preview tab bar + 내용 (2026-05-30: References 탭 추가)."""
    tab = st.session_state.get("sg_active_tab", "Manuscript")
    tabs = st.tabs(["📄 Manuscript", "📊 Figures", "🧮 Tables",
                    "📚 References", "📎 Supplement"])

    with tabs[0]:
        sections = project.get("sections") or _demo_sections()
        topic = project.get("topic") or {"title": project.get("title", "Manuscript draft")}
        html = manuscript_preview_html(
            title=topic.get("title", "Untitled"),
            authors=topic.get("authors", ["Yoosun Cho"]),
            abstract=sections.get("Abstract", ""),
            keywords=project.get("keywords", []),
            sections=sections,
        )
        st.markdown(html, unsafe_allow_html=True)

    with tabs[1]:
        figures = _figures_list()
        if not figures:
            st.markdown("<div class='sg-card' style='text-align:center;color:#A3A3B8;'>"
                         "data/exports/Figure*.png 없음 — `scripts/build_paper_figures.py` 실행 후 표시"
                         "</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(2)
            for i, f in enumerate(figures):
                with cols[i % 2]:
                    st.markdown(f"<div class='sg-card'>", unsafe_allow_html=True)
                    st.image(f["path"], caption=f["name"], use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    with tabs[2]:
        tables = project.get("tables", [])
        if not tables:
            st.markdown("<div class='sg-card' style='color:#A3A3B8;'>"
                         "Table 데이터 없음 — Chat에서 'KYRBS 통계 보강'으로 생성"
                         "</div>", unsafe_allow_html=True)
        else:
            for t in tables:
                st.markdown(
                    f"<div class='sg-card'><div style='font-weight:600;margin-bottom:8px;'>"
                    f"Table {t.get('n', '')}. {t.get('caption', '')}</div></div>",
                    unsafe_allow_html=True)
                st.json(t.get("data", []))

    with tabs[3]:
        # ── References 탭 (2026-05-30 신규) ──
        st.markdown("<div class='sg-card'>", unsafe_allow_html=True)
        st.markdown("**📚 Reference Library**")
        refs = project.get("references", []) or []
        st.caption(f"등록된 인용: **{len(refs)}**개 · Vancouver 양식 자동")

        # 현재 references 표시
        if refs:
            for i, r in enumerate(refs, 1):
                title = r.get("title", "") or "(no title)"
                authors = ", ".join(r.get("authors", [])[:3])
                if len(r.get("authors", [])) > 3:
                    authors += " et al."
                year = r.get("year", "")
                journal = r.get("journal", "")
                pmid = r.get("pmid", "")
                doi = r.get("doi", "")
                st.markdown(
                    f"<div style='border-top:1px solid rgba(255,255,255,0.08);padding:8px 0;'>"
                    f"<div style='color:#F5F5FA;font-size:0.88rem;'>"
                    f"<b>[{i}]</b> {title[:200]}</div>"
                    f"<div style='color:#A3A3B8;font-size:0.76rem;'>"
                    f"{authors} · {journal} {year}"
                    f"{f' · PMID:{pmid}' if pmid else ''}"
                    f"{f' · DOI:{doi}' if doi else ''}</div></div>",
                    unsafe_allow_html=True)
        else:
            st.info("아직 등록된 인용이 없습니다. 아래로 PubMed에서 자동 검색하거나 PMID를 추가하세요.")
        st.markdown("</div>", unsafe_allow_html=True)

        # PubMed 검색 + 추가 + 본문 [n] 자동 삽입
        st.markdown("<div class='sg-card' style='margin-top:12px;'>", unsafe_allow_html=True)
        st.markdown("**+ 인용 추가**")
        c1, c2 = st.columns([3, 1])
        with c1:
            pq = st.text_input("PubMed 검색어", key="ws_ref_q",
                                placeholder="예: zero-calorie beverage depression adolescent")
        with c2:
            pn = st.number_input("결과 수", 3, 30, 8, key="ws_ref_n")
        if st.button("🔍 PubMed 검색 → 자동 추가", type="primary", key="ws_ref_search"):
            try:
                from src.export.reference_library import ReferenceLibrary
                slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                lib = ReferenceLibrary(paper_slug=slug)
                # 기존 refs 양식 동기화
                for r in refs:
                    lib.add_from_dict(r)
                added = lib.search_and_add(pq, max_results=int(pn))
                lib.save()
                # project 양식 다시 반영
                project["references"] = [r.to_dict() for r in lib.get_refs()]
                _save_project(pid, project)
                st.success(f"✓ {added}개 인용 추가 → 총 {len(lib)}개")
                st.rerun()
            except Exception as e:
                st.error(f"검색 실패: {e}")

        pmid_in = st.text_input("PMID 직접 (쉼표/공백 구분)", key="ws_ref_pmid",
                                  placeholder="39012345, 38991234")
        if st.button("➕ PMID로 추가", key="ws_ref_pmid_add"):
            try:
                from src.export.reference_library import ReferenceLibrary
                slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                lib = ReferenceLibrary(paper_slug=slug)
                for r in refs:
                    lib.add_from_dict(r)
                import re as _re3
                pmids = [p for p in _re3.split(r"[,\s]+", pmid_in) if p.strip().isdigit()]
                added = lib.add_from_pmids(pmids)
                lib.save()
                project["references"] = [r.to_dict() for r in lib.get_refs()]
                _save_project(pid, project)
                st.success(f"✓ {added}개 추가")
                st.rerun()
            except Exception as e:
                st.error(f"추가 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        # ✨ Style polish — AI cliché 정리 + AI score 표시
        st.markdown("<div class='sg-card' style='margin-top:12px;'>", unsafe_allow_html=True)
        st.markdown("**✨ Style Polish (학술 cliché 정리)**")
        try:
            from src.safety.style_polish import ai_style_score, polish_paper
            sec_check = project.get("sections") or {}
            txt = "\n\n".join(str(v) for v in sec_check.values() if isinstance(v, str))
            if txt.strip():
                rep_now = ai_style_score(txt)
                cls = ("#10B981" if rep_now.ai_style_score <= 20
                       else "#F59E0B" if rep_now.ai_style_score <= 50 else "#F43F5E")
                st.markdown(
                    f"<div style='display:flex;gap:24px;align-items:center;'>"
                    f"<div><div style='color:#A3A3B8;font-size:0.74rem;'>AI 양식 점수 (낮을수록 자연스러움)</div>"
                    f"<div style='color:{cls};font-size:1.6rem;font-weight:700;'>{rep_now.ai_style_score} / 100</div></div>"
                    f"<div style='color:#A3A3B8;font-size:0.78rem;'>"
                    f"cliche {rep_now.overused_vocab_count}개 · em-dash {rep_now.em_dash_per_1k_words}/1k · "
                    f"burstiness {rep_now.burstiness}</div></div>",
                    unsafe_allow_html=True)
                cps1, cps2 = st.columns(2)
                with cps1:
                    if st.button("✨ Gentle polish (안전)", key="ws_polish_gentle",
                                  use_container_width=True):
                        project["sections"] = polish_paper(sec_check, mode="gentle")
                        _save_project(pid, project)
                        st.success("✓ Gentle polish 적용 — cliche 제거 + 전환어 다양화")
                        st.rerun()
                with cps2:
                    if st.button("⚡ Aggressive (em-dash 정규화)", key="ws_polish_aggr",
                                  use_container_width=True):
                        project["sections"] = polish_paper(sec_check, mode="aggressive")
                        _save_project(pid, project)
                        st.success("✓ Aggressive polish 적용")
                        st.rerun()
        except Exception as _e:
            st.caption(f"style polish unavailable: {_e}")
        st.markdown("</div>", unsafe_allow_html=True)

        # 본문 [n] 자동 삽입 + Export 모음
        st.markdown("<div class='sg-card' style='margin-top:12px;'>", unsafe_allow_html=True)
        st.markdown("**🔗 본문 인용 연동 + Export**")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📝 본문에 [n] 자동 삽입", key="ws_ref_inline", use_container_width=True):
                try:
                    from src.export.reference_library import (
                        ReferenceLibrary, insert_inline_citations,
                    )
                    slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                    lib = ReferenceLibrary(paper_slug=slug)
                    for r in refs:
                        lib.add_from_dict(r)
                    sections = project.get("sections") or {}
                    for sec_name in ("Introduction", "Methods", "Results", "Discussion"):
                        body = sections.get(sec_name)
                        if isinstance(body, str) and body.strip():
                            sections[sec_name] = insert_inline_citations(body, lib)
                    project["sections"] = sections
                    _save_project(pid, project)
                    st.success("✓ 본문에 [n] 인용 삽입 완료")
                    st.rerun()
                except Exception as e:
                    st.error(f"삽입 실패: {e}")
        with col_b:
            if refs:
                try:
                    from src.export.reference_library import ReferenceLibrary
                    slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                    lib = ReferenceLibrary(paper_slug=slug)
                    for r in refs:
                        lib.add_from_dict(r)
                    formatted = lib.format_list("Vancouver")
                    st.download_button(
                        "⬇ Vancouver 목록 (.txt)",
                        data=formatted.encode("utf-8"),
                        file_name=f"{slug}_refs.txt", mime="text/plain",
                        use_container_width=True, key="ws_ref_dl_txt")
                except Exception:
                    pass
        # EndNote XML + BibTeX
        col_c, col_d = st.columns(2)
        with col_c:
            if refs:
                try:
                    from src.export.reference_library import ReferenceLibrary
                    slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                    lib = ReferenceLibrary(paper_slug=slug)
                    for r in refs:
                        lib.add_from_dict(r)
                    xml_str = lib.export_endnote_xml()
                    st.download_button(
                        "⬇ EndNote XML",
                        data=xml_str.encode("utf-8"),
                        file_name=f"{slug}.xml", mime="application/xml",
                        use_container_width=True, key="ws_ref_dl_xml")
                except Exception:
                    pass
        with col_d:
            if refs:
                try:
                    from src.export.reference_library import ReferenceLibrary
                    slug = (project.get("topic") or {}).get("title", pid)[:60] or pid
                    lib = ReferenceLibrary(paper_slug=slug)
                    for r in refs:
                        lib.add_from_dict(r)
                    bib_str = lib.export_bibtex()
                    st.download_button(
                        "⬇ BibTeX",
                        data=bib_str.encode("utf-8"),
                        file_name=f"{slug}.bib", mime="text/plain",
                        use_container_width=True, key="ws_ref_dl_bib")
                except Exception:
                    pass
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[4]:
        # Supplement: STROBE 체크리스트 + Stata do-file + consistency report
        st.markdown("<div class='sg-card'>", unsafe_allow_html=True)
        st.markdown("**STROBE Reporting Checklist**")
        try:
            from src.research.reporting_checklist import check_strobe, format_checklist_report
            checklist = check_strobe(project.get("sections") or _demo_sections())
            st.code(format_checklist_report(checklist, verbose=True), language=None)
        except Exception as e:
            st.warning(f"STROBE 체크 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sg-card' style='margin-top:12px;'>", unsafe_allow_html=True)
        st.markdown("**Internal consistency**")
        try:
            from src.safety.consistency_checker import check_consistency
            rep = check_consistency(project.get("sections") or _demo_sections())
            color = {"ok": "#10B981", "warn": "#F59E0B", "fail": "#F43F5E"}[rep.severity]
            st.markdown(f"<span style='color:{color};font-weight:600;'>severity = {rep.severity}</span> "
                         f"({len(rep.issues)} issues)", unsafe_allow_html=True)
            if rep.issues:
                for it in rep.issues[:5]:
                    st.markdown(f"- {it.type}: {it.detail}")
        except Exception as e:
            st.warning(f"consistency 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)


def _empty_sections_notice() -> dict:
    """아직 분석이 안 됐을 때 보여줄 안내 (예전엔 _demo_sections로 가짜 ZCB 양식 보임 → 사용자가
    'Abstract만 나옴, 날림 양식'으로 혼동. 2026-05-30: 안내로 교체)."""
    notice = ("아직 본문이 생성되지 않았습니다. 입력바에 연구 아이디어를 적고 ✨ Build를 누르면 "
              "(1) KYRBS 데이터 자동 로드 → (2) 통계 분석(StatBridge) → "
              "(3) 5섹션(Abstract/Intro/Methods/Results/Discussion) 자동 작성 → "
              "(4) safety 게이트 통과 후 이 영역에 채워집니다.")
    return {
        "Abstract": {"Background": notice, "Methods": "", "Results": "", "Conclusion": ""},
        "Introduction": "",
        "Methods": "",
        "Results": "",
        "Discussion": "",
    }


# 역호환: 외부에서 _demo_sections로 import하는 곳 차단을 위해 alias 유지하지 않음.
# (전 grep 결과 _demo_sections는 같은 파일 안에서만 호출돼서 안전)


def _orchestrated_paper_run(prompt: str, project: dict, pid: str) -> str:
    """진짜 유기적 논문 생성 (2026-05-30 근본 수정).
    StatBridge 통계 → PaperWriter 5섹션 → project.sections + chat 결과 메시지.

    agentic_loop의 tool-use 양식이 아닌, 결과 보장 양식. agentic_loop는 후속 보강용.

    Returns: 최종 pid (입력이 'new'면 paper_{timestamp}로 자동 변환된 새 pid)
    """
    import traceback, time as _time
    from pathlib import Path as _P

    # ★ pid="new" 저장 구멍 우회 — _save_project가 pid=='new'면 즉시 return해서 디스크 저장 안 됨.
    # paper_{timestamp}로 자동 변환해서 영속화 보장.
    if pid == "new":
        new_pid = f"paper_{int(_time.time())}"
        st.session_state["sg_active_project"] = new_pid
        pid = new_pid

    # ★ 무의식 임프린트 (2026-05-30) — 사용자 prompt 진입 즉시 intent_sensor 발화.
    # 이후 paper_writer가 호출하는 LLM은 자동으로 사용자 의도/뉘앙스/페르소나 임프린트 픽업.
    try:
        from src.agent.intent_sensor import sense_and_imprint
        owner_email = (st.session_state.get("user") or {}).get("email") or \
                       st.session_state.get("user_email", "")
        sense_and_imprint(prompt,
                           prior_messages=project.get("messages") or [],
                           project=project, owner_email=owner_email)
    except Exception:
        pass

    messages = project["messages"]

    def _add_msg(role: str, content: str, **kw):
        m = {"role": role, "content": strip_lone_surrogates(content)[:8000]}
        m.update(kw)
        messages.append(m)

    def _emit_system(event: str, detail: str):
        messages.append({"role": "system", "event": event,
                          "detail": strip_lone_surrogates(detail)[:600]})

    _add_msg("assistant",
             "📥 시작합니다. KYRBS 2025 로드 → StatBridge → 5섹션 자동 작성 순서.")
    project["messages"] = messages
    _save_project(pid, project)

    # 1) 자료 자동 선택 — prompt에서 데이터셋/연도/다년도 추출 (2026-05-30 일반화)
    #    KYRBS 2005~2025 21개 차수 + KNHANES 지원. 미지정시 가장 최근.
    try:
        import re as _re2
        from src.data.kyrbs_raw_loader import KYRBSLoader, KNHANESLoader
        _project_root = _P(__file__).resolve().parent.parent.parent
        _raw_dir = _project_root / "data" / "raw"

        # (a) 데이터셋 종류 — KYRBS 우선, KNHANES 명시 시 전환
        ds_kind = "KYRBS"
        if _re2.search(r"KNHANES|국민건강영양|kn\s*hanes", prompt, _re2.IGNORECASE):
            ds_kind = "KNHANES"

        # (b) 연도 추출 — "2024", "2024년", "2023년-2025년", "최근 5년" 등
        years_found = sorted({int(y) for y in _re2.findall(r"(20[0-2]\d)", prompt)})
        years_range = None
        m_range = _re2.search(r"(20[0-2]\d)\s*[~\-–]\s*(20[0-2]\d)", prompt)
        if m_range:
            y1, y2 = sorted([int(m_range.group(1)), int(m_range.group(2))])
            years_range = list(range(y1, y2 + 1))

        # (c) 자료 경로 후보 수집 (실제 파일이 있는 것만)
        # uploads/ 폴더의 첨부 .sav 파일도 자동 감지 (사용자가 ez_home에서 직접 업로드한 경우)
        _uploads_dir = _project_root / "data" / "uploads"
        if ds_kind == "KYRBS":
            available = {}
            for y in range(2005, 2026):
                cand = _raw_dir / f"kyrbs{y}.sav"
                if cand.exists():
                    available[y] = cand
            # 업로드 폴백 — uploaded kyrbs*.sav
            if _uploads_dir.exists():
                for p in _uploads_dir.glob("*.sav"):
                    m = _re2.search(r"(20[0-2]\d)", p.name)
                    if m:
                        available.setdefault(int(m.group(1)), p)
                    else:
                        # 연도 없는 업로드는 9999로 (최우선)
                        available[9999] = p
        else:  # KNHANES
            available = {}
            for p in _raw_dir.glob("knhanes/*.sav"):
                m = _re2.search(r"(20[0-2]\d)", p.name)
                if m:
                    available[int(m.group(1))] = p
            if _uploads_dir.exists():
                for p in _uploads_dir.glob("knhanes*.sav"):
                    m = _re2.search(r"(20[0-2]\d)", p.name)
                    if m:
                        available.setdefault(int(m.group(1)), p)

        if not available:
            # ★ 환경 감지 — Streamlit Cloud는 GitHub repo 기반이라 대용량 .sav 없음
            import os as _os3
            is_cloud = "/mount/src/" in str(_project_root) or _os3.environ.get("STREAMLIT_RUNTIME_CLOUD")
            env_hint = (
                "**현재 Streamlit Cloud 환경입니다** — KYRBS .sav 파일들(약 1.7GB)이 "
                "GitHub repo에 없어 분석 불가.\n\n"
                "**해결**:\n"
                "1. (권장) localhost:8501 로컬 docker로 접속 — 모든 자료 사용 가능\n"
                "2. 또는 ez_home 입력바 아래 📎 파일 첨부로 .sav 직접 업로드\n"
                "3. 또는 데이터 없이 PubMed 검색·논문 작성 (Build 대신 chat에 '리뷰 논문 양식'으로 요청)"
                if is_cloud else
                "**로컬 docker 환경에서 KYRBS 파일이 발견되지 않음**.\n\n"
                "확인: `docker exec medical-agent ls /app/data/raw/`\n"
                "예상 위치: `data/raw/kyrbs2005.sav` ~ `kyrbs2025.sav`"
            )
            raise FileNotFoundError(env_hint)

        # (d) 어떤 연도(들)을 쓸지 결정
        if years_range:
            target_years = [y for y in years_range if y in available]
        elif years_found:
            target_years = [y for y in years_found if y in available]
        else:
            target_years = [max(available.keys())]  # 최근 1년 기본

        if not target_years:
            target_years = [max(available.keys())]
            _emit_system("year_fallback",
                          f"요청 연도 {years_found or years_range} → 사용 가능 {sorted(available)} → "
                          f"가장 최근 {target_years[0]}으로 폴백")

        # (e) 단일/다년도 로드
        loader = KYRBSLoader() if ds_kind == "KYRBS" else KNHANESLoader()
        import pandas as _pd2
        dfs = []
        meta_combined = {"survey_years": target_years, "dataset": ds_kind, "sources": []}
        for y in sorted(target_years):
            sav = available[y]
            _emit_system("loading_year", f"{ds_kind} {y} 로드 중... ({sav.name})")
            df_y, m_y = loader.load(sav)
            df_y["__survey_year"] = y
            dfs.append(df_y)
            meta_combined["sources"].append(str(sav))
        df = _pd2.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        _meta = meta_combined

        _emit_system("data_loaded",
                     f"{ds_kind} 로드: {len(df):,}행 × {len(df.columns)}열 "
                     f"(연도: {target_years})")
    except Exception as e:
        import traceback as _tb2
        _emit_system("data_load_failed",
                      f"{type(e).__name__}: {e}\n{_tb2.format_exc()[:400]}")
        _add_msg("assistant",
                 f"⚠️ 데이터 로드 실패 — {type(e).__name__}: {str(e)[:300]}.\n"
                 f"확인: docker container 안 `/app/data/raw/` 폴더 — "
                 f"`docker exec medical-agent ls /app/data/raw/`")
        project["messages"] = messages
        _save_project(pid, project)
        return

    # 2) outcome/exposure 자동 매핑 — prompt 단어 우선, 없으면 KYRBS 표준 변수 fallback
    p_low = prompt.lower()
    OUTCOME_TABLE = [
        ("depression", ["우울", "depress"]),
        ("stress",     ["스트레스", "stress"]),
        ("insufficient_sleep", ["수면부족", "sleep"]),
        ("suicide_ideation",   ["자살", "suicid"]),
    ]
    EXPOSURE_TABLE = [
        ("zcb_freq",         ["zcb", "제로", "zero", "음료"]),
        ("smartphone_hours", ["스마트폰", "screen", "phone"]),
        ("physical_act",     ["운동", "physical"]),
        ("smoking",          ["흡연", "smok"]),
        ("alcohol",          ["음주", "alcohol"]),
        ("breakfast",        ["아침", "breakfast"]),
    ]
    def _pick(table, df_cols):
        for col, words in table:
            if col in df_cols and any(w in p_low for w in words):
                return col
        for col, _ in table:
            if col in df_cols:
                return col
        return None
    outcome = _pick(OUTCOME_TABLE, df.columns)
    exposure = _pick(EXPOSURE_TABLE, df.columns)
    if not outcome or not exposure:
        _emit_system("var_pick_failed",
                     f"available_cols(sample)={list(df.columns)[:30]}")
        _add_msg("assistant",
                 f"⚠️ KYRBS 변수에서 outcome/exposure를 못 찾았습니다 "
                 f"(outcome={outcome}, exposure={exposure}). "
                 f"입력바에 더 구체적인 키워드(예: '우울증', '스마트폰')를 적어 주세요.")
        project["messages"] = messages
        _save_project(pid, project)
        return

    # 3) StatBridge
    try:
        from src.data.stat_bridge import StatBridge
        covs = [c for c in ["sex","age","school_type","family_econ","academic_perf",
                            "bmi","smoking","alcohol","physical_act","screen_time",
                            "breakfast"] if c in df.columns and c != exposure]
        spec = {"outcome": outcome, "predictors": [exposure], "covariates": covs,
                "weight_var": "weight_var" if "weight_var" in df.columns else None,
                "strata_var": "strata" if "strata" in df.columns else None,
                "cluster_var": "cluster" if "cluster" in df.columns else None,
                "analysis": "logistic"}
        stat = StatBridge().run(df, spec).to_dict()
        n_total = stat.get("n_total", len(df))
        _emit_system("stat_done",
                     f"StatBridge: n={n_total:,} outcome={outcome} exposure={exposure} "
                     f"covs={len(covs)}")
    except Exception as e:
        _emit_system("stat_failed",
                     f"{type(e).__name__}: {e}\n{traceback.format_exc()[:300]}")
        _add_msg("assistant",
                 f"⚠️ 통계 분석 실패 — {type(e).__name__}: {str(e)[:200]}.")
        project["messages"] = messages
        _save_project(pid, project)
        return

    # 4) PaperWriter 5섹션 (필수 인자 author_profile + 보조 라이브러리 wiring)
    try:
        from src.research.paper_writer import PaperWriter
        from src.profile.author_profile import AuthorProfile
        try:
            from src.library.methods_library import MethodsLibrary
            methods_lib = MethodsLibrary()
        except Exception:
            methods_lib = None
        try:
            from src.library.dataset_library import DatasetLibrary
            dataset_lib = DatasetLibrary("data/libraries")
        except Exception:
            dataset_lib = None
        pw = PaperWriter(
            author_profile=AuthorProfile("Yoosun Cho"),
            methods_library=methods_lib,
            dataset_library=dataset_lib,
        )
        study_info = {
            "dataset": "KYRBS 2025", "design": "cross-sectional",
            "exposure": exposure, "outcome": outcome,
            "population": f"Korean adolescents (KYRBS 2025, n={n_total:,})",
            "sample_size": n_total,
            "covariates": ", ".join(covs),
            "methods_list": ["logistic_regression"],
        }
        paper_text = pw.write_full_paper_with_stats(
            topic=prompt[:200], study_info=study_info, stat_result=stat)
        # 섹션 dict 추출 (last_sections 우선)
        sections = getattr(pw, "last_sections", None)
        if not sections:
            # fallback: text 통째로 받은 경우 단순 분할
            sections = {"Abstract": paper_text[:1500],
                        "Introduction": "", "Methods": "", "Results": "", "Discussion": ""}
        project["sections"] = sections
        project["topic"] = {"title": prompt[:120],
                             "exposure": exposure, "outcome": outcome,
                             "dataset": "KYRBS 2025"}
        _emit_system("paper_written",
                     f"sections: {list(sections.keys())}; chars={sum(len(str(v)) for v in sections.values())}")
    except Exception as e:
        _emit_system("paper_failed",
                     f"{type(e).__name__}: {e}\n{traceback.format_exc()[:300]}")
        _add_msg("assistant",
                 f"⚠️ 논문 생성 실패 — {type(e).__name__}: {str(e)[:200]}.")
        project["messages"] = messages
        _save_project(pid, project)
        return

    # 4.5) 통계 분석 preregistration (재현성·LLM 우회 차단)
    try:
        from src.research.analysis_preregistration import (
            AnalysisPlan, register as ap_register, record_result as ap_record,
        )
        plan = AnalysisPlan(
            outcome=outcome, exposure=exposure,
            confounders=covs, model_class="logistic",
            design="cross_sectional",
            dataset_label=f"{ds_kind} {target_years}",
            dataset_md5="",  # 다년도 concat이라 단일 md5 비할당 (sources 리스트로 대체 추적)
        )
        plan_hash = ap_register(plan, actor="orchestrated_paper")
        # 결과 plan_hash에 연결
        result_summary = {
            "n_total": stat.get("n_total"),
            "outcome_label": stat.get("outcome_label", outcome),
            "aOR_target": None,
        }
        if isinstance(stat.get("model_vars"), list):
            for v in stat["model_vars"]:
                if exposure in str(v.get("variable", "")):
                    result_summary["aOR_target"] = v.get("or_value")
                    break
        ap_record(plan_hash, result_summary, actor="orchestrated_paper")
        _emit_system("preregistered",
                     f"plan_hash={plan_hash} outcome={outcome} exposure={exposure} covs={len(covs)}")
    except Exception as e:
        _emit_system("preregister_skip", f"{type(e).__name__}: {str(e)[:120]}")

    # 4.7) Style polish — 5섹션 본문에서 AI cliché 자동 제거 (gentle mode)
    try:
        from src.safety.style_polish import polish_paper, ai_style_score
        # 사전 AI score 측정 (전체 본문)
        full_text_before = "\n\n".join(
            str(v) for v in sections.values() if isinstance(v, str))
        before_rep = ai_style_score(full_text_before)
        # polish 적용
        polished_sections = polish_paper(sections, mode="gentle")
        project["sections"] = polished_sections
        sections = polished_sections
        # 사후 AI score
        full_text_after = "\n\n".join(
            str(v) for v in sections.values() if isinstance(v, str))
        after_rep = ai_style_score(full_text_after)
        _emit_system("style_polish",
                     f"AI score {before_rep.ai_style_score} → {after_rep.ai_style_score} "
                     f"(cliche {before_rep.overused_vocab_count} → {after_rep.overused_vocab_count})")
    except Exception as e:
        _emit_system("style_polish_skip", f"{type(e).__name__}: {str(e)[:120]}")

    # 5) Safety check
    try:
        from src.safety import check_all
        text_for_check = "\n\n".join(str(v) for v in sections.values() if isinstance(v, str))
        rep = check_all(text_for_check, sections=sections,
                         design="cross_sectional", scope="orchestrated_paper")
        _emit_system("safety_check", f"overall={rep.overall} failed={rep.failed_gates} warn={rep.warning_gates}")
    except Exception as e:
        _emit_system("safety_check_err", f"{type(e).__name__}: {e}")

    # 5.5) 자동 PubMed 인용 검색 + 본문 [n] 삽입 (2026-05-30 — References 자동 채우기)
    try:
        from src.export.reference_library import (
            ReferenceLibrary, insert_inline_citations,
        )
        slug = (prompt[:60].strip() or "manuscript").replace(" ", "_")
        lib = ReferenceLibrary(paper_slug=slug)
        # 주제 키워드 영문 변환 — exposure/outcome 양식
        query_en = f"{exposure} {outcome} adolescent Korean".replace("_", " ")
        added = lib.search_and_add(query_en, max_results=8)
        if added > 0:
            lib.save()
            project["references"] = [r.to_dict() for r in lib.get_refs()]
            # 본문에 [n] 자동 삽입
            for sec_name in ("Introduction", "Methods", "Results", "Discussion"):
                body = sections.get(sec_name)
                if isinstance(body, str) and body.strip():
                    sections[sec_name] = insert_inline_citations(body, lib)
            project["sections"] = sections
            _emit_system("refs_added", f"PubMed 자동 {added}개 추가 → 본문 [n] 삽입 완료")
    except Exception as e:
        _emit_system("refs_skip", f"인용 자동 추가 스킵: {type(e).__name__}: {str(e)[:120]}")

    # 6) 사용자 친화 결과 메시지
    try:
        # OR 값 추출 (있으면)
        mv = stat.get("model_vars") or []
        tgt = next((v for v in mv if exposure in str(v.get("variable",""))), None)
        or_text = ""
        if tgt and tgt.get("or_value") is not None:
            or_text = (f" 핵심 결과: aOR {tgt.get('or_value', 0):.2f} "
                       f"(95% CI {tgt.get('ci_lower', 0):.2f}–{tgt.get('ci_upper', 0):.2f}, "
                       f"P={tgt.get('p_value', 0):.3g}).")
        _add_msg("assistant",
                 f"✅ 논문 초안 완성: **{exposure} → {outcome}** (KYRBS 2025, n={n_total:,}).{or_text}\n\n"
                 f"우측 Manuscript 탭에서 5섹션 전체를 확인하세요. 추가 수정·재작성·STROBE 검사는 "
                 f"하단 입력바에 자연어로 요청하면 됩니다.")
    except Exception:
        _add_msg("assistant", "✅ 논문 초안이 완성되었습니다. 우측 Manuscript 탭을 확인하세요.")

    project["messages"] = messages
    _save_project(pid, project)


def _demo_sections() -> dict:
    """역호환 alias — 새 안내 dict 반환."""
    return _empty_sections_notice()


def render(pid: str) -> None:
    """진입점. `app/streamlit_app.py`에서 호출."""
    inject_sapphire_glass()
    project = _load_project(pid)

    # back button + topbar
    cback, ctop = st.columns([1, 11])
    with cback:
        if st.button("← Home", key="ws_back", use_container_width=True):
            st.session_state["sg_view"] = "home"
            try:
                st.switch_page("pages/ez_home.py")
            except Exception:
                st.rerun()
    with ctop:
        _render_topbar(project)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # split: 좌 chat / 우 preview
    left, right = st.columns([4, 6])
    with left:
        _render_chat_left(project, pid)
    with right:
        _render_preview_right(project)


# Streamlit 멀티페이지: 페이지 파일을 runpy로 실행하므로 무조건 실행
try:
    pid = st.session_state.get("sg_active_project")
    if not pid:
        inject_sapphire_glass()
        st.markdown(
            "<div class='sg-card' style='max-width:560px;margin:120px auto;text-align:center;'>"
            "<div style='font-size:2.0rem;'>📂</div>"
            "<div style='font-weight:600;font-size:1.1rem;margin:8px 0;'>"
            "활성 프로젝트가 없습니다</div>"
            "<div style='color:#A3A3B8;font-size:0.92rem;margin-bottom:18px;'>"
            "EZ home에서 프로젝트를 먼저 선택해주세요.</div>"
            "</div>", unsafe_allow_html=True)
        if st.button("✨  EZ home으로", type="primary", use_container_width=False):
            try:
                st.switch_page("pages/ez_home.py")
            except Exception:
                st.info("좌측 사이드바에서 `ez home`을 클릭해 주세요.")
    else:
        render(pid)
except Exception as _e:
    import traceback
    st.error(f"Project workspace 렌더 실패: {_e}")
    st.code(traceback.format_exc())
