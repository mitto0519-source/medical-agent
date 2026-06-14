"""Sapphire Glass theme — EZ-style glassmorphism CSS for Streamlit.

DESIGN.md Section 9의 토큰을 Streamlit에 1회 주입. 새 페이지 진입 시 호출:
    from app.styles.sapphire_glass import inject_sapphire_glass
    inject_sapphire_glass()

UI 컴포넌트 helpers:
    glass_card(html_body, *, key=None)  → 글래스 액션 카드
    big_input(placeholder, key)         → EZ  큰 입력바
    project_card(title, edited, image, status)  → 프로젝트 카드 (홈 그리드)
    workspace_tabs(...)                 → Manuscript/Figures/Tables/Supplement chip tabs
"""
from __future__ import annotations

import streamlit as st


_INJECTED_FLAG = "_sapphire_glass_injected"


def inject_sapphire_glass(*, hide_streamlit_chrome: bool = True) -> None:
    """전역 sapphire_glass 테마 CSS 주입.

    Streamlit 멀티페이지에서 페이지 전환마다 script가 새로 실행되므로
    매번 inject해야 일관된 테마 유지. session_state guard 제거 (2026-05-29).
    중복 주입은 idempotent (같은 <style> 블록 덮어씀)."""
    st.session_state[_INJECTED_FLAG] = True

    # Streamlit 자체 chrome 전수 숨김 (2026-05-30 — 스크린샷 2번의 Share/Star/Edit/GitHub/Menu
    # 노출 사고 영구 차단). 새 Streamlit은 stToolbar/stActionButton  추가됨.
    chrome_hide = """
        #MainMenu {visibility: hidden !important; display: none !important;}
        header[data-testid="stHeader"] {background: transparent !important;}
        [data-testid="stToolbar"] {display: none !important;}
        [data-testid="stToolbarActions"] {display: none !important;}
        [data-testid="stDecoration"] {display: none !important;}
        [data-testid="stStatusWidget"] {display: none !important;}
        [data-testid="stAppDeployButton"] {display: none !important;}
        .stDeployButton {display: none !important;}
        [data-testid="stAppViewBlockContainer"] > div:first-child > [data-testid="stToolbar"] {
            display: none !important;
        }
        a[href*="github.com"][data-testid] {display: none !important;}
        button[kind="header"] {display: none !important;}
        footer {visibility: hidden !important; display: none !important;}
        footer:after {display: none !important;}
        #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0 !important;}
    """ if hide_streamlit_chrome else ""

    st.markdown(f"""
<style>
/* ── Global root — Light palette (2026-06-01: AI Visibility 첨부  톤다운) ── */
:root {{
  --sg-bg:          #F8FAFC;   /* slate-50, 거의 흰색 베이스 */
  --sg-bg-from:     #FFFFFF;
  --sg-bg-via:      #F1F5F9;   /* slate-100 */
  --sg-bg-to:       #FFFFFF;
  --sg-surface:     #FFFFFF;
  --sg-glass:       rgba(255, 255, 255, 0.78);   /* 글래스 살리되 라이트 */
  --sg-glass-hover: rgba(255, 255, 255, 0.92);
  --sg-glass-active:rgba(249, 250, 251, 0.95);
  --sg-border:      rgba(15, 23, 42, 0.06);      /* 얇고 은은하게 (slate-900 6%) */
  --sg-border-strong:rgba(15, 23, 42, 0.10);
  --sg-border-focus:rgba(59, 130, 246, 0.45);    /* sapphire focus ring */
  --sg-text:        #0F172A;   /* slate-900 */
  --sg-text-sub:    #475569;   /* slate-600 */
  --sg-text-muted:  #94A3B8;   /* slate-400 */
  --sg-accent-sap:  #3B82F6;   /* blue-500 */
  --sg-accent-cyan: #06B6D4;
  --sg-accent-vio:  #8B5CF6;
  --sg-accent-mint: #10B981;   /* emerald-500 — positive/growth */
  --sg-accent-rose: #EF4444;   /* red-500 — negative */
  --sg-accent-amber:#F59E0B;
  --sg-radius-card: 14px;
  --sg-radius-chip: 999px;
  --sg-shadow-soft: 0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 12px rgba(15, 23, 42, 0.04);
  --sg-shadow-card: 0 1px 3px rgba(15, 23, 42, 0.05), 0 8px 24px rgba(15, 23, 42, 0.06);
  --sg-shadow-glow: 0 0 0 3px rgba(59, 130, 246, 0.10);
  --sg-trans-fast:  150ms cubic-bezier(0.4, 0, 0.2, 1);
  --sg-trans-med:   250ms cubic-bezier(0.4, 0, 0.2, 1);
}}

html, body, [data-testid="stApp"] {{
  background:
    radial-gradient(1200px 800px at 12% 0%,  rgba(219, 234, 254, 0.55), transparent 55%),
    radial-gradient(1000px 700px at 88% 5%,  rgba(220, 252, 231, 0.45), transparent 55%),
    radial-gradient(1100px 800px at 50% 100%, rgba(243, 232, 255, 0.40), transparent 60%),
    linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
  color: var(--sg-text) !important;
  font-family: "Inter", "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif !important;
  letter-spacing: -0.01em;
  background-attachment: fixed !important;
}}

{chrome_hide}

/* ── Sidebar — light, very subtle right border ───────────────────────── */
[data-testid="stSidebar"] {{
  background: rgba(255, 255, 255, 0.85) !important;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-right: 1px solid var(--sg-border);
}}
[data-testid="stSidebar"] * {{ color: var(--sg-text) !important; }}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stSelectbox label {{ color: var(--sg-text-sub) !important; }}

/* ── Buttons — light glass, thin border, no transform ────────────────── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {{
  background: var(--sg-glass) !important;
  color: var(--sg-text) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: 10px !important;
  padding: 9px 18px !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: var(--sg-trans-fast);
  box-shadow: var(--sg-shadow-soft);
}}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
  background: var(--sg-glass-hover) !important;
  border-color: var(--sg-border-strong) !important;
  box-shadow: var(--sg-shadow-card);
}}
.stButton > button[kind="primary"],
.stButton > button.sg-primary {{
  background: var(--sg-accent-sap) !important;
  border: 1px solid var(--sg-accent-sap) !important;
  color: white !important;
}}
.stButton > button[kind="primary"]:hover {{
  background: #2563EB !important;   /* blue-600 */
  border-color: #2563EB !important;
}}

/* ── Text input — light, thin border ────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stChatInput textarea {{
  background: rgba(255, 255, 255, 0.88) !important;
  color: var(--sg-text) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: 10px !important;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: 11px 14px !important;
  font-size: 0.92rem !important;
  box-shadow: var(--sg-shadow-soft);
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stChatInput textarea:focus {{
  border-color: var(--sg-accent-sap) !important;
  box-shadow: var(--sg-shadow-glow) !important;
  outline: none !important;
}}

/* ── Tabs (chip style) — light, thin ─────────────────────────────────── */
[data-baseweb="tab-list"] {{
  gap: 6px !important;
  background: transparent !important;
}}
[data-baseweb="tab"] {{
  background: rgba(255, 255, 255, 0.7) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: var(--sg-radius-chip) !important;
  padding: 7px 16px !important;
  color: var(--sg-text-sub) !important;
  font-size: 0.85rem !important;
  transition: var(--sg-trans-fast);
}}
[data-baseweb="tab"]:hover {{
  background: rgba(255, 255, 255, 0.95) !important;
  color: var(--sg-text) !important;
  border-color: var(--sg-border-strong) !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  background: var(--sg-text) !important;       /* dark pill on light — AI Visibility 양식 */
  color: #FFFFFF !important;
  border-color: var(--sg-text) !important;
}}
[data-baseweb="tab-highlight"] {{ display: none !important; }}

/* ── Expander — light card ───────────────────────────────────────────── */
.streamlit-expanderHeader {{
  background: var(--sg-glass) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: var(--sg-radius-card) !important;
  color: var(--sg-text) !important;
}}

/* ── Markdown body ───────────────────────────────────────────────────── */
[data-testid="stMarkdownContainer"], .stMarkdown {{
  color: var(--sg-text) !important;
}}
[data-testid="stMarkdownContainer"] code {{
  background: #F1F5F9 !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: 5px !important;
  padding: 1px 6px !important;
  color: var(--sg-accent-sap) !important;
  font-size: 0.86em !important;
}}

/* ── Our custom classes ──────────────────────────────────────────────── */
.sg-card {{
  background: var(--sg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-card);
  padding: 18px 22px;
  box-shadow: var(--sg-shadow-soft);
  transition: var(--sg-trans-fast);
}}
.sg-card:hover {{
  background: var(--sg-glass-hover);
  border-color: var(--sg-border-strong);
  box-shadow: var(--sg-shadow-card);
}}

.sg-big-input {{
  background: var(--sg-surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--sg-border);
  border-radius: 14px;
  padding: 8px 12px 8px 18px;
  box-shadow: var(--sg-shadow-card);
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.sg-big-input:focus-within {{
  border-color: var(--sg-accent-sap);
  box-shadow: var(--sg-shadow-glow), var(--sg-shadow-card);
}}

.sg-hero-title {{
  text-align: center;
  font-size: 2.4rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--sg-text);
  margin: 80px 0 28px 0;
}}

.sg-project-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 24px;
}}
.sg-project-card {{
  background: var(--sg-surface);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-card);
  overflow: hidden;
  cursor: pointer;
  transition: var(--sg-trans-fast);
  box-shadow: var(--sg-shadow-soft);
}}
.sg-project-card:hover {{
  border-color: var(--sg-border-strong);
  box-shadow: var(--sg-shadow-card);
  transform: translateY(-1px);
}}
.sg-project-thumb {{
  height: 150px;
  background: linear-gradient(135deg, #DBEAFE 0%, #E0E7FF 60%, #FCE7F3 100%);
  position: relative;
  overflow: hidden;
}}
.sg-project-thumb::after {{
  content: "";
  position: absolute; inset: 0;
  background: radial-gradient(circle at 28% 22%, rgba(255, 255, 255, 0.55), transparent 60%);
}}
.sg-project-meta {{
  padding: 14px 16px;
  display: flex; flex-direction: column; gap: 4px;
  background: var(--sg-surface);
  border-top: 1px solid var(--sg-border);
}}
.sg-project-title {{
  font-weight: 600; color: var(--sg-text); font-size: 0.94rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.sg-project-date {{
  font-size: 0.78rem; color: var(--sg-text-muted);
}}
.sg-badge {{
  display: inline-block;
  background: #F8FAFC;
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-chip);
  padding: 2px 9px;
  font-size: 0.72rem;
  color: var(--sg-text-sub);
  margin-right: 6px;
}}
.sg-badge.published {{
  color: var(--sg-accent-mint);
  border-color: rgba(16, 185, 129, 0.30);
  background: rgba(16, 185, 129, 0.08);
}}

.sg-chip-row {{
  display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0;
}}
.sg-chip {{
  background: var(--sg-glass);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-chip);
  padding: 6px 14px;
  font-size: 0.83rem;
  color: var(--sg-text-sub);
  cursor: pointer;
  transition: var(--sg-trans-fast);
}}
.sg-chip:hover {{
  background: var(--sg-glass-hover);
  color: var(--sg-text);
  border-color: var(--sg-border-strong);
}}
.sg-chip.active {{
  background: var(--sg-text);
  color: #FFFFFF;
  border-color: var(--sg-text);
}}

.sg-manuscript {{
  background: #FFFFFF;
  color: #0F172A;
  border: 1px solid var(--sg-border);
  border-radius: 14px;
  padding: 56px 64px;
  font-family: "Times New Roman", Georgia, serif;
  line-height: 2.0;
  font-size: 16px;
  max-width: 720px;
  margin: 0 auto;
  box-shadow: var(--sg-shadow-card);
  min-height: 600px;
}}
.sg-manuscript h1 {{
  text-align: center; font-size: 1.4rem; margin-bottom: 24px;
}}
.sg-manuscript h2 {{ font-size: 1.1rem; margin-top: 28px; }}
.sg-manuscript h3 {{ font-size: 1.0rem; font-style: italic; margin-top: 20px; }}
.sg-manuscript p {{ text-align: justify; text-indent: 1.27cm; margin: 0 0 4px 0; }}
.sg-manuscript .label-bold {{ font-weight: 700; }}

.sg-split {{
  display: grid; grid-template-columns: 38% 62%; gap: 16px;
  height: calc(100vh - 140px);
}}
.sg-split-left, .sg-split-right {{
  background: var(--sg-glass);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-card);
  padding: 16px;
  overflow-y: auto;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: var(--sg-shadow-soft);
}}
.sg-split-right {{ padding: 24px; }}

.sg-msg-user {{
  background: #F1F5F9;          /* slate-100 — assistant 대비 차분히 */
  border: 1px solid var(--sg-border);
  border-radius: 12px;
  padding: 11px 14px;
  margin: 8px 0;
  color: var(--sg-text);
  font-size: 0.92rem;
}}
.sg-msg-assistant {{
  background: rgba(219, 234, 254, 0.55);   /* blue-100 옅게 */
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 12px;
  padding: 13px 16px;
  margin: 8px 0;
  color: var(--sg-text);
  font-size: 15px;
  line-height: 1.65;
  max-width: 74ch;
}}
/* UX_CHAT_DESIGN_SPEC §6.1 — 채팅 말풍선 내부 타이포 (문서급 거대 헤더 차단) */
.sg-msg-assistant h1, .sg-msg-assistant h2 {{
  font-size: 1.05rem;
  font-weight: 700;
  margin: 14px 0 6px;
  line-height: 1.3;
  color: var(--sg-text);
  border: none;
  padding: 0;
}}
.sg-msg-assistant h3 {{
  font-size: 0.95rem;
  font-weight: 600;
  margin: 12px 0 4px;
  color: var(--sg-text);
}}
.sg-msg-assistant p {{
  margin: 0 0 10px;
  line-height: 1.65;
  text-indent: 0;       /* 문서체 들여쓰기 무시 (대화는 일반 단락) */
  text-align: left;
}}
.sg-msg-assistant ul, .sg-msg-assistant ol {{
  margin: 6px 0 10px;
  padding-left: 22px;
}}
.sg-msg-assistant li {{ margin: 2px 0; }}
.sg-msg-assistant table {{
  font-size: 0.88rem;
  border-collapse: collapse;
  margin: 8px 0;
}}
.sg-msg-assistant th, .sg-msg-assistant td {{
  padding: 4px 8px;
  border: 1px solid rgba(59, 130, 246, 0.18);
}}
.sg-msg-assistant code {{
  font-size: 0.86em;
  font-family: ui-monospace, "SF Mono", Consolas, monospace;
  background: rgba(15, 23, 42, 0.04);
  padding: 1px 5px;
  border-radius: 4px;
}}
.sg-msg-assistant pre {{
  background: rgba(15, 23, 42, 0.04);
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}}
.sg-msg-assistant strong, .sg-msg-assistant b {{ font-weight: 700; }}
/* 사용자 말풍선도 동일 타이포 안전망 */
.sg-msg-user {{ max-width: 74ch; line-height: 1.55; }}

.sg-action-card {{
  background: var(--sg-surface);
  border: 1px solid var(--sg-border);
  border-radius: 12px;
  padding: 13px 16px;
  margin: 10px 0;
  display: flex; align-items: center; gap: 12px;
  box-shadow: var(--sg-shadow-soft);
  transition: var(--sg-trans-fast);
}}
.sg-action-card:hover {{
  border-color: var(--sg-border-strong);
  box-shadow: var(--sg-shadow-card);
}}
.sg-action-card .sg-icon {{ font-size: 1.3rem; color: var(--sg-text-sub); }}
.sg-action-card .sg-detail {{ flex: 1; }}
.sg-action-card .sg-title {{ font-weight: 600; color: var(--sg-text); font-size: 0.92rem; }}
.sg-action-card .sg-sub {{ color: var(--sg-text-sub); font-size: 0.80rem; }}

/* ── Metric strip (AI Visibility  KPI 블록) ─────────────────────── */
.sg-metric {{
  background: var(--sg-surface);
  border: 1px solid var(--sg-border);
  border-radius: 12px;
  padding: 14px 18px;
  box-shadow: var(--sg-shadow-soft);
}}
.sg-metric-label {{
  font-size: 0.78rem; color: var(--sg-text-muted);
  text-transform: none; letter-spacing: 0;
  margin-bottom: 4px;
}}
.sg-metric-value {{
  font-size: 1.6rem; font-weight: 700; color: var(--sg-text);
  line-height: 1.15;
}}
.sg-metric-delta-pos {{ color: var(--sg-accent-mint); font-size: 0.82rem; margin-left: 6px; }}
.sg-metric-delta-neg {{ color: var(--sg-accent-rose); font-size: 0.82rem; margin-left: 6px; }}

hr {{ border-color: var(--sg-border) !important; opacity: 1; }}
</style>
""", unsafe_allow_html=True)


