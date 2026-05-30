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
    """working_papers/{pid}.json 또는 new 빈 프로젝트."""
    if pid == "new":
        return {"title": "New manuscript",
                "topic": {}, "sections": {}, "messages": [], "figures": [], "tables": []}
    p = _WP_DIR / f"{pid}.json"
    if not p.exists():
        return {"title": pid, "sections": {}, "messages": [], "figures": [], "tables": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
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
        if st.button("⬇ Export", use_container_width=True, key="ws_export", type="primary"):
            _export_docx(project)

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
    except Exception as e:
        st.error(f"Export 실패: {e}")


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
    if initial and not messages:
        messages.append({"role": "user", "content": initial})

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
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
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


def _run_agentic_step(prompt: str, project: dict, pid: str, mode: str):
    """★ Agentic loop — LLM이 tool을 직접 호출해 preview를 갱신.
    각 step(assistant text / tool_use / tool_result / system)을 chat에 시간순 기록.
    실패해도 UX는 살아있게 system 이벤트로 남김."""
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
        system = build_system_with_preview(
            base_system + f"\n\nMode: {mode}.", project)

        cc = ClaudeClient(task="paper_writing")
        # 사용자 프롬프트 + 직전 대화 컨텍스트 (간단히 마지막 사용자 메시지만 보내고
        # 직전 assistant/tool 흐름은 system 안의 preview snapshot으로 대체)
        user_msg = prompt

        result = cc.generate_with_tools(
            user_message=user_msg, tools=TOOL_SCHEMAS,
            tool_handler=handler, system_prompt=system,
            max_tokens=3000, max_iters=6, task="paper_writing",
        )

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
    """단순 one-shot LLM 호출 (tool-use OFF일 때). 실패 시 graceful."""
    try:
        from src.llm import get_llm_client
        from src.agent.prompt_loader import load_prompt
        from app.agentic_loop import build_system_with_preview
        base = load_prompt("paper_write")
        sys_prompt = build_system_with_preview(base + f"\n\nMode: {mode}.", project)
        client = get_llm_client(task="paper_writing")
        out = client.generate(prompt, system_prompt=sys_prompt, max_tokens=1500)
        return {"content": out[:2000]}
    except Exception as e:
        return {"content": f"⚠️ LLM 호출 실패: {e}"[:300]}


def _render_preview_right(project: dict):
    """우측 preview tab bar + 내용."""
    tab = st.session_state.get("sg_active_tab", "Manuscript")
    tabs = st.tabs(["📄 Manuscript", "📊 Figures", "🧮 Tables", "📎 Supplement"])

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


def _demo_sections() -> dict:
    return {
        "Abstract": {
            "Background": "Zero-calorie beverages (ZCB) are increasingly consumed by adolescents.",
            "Methods": "Cross-sectional analysis of KYRBS 2025 (n = 50,972).",
            "Results": "Daily ZCB associated with depressive symptoms (aOR 1.27; 95% CI 1.03-1.56).",
            "Conclusion": "Higher ZCB intake independently associated with depression in adolescents.",
        },
        "Introduction": "Depression is a leading cause of disability in adolescence [1, 2]. "
                          "ZCB consumption has risen, with unclear mental health implications.",
        "Methods": {
            "Study population": "We used 2025 KYRBS data (n = 50,972 aged 12-18).",
            "Measurements": "ZCB ascertained on 7-point scale, collapsed into 4 categories.",
            "Statistical analysis": "Survey-weighted logistic regression with 95% CI.",
        },
        "Results": "Daily ZCB consumption ≥1/day showed aOR 1.27 (95% CI 1.03-1.56, "
                    "P = 0.026). Significant interaction by sex (P for interaction < 0.001).",
        "Discussion": "Key finding: female-predominant dose-response association. "
                       "Limitation: cross-sectional design precludes causal inference.",
    }


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
