"""Chat service — system-prompt assembly + streaming + per-turn hooks.

Pure: takes project dict + user_msg, returns text generator. No Streamlit.
ez_home.py wraps these for the Streamlit chat panel; FastAPI later does SSE wrap.
"""
from __future__ import annotations

from typing import Generator, Iterable, Optional

from src.config.logging_config import get_logger
from src.service import rag as rag_service

_log = get_logger(__name__)


def _load_yoosun_style_block() -> str:
    """★ 조유선 풀텍스트 v3 (1저자 7편: 풀텍스트 5 + 메타 2) — 매 턴 inject.

    사용자 명시(2026-06-19): "abstract 찌끄라기 X — 본문 마디·스타일별 제대로".
    v3 = mitto 첨부 PDF 본문 → IMRaD 마디별 추출 + 공저자 2편 제외.
    + skills/yoosun_cho_writing/SKILL.md (외부 LLM 풀텍스트 13편 분석) supersedes prompts/yoosun_style.md v1.
    """
    from pathlib import Path as _P
    import json as _json
    # ★ v3 우선, 없으면 v2 폴백
    p3 = _P("data/agent_self/yoosun_style_v3.json")
    p2 = _P("data/agent_self/yoosun_style_v2.json")
    p = p3 if p3.exists() else p2
    if not p.exists():
        return ""
    try:
        d = _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    # v3은 본문 기반 — 풍부한 템플릿 + SKILL.md cross-ref
    if "moves" in d:  # v3 양식
        m = d.get("metrics", {})
        r = d.get("style_rules", {})
        mv = d.get("moves", {})
        parts = ["--- ★ YOOSUN STYLE v3 (1저자 7편 본문 마디 분석, 2026-06-19) ---"]
        parts.append(f"[skills/yoosun_cho_writing/SKILL.md supersedes prompts/yoosun_style.md v1]")
        parts.append(f"문장 길이: 평균 {m.get('avg_sent_len_words','?')} 단어 (중앙값 {m.get('median_sent_len_words','?')}, IQR {m.get('sent_len_iqr')}).")
        parts.append(f"표본 N: {m.get('min_n',0):,} ~ {m.get('max_n',0):,} (중앙값 {m.get('median_n',0):,}). 95% CI 추출 {m.get('ci_estimates_extracted')}개.")
        parts.append("")
        parts.append("★ IMRaD 마디 (M1~M10) 본문 양식:")
        for key in ("M1_intro_opening", "M2_gap", "M3_aim", "M4_methods_skeleton",
                      "M5_results_inline", "M6_discussion_opening",
                      "M7_mechanism_3steps", "M8_limitations_6items",
                      "M9_strengths", "M10_conclusions"):
            move = mv.get(key, {})
            if isinstance(move, dict) and move.get("template"):
                parts.append(f"  {key}: {move['template']}")
        parts.append("")
        parts.append("★ Discussion 시그니처 오프닝 (가장 식별적):")
        parts.append("  [설계] of [N] [Korean adults] (mean age, X) with [Y person-years], [노출] was associated with [결과].")
        parts.append("")
        parts.append("★ 통계 reporting (★ 고정):")
        parts.append(f"  - {r.get('stats_reporting','')}")
        parts.append(f"  - {r.get('effect_modification','')}")
        parts.append(f"  - per 1000 person-years · median follow-up X years · 성별 쌍 끝에 'respectively'")
        parts.append("")
        parts.append("★ 어휘:")
        parts.append("  권장: associated with · remained significant · effect modification · more pronounced · By contrast · even after adjustment for")
        parts.append(f"  금지: {', '.join(r.get('forbidden_overclaim', []))}")
        parts.append("")
        parts.append(f"★ Cohort: {', '.join(r.get('preferred_cohorts', [])[:2])}")
        parts.append(f"★ Estimators: {' · '.join(r.get('preferred_estimators', [])[:4])}")
        parts.append("--- END YOOSUN STYLE v3 ---")
        return "\n".join(parts)
    m = d.get("metrics", {})
    r = d.get("style_rules", {})
    mv = d.get("moves_pattern", {})
    parts = ["--- ★ YOOSUN STYLE v2 (5편 마디별 정량 분석, 2026-06-19) ---"]
    parts.append(f"문장 길이 목표: 평균 {m.get('avg_sent_len_words','?')} 단어 (중앙값 {m.get('median_sent_len_words','?')}, IQR {m.get('sent_len_p25_p75')}).")
    parts.append(f"수동태 비율 {m.get('passive_per_sentence','?')} · 헤지 {m.get('hedge_per_sentence','?')}.")
    parts.append(f"샘플 N 중앙값 {m.get('median_n','?'):,} · follow-up {m.get('follow_up_years_range')}년.")
    parts.append("")
    parts.append("★ Abstract 마디 (M1~M8) 강제 양식:")
    parts.append(f"  M1 (Gap): {mv.get('M1_gap_template','')}")
    parts.append(f"  M2 (Aim): {mv.get('M2_aim_template','')}")
    parts.append(f"  M3 (Methods): {' · '.join(mv.get('M3_methods_skeleton', []))}")
    parts.append(f"  M4 (Result): {mv.get('M4_result_template','')}")
    parts.append(f"  M5 (Secondary): {mv.get('M5_secondary_template','')}")
    parts.append(f"  M6 (Sensitivity): {mv.get('M6_sensitivity_template','')}")
    parts.append(f"  M7 (Added value): {mv.get('M7_added_value_template','')}")
    parts.append(f"  M8 (Conclusion): {mv.get('M8_conclusion_template','')}")
    parts.append("")
    parts.append("★ 통계 reporting 양식:")
    parts.append(f"  - {r.get('estimate_format','')}")
    parts.append(f"  - {r.get('interaction','')}")
    parts.append(f"  - {r.get('covariate_adjustment','')}")
    parts.append("")
    parts.append("★ 금지 (과대주장): " + ", ".join(r.get('forbidden_overclaim', [])))
    parts.append("★ 권장 추정기: " + " · ".join(r.get('preferred_estimator', [])))
    parts.append("★ Cohort 표현: " + r.get('preferred_cohort_phrase', ''))
    parts.append("--- END YOOSUN STYLE v2 ---")
    return "\n".join(parts)


