"""Agent Dashboard — Vision 다이어그램 'Agent Dashboard (상태/모니터링)'.

5층 메모리 통계 + 백로그 + budget + longitudinal trend + notification 한 화면.
Streamlit 자동 멀티페이지 → http://localhost:8501/dashboard
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

from app.styles.sapphire_glass import inject_sapphire_glass


def render():
    inject_sapphire_glass()
    st.markdown(
        "<div style='display:flex;align-items:center;gap:12px;padding:8px 0;'>"
        "<div style='width:36px;height:36px;border-radius:12px;"
        "background:linear-gradient(135deg,#3B82F6,#8B5CF6);'></div>"
        "<div><div style='font-weight:700;font-size:1.25rem;color:#F5F5FA;'>Agent Dashboard</div>"
        "<div style='color:#475569;font-size:0.82rem;'>시스템 상태 · 5층 메모리 · 백로그 · 알림</div>"
        "</div></div>", unsafe_allow_html=True)

    cols = st.columns(4)

    # ── 1. 5-layer memory stats ──
    with cols[0]:
        try:
            from src.memory import stats as mem_stats
            s = mem_stats()
        except Exception as e:
            s = {"error": str(e)[:120]}
        total = (s.get("episodic_events", 0) + s.get("working_events", 0)
                  + sum(v for k, v in s.items() if k.startswith("semantic.") and isinstance(v, int)))
        st.markdown(
            f"<div class='sg-card' style='text-align:center;'>"
            f"<div style='color:#475569;font-size:0.78rem;'>🧠 Memory total</div>"
            f"<div style='color:#A78BFA;font-weight:700;font-size:1.6rem;'>{total:,}</div>"
            f"<div style='color:#64748B;font-size:0.72rem;'>5층 누적</div>"
            f"</div>", unsafe_allow_html=True)

    # ── 2. Backlog stats ──
    with cols[1]:
        try:
            from src.runtime.backlog import status as bl_status
            bs = bl_status(limit=100)
            counts = bs.get("counts", {})
        except Exception:
            counts = {}
        pending = counts.get("CREATED", 0) + counts.get("RETRYING", 0)
        st.markdown(
            f"<div class='sg-card' style='text-align:center;'>"
            f"<div style='color:#475569;font-size:0.78rem;'>📋 Backlog pending</div>"
            f"<div style='color:#60A5FA;font-weight:700;font-size:1.6rem;'>{pending:,}</div>"
            f"<div style='color:#64748B;font-size:0.72rem;'>completed {counts.get('COMPLETED', 0)}</div>"
            f"</div>", unsafe_allow_html=True)

    # ── 3. Budget ──
    with cols[2]:
        try:
            from src.llm.budget import remaining
            r = remaining("day")
            pct = r.get("pct_used", 0)
            left = r.get("left_cost_usd", 0)
        except Exception:
            pct, left = 0, 0
        color = "#10B981" if pct < 60 else ("#F59E0B" if pct < 80 else "#F43F5E")
        st.markdown(
            f"<div class='sg-card' style='text-align:center;'>"
            f"<div style='color:#475569;font-size:0.78rem;'>💰 Today budget</div>"
            f"<div style='color:{color};font-weight:700;font-size:1.6rem;'>{pct:.0f}%</div>"
            f"<div style='color:#64748B;font-size:0.72rem;'>left ${left:.2f}</div>"
            f"</div>", unsafe_allow_html=True)

    # ── 4. Notifications ──
    with cols[3]:
        try:
            from src.runtime.notifier import stats as nstats
            n = nstats()
        except Exception:
            n = {}
        unread = n.get("unread", 0)
        bg = "rgba(244,63,94,0.12)" if unread > 0 else "rgba(255,255,255,0.04)"
        st.markdown(
            f"<div class='sg-card' style='text-align:center;background:{bg};'>"
            f"<div style='color:#475569;font-size:0.78rem;'>🔔 Notifications</div>"
            f"<div style='color:#FB7185;font-weight:700;font-size:1.6rem;'>{unread:,}</div>"
            f"<div style='color:#64748B;font-size:0.72rem;'>unread / total {n.get('total', 0)}</div>"
            f"</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    tabs = st.tabs(["🧠 Memory 5-layers", "📈 Longitudinal trend",
                     "🔔 Notifications", "🛠️ System info"])

    with tabs[0]:
        try:
            from src.memory import stats as mem_stats
            s = mem_stats()
            st.json(s)
        except Exception as e:
            st.error(str(e))

    with tabs[1]:
        try:
            from src.diagnostics.longitudinal_eval import summary
            ls = summary(days=30)
            st.metric("n_runs (30d)", ls.get("n_runs", 0))
            st.metric("avg pass_rate", ls.get("avg_pass_rate", 0))
            if ls.get("alerts"):
                st.error(f"⚠️ {len(ls['alerts'])} regression alerts")
                for a in ls["alerts"]:
                    st.markdown(f"- **{a['metric']}**: {a['latest']:.3f} (drop {a['drop']:.3f})")
            if ls.get("trends"):
                st.markdown("**Metric trends:**")
                for m, t in ls["trends"].items():
                    arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(t.get("direction"), "?")
                    st.markdown(f"- `{m}` {arrow} first={t.get('first', '?')} → last={t.get('last', '?')} "
                                 f"avg7={t.get('moving_avg_7')}")
        except Exception as e:
            st.warning(str(e))

    with tabs[2]:
        try:
            from src.runtime.notifier import list_unread, list_all, mark_read, mark_all_read
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("✓ Mark all read", use_container_width=True):
                    n = mark_all_read()
                    st.toast(f"{n} marked", icon="✅")
                    st.rerun()
            with c2:
                view = st.radio("view", ["Unread", "All"], horizontal=True,
                                 label_visibility="collapsed")
            items = list_unread(limit=50) if view == "Unread" else list_all(limit=100)
            if not items:
                st.markdown("<div class='sg-card' style='text-align:center;color:#475569;'>"
                             "알림 없음</div>", unsafe_allow_html=True)
            for it in items:
                sev = it.get("severity", "info")
                color = {"info": "#60A5FA", "warning": "#F59E0B",
                          "error": "#FB7185", "critical": "#DC2626"}.get(sev, "#475569")
                read_mark = "✅" if it.get("read") else "🔴"
                st.markdown(
                    f"<div class='sg-card' style='border-left:4px solid {color};margin:6px 0;'>"
                    f"<div style='display:flex;justify-content:space-between;'>"
                    f"<div><span style='color:{color};font-weight:600;'>{sev.upper()}</span> "
                    f"<span style='color:#F5F5FA;'>{it.get('title','')}</span></div>"
                    f"<div style='color:#64748B;font-size:0.74rem;'>{read_mark} {it.get('timestamp','')}</div>"
                    f"</div>"
                    f"<div style='color:#475569;font-size:0.84rem;margin-top:4px;'>"
                    f"{it.get('detail','')[:300]}</div></div>",
                    unsafe_allow_html=True)
                if not it.get("read"):
                    if st.button("Mark read", key=f"nm_{it['id']}"):
                        mark_read(it["id"])
                        st.rerun()
        except Exception as e:
            st.error(str(e))

    with tabs[3]:
        try:
            from src.runtime.heartbeat import JOBS
            st.markdown("**Heartbeat jobs:**")
            for j in JOBS:
                st.markdown(f"- `{j.name}` — every {j.interval_sec}s")
        except Exception as e:
            st.warning(str(e))
        try:
            from src.agent.roles import role_stats
            rs = role_stats()
            st.markdown(f"**Multi-agent roles**: {rs.get('n_roles', 0)}")
        except Exception:
            pass
        try:
            from app.agentic_loop import TOOL_SCHEMAS
            st.markdown(f"**Agentic tools**: {len(TOOL_SCHEMAS)}")
            with st.expander("Tool list"):
                for t in TOOL_SCHEMAS:
                    st.markdown(f"- `{t['name']}` — {t.get('description','')[:140]}")
        except Exception:
            pass


# Streamlit 자동 페이지 실행
try:
    render()
except Exception as _e:
    import traceback
    st.error(f"Dashboard 렌더 실패: {_e}")
    st.code(traceback.format_exc())
