"""전 기능 End-to-End 테스트 — 실제 AI 호출 포함.

테스트 범위:
  T01  연구 주제 생성
  T02  신규성 확인
  T03  타당성 검증
  T04  논문 전체 작성 (write_paper)
  T05  섹션별 작성 ×5  (write_section 어댑터)
  T06  통계 주입 논문 (write_paper_with_stats — 더미 stat)
  T07  동료 심사 (peer_review)
  T08  Agent Q&A
  T09  RAG 수집 — BRCT docx
  T10  RAG 검색
  T11  StorageManager 상태
  T12  자가 진단
  T13  run_full() E2E — KYRBS 2025 실제 원시자료 + 통계 + 논문 + 심사
"""
import sys, io, traceback, time, os
from pathlib import Path

# 프로젝트 루트를 sys.path 최상단에 추가 (어떤 CWD에서 실행해도 동작)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from src.config.env import bootstrap; bootstrap()

# ─── 공통 픽스처 ─────────────────────────────────────────────────────────────
TOPIC = {
    "title": "청소년 스마트폰 과사용과 수면 부족",
    "exposure": "smartphone overuse",
    "outcome": "sleep deprivation",
    "population": "Korean adolescents",
    "suggested_design": "Cross-sectional",
    "suggested_methods": ["logistic_regression", "complex_sampling"],
}
STUDY = {
    "dataset": "KYRBS 2025",
    "design": "Cross-sectional",
    "sample_size": "54633",
    "survey_year": "2025",
    "journal": "IJERPH",
    "exposure": "smartphone overuse",
    "outcome": "sleep deprivation",
    "population": "Korean adolescents",
}
RES = "스마트폰 4시간 이상 사용군 수면 부족 OR=2.34 (95%CI 2.10-2.61, p<0.001)"
STAT = {
    "n_total": 54633,
    "model_vars": [
        {"variable": "smartphone_4h", "or_value": 2.34, "ci_lower": 2.10,
         "ci_upper": 2.61, "p_value": 0.001, "significant": True}
    ],
    "outcome": "sleep_deprivation",
    "method": "logistic",
}
DRAFT = """# 청소년 스마트폰 과사용과 수면 부족 연구

## Abstract
Background: Smartphone overuse is prevalent among Korean adolescents.
Objective: To examine the association between smartphone overuse and sleep deprivation.
Methods: Cross-sectional study using KYRBS 2025 (n=54,633). Logistic regression with complex sampling.
Results: Smartphone use ≥4h/day was associated with sleep deprivation (OR=2.34, 95%CI 2.10-2.61).
Conclusion: Screen time restriction policies may improve adolescent sleep.

## Introduction
Smartphone overuse has increased rapidly among Korean adolescents. Sleep deprivation affects
academic performance and health. This study examines their association in a nationally representative sample.

## Methods
Study design: Cross-sectional. Data: KYRBS 2025 (n=54,633). Exposure: daily smartphone use hours.
Outcome: sleep duration <8h. Analysis: complex-weighted logistic regression adjusted for sex, age, SES.

## Results
54,633 participants. 42.1% reported smartphone use ≥4h/day. Adjusted OR=2.34 (95%CI 2.10-2.61, p<0.001).
Consistent across sex and grade subgroups.

## Discussion
Our findings are consistent with prior Korean studies. Cross-sectional design limits causal inference.
Strengths: large nationally representative sample with standardized protocol.
Conclusion: These findings support smartphone-use guidelines in schools.
"""

BRCT_DOCX = "data/papers/BRCT/BRCT_LIBRA_AI_text_v2_clean.docx"

# ─── 테스트 하네스 ────────────────────────────────────────────────────────────
PASS_L, FAIL_L = [], []

def run(name, fn, skip_reason=None):
    if skip_reason:
        print(f"  [SKIP] {name} — {skip_reason}")
        return
    t0 = time.time()
    try:
        r = fn()
        PASS_L.append(name)
        snippet = (f" -> {str(r)[:120]}" if r else "")
        print(f"  [PASS] {name} ({round(time.time()-t0,1)}s){snippet}")
    except Exception as e:
        FAIL_L.append((name, str(e), traceback.format_exc()))
        print(f"  [FAIL] {name} ({round(time.time()-t0,1)}s)\n         {e}")
        for line in [x for x in traceback.format_exc().strip().splitlines() if x.strip()][-4:]:
            print(f"         {line.strip()}")