def _load_datasets_block(owner_email: str = "") -> str:
    """★ 사용자가 '데이터셋 위치 어디?'를 매번 묻게 되는 J3 fix.

    이미 등록된 데이터셋(Supabase ma_datasets + 로컬 dataset_*.json)과 실 파일
    (data/raw/*.sav)을 매 턴 system 최상단 블록으로 inject.
    LLM이 "데이터 위치 알려주세요" 같은 헛질문을 안 하게.
    """
    parts = ["--- ★ REGISTERED DATASETS (서버·로컬에 이미 로드됨, 위치 묻지 말 것) ---"]

    # 1) DatasetLibrary 등록본 (Supabase + 로컬)
    try:
        from src.library.dataset_library import DatasetLibrary
        lib = DatasetLibrary()
        registered = list(lib._datasets.keys()) if hasattr(lib, "_datasets") else []
        if registered:
            parts.append(f"등록 데이터셋: {', '.join(registered[:20])}")
    except Exception as _e:
        _log.debug("DatasetLibrary load fail: %s", _e)

    # 2) 실 파일 — KYRBS 21년치
    from pathlib import Path as _P
    raw = _P("data/raw")
    if raw.exists():
        kyrbs = sorted([f.stem for f in raw.glob("kyrbs*.sav")])
        if kyrbs:
            years = sorted(set(int(s.replace("kyrbs", "")) for s in kyrbs
                                  if s.replace("kyrbs", "").isdigit()))
            if years:
                parts.append(f"★ KYRBS (청소년건강행태조사) .sav: {len(years)}년 — "
                              f"{years[0]}~{years[-1]} 전체 보유 (data/raw/kyrbs{{year}}.sav)")
        knhanes_dir = raw / "knhanes"
        if knhanes_dir.exists():
            kns = list(knhanes_dir.glob("HN*.zip"))
            if kns:
                parts.append(f"★ KNHANES (국민건강영양조사) ZIP: {len(kns)}개 "
                              f"(data/raw/knhanes/HN*.zip — 자동 압축해제+로드)")
        misc = [f.name for f in raw.glob("*.xlsx")] + [f.name for f in raw.glob("*.csv")]
        if misc:
            parts.append(f"기타 raw 파일: {', '.join(misc[:10])}")

    # 3) 컴포넌트 라이브러리 (data/library/components.db) 통계
    try:
        import sqlite3
        comp_db = _P("data/library/components.db")
        if comp_db.exists():
            conn = sqlite3.connect(str(comp_db))
            try:
                n = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
                if n: parts.append(f"★ 컴포넌트 라이브러리: {n:,}개 (도표·인용·문체 단위 검색 가능)")
            except Exception: pass
            conn.close()
    except Exception:
        pass

    # 4) 사용자별 본인 코호트 (attachments는 project에서, 여기선 hint만)
    parts.append("")
    parts.append("★ 데이터 로딩 양식 (절대 위치 묻지 말 것):")
    parts.append("  - KYRBS: from src.data.kyrbs_raw_loader import KYRBSLoader; KYRBSLoader().load('data/raw/kyrbs2025.sav')")
    parts.append("  - KNHANES: from src.data.knhanes_raw_loader import KNHANESLoader; KNHANESLoader().load(year=2023)")
    parts.append("  - 사용자 코호트 xlsx: project['attachments']에 universal_loader로 미리 로드돼 system prompt 하단에 inject됨.")
    parts.append("  - 통계: from src.data.stat_bridge import StatBridge; StatBridge().run(df, spec)")
    parts.append("--- END DATASETS ---")
    return "\n".join(parts)