# ── Component helpers (server-side HTML emitters) ───────────────────────────

def glass_card(html_body: str) -> None:
    """글래스 액션 카드. html_body는 inner HTML 그대로 주입."""
    st.markdown(f"<div class='sg-card'>{html_body}</div>", unsafe_allow_html=True)


def hero_title(text: str) -> None:
    st.markdown(f"<div class='sg-hero-title'>{text}</div>", unsafe_allow_html=True)


def chip_row(chips: list[tuple[str, bool]]) -> None:
    """[(label, active), ...] → 가로 chip 한 줄."""
    html = "<div class='sg-chip-row'>" + "".join(
        f"<span class='sg-chip{' active' if active else ''}'>{label}</span>"
        for label, active in chips
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def project_card_html(title: str, edited: str, status: str = "",
                       gradient: str = "linear-gradient(135deg, #DBEAFE 0%, #E0E7FF 60%, #FCE7F3 100%)") -> str:
    """프로젝트 카드 HTML 반환 (외부에서 grid에 collect).

    기본 thumb는 라이트 파스텔 그라데이션 (blue-100 → indigo-100 → pink-100).
    """
    badge = (f"<div style='position:absolute;bottom:8px;left:8px;'>"
              f"<span class='sg-badge published'>{status}</span></div>") if status else ""
    return (f"<div class='sg-project-card'>"
            f"<div class='sg-project-thumb' style='background:{gradient};'>{badge}</div>"
            f"<div class='sg-project-meta'>"
            f"<div class='sg-project-title'>{title}</div>"
            f"<div class='sg-project-date'>{edited}</div>"
            f"</div></div>")


def project_grid(projects: list[dict]) -> None:
    """projects = [{"title":..., "edited":..., "status":..., "gradient":...}, ...]"""
    default_g = "linear-gradient(135deg, #DBEAFE 0%, #E0E7FF 60%, #FCE7F3 100%)"
    html = "<div class='sg-project-grid'>" + "".join(
        project_card_html(p.get("title", "Untitled"),
                           p.get("edited", ""),
                           p.get("status", ""),
                           p.get("gradient", default_g))
        for p in projects
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def metric_card(label: str, value: str, *, delta: str = "",
                 delta_kind: str = "pos") -> None:
    """AI Visibility  KPI 블록: label / value / delta(+x.x%).

    delta_kind: 'pos' (emerald) | 'neg' (rose) | 'neutral' (sub-text)
    """
    import html as _h
    delta_cls = {"pos": "sg-metric-delta-pos",
                 "neg": "sg-metric-delta-neg"}.get(delta_kind, "sg-metric-delta-pos")
    delta_html = (f"<span class='{delta_cls}'>{_h.escape(delta)}</span>"
                   if delta else "")
    st.markdown(
        f"<div class='sg-metric'>"
        f"<div class='sg-metric-label'>{_h.escape(label)}</div>"
        f"<div class='sg-metric-value'>{_h.escape(value)}{delta_html}</div>"
        f"</div>", unsafe_allow_html=True)


def message_bubble(role: str, text: str) -> None:
    """role: 'user' | 'assistant'. text는 plain (HTML escape됨)."""
    import html as _h
    cls = "sg-msg-user" if role == "user" else "sg-msg-assistant"
    safe = _h.escape(text).replace("\n", "<br/>")
    st.markdown(f"<div class='{cls}'>{safe}</div>", unsafe_allow_html=True)


def action_card(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='sg-action-card'>"
        f"<div class='sg-icon'>{icon}</div>"
        f"<div class='sg-detail'><div class='sg-title'>{title}</div>"
        f"<div class='sg-sub'>{subtitle}</div></div>"
        f"</div>", unsafe_allow_html=True)


def manuscript_preview_html(*, title: str, authors: list[str] | str,
                              abstract: dict | str = "",
                              keywords: list[str] | None = None,
                              sections: dict | None = None) -> str:
    """Word 양식 1:1 HTML 프리뷰 — sg-manuscript 클래스."""
    import html as _h
    if isinstance(authors, list):
        authors_str = ", ".join(authors)
    else:
        authors_str = authors or ""

    parts = [f"<h1>{_h.escape(title)}</h1>"]
    if authors_str:
        parts.append(f"<p style='text-align:center;text-indent:0;font-weight:400;'>{_h.escape(authors_str)}</p>")

    if abstract:
        parts.append("<h2>Abstract</h2>")
        if isinstance(abstract, dict):
            for label in ("Background", "Methods", "Results", "Conclusion"):
                content = abstract.get(label) or abstract.get(label.lower())
                if content:
                    parts.append(
                        f"<p><span class='label-bold'>{label}</span>: "
                        f"{_h.escape(str(content))}</p>"
                    )
        else:
            parts.append(f"<p>{_h.escape(str(abstract))}</p>")
        if keywords:
            parts.append(
                f"<p><span class='label-bold'>Keywords</span>: "
                f"{_h.escape('; '.join(keywords))}</p>"
            )

    if sections:
        for sec_name in ("Introduction", "Methods", "Results", "Discussion"):
            body = sections.get(sec_name)
            if not body:
                continue
            parts.append(f"<h2>{sec_name}</h2>")
            if isinstance(body, dict):
                for sub, sub_body in body.items():
                    parts.append(f"<h3>{_h.escape(sub)}</h3>")
                    for para in str(sub_body).split("\n\n"):
                        if para.strip():
                            parts.append(f"<p>{_h.escape(para.strip())}</p>")
            else:
                for para in str(body).split("\n\n"):
                    if para.strip():
                        parts.append(f"<p>{_h.escape(para.strip())}</p>")

    return "<div class='sg-manuscript'>" + "".join(parts) + "</div>"


# NOTE: 과거에 있던 `manuscript_preview()` wrapper는 제거 (2026-05-27).
# 호출자 0건이었고, `_project_workspace.py`가 manuscript_preview_html()을
# 직접 st.markdown(...)으로 출력하는 한 줄이라 wrapper의 가치가 없음. dead code 차단.