# ─── 테스트 정의 ─────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("  Medical-Agent 전 기능 E2E 테스트")
print("="*60)

# T01 ── 연구 주제 생성
print("\n[T01] 연구 주제 생성")
def t01():
    from src.research.research_pipeline import ResearchPipeline
    topics = ResearchPipeline().generate_topics(dataset_name="KYRBS", focus="청소년 비만과 수면", n_topics=2)
    assert topics and "title" in topics[0], "topics 구조 오류"
    return f"{len(topics)}개: {topics[0]['title'][:60]}"
run("generate_topics", t01)

# T02 ── 신규성 확인
print("\n[T02] 신규성 확인")
def t02():
    from src.research.novelty_checker import NoveltyChecker
    r = NoveltyChecker().check(
        topic=TOPIC["title"], exposure=TOPIC["exposure"],
        outcome=TOPIC["outcome"], population=TOPIC["population"]
    )
    assert "novelty_score" in r, "novelty_score 키 없음"
    return f"점수 {r['novelty_score']}/10  권고:{r.get('recommendation','?')}"
run("check_novelty", t02)

# T03 ── 타당성 검증
print("\n[T03] 타당성 검증")
def t03():
    from src.research.research_pipeline import ResearchPipeline
    r = ResearchPipeline().validate_feasibility(TOPIC, "KYRBS")
    assert "is_feasible" in r, "is_feasible 키 없음"
    return f"feasible={r['is_feasible']}  변수={len(r.get('variable_list',[]))}개"
run("validate_feasibility", t03)

# T04 ── 논문 전체 작성
print("\n[T04] 논문 전체 작성 (write_paper)")
def t04():
    from src.research.research_pipeline import ResearchPipeline
    draft = ResearchPipeline().write_paper(TOPIC, STUDY, {"summary": RES})
    assert draft and len(draft) > 200, f"초안이 너무 짧음: {len(draft)}자"
    return f"{len(draft)}자"
run("write_paper", t04)

# T05 ── 섹션별 작성 (write_section 어댑터)
print("\n[T05] 섹션별 작성 (write_section 어댑터)")
def _make_section_fn(section_name):
    def fn():
        from src.research.paper_writer import PaperWriter
        from src.profile.author_profile import AuthorProfile
        from src.library.methods_library import MethodsLibrary
        from src.library.dataset_library import DatasetLibrary
        from src.rag.pipeline import RAGPipeline
        writer = PaperWriter(
            AuthorProfile("Yoosun Cho"),
            MethodsLibrary(),
            DatasetLibrary(),
            RAGPipeline(),
        )
        text = writer.write_section(section_name, TOPIC["title"], STUDY, {"summary": RES})
        assert text and len(text) > 50, f"'{section_name}' 결과 너무 짧음: {len(text)}자"
        return f"{len(text)}자"
    fn.__name__ = section_name
    return fn

for sec in ["Abstract", "Introduction", "Methods", "Results", "Discussion"]:
    run(f"write_section:{sec}", _make_section_fn(sec))

# T06 ── 통계 주입 논문
print("\n[T06] 통계 주입 논문 (write_paper_with_stats)")
def t06():
    from src.research.research_pipeline import ResearchPipeline
    draft, docx_path = ResearchPipeline().write_paper_with_stats(
        TOPIC, STUDY, STAT, export_docx=False
    )
    assert draft and len(draft) > 200, f"초안 너무 짧음: {len(draft)}자"
    return f"{len(draft)}자  docx={'저장됨' if docx_path else '스킵'}"
run("write_paper_with_stats", t06)