def _load_research_state_block(project: dict) -> str:
    """★ RESEARCH_STATE_SPEC §1.5: 매 턴 강제 로드.

    project가 활성 연구라면 objective + locked_decisions + forbidden_changes를
    system 최상단 블록으로 반환. 이게 빠지면 매번 시드 데모(ZCB)로 회귀 → 멍청함.
    """
    rs = (project.get("research_state") or {}) if isinstance(project, dict) else {}
    if not rs:
        return ""
    parts = ["--- ★ ACTIVE RESEARCH PROJECT (mandatory state load, 매 턴 강제) ---"]
    obj = rs.get("objective") or rs.get("topic") or project.get("title")
    if obj:
        parts.append(f"OBJECTIVE: {obj}")
    pico = rs.get("pico") or {}
    if isinstance(pico, dict) and any(pico.values()):
        for k in ("population", "exposure", "outcome", "study_design"):
            v = pico.get(k)
            if v: parts.append(f"  {k.upper()}: {v}")
    locked = rs.get("locked_decisions") or {}
    if isinstance(locked, dict) and locked:
        parts.append("LOCKED_DECISIONS (절대 변경 금지 — 사용자가 명시 승인 없이는 X):")
        for k, v in locked.items():
            if v: parts.append(f"  · {k}: {v}")
    forb = rs.get("forbidden_changes") or []
    if forb:
        parts.append("FORBIDDEN_CHANGES (이 방향으로 절대 회귀 X):")
        for f in forb[:6]:
            parts.append(f"  · {f}")
    dataset = rs.get("dataset")
    if dataset:
        parts.append(f"DATASET: {dataset}")
    parts.append("")
    parts.append("★ '묻지 말고 결정' 규율 (§1.5 B):")
    parts.append("  - 불확실해도 '추가 정보 주세요'로 사용자에 핑퐁 금지.")
    parts.append("  - 가장 방어적 설계 + 가정 명시 + 진행 (예: '나이 누락 → AGE 결측 listwise drop 가정').")
    parts.append("  - STATS gate 외에는 멈추지 말고 완성까지.")
    parts.append("--- END ACTIVE PROJECT ---")
    return "\n".join(parts)


