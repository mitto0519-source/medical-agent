"""Sapphire Glass entry point — Lovable-style UI 전용.

기존 `app/streamlit_app.py`와 완전 분리. 다른 port에서 독립 실행:
    streamlit run app/sapphire_app.py --server.port 8502

docker-compose의 `sapphire-ui` 서비스가 자동 실행 (port 8502).

라우팅: session_state["sg_view"] ∈ {"home", "workspace"} (default: home).
"""
from __future__ import annotations

import io
import os
import sys

# Windows CP949 → UTF-8 강제 (한글 로그 깨짐 방지)
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "buffer"):
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)
    except Exception:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dotenv import load_dotenv  # noqa: E402
from pathlib import Path as _P  # noqa: E402
load_dotenv(dotenv_path=_P(__file__).parent.parent / ".env", override=True)

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Medical-Agent · Sapphire",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": ("Medical-Agent — Sapphire Glass UI (Lovable 양식). "
                  "기존 단위 기능 UI는 별도 port 8501에서 동작.")},
)

# 환경 secrets → env
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

# Router
from app.sapphire_pages.lovable_home import render as render_home  # noqa: E402
from app.sapphire_pages.project_workspace import render as render_workspace  # noqa: E402

view = st.session_state.get("sg_view", "home")
if view == "workspace":
    pid = st.session_state.get("sg_active_project", "new")
    render_workspace(pid)
else:
    st.session_state["sg_view"] = "home"
    render_home()
