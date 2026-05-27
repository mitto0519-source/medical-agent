"""Sapphire Glass theme — Lovable-style glassmorphism CSS for Streamlit.

DESIGN.md Section 9의 토큰을 Streamlit에 1회 주입. 새 페이지 진입 시 호출:
    from app.styles.sapphire_glass import inject_sapphire_glass
    inject_sapphire_glass()

UI 컴포넌트 helpers:
    glass_card(html_body, *, key=None)  → 글래스 액션 카드
    big_input(placeholder, key)         → Lovable 양식 큰 입력바
    project_card(title, edited, image, status)  → 프로젝트 카드 (홈 그리드)
    workspace_tabs(...)                 → Manuscript/Figures/Tables/Supplement chip tabs
"""
from __future__ import annotations

import streamlit as st


_INJECTED_FLAG = "_sapphire_glass_injected"


def inject_sapphire_glass(*, hide_streamlit_chrome: bool = True) -> None:
    """전역 sapphire_glass 테마 CSS를 1회 주입. 중복 호출은 무시."""
    if st.session_state.get(_INJECTED_FLAG):
        return
    st.session_state[_INJECTED_FLAG] = True

    chrome_hide = """
        #MainMenu {visibility: hidden;}
        header[data-testid="stHeader"] {background: transparent;}
        footer {visibility: hidden;}
    """ if hide_streamlit_chrome else ""

    st.markdown(f"""
<style>
/* ── Global root ─────────────────────────────────────────────────────── */
:root {{
  --sg-bg:          #0A0A1F;
  --sg-bg-from:     #1E1B4B;
  --sg-bg-via:      #7C3AED;
  --sg-bg-to:       #EC4899;
  --sg-surface:     #0F0F23;
  --sg-glass:       rgba(255, 255, 255, 0.06);
  --sg-glass-hover: rgba(255, 255, 255, 0.10);
  --sg-glass-active:rgba(255, 255, 255, 0.14);
  --sg-border:      rgba(255, 255, 255, 0.12);
  --sg-border-focus:rgba(124, 58, 237, 0.55);
  --sg-text:        #F5F5FA;
  --sg-text-sub:    #A3A3B8;
  --sg-text-muted:  #6B6B7E;
  --sg-accent-sap:  #3B82F6;
  --sg-accent-cyan: #06B6D4;
  --sg-accent-vio:  #8B5CF6;
  --sg-accent-mint: #10B981;
  --sg-accent-rose: #F43F5E;
  --sg-radius-card: 18px;
  --sg-radius-chip: 999px;
  --sg-shadow-soft: 0 8px 32px rgba(15, 15, 35, 0.40);
  --sg-shadow-glow: 0 0 24px rgba(124, 58, 237, 0.28);
  --sg-trans-fast:  150ms cubic-bezier(0.4, 0, 0.2, 1);
  --sg-trans-med:   250ms cubic-bezier(0.4, 0, 0.2, 1);
}}

html, body, [data-testid="stApp"] {{
  background:
    radial-gradient(1100px 700px at 18% 8%, rgba(124, 58, 237, 0.28), transparent 60%),
    radial-gradient(1000px 700px at 88% 92%, rgba(236, 72, 153, 0.18), transparent 60%),
    linear-gradient(135deg, #0A0A1F 0%, #14143C 40%, #0F0F23 100%) !important;
  color: var(--sg-text) !important;
  font-family: "Inter", "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif !important;
  letter-spacing: -0.01em;
}}

{chrome_hide}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: rgba(10, 10, 31, 0.72) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid var(--sg-border);
}}
[data-testid="stSidebar"] * {{ color: var(--sg-text) !important; }}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stSelectbox label {{ color: var(--sg-text-sub) !important; }}

/* ── Buttons (default → glass pill) ─────────────────────────────────── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {{
  background: var(--sg-glass) !important;
  color: var(--sg-text) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: var(--sg-radius-chip) !important;
  padding: 10px 22px !important;
  font-weight: 500 !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: var(--sg-trans-fast);
  box-shadow: var(--sg-shadow-soft);
}}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
  background: var(--sg-glass-hover) !important;
  transform: translateY(-2px);
  box-shadow: var(--sg-shadow-glow);
}}
.stButton > button[kind="primary"],
.stButton > button.sg-primary {{
  background: linear-gradient(135deg, var(--sg-accent-sap), var(--sg-accent-vio)) !important;
  border: none !important;
  color: white !important;
}}

/* ── Text input ─────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stChatInput textarea {{
  background: var(--sg-glass) !important;
  color: var(--sg-text) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: 14px !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  padding: 14px 18px !important;
  font-size: 0.95rem !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stChatInput textarea:focus {{
  border-color: var(--sg-border-focus) !important;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.18), var(--sg-shadow-glow) !important;
  outline: none !important;
}}

/* ── Tabs (chip style) ───────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{
  gap: 8px !important;
  background: transparent !important;
}}
[data-baseweb="tab"] {{
  background: var(--sg-glass) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: var(--sg-radius-chip) !important;
  padding: 8px 18px !important;
  color: var(--sg-text-sub) !important;
  font-size: 0.88rem !important;
  transition: var(--sg-trans-fast);
}}
[data-baseweb="tab"]:hover {{
  background: var(--sg-glass-hover) !important;
  color: var(--sg-text) !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  background: linear-gradient(135deg, var(--sg-accent-sap), var(--sg-accent-vio)) !important;
  color: white !important;
  border-color: transparent !important;
}}
[data-baseweb="tab-highlight"] {{ display: none !important; }}

/* ── Expander as glass card ──────────────────────────────────────────── */
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
  background: var(--sg-glass) !important;
  border: 1px solid var(--sg-border) !important;
  border-radius: 6px !important;
  padding: 2px 6px !important;
  color: var(--sg-accent-cyan) !important;
}}

/* ── Our custom classes ──────────────────────────────────────────────── */
.sg-card {{
  background: var(--sg-glass);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-card);
  padding: 20px 24px;
  box-shadow: var(--sg-shadow-soft);
  transition: var(--sg-trans-med);
}}
.sg-card:hover {{
  background: var(--sg-glass-hover);
  transform: translateY(-2px);
  box-shadow: var(--sg-shadow-glow), var(--sg-shadow-soft);
}}

.sg-big-input {{
  background: var(--sg-glass);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  border: 1px solid var(--sg-border);
  border-radius: 22px;
  padding: 8px 12px 8px 20px;
  box-shadow: var(--sg-shadow-soft);
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.sg-big-input:focus-within {{
  border-color: var(--sg-border-focus);
  box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.18), var(--sg-shadow-glow);
}}

.sg-hero-title {{
  text-align: center;
  font-size: 2.4rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--sg-text);
  margin: 80px 0 28px 0;
  background: linear-gradient(135deg, #F5F5FA, #C4B5FD);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.sg-project-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
  margin-top: 24px;
}}
.sg-project-card {{
  background: var(--sg-glass);
  border: 1px solid var(--sg-border);
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: var(--sg-trans-med);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}}
.sg-project-card:hover {{
  border-color: var(--sg-border-focus);
  box-shadow: var(--sg-shadow-glow);
  transform: translateY(-3px);
}}
.sg-project-thumb {{
  height: 160px;
  background: linear-gradient(135deg, #1E1B4B, #312E81);
  position: relative;
  overflow: hidden;
}}
.sg-project-thumb::after {{
  content: "";
  position: absolute; inset: 0;
  background: radial-gradient(circle at 30% 20%, rgba(124, 58, 237, 0.35), transparent 70%);
}}
.sg-project-meta {{
  padding: 14px 16px;
  display: flex; flex-direction: column; gap: 4px;
}}
.sg-project-title {{
  font-weight: 600; color: var(--sg-text); font-size: 0.95rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.sg-project-date {{
  font-size: 0.78rem; color: var(--sg-text-muted);
}}
.sg-badge {{
  display: inline-block;
  background: var(--sg-glass-active);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-chip);
  padding: 3px 10px;
  font-size: 0.72rem;
  color: var(--sg-text-sub);
  margin-right: 6px;
}}
.sg-badge.published {{ color: var(--sg-accent-mint); border-color: rgba(16, 185, 129, 0.40); }}

.sg-chip-row {{
  display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0;
}}
.sg-chip {{
  background: var(--sg-glass);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius-chip);
  padding: 8px 16px;
  font-size: 0.85rem;
  color: var(--sg-text-sub);
  cursor: pointer;
  transition: var(--sg-trans-fast);
}}
.sg-chip:hover {{ background: var(--sg-glass-hover); color: var(--sg-text); }}
.sg-chip.active {{
  background: linear-gradient(135deg, var(--sg-accent-sap), var(--sg-accent-vio));
  color: white; border-color: transparent;
}}

.sg-manuscript {{
  background: #FAFAF7;
  color: #1A1A1A;
  border-radius: 14px;
  padding: 56px 64px;
  font-family: "Times New Roman", Georgia, serif;
  line-height: 2.0;
  font-size: 16px;
  max-width: 720px;
  margin: 0 auto;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
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
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}}
.sg-split-right {{ padding: 24px; }}

.sg-msg-user {{
  background: var(--sg-glass-active);
  border: 1px solid var(--sg-border);
  border-radius: 14px;
  padding: 12px 16px;
  margin: 8px 0;
  color: var(--sg-text);
  font-size: 0.92rem;
}}
.sg-msg-assistant {{
  background: rgba(124, 58, 237, 0.10);
  border: 1px solid rgba(124, 58, 237, 0.30);
  border-radius: 14px;
  padding: 12px 16px;
  margin: 8px 0;
  color: var(--sg-text);
  font-size: 0.92rem;
}}

.sg-action-card {{
  background: var(--sg-glass);
  border: 1px solid var(--sg-border);
  border-radius: 14px;
  padding: 14px 16px;
  margin: 10px 0;
  display: flex; align-items: center; gap: 12px;
}}
.sg-action-card .sg-icon {{ font-size: 1.4rem; }}
.sg-action-card .sg-detail {{ flex: 1; }}
.sg-action-card .sg-title {{ font-weight: 600; color: var(--sg-text); font-size: 0.92rem; }}
.sg-action-card .sg-sub {{ color: var(--sg-text-sub); font-size: 0.80rem; }}

hr {{ border-color: var(--sg-border) !important; opacity: 0.5; }}
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
                       gradient: str = "linear-gradient(135deg, #1E1B4B, #312E81)") -> str:
    """프로젝트 카드 HTML 반환 (외부에서 grid에 collect)."""
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
    html = "<div class='sg-project-grid'>" + "".join(
        project_card_html(p.get("title", "Untitled"),
                           p.get("edited", ""),
                           p.get("status", ""),
                           p.get("gradient", "linear-gradient(135deg, #1E1B4B, #312E81)"))
        for p in projects
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


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


def manuscript_preview(**kwargs) -> None:
    st.markdown(manuscript_preview_html(**kwargs), unsafe_allow_html=True)