def build_full_system(project: dict, user_msg: str, *, owner_email: str = "") -> str:
    """Single-core system prompt: ★ ACTIVE PROJECT (mandatory) → persona → RAG → rules.

    RESEARCH_STATE_SPEC §1.5 강제: 매 턴 시작에 활성 프로젝트 state 로드 → system 최상단.
    이게 빠지면 '제로음료-우울' 시드 데모로 회귀하는 J3 root cause.
    """
    # ★ MANDATORY 1: 등록된 데이터셋 블록 (위치 묻지 마라)
    datasets_block = _load_datasets_block(owner_email)

    # ★ MANDATORY 2: 활성 프로젝트 state 최상단 (다른 모든 것보다 먼저)
    active_state = _load_research_state_block(project)

    # ★ MANDATORY 3: 조유선 5편 마디별 스타일 v2 (yoosun_style_v2)
    yoosun_block = _load_yoosun_style_block()

    try:
        from src.agent.persona import get_system_prompt
        base_sys = get_system_prompt(task="chat", owner_email=owner_email or None)
    except Exception as e:
        _log.warning("persona load fail: %s", e)
        base_sys = "당신은 의학 연구 코파일럿입니다."

    # 데이터셋 + 활성 state + yoosun v2 셋 다 base_sys보다 앞 (LLM이 가장 먼저 읽음)
    prefix = ""
    if datasets_block:
        prefix += datasets_block + "\n\n"
    if active_state:
        prefix += active_state + "\n\n"
    if yoosun_block:
        prefix += yoosun_block + "\n\n"
    if prefix:
        base_sys = prefix + base_sys

    try:
        from app.agentic_loop import build_system_with_preview
        full_sys = build_system_with_preview(base_sys, project, user_msg)
    except Exception as e:
        _log.warning("agentic_loop build fail: %s", e)
        full_sys = base_sys

    rag_block = rag_service.retrieve_as_text_block(user_msg, top_k=5, max_text_per_hit=600)
    if rag_block:
        full_sys = (
            full_sys
            + "\n\n--- RETRIEVED MEDICAL EVIDENCE (cite by PMID inline as [PMID:xxx]) ---\n"
            + rag_block
            + "\n--- END EVIDENCE ---"
        )

    # ★ 첨부 파일 컨텍스트 inject (2026-06-16) — project["attachments"]에 저장된 텍스트 추출본
    # universal_loader.load()로 미리 추출됐고 영속화됨. 다음 turn마다 system prompt에 자동.
    attachments = project.get("attachments") or []
    if attachments:
        try:
            from src.ingestion.universal_loader import render_for_llm
            att_block = render_for_llm(attachments[-6:], max_text_per_file=4000)
            if att_block:
                full_sys = full_sys + "\n\n" + att_block
        except Exception as e:
            _log.debug("attachments inject fail: %s", e)

    rule_overlay = (
        "\n\n--- RULE-8 (vibe paper) ---\n"
        "★ RESEARCH_STATE_SPEC §1.5 강제 (위 ACTIVE PROJECT 블록이 있다면):\n"
        "  - LOCKED_DECISIONS는 사용자가 명시 승인 없이 절대 변경 X.\n"
        "  - FORBIDDEN_CHANGES 방향으로 절대 회귀 X (예: 흡연-심혈관 잡았는데 '제로음료-우울'로 돌아가기 X).\n"
        "  - 사용자가 다른 주제 단어를 던져도 ACTIVE PROJECT가 있으면 그 안에서 보조 발견(secondary)으로 정리.\n"
        "  - exposure/outcome을 또 묻지 말 것 — 이미 LOCKED. 데이터셋도 또 묻지 말 것.\n"
        "★ '묻지 말고 결정':\n"
        "  - 모호하면 PICO·통계·하위군 중 짧은 역질문 2-3개. **단 ACTIVE PROJECT 있으면 묻지 말고 기본값으로 진행** + 가정 명시.\n"
        "  - '알아서 해' '그냥 해' '한번에' = STATS gate 외엔 안 묻고 완성까지.\n"
        "응답은 한국어 대화체, 동료 의학연구자 어투, 마크다운 짧게.\n"
        "위 RETRIEVED MEDICAL EVIDENCE를 참고해 답변에 PMID 인라인 인용을 넣으세요."
    )
    return full_sys + rule_overlay


