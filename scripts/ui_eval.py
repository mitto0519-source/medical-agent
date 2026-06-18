"""UI Eval Harness — browser-agent 회귀 eval (Anthropic 'evals for AI agents' 방식).

각 task = (페이지/워크플로) + graders(assertions). 실 브라우저로 admin 로그인 후
모든 task를 돌리고 assertion별 PASS/FAIL을 구조화 리포트로 남긴다.
회귀 eval(목표 ~100%): 점수 하락 = 무언가 깨짐. 거짓양성 방지를 위해 채팅 버블 내
에러 텍스트, 섹션 실제 반영, 영속 복원까지 '결과(outcome)'를 검증한다.

전제: 컨테이너/앱이 BASE_URL에서 healthy.
실행: python scripts/ui_eval.py
결과: scripts/ui_eval_outputs/{report.json, report.md, *.png}
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8501"
ADMIN = "mitto0519@gmail.com"
OUT = Path("scripts/ui_eval_outputs")
OUT.mkdir(parents=True, exist_ok=True)

_ERR_KW = ["Traceback", "오류:", "Error code", "Exception", "찾을 수 없",
           "AttributeError", "KeyError", "ModuleNotFound", "is not defined",
           "credit balance", "I/O operation"]


# ── 공통 ──────────────────────────────────────────────────────────────────
def wait_idle(page: Page, ms: int = 2200):
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=ms)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def nav(page: Page, label: str) -> bool:
    try:
        btn = page.get_by_role("button", name=re.compile(re.escape(label))).first
        try:
            btn.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        btn.click(timeout=6000)
        wait_idle(page)
        return True
    except Exception:
        return False


# ── Graders (page -> (passed, detail)) ─────────────────────────────────────
def g_no_exception(page: Page):
    n = len(page.query_selector_all('[data-testid="stException"]'))
    return n == 0, f"stException={n}"


def g_no_error_text(page: Page):
    hits = []
    for sel in ['[data-testid="stAlert"]', '[data-testid="stChatMessage"]']:
        for el in page.query_selector_all(sel):
            try:
                t = el.inner_text()
            except Exception:
                continue
            if any(k in t for k in _ERR_KW):
                hits.append(t[:120])
    return len(hits) == 0, ("; ".join(hits)[:200] if hits else "no error text")


def g_text_present(text: str):
    def _g(page: Page):
        n = page.get_by_text(re.compile(re.escape(text))).count()
        return n > 0, f"'{text}' x{n}"
    return _g


# ── Tasks ──────────────────────────────────────────────────────────────────
def task_render(label: str, marker: str):
    """페이지 클릭 → 렌더 마커 + 무에러 검증."""
    def _run(page: Page) -> list:
        ok_nav = nav(page, label) if label != "홈" else (wait_idle(page) or True)
        page.screenshot(path=str(OUT / f"render_{label}.png"))
        res = [("navigated", ok_nav, label)]
        res.append(("marker:" + marker, *g_text_present(marker)(page)))
        res.append(("no_exception", *g_no_exception(page)))
        res.append(("no_error_text", *g_no_error_text(page)))
        return res
    return (f"render:{label}", _run)


def task_chat_write(page: Page) -> list:
    """워크플로 — 채팅으로 서론 작성 시 우측 Introduction 섹션에 실제 반영(outcome)."""
    nav(page, "논문 작업실")
    chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
    chat.fill("청소년 스마트폰 과사용과 수면부족 연구로 서론 한 단락 써줘")
    chat.press("Enter")
    filled = ""
    for _ in range(30):
        page.wait_for_timeout(3000)
        # 에러가 채팅에 떴으면 즉시 실패 판정 위해 수집
        err_ok, err_d = g_no_error_text(page)
        try:
            filled = page.get_by_label("Introduction", exact=True).input_value(timeout=2000)
        except Exception:
            filled = ""
        if (filled and len(filled.strip()) > 40) or not err_ok:
            break
    page.screenshot(path=str(OUT / "flow_chat_write.png"))
    err_ok, err_d = g_no_error_text(page)
    return [
        ("chat_no_error", err_ok, err_d),
        ("introduction_filled(outcome)", bool(filled and len(filled.strip()) > 40), f"len={len(filled)}"),
    ]


def task_save_restore(page, browser) -> list:
    """워크플로 — 저장 후 새 세션에서 복원(영속성, outcome)."""
    res = []
    try:
        page.get_by_role("button", name=re.compile("💾 저장")).first.click(timeout=5000)
        wait_idle(page, 2000)
        res.append(("save_clicked", page.get_by_text(re.compile("저장됨")).count() > 0, ""))
    except Exception as e:
        res.append(("save_clicked", False, str(e)[:100]))
        return res
    # 새 세션
    ctx = browser.new_context()
    p2 = ctx.new_page()
    p2.set_viewport_size({"width": 1500, "height": 1000})
    p2.goto(f"{BASE}/?email={ADMIN}&auto=1", wait_until="domcontentloaded", timeout=30000)
    wait_idle(p2, 5000)
    nav(p2, "논문 작업실")
    restored = ""
    try:
        p2.locator('[data-testid="stSelectbox"]').first.click(timeout=6000)
        p2.wait_for_timeout(800)
        p2.get_by_role("option").nth(1).click(timeout=4000)
        wait_idle(p2, 1200)
        p2.get_by_role("button", name=re.compile("열기")).first.click(timeout=6000)
        wait_idle(p2, 2500)
        restored = p2.get_by_label("Introduction", exact=True).input_value(timeout=3000)
    except Exception as e:
        restored = ""
        res.append(("restore_exec", False, str(e)[:100]))
    p2.screenshot(path=str(OUT / "flow_save_restore.png"))
    res.append(("restored_in_new_session(outcome)", bool(restored and len(restored.strip()) > 40), f"len={len(restored)}"))
    ctx.close()
    return res


def task_kyrbs_survey_logistic(page: Page) -> list:
    """J4 (E2E_PILOT_TEST_PLAN) — KYRBS 2023 survey-weighted logistic → 표 → 프리뷰.

    SELF_EVOLUTION_SPEC gold_set.survey_design_test_cases와 동일 spec:
       outcome=M_SAD, exposure=F_CAFFEINE, covariates=[AGE,SEX,GRADE],
       strata=STRATA, cluster=CLUSTER, weight=W

    Litmus test: 'KYRBS 2023으로 로지스틱 돌려 표 만들어'가 끝까지(load→survey
    stats→table→preview 삽입) 가는지가 뇌 embed의 첫 그린.
    """
    res = []
    nav(page, "논문 작업실")
    try:
        ta = page.locator('textarea, [contenteditable="true"]').first
        ta.click(timeout=4000)
        ta.fill("KYRBS 2023 데이터로 caffeine 섭취와 우울증의 로지스틱 회귀를 "
                "복합표본설계(strata/cluster/weight) 반영해서 돌리고 "
                "결과를 표(Table 2)로 만들어줘. covariates는 age, sex, grade.")
        page.keyboard.press("Enter")
        res.append(("j4_prompt_sent", True, "KYRBS 2023 survey-weighted logistic"))
    except Exception as e:
        res.append(("j4_prompt_sent", False, str(e)[:120]))
        return res

    # Wait for response — long-running stat call
    table_appeared = False
    survey_engine_mentioned = False
    deadline = time.time() + 90
    while time.time() < deadline:
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text()[:30000]
        # Sentinels — table markers + survey engine mention
        if any(k in body for k in ("Table 2", "표 2", "aOR", "Adjusted OR")):
            table_appeared = True
        if any(k in body for k in ("SurveyDesign", "Taylor", "survey-weighted",
                                       "복합표본", "wt_itvex", "W ", "weights")):
            survey_engine_mentioned = True
        if table_appeared and survey_engine_mentioned:
            break
        if not g_no_error_text(page)[0]:
            break

    page.screenshot(path=str(OUT / "j4_kyrbs_survey_logistic.png"), full_page=True)
    res.append(("j4_table_produced(outcome)", table_appeared, ""))
    res.append(("j4_survey_engine_used", survey_engine_mentioned,
                  "expected: SurveyDesign / Taylor / wt_itvex"))
    res.append(("j4_no_error", *g_no_error_text(page)))
    res.append(("j4_no_exception", *g_no_exception(page)))
    return res


def task_citation_fullset(page: Page) -> list:
    """워크플로 — 인용/레퍼런스 모드: PMID 검수 → 풀셋(Word/EndNote) 생성(outcome)."""
    res = []
    nav(page, "논문 작업실")
    # 모드 전환: 📚 인용/레퍼런스
    try:
        page.get_by_text(re.compile("인용/레퍼런스")).first.click(timeout=6000)
        wait_idle(page, 1500)
        res.append(("mode_switched", True, "인용/레퍼런스"))
    except Exception as e:
        res.append(("mode_switched", False, str(e)[:100]))
        return res
    # 레퍼런스(실 PMID 2개) 입력
    try:
        ta = page.locator('textarea[aria-label="레퍼런스 목록"], textarea[placeholder*="한 줄에 하나씩"]').first
        ta.fill("33069327\n29186274")
        page.get_by_role("button", name=re.compile("차용 가능성 검수")).first.click(timeout=6000)
    except Exception as e:
        res.append(("screen_clicked", False, str(e)[:100]))
        return res
    # 검수 결과 테이블 대기
    screened = False
    for _ in range(20):
        page.wait_for_timeout(3000)
        if page.get_by_text(re.compile("검수 결과")).count() > 0:
            screened = True
            break
        if not g_no_error_text(page)[0]:
            break
    page.screenshot(path=str(OUT / "flow_citation_screen.png"))
    res.append(("screen_result_shown(outcome)", screened, ""))
    res.append(("screen_no_error", *g_no_error_text(page)))
    if not screened:
        return res
    # 풀셋 생성
    try:
        page.get_by_role("button", name=re.compile("본문에 인용 삽입")).first.click(timeout=6000)
    except Exception as e:
        res.append(("build_clicked", False, str(e)[:100]))
        return res
    built = False
    for _ in range(20):
        page.wait_for_timeout(3000)
        if page.get_by_role("button", name=re.compile(r"Word \(\.docx\)")).count() > 0:
            built = True
            break
        if not g_no_error_text(page)[0]:
            break
    page.screenshot(path=str(OUT / "flow_citation_fullset.png"))
    res.append(("fullset_word_btn(outcome)", built, ""))
    res.append(("fullset_endnote_btn", page.get_by_role("button", name=re.compile("EndNote")).count() > 0, ""))
    res.append(("fullset_no_error", *g_no_error_text(page)))
    return res


def task_topic_lock(page: Page) -> list:
    """J5 (E2E_PILOT_TEST_PLAN 확장) — 주제 잠금: A 입력 → 무관 B 입력 → A 유지.

    외부 LLM 통찰(2026-06-18): 흡연-심혈관 잡았는데 다른 주제 입력하면 ZCB로 회귀.
    RESEARCH_STATE_SPEC §1.5 (Decision Lock + 매 턴 강제 로드) 검증.
    """
    res = []
    nav(page, "논문 작업실")
    chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
    # 1차: 주제 명확히 잡음
    chat.fill("흡연이 심혈관 사건 위험에 미치는 효과 — Cox 모형으로 분석할 거야")
    chat.press("Enter")
    page.wait_for_timeout(15000)
    # 2차: 무관한 잡음
    chat.fill("그러면 다른 주제도 볼까?")
    chat.press("Enter")
    page.wait_for_timeout(15000)
    # 응답에 'ZCB' '제로음료' '우울' '카페인' 같은 회귀 단어 나오면 FAIL
    body = page.locator("body").inner_text()
    regression_words = ["제로음료", "ZCB", "zero-calorie", "depression", "우울", "카페인", "caffeine"]
    found_regression = [w for w in regression_words if w.lower() in body.lower()]
    kept_topic = any(w in body.lower() for w in ["흡연", "smoking", "cox", "심혈관", "cardiovascular"])
    page.screenshot(path=str(OUT / "j5_topic_lock.png"))
    res.append(("topic_kept_after_distraction", kept_topic,
                  "흡연/cox/심혈관 유지" if kept_topic else "주제 잃음"))
    res.append(("no_regression_to_seed_demo", not found_regression,
                  f"회귀 단어: {found_regression}" if found_regression else "회귀 없음"))
    return res


def task_dataset_known(page: Page) -> list:
    """J6 — '데이터셋 어디 있어?'에 묻지 않고 답하는지 검증.

    DATASETS 블록 매 턴 inject 확인. LLM이 "위치 알려주세요" 반응하면 FAIL.
    """
    res = []
    nav(page, "논문 작업실")
    chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
    chat.fill("KYRBS 2025 데이터로 카페인-우울 분석 시작해줘. 데이터 어디 있어?")
    chat.press("Enter")
    page.wait_for_timeout(20000)
    body = page.locator("body").inner_text()
    page.screenshot(path=str(OUT / "j6_dataset_known.png"))
    # PASS: data/raw/kyrbs2025.sav 또는 'data/raw' 언급 + "어디" 같은 되묻기 없음
    knows_path = any(s in body for s in ["data/raw/kyrbs2025", "data/raw", "KYRBSLoader",
                                              "21년", "2005~2025", "이미 보유", "이미 등록"])
    asks_back = any(s in body for s in ["경로 알려주", "어디 있나요", "업로드 해 주",
                                            "위치를 알려"])
    res.append(("knows_dataset_path", knows_path,
                  "DATASETS 블록 inject됨" if knows_path else "위치 인지 못함"))
    res.append(("no_asking_back", not asks_back,
                  "되묻지 않음" if not asks_back else "위치 되물음"))
    return res


def task_knhanes_upf_masld(page: Page) -> list:
    """J7 — ★ 가장 식별적 테스트 (외부 LLM 통찰 2026-06-19):
    'KNHANES UPF × MASLD 분석' 입력 → masld_classification/fib4_index/upf_share 호출 인지 +
    'MASLD 정의는?' / '데이터 어디' 재질문 없음.

    RESEARCH_STATE_SPEC §1.5 (Decision Lock + 묻지말고결정 + 매턴 state 로드)와
    KNHANES 도메인 함수 inject가 실제로 LLM 응답에 반영되는지의 진짜 첫 테스트.
    """
    res = []
    nav(page, "논문 작업실")
    chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
    # ★ 핵심 시나리오 — 분석 시작 트리거
    chat.fill("KNHANES 2023 데이터로 UPF(NOVA 4) 섭취와 MASLD(2023 신정의) 연관 분석 시작해줘. "
                "ultrasonography는 없어. fibrotic MASLD 양식으로 끝까지.")
    chat.press("Enter")
    page.wait_for_timeout(30000)  # LLM 응답 충분 대기
    body = page.locator("body").inner_text()
    page.screenshot(path=str(OUT / "j7_knhanes_upf_masld.png"))

    # PASS 1: KNHANES 도메인 함수 호출/언급 (LLM이 인지)
    knows_functions = sum(1 for s in [
        "masld_classification", "fib4_index", "fib4_stratify",
        "upf_share_by_person", "upf_intake_share", "classify_nova",
        "fli(", "hsi(", "FLI", "HSI", "FIB-4", "Rinella"
    ] if s in body)
    # PASS 2: MASLD 정의 재질문 양식 없음
    asks_definition = any(s in body for s in [
        "MASLD 정의는", "MASLD 정의가 뭐", "MASLD가 무엇",
        "MASLD 양식 알려", "어떤 양식으로", "정의를 알려주",
    ])
    # PASS 3: 데이터 위치 재질문 없음
    asks_location = any(s in body for s in [
        "KNHANES 어디", "데이터 어디", "데이터셋 경로", "파일 위치",
        "원본 파일 어디", "업로드 해 주", "위치를 알려",
    ])
    # PASS 4: 자동 분석 진행 양식 (table/aOR/CI/n=)
    progresses = any(s in body for s in [
        "aOR", "95% CI", "p-interaction", "logistic", "Cox",
        "Methods", "Results", "Table 1", "n =", "n=", "person-years",
    ])

    res.append(("knows_knhanes_functions", knows_functions >= 2,
                  f"인지 함수: {knows_functions}/12 (>= 2 PASS)"))
    res.append(("no_asking_masld_definition", not asks_definition,
                  "MASLD 정의 재질문 X" if not asks_definition else "★ FAIL: MASLD 정의 또 물음"))
    res.append(("no_asking_data_location", not asks_location,
                  "데이터 위치 재질문 X" if not asks_location else "★ FAIL: 위치 또 물음"))
    res.append(("progresses_to_analysis", progresses,
                  "분석 진행 양식 검출" if progresses else "★ FAIL: 통계 산출 양식 없음"))
    return res


def main() -> int:
    suite = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(f"{BASE}/?email={ADMIN}&auto=1", wait_until="domcontentloaded", timeout=30000)
        wait_idle(page, 5000)
        login_ok = page.get_by_role("button", name=re.compile("접속하기")).count() == 0
        suite.append(("login:admin", [("logged_in", login_ok, ADMIN)]))

        # 기본(바이브) 페이지 렌더 회귀
        for label, marker in [("홈", "Medical-Agent"), ("논문 작업실", "논문 작업실"),
                              ("글쓰기 스타일", "글쓰기 스타일"), ("작업 타임라인", "타임라인")]:
            name, fn = task_render(label, marker)
            suite.append((name, fn(page)))

        # 핵심 워크플로 (outcome 검증)
        suite.append(("flow:chat_write", task_chat_write(page)))
        suite.append(("flow:save_restore", task_save_restore(page, browser)))
        suite.append(("flow:citation_fullset", task_citation_fullset(page)))
        # J4 (E2E_PILOT_TEST_PLAN) — KYRBS survey-weighted logistic litmus test
        suite.append(("j4:kyrbs_survey_logistic", task_kyrbs_survey_logistic(page)))
        # ★ J5 — 주제 잠금 (Decision Lock + locked_decisions 매 턴 강제 로드)
        suite.append(("j5:topic_lock", task_topic_lock(page)))
        # ★ J6 — 데이터셋 인지 (DATASETS 블록 매 턴 inject)
        suite.append(("j6:dataset_known", task_dataset_known(page)))
        # ★ J7 — KNHANES UPF × MASLD 풀체인 (가장 식별적 — RESEARCH_STATE §1.5 + KNHANES 도메인 inject 실작동)
        suite.append(("j7:knhanes_upf_masld", task_knhanes_upf_masld(page)))

        # 관리자 단위 페이지 렌더 회귀 (관리자 모드 ON)
        for sel in ['[data-testid="stCheckbox"]', 'label:has-text("관리자 모드")']:
            try:
                page.locator(sel).first.click(timeout=3000); wait_idle(page); break
            except Exception:
                continue
        for label, marker in [("연구 주제 생성", "주제"), ("신규성 확인", "신규성"),
                              ("데이터 분석", "분석"), ("논문 작성", "논문"),
                              ("자가 진단", "진단"), ("지식베이스 관리", "지식"),
                              ("지식 위키", "위키")]:
            name, fn = task_render(label, marker)
            suite.append((name, fn(page)))

        browser.close()

    # 집계
    total = passed = 0
    lines = ["# UI Eval 리포트", ""]
    for tname, assertions in suite:
        t_ok = all(a[1] for a in assertions)
        lines.append(f"## {'✅' if t_ok else '❌'} {tname}")
        for aname, ok, detail in assertions:
            total += 1
            passed += 1 if ok else 0
            lines.append(f"- {'PASS' if ok else 'FAIL'} `{aname}` — {detail}")
        lines.append("")
    header = f"**{passed}/{total} assertions PASS** · {time.strftime('%Y-%m-%d %H:%M')}"
    (OUT / "report.md").write_text(header + "\n\n" + "\n".join(lines), encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(
        [{"task": t, "assertions": [{"name": a, "ok": o, "detail": d} for a, o, d in al]} for t, al in suite],
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(header)
    for tname, assertions in suite:
        t_ok = all(a[1] for a in assertions)
        print(f"  {'✅' if t_ok else '❌'} {tname}")
        for aname, ok, detail in assertions:
            if not ok:
                print(f"      FAIL {aname} — {detail}")
    print(f"\n=== {passed}/{total} assertions PASS — scripts/ui_eval_outputs/report.md ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