# T07 ── 동료 심사
print("\n[T07] 동료 심사 (peer_review)")
def t07():
    from src.research.research_pipeline import ResearchPipeline
    r = ResearchPipeline().run_peer_review(DRAFT, TOPIC, stat_result=STAT)
    assert "total_score" in r, "total_score 키 없음"
    score = r["total_score"]
    assert score > 0, f"점수가 0 — JSON 파싱 실패 가능성"
    return f"점수 {score}/100  등급:{r.get('grade','?')}  권고:{r.get('accept_recommendation','?')}"
run("run_peer_review", t07)

# T08 ── Agent Q&A
print("\n[T08] Agent Q&A")
def t08():
    from src.agent.medical_agent import MedicalAgent
    r = MedicalAgent().ask("KYRBS 청소년 비만 연구 시 주의해야 할 편향과 통계 방법을 알려줘")
    answer = r.get("answer") or r.get("raw") or str(r)
    assert answer and len(answer) > 50, f"응답 너무 짧음: {len(answer)}자"
    return f"{len(answer)}자"
run("MedicalAgent.ask", t08)

# T09 ── RAG 수집
print("\n[T09] RAG 수집 (ingest_file)")
def t09():
    from src.rag.pipeline import RAGPipeline
    assert os.path.exists(BRCT_DOCX), f"테스트 파일 없음: {BRCT_DOCX}"
    r = RAGPipeline().ingest_file(BRCT_DOCX)
    assert "chunks_added" in r, "chunks_added 키 없음"
    return f"청크 {r['chunks_added']}개 추가 (전체 {r['chunks_total']}개)"
run("RAGPipeline.ingest_file", t09)

# T10 ── RAG 검색
print("\n[T10] RAG 검색")
def t10():
    from src.rag.pipeline import RAGPipeline
    hits = RAGPipeline().search("adolescent obesity sleep Korea")
    assert hits is not None, "None 반환"
    return f"{len(hits)}개 청크 반환"
run("RAGPipeline.search", t10)

# T11 ── StorageManager
print("\n[T11] StorageManager 상태")
def t11():
    from src.storage.manager import StorageManager
    s = StorageManager().status()
    assert "notebooklm" in s and "vector_chunks" in s, "필수 키 없음"
    return str(s)[:100]
run("StorageManager.status", t11)

# T12 ── 자가 진단
print("\n[T12] 자가 진단")
def t12():
    from src.diagnostics.self_auditor import SelfAuditor
    r = SelfAuditor().run_quick_audit()
    assert r.overall_score >= 0, "점수 음수"
    issue_count = len(r.code_issues) if hasattr(r, "code_issues") else 0
    return f"점수 {r.overall_score}  code_issues {issue_count}개"
run("SelfAuditor.run_quick_audit", t12)

# T13 ── run_full() 전체 파이프라인 (실제 KYRBS 2025 원시자료)
print("\n[T13] run_full() E2E — KYRBS 2025 실제 원시자료")
def t13():
    from src.research.research_pipeline import ResearchPipeline
    result = ResearchPipeline().run_full(
        dataset_name="KYRBS",
        focus="청소년 수면과 스마트폰 사용",
        export_docx=False,
    )
    assert "draft" in result and result["draft"], "초안 없음"
    assert "review" in result and "total_score" in result["review"], "리뷰 없음"
    draft_len = len(result["draft"])
    score = result["review"]["total_score"]
    topic_title = result["topic"].get("title", "?")[:50]
    return f"주제: {topic_title} | 초안 {draft_len}자 | 심사 {score}/100"
run("run_full (E2E)", t13)

# ─── 최종 결과 ────────────────────────────────────────────────────────────────
total = len(PASS_L) + len(FAIL_L)
print("\n" + "="*60)
print(f"  결과: {len(PASS_L)} PASS / {len(FAIL_L)} FAIL  (총 {total}개)")
print("="*60)

if FAIL_L:
    print("\n[실패 목록]")
    for name, err, tb in FAIL_L:
        print(f"\n  FAIL: {name}")
        print(f"  -> {err[:300]}")
        for line in [x for x in tb.splitlines() if x.strip()][-5:]:
            print(f"     {line.strip()}")

sys.exit(0 if not FAIL_L else 1)