def stream_reply(
    project: dict,
    user_msg: str,
    *,
    extra_system: str = "",
    max_tokens: int = 1200,
    owner_email: str = "",
) -> Generator[str, None, None]:
    """Generator yielding token chunks via failover LLM client."""
    try:
        from src.llm import get_llm_client
    except Exception as e:
        yield f"(LLM 클라이언트 import 실패: {e})"
        return

    full_sys = build_full_system(project, user_msg, owner_email=owner_email)
    if extra_system:
        full_sys = full_sys + "\n\n--- TASK OVERLAY ---\n" + extra_system

    history_lines = []
    for m in project.get("messages", [])[-10:]:
        role = "사용자" if m.get("role") == "user" else "코파일럿"
        history_lines.append(f"{role}: {m.get('content','')}")
    prompt = "\n".join(history_lines) + f"\n사용자: {user_msg}\n코파일럿:"

    try:
        client = get_llm_client(task="paper_writing")
        yielded = False
        for chunk in client.generate_streamed(prompt, system_prompt=full_sys, max_tokens=max_tokens):
            if chunk:
                yielded = True
                yield chunk
        if not yielded:
            yield "(빈 응답)"
    except Exception as e:
        _log.warning("stream_reply LLM fail: %s", e)
        yield f"(LLM 호출 실패: {e})"


