"""Memory Explorer — Vision 다이어그램 'Memory Explorer (기억 탐색/편집)'.

5층 메모리 + procedural rule + change_log + events 탐색·검색.
http://localhost:8501/memory_explorer
"""
from __future__ import annotations

import json
import sys
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
        "background:linear-gradient(135deg,#8B5CF6,#06B6D4);'></div>"
        "<div><div style='font-weight:700;font-size:1.25rem;color:#F5F5FA;'>Memory Explorer</div>"
        "<div style='color:#A3A3B8;font-size:0.82rem;'>5층 메모리 + procedural + events 탐색</div>"
        "</div></div>", unsafe_allow_html=True)

    # 검색 박스
    q = st.text_input("🔎 Query (모든 layer 동시 검색)", key="me_q",
                       placeholder="ZCB depression / Yoosun / aOR")
    owner = st.text_input("Owner email (선택, episodic 격리)", key="me_owner",
                            value=st.session_state.get("user_email", ""))

    if q:
        try:
            from src.memory import recall_all_layers
            layers = recall_all_layers(q, owner=owner or None, n_per_layer=5)
        except Exception as e:
            st.error(str(e))
            layers = {}

        # 5층 탭
        tabs = st.tabs([f"🧠 Episodic ({_n(layers.get('episodic'))})",
                         f"📚 Semantic ({len(layers.get('semantic') or [])})",
                         f"⚙️ Procedural ({len(layers.get('procedural') or [])})",
                         f"🎯 Goal ({len(layers.get('goal') or [])})",
                         f"⏱️ Working ({len(layers.get('working') or [])})"])
        with tabs[0]:
            ep = layers.get("episodic", "")
            if ep:
                st.code(ep[:3000], language=None)
            else:
                st.caption("(no episodic match)")
        with tabs[1]:
            for h in layers.get("semantic", [])[:10]:
                md = h.get("metadata", {})
                st.markdown(f"<div class='sg-card' style='margin:6px 0;'>"
                              f"<div style='color:#F5F5FA;font-size:0.92rem;'>"
                              f"{h.get('text','')[:300]}</div>"
                              f"<div style='color:#A3A3B8;font-size:0.74rem;'>"
                              f"score={h.get('score')} · {md.get('title','')[:80]}</div></div>",
                              unsafe_allow_html=True)
        with tabs[2]:
            for r in layers.get("procedural", [])[:10]:
                st.markdown(f"<div class='sg-card' style='margin:6px 0;'>"
                              f"<div style='color:#A78BFA;font-size:0.78rem;'>{r.get('domain','?')} "
                              f"· conf={r.get('confidence',0):.2f} · match={r.get('match_score',0):.2f}</div>"
                              f"<div style='color:#F5F5FA;font-size:0.88rem;margin-top:4px;'>"
                              f"<b>If</b> {r.get('trigger','')[:200]}<br/>"
                              f"<b>Then</b> {r.get('action','')[:300]}</div></div>",
                              unsafe_allow_html=True)
        with tabs[3]:
            for g in layers.get("goal", []):
                st.json(g)
        with tabs[4]:
            for w in layers.get("working", []):
                st.markdown(f"- {str(w.get('text',''))[:200]} (`{w.get('ts','')}`)")

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # 메모리 누적 통계
    with st.expander("📊 5층 누적 통계"):
        try:
            from src.memory import stats as ms
            st.json(ms())
        except Exception as e:
            st.warning(str(e))

    # Procedural rule 직접 추가
    with st.expander("➕ Procedural rule 추가"):
        with st.form("me_proc_add", clear_on_submit=True):
            tr = st.text_input("trigger (when/condition)")
            ac = st.text_input("action (then/strategy)")
            dom = st.selectbox("domain", ["general", "journal_review",
                                            "stat_method", "figure_style",
                                            "citation", "writing_style"])
            conf = st.slider("confidence", 0.0, 1.0, 0.5)
            sub = st.form_submit_button("Add rule", type="primary")
        if sub and tr and ac:
            try:
                from src.memory.procedural import add_rule
                rid = add_rule(trigger=tr, action=ac, domain=dom, confidence=conf)
                st.success(f"✓ rule added: {rid}")
            except Exception as e:
                st.error(str(e))

    # Recent events log
    with st.expander("📜 최근 events (audit)"):
        try:
            from src.runtime.events import recent
            etype = st.selectbox("type filter",
                                   ["(all)", "memory_episodic", "memory_quarantined",
                                    "safety", "backlog_done", "backlog_failed",
                                    "orchestrator_ingest", "components_extracted",
                                    "trigger_analyzed", "cognitive_activation",
                                    "planner_dag_done", "longitudinal_eval_recorded"],
                                   key="me_evt_type")
            n = st.slider("limit", 10, 200, 30, key="me_evt_n")
            rows = recent(n=n, type=None if etype == "(all)" else etype)
            for r in rows[:n]:
                st.markdown(f"<div style='color:#A3A3B8;font-size:0.80rem;'>"
                              f"<code>{r.get('ts','?')[:19]}</code> "
                              f"<span style='color:#06B6D4;'>{r.get('type','?')}</span> "
                              f"actor={r.get('actor','?')} "
                              f"{json.dumps(r.get('payload') or {}, ensure_ascii=False, default=str)[:200]}</div>",
                              unsafe_allow_html=True)
        except Exception as e:
            st.warning(str(e))


def _n(v):
    if v is None:
        return 0
    if isinstance(v, str):
        return 1 if v else 0
    try:
        return len(v)
    except Exception:
        return 0


# Streamlit 자동 페이지 실행
try:
    render()
except Exception as _e:
    import traceback
    st.error(f"Memory Explorer 렌더 실패: {_e}")
    st.code(traceback.format_exc())
