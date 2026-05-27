"""프로젝트 워크스페이스 — Lovable 양식의 split 화면.

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

from app.styles.sapphire_glass import (
    inject_sapphire_glass, message_bubble, manuscript_preview_html, action_card,
)


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


def _save_project(pid: str, data: dict) -> None:
    if pid == "new":
        return
    _WP_DIR.mkdir(parents=True, exist_ok=True)
    p = _WP_DIR / f"{pid}.json"
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
        if st.button("💬 Comments", use_container_width=True, key="ws_comments"):
            st.toast("Comments: 곧 활성화", icon="💬")
    with cols[2]:
        if st.button("🔗 Share", use_container_width=True, key="ws_share"):
            st.toast("Share link: 곧 활성화", icon="🔗")
    with cols[3]:
        if st.button("⬇ Export", use_container_width=True, key="ws_export", type="primary"):
            _export_docx(project)


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


def _render_chat_event(m: dict):
    """user/assistant/tool_use/tool_result/system 모두 시각 양식 분기 렌더."""
    role = m.get("role", "system")
    if role == "user":
        message_bubble("user", m.get("content", ""))
        return
    if role == "assistant":
        if m.get("content"):
            message_bubble("assistant", m["content"])
        return
    if role == "tool_use":
        st.markdown(
            f"<div class='sg-action-card' style='border-color:rgba(6,182,212,0.45);"
            f"background:rgba(6,182,212,0.10);'>"
            f"<div class='sg-icon'>🛠️</div>"
            f"<div class='sg-detail'>"
            f"<div class='sg-title'>{m.get('tool', '?')}</div>"
            f"<div class='sg-sub'>input: <code>{json.dumps(m.get('input', {}), ensure_ascii=False)[:200]}</code></div>"
            f"</div></div>", unsafe_allow_html=True)
        return
    if role == "tool_result":
        preview = (m.get("content") or "")[:280]
        st.markdown(
            f"<div class='sg-action-card' style='border-color:rgba(16,185,129,0.40);"
            f"background:rgba(16,185,129,0.08);'>"
            f"<div class='sg-icon'>📥</div>"
            f"<div class='sg-detail'>"
            f"<div class='sg-title'>tool_result</div>"
            f"<div class='sg-sub'>{preview}…</div>"
            f"</div></div>", unsafe_allow_html=True)
        return
    if role == "system":
        st.markdown(
            f"<div class='sg-action-card' style='border-color:rgba(124,58,237,0.40);"
            f"background:rgba(124,58,237,0.08);'>"
            f"<div class='sg-icon'>⚙️</div>"
            f"<div class='sg-detail'>"
            f"<div class='sg-title'>{m.get('event', 'system')}</div>"
            f"<div class='sg-sub'>{m.get('detail', '')}</div>"
            f"</div></div>", unsafe_allow_html=True)


def _render_chat_left(project: dict, pid: str):
    """좌측 chat panel — VS Code/Claude Code 양식.
    user/assistant/tool_use/tool_result/system 모두 시간순 표시."""
    st.markdown("<div style='font-size:0.78rem;color:#A3A3B8;margin:4px 0 8px 4px;'>"
                f"{project.get('updated', 'today')}</div>", unsafe_allow_html=True)

    messages = project.get("messages", [])
    initial = st.session_state.pop("sg_initial_prompt", None)
    if initial and not messages:
        messages.append({"role": "user", "content": initial})

    for m in messages:
        _render_chat_event(m)

    # 입력 form
    with st.form(key="ws_form", clear_on_submit=True):
        prompt = st.text_area("ask", placeholder="Ask Medical-Agent… (LLM이 tool을 직접 호출해 preview를 갱신합니다)",
                               label_visibility="collapsed", height=80)
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

    if sent and prompt:
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
    except Exception as e:
        import traceback
        project["messages"].append({"role": "system", "event": "agentic_error",
                                      "detail": f"{e}\n\n{traceback.format_exc()[:500]}"})
        _save_project(pid, project)


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
            "Lovable home에서 프로젝트를 먼저 선택해주세요.</div>"
            "</div>", unsafe_allow_html=True)
        if st.button("✨  Lovable home으로", type="primary", use_container_width=False):
            try:
                st.switch_page("pages/lovable_home.py")
            except Exception:
                st.info("좌측 사이드바에서 `lovable home`을 클릭해 주세요.")
    else:
        render(pid)
except Exception as _e:
    import traceback
    st.error(f"Project workspace 렌더 실패: {_e}")
    st.code(traceback.format_exc())