def stream_turn(project: dict, msg: str, *,
                  owner_email: str = "",
                  save_project_fn=None,
                  max_tokens: int = 4096,
                  max_iters: int = 6):
    """3-Lane event generator — FRONTEND_MIGRATION_SPEC §5.5.3.

    HOT (<300ms):  status emit immediately (no model wait)
    STREAM:        tool_start / tool_result / token events as LLM dispatches tools
    BACKGROUND:    provenance / confidence / critique deferred → badge events at end

    Yields ChatEvent. ez_home / FastAPI both consume this same generator.
    """
    from src.service import events as ev
    import time as _t

    # === HOT LANE — instant ack (no LLM wait) ===
    t0 = _t.time()
    yield ev.status("이해 중", lane="hot", elapsed_ms=int((_t.time()-t0)*1000))

    # Build system prompt (cached when project unchanged)
    full_sys = build_full_system(project, msg, owner_email=owner_email)
    yield ev.status("컨텍스트 합성 완료", lane="hot",
                       elapsed_ms=int((_t.time()-t0)*1000))

    try:
        from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler
    except Exception as e:
        yield ev.error("agentic_loop_import", str(e)[:200])
        yield ev.done()
        return

    _proj_ref = {"p": project}
    _tool_events: list = []   # captured tool events to yield after dispatch

    def _get(): return _proj_ref["p"]
    def _set(p):
        _proj_ref["p"] = p
        if save_project_fn:
            try: save_project_fn(p)
            except Exception as _e: _log.debug("save_project_fn fail: %s", _e)
    def _evt(t, payload):
        # Map legacy tool handler events → ChatEvent
        if t == "preview_patched":
            _tool_events.append(ev.tool_result("patch_preview", payload))
        elif t == "user_message":
            _tool_events.append(ev.status(payload.get("user_message", "")[:200]))
        else:
            _tool_events.append(ev.status(f"{t}: {str(payload)[:120]}"))

    handler = make_tool_handler(_get, _set, _evt)

    # === STREAM LANE — native tool-use dispatch ===
    yield ev.status("LLM dispatch 시작", lane="stream")

    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="chat_orchestrate")
        active = getattr(client, "_active", client)

        # ★ Streaming + tools (2026-06-15) — 토큰 단위 yield로 Claude/VS Code 양식 효과
        if hasattr(active, "generate_with_tools_streamed"):
            text_acc: list = []
            for chunk in active.generate_with_tools_streamed(
                    user_message=msg, tools=TOOL_SCHEMAS, tool_handler=handler,
                    system_prompt=full_sys, max_tokens=max_tokens, max_iters=max_iters):
                ct = chunk.get("type")
                if ct == "text_delta":
                    text_acc.append(chunk.get("text", ""))
                    yield ev.token("body", chunk.get("text", ""))
                elif ct == "tool_start":
                    yield ev.tool_start(chunk.get("tool", "?"),
                                          args_brief=str(chunk.get("input", ""))[:120])
                elif ct == "tool_result":
                    yield ev.tool_result(chunk.get("tool", "?"),
                                            {"preview": (chunk.get("result_preview") or "")[:300]})
                elif ct == "error":
                    yield ev.warning("stream_partial", chunk.get("msg", "")[:200])
                elif ct == "done":
                    # captured preview_patched 등 chat events flush
                    for e in _tool_events: yield e
                    _tool_events.clear()
            text = "".join(text_acc)
        elif hasattr(active, "generate_with_tools"):
            # Non-streaming tool-use fallback
            result = active.generate_with_tools(
                user_message=msg, tools=TOOL_SCHEMAS, tool_handler=handler,
                system_prompt=full_sys, max_tokens=max_tokens, max_iters=max_iters,
            )
            text = result.get("text", "")
            trace = result.get("trace") or []
            for t in trace:
                yield ev.tool_start(t.get("tool", "?"),
                                      args_brief=str(t.get("input", ""))[:120])
                yield ev.tool_result(t.get("tool", "?"),
                                       {"preview": (t.get("result_preview") or "")[:400]})
            for e in _tool_events:
                yield e
            if text:
                yield ev.token("body", text)
        else:
            # Plain streamed text fallback
            yield ev.warning("no_tools", "client lacks tool-use, text-only stream")
            buf = []
            for chunk in client.generate_streamed(msg, system_prompt=full_sys,
                                                      max_tokens=max_tokens):
                if chunk:
                    buf.append(chunk)
                    yield ev.token("body", chunk)
            text = "".join(buf)
    except Exception as e:
        # 에러 출력은 silent log + UI에는 한 줄만
        _log.warning("dispatch fail: %s", str(e)[:300])
        yield ev.error("dispatch", str(e)[:150])
        yield ev.done()
        return

    # === BACKGROUND LANE — deferred verification badges (non-blocking concept) ===
    # NOTE: Streamlit context blocks true async. We emit badges inline but mark them
    # as background so the UI knows they came after primary content.
    try:
        from src.reliability.confidence import aggregate
        manuscript = (_proj_ref["p"].get("research_state") or {}).get("manuscript_text") or text
        rep = aggregate(draft=manuscript)
        yield ev.badge("confidence", rep.overall,
                          components=rep.components, lane="background")
        for issue in rep.issues[:3]:
            yield ev.warning("provenance", issue, lane="background")
    except Exception as e:
        _log.debug("background confidence fail: %s", e)

    yield ev.done(elapsed_ms=int((_t.time()-t0)*1000),
                     n_tool_events=len(_tool_events))


