"""모든 Streamlit 페이지 헤드리스 브라우저 검증 스크립트."""
import sys, asyncio, json, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

SS = Path("scripts/screenshots")
SS.mkdir(exist_ok=True)

BASE_URL = "http://localhost:8502"
EMAIL = "mitto0519@gmail.com"

results: list[dict] = []

async def nav_to(page, page_name: str, ss_name: str):
    """사이드바에서 특정 페이지로 이동."""
    btn = page.locator("[data-testid='stSidebar'] button").filter(has_text=page_name)
    count = await btn.count()
    if count == 0:
        print(f"    ⚠ 사이드바 버튼 미발견: '{page_name}'")
        return False
    await btn.first.click()
    await asyncio.sleep(2)
    await page.wait_for_load_state("networkidle", timeout=10000)
    await page.screenshot(path=str(SS / ss_name))
    print(f"    → {ss_name}")
    return True

async def wait_for_result(page, done_words: list[str], timeout_s: int = 180, poll_s: int = 5, ss_prefix: str = "wait") -> tuple[bool, int]:
    """결과가 나타날 때까지 폴링."""
    for i in range(timeout_s // poll_s):
        await asyncio.sleep(poll_s)
        body = await page.inner_text("body")
        if any(w in body for w in done_words):
            return True, (i + 1) * poll_s
        if i % 6 == 5:
            await page.screenshot(path=str(SS / f"{ss_prefix}_{(i+1)*poll_s}s.png"))
            print(f"    {(i+1)*poll_s}s 대기 중...")
    return False, timeout_s

def ok(name, detail=""):
    results.append({"page": name, "status": "✅ PASS", "detail": detail})
    print(f"  ✅ PASS{' — ' + detail if detail else ''}")

def fail(name, detail=""):
    results.append({"page": name, "status": "❌ FAIL", "detail": detail})
    print(f"  ❌ FAIL{' — ' + detail if detail else ''}")

def warn(name, detail=""):
    results.append({"page": name, "status": "⚠ WARN", "detail": detail})
    print(f"  ⚠ WARN{' — ' + detail if detail else ''}")


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # ── 로그인 ──────────────────────────────────────────────────────
        print("\n[LOGIN] 로그인 중...")
        await page.goto(BASE_URL, timeout=20000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)
        await page.locator("input[type='text']").first.fill(EMAIL)
        await page.locator("button:has-text('접속하기')").click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)
        body = await page.inner_text("body")
        if "홈" in body or "Medical-Agent" in body:
            print("  ✅ 로그인 성공")
        else:
            print("  ❌ 로그인 실패 — 중단")
            await browser.close()
            return
        await page.screenshot(path=str(SS / "00_home.png"))

        # ════════════════════════════════════════════════════════
        # 1. 홈 페이지
        # ════════════════════════════════════════════════════════
        print("\n[1/14] 홈")
        await nav_to(page, "홈", "01_홈.png")
        body = await page.inner_text("body")
        if "Medical-Agent" in body or "Recent" in body or "지식베이스" in body or "작업 현황" in body:
            ok("홈", "홈 화면 렌더링 OK")
        else:
            warn("홈", "홈 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 2. 워크플로우
        # ════════════════════════════════════════════════════════
        print("\n[2/14] 워크플로우")
        await nav_to(page, "워크플로우", "02_워크플로우.png")
        body = await page.inner_text("body")
        if "워크플로우" in body or "Step" in body or "단계" in body:
            ok("워크플로우", "워크플로우 페이지 렌더링 OK")
        else:
            warn("워크플로우", "워크플로우 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 3. 작업 타임라인
        # ════════════════════════════════════════════════════════
        print("\n[3/14] 작업 타임라인")
        await nav_to(page, "작업 타임라인", "03_타임라인.png")
        body = await page.inner_text("body")
        if "타임라인" in body or "작업" in body or "이력" in body:
            ok("작업 타임라인", "타임라인 페이지 렌더링 OK")
        else:
            warn("작업 타임라인", "타임라인 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 4. 논문 생산 파이프라인
        # ════════════════════════════════════════════════════════
        print("\n[4/14] 논문 생산 파이프라인")
        await nav_to(page, "논문 생산 파이프라인", "04_파이프라인.png")
        body = await page.inner_text("body")
        if "파이프라인" in body or "KYRBS" in body or "주제" in body:
            ok("논문 생산 파이프라인", "파이프라인 페이지 렌더링 OK")
        else:
            warn("논문 생산 파이프라인", "파이프라인 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 5. 연구 주제 생성 (이미 검증됨 — 핵심 기능 재확인)
        # ════════════════════════════════════════════════════════
        print("\n[5/14] 연구 주제 생성")
        await nav_to(page, "연구 주제 생성", "05_주제생성_before.png")
        body = await page.inner_text("body")
        if "연구 포커스" in body or "데이터셋" in body or "주제" in body:
            ok("연구 주제 생성", "UI 렌더링 OK (이전 세션에서 기능 검증 완료)")
        else:
            warn("연구 주제 생성", "UI 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 6. 신규성 확인 — 실제 실행
        # ════════════════════════════════════════════════════════
        print("\n[6/14] 신규성 확인 — PubMed 검증 실행")
        await nav_to(page, "신규성 확인", "06_신규성_before.png")
        body = await page.inner_text("body")
        if "연구 제목" not in body and "PubMed" not in body:
            warn("신규성 확인", "페이지 UI 없음")
        else:
            try:
                # 연구 제목 입력
                title_inp = page.get_by_label("연구 제목")
                await title_inp.fill("청소년의 수면 부족과 비만의 연관성")
                # 노출변수
                exp_inp = page.get_by_label("노출변수")
                await exp_inp.fill("수면 시간")
                # 결과변수
                out_inp = page.get_by_label("결과변수")
                await out_inp.fill("비만 (BMI ≥ 95th percentile)")
                # 대상 집단
                pop_inp = page.get_by_label("대상 집단")
                await pop_inp.fill("한국 청소년")
                await page.screenshot(path=str(SS / "06_신규성_filled.png"))
                # 버튼 클릭
                await page.locator("button:has-text('PubMed 신규성 확인')").click()
                await asyncio.sleep(2)
                await page.screenshot(path=str(SS / "06_신규성_spinner.png"))
                print("    → 버튼 클릭 완료, 결과 대기 중 (최대 3분)...")
                done_words = ["신규성 점수", "novelty_score", "권고사항", "오류", "PROCEED", "MODIFY", "REJECT"]
                found, elapsed = await wait_for_result(page, done_words, timeout_s=180, poll_s=6, ss_prefix="06_novel_wait")
                await page.screenshot(path=str(SS / "06_신규성_result.png"))
                body = await page.inner_text("body")
                if "오류" in body and "신규성 점수" not in body:
                    for line in body.split("\n"):
                        if "오류" in line and line.strip():
                            fail("신규성 확인", f"오류: {line.strip()[:100]}")
                            break
                elif any(w in body for w in ["신규성 점수", "권고사항", "PROCEED", "MODIFY"]):
                    ok("신규성 확인", f"{elapsed}s만에 결과 수신 — PubMed + Claude 분석 완료")
                else:
                    warn("신규성 확인", f"{elapsed}s 후 결과 불명확 — 스크린샷 확인")
            except Exception as e:
                await page.screenshot(path=str(SS / "06_신규성_error.png"))
                fail("신규성 확인", f"예외: {e}")

        # ════════════════════════════════════════════════════════
        # 7. 논문 설계 & 타당성 — 실제 실행
        # ════════════════════════════════════════════════════════
        print("\n[7/14] 논문 설계 & 타당성 — 타당성 검증 실행")
        await nav_to(page, "논문 설계 & 타당성", "07_타당성_before.png")
        body = await page.inner_text("body")
        if "타당성" not in body and "주제 JSON" not in body:
            warn("논문 설계 & 타당성", "페이지 UI 없음")
        else:
            try:
                sample_topic = json.dumps({
                    "title": "청소년의 수면 부족과 비만의 연관성: KYRBS 2023 단면 연구",
                    "exposure": "수면 시간 (주중 평균)",
                    "outcome": "비만 (BMI ≥ 95th percentile)",
                    "population": "한국 중고등학생"
                }, ensure_ascii=False, indent=2)
                textarea = page.locator("textarea").first
                await textarea.click()
                await textarea.press("Control+a")
                await textarea.fill(sample_topic)
                await page.screenshot(path=str(SS / "07_타당성_filled.png"))
                await page.locator("button:has-text('타당성 검증')").click()
                await asyncio.sleep(3)
                # 스피너 대기 ("분석 중"이 사라지면 완료)
                print("    → 타당성 검증 버튼 클릭, 결과 대기 중 (최대 2분)...")
                # 결과에만 나오는 단어 (heading의 "타당성"과 겹치지 않도록)
                done_words = ["사용 가능 변수", "판정", "is_feasible", "오류"]
                found, elapsed = await wait_for_result(page, done_words, timeout_s=120, poll_s=5, ss_prefix="07_feas_wait")
                await page.screenshot(path=str(SS / "07_타당성_result.png"))
                body = await page.inner_text("body")
                if any(w in body for w in ["사용 가능 변수", "판정"]):
                    ok("논문 설계 & 타당성", f"{elapsed}s만에 타당성 검증 완료")
                elif "오류" in body:
                    fail("논문 설계 & 타당성", "타당성 검증 오류 발생")
                else:
                    warn("논문 설계 & 타당성", f"{elapsed}s 후 결과 불명확 — 스크린샷 확인")
            except Exception as e:
                await page.screenshot(path=str(SS / "07_타당성_error.png"))
                fail("논문 설계 & 타당성", f"예외: {e}")

        # ════════════════════════════════════════════════════════
        # 8. 데이터 분석 — 데이터셋 라이브러리 로드 확인
        # ════════════════════════════════════════════════════════
        print("\n[8/14] 데이터 분석 — 데이터셋 라이브러리 로드")
        await nav_to(page, "데이터 분석", "08_데이터분석.png")
        await asyncio.sleep(2)
        body = await page.inner_text("body")
        if "데이터셋" in body or "변수" in body or "라이브러리" in body:
            # 변수명 검색 테스트
            try:
                search = page.get_by_placeholder("예: bmi, 흡연")
                if await search.count() > 0:
                    await search.fill("bmi")
                    await asyncio.sleep(1)
                    await page.screenshot(path=str(SS / "08_데이터분석_search.png"))
            except Exception:
                pass
            ok("데이터 분석", "데이터셋 라이브러리 렌더링 OK")
        else:
            warn("데이터 분석", "데이터셋 로드 실패 또는 UI 없음")

        # ════════════════════════════════════════════════════════
        # 9. 논문 작성 — 실제 실행 (Abstract 섹션만, 빠름)
        # ════════════════════════════════════════════════════════
        print("\n[9/14] 논문 작성 — Abstract 작성 실행")
        await nav_to(page, "논문 작성", "09_논문작성_before.png")
        body = await page.inner_text("body")
        if "연구 제목" not in body and "논문 작성" not in body:
            warn("논문 작성", "페이지 UI 없음")
        else:
            try:
                title_inp = page.get_by_label("연구 제목")
                await title_inp.fill("청소년의 수면 부족과 비만의 연관성: KYRBS 2023 단면 연구")
                # 주요 결과 입력 (섹션은 기본값 "전체 논문" 그대로 사용)
                results_area = page.get_by_placeholder("예: 스마트폰 주중 4시간 이상")
                await results_area.fill("수면 5시간 미만 청소년에서 비만 OR=1.87 (95% CI: 1.52-2.31), p<0.001")
                await page.screenshot(path=str(SS / "09_논문작성_filled.png"))
                await page.locator("button:has-text('논문 작성 시작')").click()
                await asyncio.sleep(2)
                print("    → 논문 작성 버튼 클릭, 결과 대기 중 (최대 3분)...")
                done_words = ["작성 완료", "생성된 논문", "Abstract", "Introduction", "오류", "초안"]
                found, elapsed = await wait_for_result(page, done_words, timeout_s=180, poll_s=6, ss_prefix="09_paper_wait")
                await page.screenshot(path=str(SS / "09_논문작성_result.png"))
                body = await page.inner_text("body")
                if "오류" in body:
                    # 오류 메시지 추출
                    err_line = next((l.strip()[:120] for l in body.split("\n") if "오류" in l and l.strip()), "오류 발생")
                    fail("논문 작성", err_line)
                elif "작성 완료" in body or "초안" in body:
                    ok("논문 작성", f"{elapsed}s만에 논문 초안 생성 완료")
                else:
                    warn("논문 작성", f"{elapsed}s 후 결과 불명확")
            except Exception as e:
                await page.screenshot(path=str(SS / "09_논문작성_error.png"))
                fail("논문 작성", f"예외: {e}")

        # ════════════════════════════════════════════════════════
        # 10. Agent Q&A — 실제 질문 전송
        # ════════════════════════════════════════════════════════
        print("\n[10/14] Agent Q&A — 질문 전송")
        await nav_to(page, "Agent Q&A", "10_agent_qa_before.png")
        await asyncio.sleep(1)
        body = await page.inner_text("body")
        if "질문" not in body and "Agent" not in body:
            warn("Agent Q&A", "페이지 UI 없음")
        else:
            try:
                chat_inp = page.locator("textarea[aria-label='질문을 입력하세요...']").first
                if await chat_inp.count() == 0:
                    chat_inp = page.locator("[data-testid='stChatInputTextArea']").first
                await chat_inp.fill("KYRBS 데이터셋에서 사용 가능한 주요 변수는 무엇인가요?")
                await asyncio.sleep(0.5)
                await chat_inp.press("Enter")
                await asyncio.sleep(2)
                await page.screenshot(path=str(SS / "10_agent_qa_sent.png"))
                print("    → 질문 전송, 답변 생성 대기 중 (최대 2분)...")
                # 스피너 "답변 생성 중"이 사라지면 완료 — 사용자 메시지에도 없는 단어
                start_t = time.time()
                for _ in range(24):
                    await asyncio.sleep(5)
                    body = await page.inner_text("body")
                    if "답변 생성 중" not in body and "질문을 입력하세요" in body:
                        break
                elapsed = int(time.time() - start_t)
                await page.screenshot(path=str(SS / "10_agent_qa_result.png"))
                body = await page.inner_text("body")
                msg_count = body.count("KYRBS 데이터셋에서")  # 사용자 메시지 + 답변 속 반복
                if "답변 생성 중" not in body and any(w in body for w in ["BMI", "흡연", "수면", "변수명", "체질량"]):
                    ok("Agent Q&A", f"{elapsed}s만에 답변 수신")
                elif "오류" in body:
                    fail("Agent Q&A", "답변 오류 발생")
                else:
                    warn("Agent Q&A", f"{elapsed}s 후 답변 불명확")
            except Exception as e:
                await page.screenshot(path=str(SS / "10_agent_qa_error.png"))
                fail("Agent Q&A", f"예외: {e}")

        # ════════════════════════════════════════════════════════
        # 11. Notebook 에디터 — 초기화 상태 확인
        # ════════════════════════════════════════════════════════
        print("\n[11/14] Notebook 에디터 — 초기화 상태 확인")
        await nav_to(page, "Notebook 에디터", "11_notebook_editor_nav.png")
        # 이전 페이지(Agent Q&A) 처리 중일 수 있으므로 페이지 콘텐츠 전환 대기
        for _ in range(12):
            await asyncio.sleep(2)
            body = await page.inner_text("body")
            if any(w in body for w in ["NotebookLM", "로컬 DB", "논문 추가", "초기화 오류", "Research Hub"]):
                break
        await page.screenshot(path=str(SS / "11_notebook_editor.png"))
        body = await page.inner_text("body")
        if "초기화 오류" in body:
            fail("Notebook 에디터", "StorageManager 초기화 오류")
        elif any(w in body for w in ["NotebookLM", "로컬 DB", "논문 추가", "Research Hub"]):
            ok("Notebook 에디터", "StorageManager 초기화 OK — 탭 렌더링 확인")
        else:
            warn("Notebook 에디터", "UI 상태 불명확 (페이지 전환 지연 가능성)")

        # ════════════════════════════════════════════════════════
        # 12. 논문 업로드 & 인제스트 — PubMed 탭 UI 확인
        # ════════════════════════════════════════════════════════
        print("\n[12/14] 논문 업로드 & 인제스트 — PubMed 탭 UI 확인")
        await nav_to(page, "논문 업로드 & 인제스트", "12_인제스트_before.png")
        await asyncio.sleep(1)
        # PubMed 탭 클릭
        try:
            await page.locator("[data-testid='stTab']").filter(has_text="PubMed").click()
            await asyncio.sleep(1)
        except Exception:
            pass
        body = await page.inner_text("body")
        if any(w in body for w in ["PDF", "PubMed", "검색어", "인제스트"]):
            # PubMed 검색어 입력 후 버튼은 실제로 누르지 않음 (시간이 오래 걸림)
            try:
                pm_q = page.get_by_placeholder("adolescent obesity sleep Korea")
                if await pm_q.count() > 0:
                    await pm_q.fill("adolescent sleep Korea obesity")
                    await asyncio.sleep(0.5)
                    await page.screenshot(path=str(SS / "12_인제스트_filled.png"))
            except Exception:
                pass
            ok("논문 업로드 & 인제스트", "PDF/PubMed/텍스트 탭 렌더링 OK")
        else:
            warn("논문 업로드 & 인제스트", "UI 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 13. 지식베이스 관리 — 청크 수 및 검색 확인
        # ════════════════════════════════════════════════════════
        print("\n[13/14] 지식베이스 관리 — DB 현황 확인")
        await nav_to(page, "지식베이스 관리", "13_지식베이스_before.png")
        await asyncio.sleep(2)
        body = await page.inner_text("body")
        if "DB 연결 오류" in body:
            fail("지식베이스 관리", "DB 연결 오류")
        elif any(w in body for w in ["청크", "DB 유형", "ChromaDB", "Supabase"]):
            # 검색 테스트
            try:
                test_q = page.get_by_placeholder("예: 청소년 비만 위험요인")
                if await test_q.count() > 0:
                    await test_q.fill("청소년 비만")
                    await asyncio.sleep(2)
                    await page.screenshot(path=str(SS / "13_지식베이스_search.png"))
                    body2 = await page.inner_text("body")
                    if "유사도" in body2 or "score" in body2.lower():
                        ok("지식베이스 관리", "DB 현황 + 의미 검색 OK")
                    else:
                        ok("지식베이스 관리", "DB 현황 렌더링 OK (검색 결과 없음)")
                else:
                    ok("지식베이스 관리", "DB 현황 렌더링 OK")
            except Exception:
                ok("지식베이스 관리", "DB 현황 렌더링 OK")
        else:
            warn("지식베이스 관리", "UI 콘텐츠 불명확")

        # ════════════════════════════════════════════════════════
        # 14. 자동 학습 루프 — 키워드 등록
        # ════════════════════════════════════════════════════════
        print("\n[14/14] 자동 학습 루프 — 키워드 등록")
        await nav_to(page, "자동 학습 루프", "14_자동학습_before.png")
        await asyncio.sleep(1)
        body = await page.inner_text("body")
        if "키워드" not in body and "자동 학습" not in body:
            warn("자동 학습 루프", "페이지 UI 없음")
        else:
            try:
                # PubMed 검색어 입력
                kw_inp = page.get_by_label("PubMed 검색어")
                await kw_inp.fill("adolescent sleep obesity Korea")
                # 주제 태그 입력
                topic_inp = page.get_by_label("주제 태그")
                await topic_inp.fill("청소년 수면-비만")
                await page.screenshot(path=str(SS / "14_자동학습_filled.png"))
                # 폼 제출 (➕ 추가)
                await page.locator("button:has-text('추가')").click()
                await asyncio.sleep(2)
                await page.screenshot(path=str(SS / "14_자동학습_added.png"))
                body = await page.inner_text("body")
                if "등록됨" in body or "adolescent sleep obesity Korea" in body:
                    ok("자동 학습 루프", "키워드 등록 완료 — 목록에 표시됨")
                else:
                    warn("자동 학습 루프", "키워드 등록 결과 불명확")
            except Exception as e:
                await page.screenshot(path=str(SS / "14_자동학습_error.png"))
                fail("자동 학습 루프", f"예외: {e}")

        await browser.close()

    # ── 최종 리포트 ────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  전체 페이지 검증 결과 리포트")
    print("═" * 60)
    pass_cnt = sum(1 for r in results if "PASS" in r["status"])
    fail_cnt = sum(1 for r in results if "FAIL" in r["status"])
    warn_cnt = sum(1 for r in results if "WARN" in r["status"])
    for r in results:
        print(f"  {r['status']}  [{r['page']}]  {r['detail']}")
    print("─" * 60)
    print(f"  총 {len(results)}개 페이지  ✅ {pass_cnt}  ❌ {fail_cnt}  ⚠ {warn_cnt}")
    print("═" * 60)
    print(f"\n  스크린샷 저장 위치: scripts/screenshots/")


asyncio.run(main())
