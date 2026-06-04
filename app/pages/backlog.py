"""백로그 큐 가시화 — Streamlit 자동 멀티페이지 (`/backlog`).

PENDING / RUNNING / COMPLETED / FAILED를 카드 + events 로그로 실시간 표시.
manual drain 버튼 + OA 학습 진행도 (manifest_stats) + 미처리 작업 한 화면.

사용자 요구: "지금 논문 학습부터 미처리 많아. 다 로그 띄워."
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

from app.styles.sapphire_glass import inject_sapphire_glass, glass_card, action_card


def _fmt_ts(ts):
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


_STATUS_ICON = {
    "CREATED":   "⏳",
    "WAITING":   "⏸️",
    "RETRYING":  "🔁",
    "RUNNING":   "⚙️",
    "COMPLETED": "✅",
    "FAILED":    "❌",
}
_STATUS_COLOR = {
    "CREATED":   "rgba(124, 58, 237, 0.40)",
    "WAITING":   "rgba(168, 85, 247, 0.40)",
    "RETRYING":  "rgba(245, 158, 11, 0.50)",
    "RUNNING":   "rgba(59, 130, 246, 0.55)",
    "COMPLETED": "rgba(16, 185, 129, 0.50)",
    "FAILED":    "rgba(244, 63, 94, 0.50)",
}


def _enqueue_form():
    """수동 enqueue (테스트/관리용)."""
    with st.expander("➕ 새 작업 추가 (manual enqueue)"):
        from src.runtime.backlog import enqueue, JOB_COST
        kind = st.selectbox("Job kind", list(JOB_COST.keys()), key="bl_kind")
        payload_str = st.text_area("Payload (JSON)",
                                     value='{"query": "depression adolescents", "n_target": 50}'
                                            if kind == "oa_bulk_fetch" else "{}",
                                     height=100, key="bl_payload")
        c1, c2 = st.columns([1, 4])
        with c1:
            submit = st.button("➤ Enqueue", type="primary", use_container_width=True)
        if submit:
            try:
                payload = json.loads(payload_str or "{}")
                tid = enqueue(kind, payload, owner=st.session_state.get("user_email", ""))
                st.success(f"✓ enqueued: {kind} → task_id={tid}")
            except json.JSONDecodeError as e:
                st.error(f"JSON 파싱 실패: {e}")


def _stats_cards(stat: dict):
    """상단 KPI 카드: 전체/대기/실행/완료/실패."""
    counts = stat.get("counts", {})
    total = sum(counts.values())
    cols = st.columns(5)
    metrics = [
        ("전체", total, "#475569"),
        ("⏳ Pending", counts.get("CREATED", 0) + counts.get("WAITING", 0)
                       + counts.get("RETRYING", 0), "#A78BFA"),
        ("⚙️ Running", counts.get("RUNNING", 0), "#60A5FA"),
        ("✅ Done", counts.get("COMPLETED", 0), "#34D399"),
        ("❌ Failed", counts.get("FAILED", 0), "#FB7185"),
    ]
    for col, (label, n, color) in zip(cols, metrics):
        with col:
            st.markdown(
                f"<div class='sg-card' style='text-align:center;padding:18px 12px;'>"
                f"<div style='color:#475569;font-size:0.78rem;'>{label}</div>"
                f"<div style='color:{color};font-weight:700;font-size:1.8rem;'>{n}</div>"
                f"</div>", unsafe_allow_html=True)


def _job_list(stat: dict):
    items = stat.get("items", [])
    if not items:
        st.markdown("<div class='sg-card' style='text-align:center;color:#475569;padding:40px;'>"
                     "백로그가 비었습니다. 위 입력바 또는 ➕ 새 작업으로 추가하세요."
                     "</div>", unsafe_allow_html=True)
        return

    for it in items:
        st_label = it.get("status", "?")
        icon = _STATUS_ICON.get(st_label, "•")
        color = _STATUS_COLOR.get(st_label, "rgba(255,255,255,0.20)")
        inp = it.get("input") or {}
        out = it.get("output") or {}
        err = it.get("error") or ""

        # 핵심 라인 — kind, status, ts
        st.markdown(
            f"<div class='sg-card' style='border-left:4px solid {color};margin-bottom:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<div>"
            f"<span style='font-size:1.1rem;'>{icon}</span> "
            f"<span style='font-weight:600;color:#F5F5FA;'>{it['kind']}</span> "
            f"<span style='color:#475569;font-size:0.78rem;'>· {st_label}</span> "
            f"<span style='color:#64748B;font-size:0.72rem;margin-left:8px;'>"
            f"created {_fmt_ts(it.get('created_at'))} · updated {_fmt_ts(it.get('updated_at'))}</span>"
            f"</div>"
            f"<code style='color:#475569;font-size:0.70rem;'>{it.get('id', '')[:12]}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
        # input/output/error 디테일
        with st.expander("Details"):
            if inp:
                st.markdown("**Input**")
                st.code(json.dumps(inp, ensure_ascii=False, indent=2)[:1500], language="json")
            if out:
                st.markdown("**Output**")
                st.code(json.dumps(out, ensure_ascii=False, indent=2)[:1500], language="json")
            if err:
                st.markdown("**Error**")
                st.code(err[:1500])
        st.markdown("</div>", unsafe_allow_html=True)


def _events_log():
    """최근 backlog 관련 이벤트 — events.db에서 시간순."""
    try:
        from src.runtime.events import find
        rows = find(type=None, limit=50)
        rows = [r for r in rows if (r.get("type") or "").startswith("backlog")]
    except Exception as e:
        st.warning(f"events 로그 조회 실패: {e}")
        return
    if not rows:
        st.caption("(아직 backlog event 없음)")
        return
    for r in rows[:30]:
        pl = r.get("payload") or {}
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except Exception:
                pl = {"raw": pl}
        st.markdown(
            f"<div style='font-size:0.82rem;color:#475569;margin:4px 0;'>"
            f"<code style='color:#06B6D4;'>{r.get('ts', '?')[:19]}</code> "
            f"<span style='color:#F5F5FA;'>{r.get('type', '?')}</span> "
            f"<span style='color:#64748B;'>{json.dumps(pl, ensure_ascii=False)[:200]}</span>"
            f"</div>", unsafe_allow_html=True)


def _oa_learning_panel():
    """Europe PMC OA 수집 진행률 — 5만편 목표 대비."""
    try:
        from src.ingestion.oa_bulk_fetcher import manifest_stats
        stat = manifest_stats()
    except Exception as e:
        st.warning(f"OA manifest 조회 실패: {e}")
        return
    total = stat.get("total_papers", 0)
    chunked = stat.get("chunked_papers", 0)
    pct = (total / 50000) * 100 if 50000 else 0
    st.markdown(
        f"<div class='sg-card'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;'>"
        f"<div style='font-weight:600;color:#F5F5FA;'>🎓 PubMed OA 학습 진행도</div>"
        f"<div style='color:#475569;font-size:0.85rem;'>목표: 50,000편 — 의미있는 ontology</div>"
        f"</div>"
        f"<div style='margin-top:12px;color:#F5F5FA;font-size:1.6rem;font-weight:700;'>"
        f"{total:,} / 50,000 <span style='color:#A78BFA;font-size:0.9rem;'>({pct:.2f}%)</span></div>"
        f"<div style='margin-top:8px;height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden;'>"
        f"<div style='height:100%;width:{min(pct, 100):.2f}%;"
        f"background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);'></div>"
        f"</div>"
        f"<div style='margin-top:8px;color:#475569;font-size:0.80rem;'>"
        f"청킹 완료: {chunked:,} · 청킹 대기: {stat.get('pending_chunk', 0):,} · "
        f"총 char: {stat.get('total_chars', 0):,}</div>"
        f"</div>", unsafe_allow_html=True)

    # 🚀 5만편 학습 시작 / 추가 / Component lib 통계
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("🚀 5만편 학습 시작 (50 시드 enqueue)", use_container_width=True,
                      type="primary", key="bl_start_50k"):
            _bootstrap_learning(per=200, target=50000)
    with c2:
        if st.button("+ 빠른 시드 1k 추가", use_container_width=True, key="bl_quick"):
            _bootstrap_learning(per=200, target=1000)
    with c3:
        if st.button("📊 Component 통계", use_container_width=True, key="bl_compstat"):
            try:
                from src.library.components import get_library
                cs = get_library().stats()
                st.session_state["_bl_compstat"] = cs
            except Exception as e:
                st.warning(str(e))

    if "_bl_compstat" in st.session_state:
        cs = st.session_state["_bl_compstat"]
        with st.expander("📚 ComponentLibrary 통계", expanded=True):
            st.metric("총 components", cs.get("total", 0))
            if cs.get("by_kind"):
                st.markdown("**종류별:**")
                for k, n in cs["by_kind"].items():
                    st.markdown(f"- {k}: {n:,}")
            if cs.get("most_used"):
                st.markdown("**가장 자주 쓰임:**")
                for m in cs["most_used"]:
                    st.markdown(f"- ({m['n_uses']}회) `{m['kind']}` — {m['text'][:80]}")

    if stat.get("by_query"):
        with st.expander("Query별 분포"):
            for row in stat["by_query"]:
                st.markdown(f"- **{row['query'][:60]}** — {row['n']:,}편")


def _drain_all_background():
    """🌊 Drain ALL — 모든 대기 작업을 전부 처리. 큰 batch를 한 spinner 안에서 진행.
    UI는 progress bar로 한 건씩 표시. budget 초과 시 자동 중단."""
    try:
        from src.runtime.backlog import drain_once, status
        s0 = status(limit=500)
        pending = s0["counts"].get("CREATED", 0) + s0["counts"].get("RETRYING", 0)
        if pending == 0:
            st.warning("처리할 대기 작업이 없습니다.")
            return
        st.info(f"🌊 총 {pending:,}건 처리 시작 (한 건당 ~30초-3분 소요).")
        prog = st.progress(0.0, text=f"0 / {pending}")
        log_box = st.empty()
        done, fail = 0, 0
        for i in range(pending):
            r = drain_once(max_jobs=1)
            proc = r.get("processed", [])
            if not proc:
                # 남은 job 없거나 budget 초과로 skip
                if r.get("skipped"):
                    skp = r["skipped"][0]
                    st.warning(f"⏸ 중단: {skp.get('reason')} (budget {r.get('pct_used_today',0):.0f}%)")
                break
            for p in proc:
                if p.get("status") == "COMPLETED":
                    done += 1
                else:
                    fail += 1
            prog.progress((i + 1) / pending,
                            text=f"{i+1} / {pending} · ✅ {done} · ❌ {fail}")
            # 5건마다 manifest 갱신
            if (i + 1) % 5 == 0:
                try:
                    from src.ingestion.oa_bulk_fetcher import manifest_stats
                    ms = manifest_stats()
                    log_box.markdown(
                        f"<div style='color:#475569;font-size:0.84rem;'>"
                        f"📚 OA 누적 {ms['total_papers']:,}편 · "
                        f"{ms['total_chars']:,} chars</div>",
                        unsafe_allow_html=True)
                except Exception:
                    pass
        st.success(f"🌊 완료: ✅ {done} · ❌ {fail}")
        st.balloons()
    except Exception as e:
        st.error(f"Drain ALL 실패: {e}")


def _bootstrap_learning(*, per: int, target: int):
    """bootstrap_oa_learning.py와 같은 시드를 backlog에 enqueue."""
    try:
        # Streamlit Cloud는 scripts/ 가 sys.path에 없을 수 있어 안전하게 inline import
        import importlib.util as _ilu
        from pathlib import Path as _P
        spec = _ilu.spec_from_file_location(
            "_oa_seeds", str(_P(__file__).resolve().parent.parent.parent
                                  / "scripts" / "bootstrap_oa_learning.py"))
        if spec and spec.loader:
            mod = _ilu.module_from_spec(spec); spec.loader.exec_module(mod)
            DEFAULT_SEEDS = mod.DEFAULT_SEEDS
        else:
            DEFAULT_SEEDS = ["depression adolescent", "diabetes Korea", "obesity BMI"]
        from src.runtime.backlog import enqueue
        n_q = max(1, target // max(1, per))
        queries = (DEFAULT_SEEDS * (n_q // len(DEFAULT_SEEDS) + 1))[:n_q]
        enqueued = 0
        for q in queries:
            try:
                enqueue("oa_bulk_fetch",
                         {"query": q, "n_target": per, "year_min": 2018},
                         owner=st.session_state.get("user_email", "bootstrap@oa"))
                enqueued += 1
            except Exception:
                continue
        st.success(f"🚀 {enqueued}편의 OA bulk_fetch job 백로그 등록 완료.")
        st.info("⚠️ Streamlit Cloud 환경에선 heartbeat 백그라운드 worker가 없습니다. "
                "**▶ Drain now** 버튼을 직접 눌러 한 배치씩 처리하세요. "
                "(Docker 환경에선 learner 컨테이너가 5분마다 자동 drain)")
        st.toast(f"🚀 {enqueued} queries enqueued", icon="🚀")
    except Exception as e:
        st.error(f"bootstrap 실패: {e}")


def render():
    inject_sapphire_glass()

    # 헤더 + drain 버튼 3종
    c1, c2, c3, c4 = st.columns([5, 1.2, 1.4, 1.6])
    with c1:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:12px;padding:8px 0;'>"
            "<div style='width:36px;height:36px;border-radius:12px;"
            "background:linear-gradient(135deg,#3B82F6,#8B5CF6);'></div>"
            "<div><div style='font-weight:700;font-size:1.25rem;color:#F5F5FA;'>Backlog</div>"
            "<div style='color:#475569;font-size:0.82rem;'>"
            "미처리 작업 · API 한도 초과시 자동 대기 · heartbeat가 5분마다 처리"
            "</div></div></div>", unsafe_allow_html=True)
    with c2:
        if st.button("🔄 Refresh", use_container_width=True, key="bl_refresh"):
            st.rerun()
    with c3:
        if st.button("▶ Drain 5", use_container_width=True, key="bl_drain"):
            with st.spinner("백로그 5건 처리 중…"):
                try:
                    from src.runtime.backlog import drain_once
                    r = drain_once(max_jobs=5)
                    st.session_state["_bl_drain_result"] = r
                except Exception as e:
                    st.error(f"drain 실패: {e}")
    with c4:
        if st.button("🌊 Drain ALL", use_container_width=True, type="primary",
                      key="bl_drain_all",
                      help="대기 중인 모든 작업 처리 (시간 오래 걸림 · budget 80% 초과 시 high-cost 자동 skip)"):
            _drain_all_background()

    if "_bl_drain_result" in st.session_state:
        r = st.session_state.pop("_bl_drain_result")
        proc = r.get("processed", [])
        skip = r.get("skipped", [])
        st.toast(f"처리 {len(proc)}건 · skip {len(skip)}건 "
                  f"(today budget {r.get('pct_used_today', 0):.0f}%)", icon="✅")
        # 디테일을 expander로 표시 (사용자가 실제 무엇이 처리됐는지 확인)
        if proc or skip:
            with st.expander(f"🔍 Drain 결과 — processed {len(proc)} · skipped {len(skip)}",
                              expanded=True):
                if proc:
                    st.markdown("**처리됨:**")
                    for p in proc[:10]:
                        emoji = "✅" if p.get("status") == "COMPLETED" else "❌"
                        st.markdown(f"- {emoji} `{p.get('kind')}` ({p.get('id','')[:12]}) "
                                     f"{p.get('error', '')[:120]}")
                if skip:
                    st.markdown("**대기됨 (budget/handler):**")
                    for s in skip[:10]:
                        st.markdown(f"- ⏸️ `{s.get('kind')}` — {s.get('reason')}")

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # KPI cards
    try:
        from src.runtime.backlog import status as bl_status
        stat = bl_status(limit=100)
    except Exception as e:
        st.error(f"backlog 상태 조회 실패: {e}")
        return
    _stats_cards(stat)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    _oa_learning_panel()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    _enqueue_form()

    # 본문 — 작업 카드 + events
    tab1, tab2, tab3 = st.tabs(["📋 작업 큐", "📜 Events (실시간 로그)", "ℹ️ Job kinds"])
    with tab1:
        _job_list(stat)
    with tab2:
        _events_log()
    with tab3:
        try:
            from src.runtime.backlog import JOB_COST
            for k, cost in JOB_COST.items():
                badge = {"low": "🟢 low", "medium": "🟡 medium", "high": "🔴 high"}[cost]
                action_card(badge.split()[0], k,
                             f"비용 등급: {cost} · budget 80% 초과 시 high는 자동 대기")
        except Exception as e:
            st.warning(str(e))


# Streamlit 멀티페이지 자동 실행
try:
    render()
except Exception as _e:
    import traceback
    st.error(f"Backlog 렌더 실패: {_e}")
    st.code(traceback.format_exc())