def dispatch_with_tools(project: dict, user_msg: str, *,
                           owner_email: str = "",
                           save_project_fn=None,
                           append_chat_event_fn=None,
                           max_tokens: int = 4096,
                           max_iters: int = 6) -> dict:
    """Native Anthropic tool-use dispatch — replaces regex JSON parser.

    LLM이 tools=[patch_preview, kyrbs_stat, rag_search, ...] 양식 tool_use 블록을 반환하면
    agentic_loop.make_tool_handler 가 직접 실행 → project.sections 갱신.
    이걸로 patch_preview/stat/figure/refs/strobe/rag 18개 툴 동시 작동.

    save_project_fn: callback(project_dict) — handler가 project를 mutate한 후 호출
    append_chat_event_fn: callback(event_type, payload) — preview_patched 등 chat 이벤트

    Returns: {"text": str, "trace": list, "stop_reason": str, "iters": int}
    """
    full_sys = build_full_system(project, user_msg, owner_email=owner_email)
    try:
        from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler
    except Exception as e:
        _log.warning("agentic_loop import fail: %s", e)
        return {"text": f"(agentic_loop import 실패: {e})", "trace": [],
                 "stop_reason": "import_error", "iters": 0}

    _proj_ref = {"p": project}

    def _get(): return _proj_ref["p"]
    def _set(p):
        _proj_ref["p"] = p
        if save_project_fn:
            try: save_project_fn(p)
            except Exception as e: _log.debug("save_project_fn fail: %s", e)
    def _evt(t, payload):
        if append_chat_event_fn:
            try: append_chat_event_fn(t, payload)
            except Exception as e: _log.debug("append_chat_event fn fail: %s", e)

    handler = make_tool_handler(_get, _set, _evt)

    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="paper_writing")
        # Unwrap failover wrapper if present
        active = getattr(client, "_active", client)
        if not hasattr(active, "generate_with_tools"):
            _log.warning("active client lacks generate_with_tools — text-only fallback")
            text = "".join(client.generate_streamed(user_msg, system_prompt=full_sys,
                                                       max_tokens=max_tokens))
            return {"text": text, "trace": [], "stop_reason": "no_tools",
                     "iters": 0}
        result = active.generate_with_tools(
            user_message=user_msg,
            tools=TOOL_SCHEMAS,
            tool_handler=handler,
            system_prompt=full_sys,
            max_tokens=max_tokens,
            max_iters=max_iters,
        )
        return result
    except Exception as e:
        _log.warning("dispatch_with_tools fail: %s", e)
        return {"text": f"(tool dispatch 실패: {e})", "trace": [],
                 "stop_reason": "exception", "iters": 0}


def post_turn_hooks(project: dict, user_msg: str, full_reply: str, *, owner_email: str = "") -> None:
    """After-each-turn persistence: conversation_memory + events + typed memory + change_log."""
    try:
        from src.memory.conversation_memory import record as _cm_record
        _cm_record(user_message=user_msg, agent_response=full_reply,
                    topic=project.get("title", "")[:80],
                    context_type="ez_home_chat", quality="neutral",
                    owner_email=owner_email or "")
    except Exception as e:
        _log.debug("conversation_memory.record fail: %s", e)

    try:
        from src.runtime.events import append as _evt
        _evt(type="ez_home_chat_turn",
              payload={"pid": project.get("id"), "user": user_msg[:300],
                       "resp_len": len(full_reply)},
              actor=owner_email or "anon")
    except Exception as e:
        _log.debug("events.append fail: %s", e)

    try:
        from src.memory.router import write as _mem_write
        _mem_write(f"[chat:{project.get('id','')}] {user_msg[:200]} || {full_reply[:400]}",
                    type="episodic", source="ez_home_chat",
                    owner_email=owner_email or None,
                    extra_meta={"project_id": project.get("id"),
                                  "project_title": project.get("title", "")[:80]})
    except Exception as e:
        _log.debug("memory.router.write fail: %s", e)

    try:
        from src.memory import change_log as _cl
        _cl.log(title=f"chat turn: {user_msg[:50]}",
                 action_type="chat",
                 description=f"pid={project.get('id')} user={user_msg[:200]}",
                 why_better="user dialogue accumulated for cross-session context",
                 impact={"project_id": project.get("id")})
    except Exception as e:
        _log.debug("change_log.log fail: %s", e)
