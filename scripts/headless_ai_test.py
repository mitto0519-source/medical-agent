"""전 기능 헤드리스 AI 호출 테스트."""
import sys, io, traceback, time, os, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
_root = pathlib.Path(__file__).resolve().parent.parent
os.chdir(_root)
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from src.config.env import bootstrap; bootstrap()

PASS_L, FAIL_L = [], []

def run(name, fn):
    t0 = time.time()
    try:
        r = fn()
        PASS_L.append(name)
        suffix = f" -> {str(r)[:100]}" if r else ""
        print(f"  [PASS] {name} ({round(time.time()-t0,1)}s){suffix}")
    except Exception as e:
        FAIL_L.append((name, str(e), traceback.format_exc()))
        print(f"  [FAIL] {name} ({round(time.time()-t0,1)}s) -> {e}")
        for l in traceback.format_exc().strip().splitlines()[-4:]:
            if l.strip():
                print(f"         {l.strip()}")

TOPIC = {
    "title": "청소년 스마트폰 과사용과 수면 부족",
    "exposure": "smartphone overuse",
    "outcome": "sleep deprivation",
    "population": "Korean adolescents",
    "suggested_design": "Cross-sectional",
}
STUDY = {
    "dataset": "KYRBS 2025",
    "design": "Cross-sectional",
    "sample_size": "54633",
    "survey_year": "2025",
    "journal": "IJERPH",
}
RES = "스마트폰 4시간 이상 사용군 수면 부족 OR=2.34 (95%CI 2.10-2.61, p<0.001)"
DRAFT = (
    "# 청소년 스마트폰 과사용\n"
    "## Abstract\nStudy n=54633 found OR=2.34.\n"
    "## Methods\nLogistic regression.\n"
    "## Results\nOR=2.34 p<0.001.\n"
    "## Discussion\nPublic health implications."
)

print("\n" + "="*60)
print("  Medical-Agent 전 기능 헤드리스 테스트")
print("="*60)

print("\n[1] 연구 주제 생성")
def t1():
    from src.research.research_pipeline import ResearchPipeline
    topics = ResearchPipeline().generate_topics(dataset_name="KYRBS", focus="청소년 비만과 수면", n_topics=2)
    assert topics and "title" in topics[0]
    return f"{len(topics)}개: {topics[0]['title'][:50]}"
run("generate_topics", t1)

print("\n[2] 신규성 확인")
def t2():
    from src.research.novelty_checker import NoveltyChecker
    r = NoveltyChecker().check(
        topic=TOPIC["title"], exposure=TOPIC["exposure"],
        outcome=TOPIC["outcome"], population=TOPIC["population"]
    )
    assert "novelty_score" in r
    return f"점수 {r['novelty_score']}/10"
run("check_novelty", t2)

print("\n[3] 타당성 검증")
def t3():
    from src.research.research_pipeline import ResearchPipeline
    r = ResearchPipeline().validate_feasibility(TOPIC, "KYRBS")
    assert "is_feasible" in r
    return f"feasible={r['is_feasible']}"
run("validate_feasibility", t3)

print("\n[4] 논문 작성 - 전체")
def t4a():
    from src.research.research_pipeline import ResearchPipeline
    d = ResearchPipeline().write_paper(TOPIC, STUDY, {"summary": RES})
    assert d and len(d) > 200
    return f"{len(d)}자"
run("write_paper (전체)", t4a)

print("\n[4b] 논문 작성 - write_full_paper 섹션 완성 확인")
def t4b():
    from src.research.paper_writer import PaperWriter
    from src.profile.author_profile import AuthorProfile
    from src.library.methods_library import MethodsLibrary
    from src.library.dataset_library import DatasetLibrary
    from src.rag.pipeline import RAGPipeline
    w = PaperWriter(AuthorProfile("Yoosun Cho"), MethodsLibrary(), DatasetLibrary(), RAGPipeline())
    d = w.write_full_paper(topic=TOPIC["title"], study_info=STUDY, results={"summary": RES})
    import re
    has_intro = bool(re.search(r"Introduction|서론", d, re.I))
    has_methods = bool(re.search(r"Methods|방법", d, re.I))
    has_results = bool(re.search(r"Results|결과", d, re.I))
    assert has_intro and has_methods and has_results, "IMRAD 구조 불완전"
    return f"{len(d)}자 (IMRAD: Intro={has_intro}, Methods={has_methods}, Results={has_results})"
run("write_full_paper IMRAD 확인", t4b)

print("\n[5] 통계 주입 논문 작성")
def t5():
    from src.research.research_pipeline import ResearchPipeline
    stat = {
        "n_total": 54633, "n_outcome": 12000, "outcome_rate": 22.0,
        "outcome": "sleep_deprivation", "outcome_label": "수면 부족",
        "analysis_type": "logistic",
        "model_vars": [
            {"variable": "smartphone_4h", "label": "스마트폰 4시간 이상",
             "or_value": 2.34, "ci_lower": 2.10, "ci_upper": 2.61,
             "p_value": 0.001, "significant": True,
             "or_formatted": "2.34 (95% CI 2.10-2.61)", "p_formatted": "p<0.001"}
        ],
        "model_metrics": {}, "descriptive_stats": {}, "paper_summary": "OR=2.34",
    }
    d, p = ResearchPipeline().write_paper_with_stats(TOPIC, STUDY, stat, export_docx=False)
    assert d and len(d) > 200
    return f"{len(d)}자"
run("write_paper_with_stats", t5)

print("\n[6] 동료 심사")
def t6():
    from src.research.research_pipeline import ResearchPipeline
    r = ResearchPipeline().run_peer_review(DRAFT, TOPIC)
    assert "total_score" in r
    return f"점수 {r['total_score']}/100"
run("run_peer_review", t6)

print("\n[7] Agent Q&A")
def t7():
    from src.agent.medical_agent import MedicalAgent
    r = MedicalAgent().ask("KYRBS 청소년 비만 연구 주의사항")
    a = r.get("answer", r.get("raw", str(r)))
    assert a and len(a) > 30
    return f"{len(a)}자"
run("MedicalAgent.ask", t7)

print("\n[8] RAG 검색")
def t8():
    from src.rag.pipeline import RAGPipeline
    hits = RAGPipeline().search("adolescent obesity sleep Korea")
    assert hits is not None
    return f"{len(hits)}개"
run("RAGPipeline.search", t8)

print("\n[9] StorageManager")
def t9():
    from src.storage.manager import StorageManager
    s = StorageManager().status()
    assert "notebooklm" in s
    return str(s)[:80]
run("StorageManager.status", t9)

print("\n[10] 자가 진단")
def t10():
    from src.diagnostics.self_auditor import SelfAuditor
    r = SelfAuditor().run_quick_audit()
    return f"점수 {r.overall_score}"
run("SelfAuditor.run_quick_audit", t10)

print("\n[11] StatBridge 실데이터 분석 (data/raw/ 있을 때)")
def t11():
    import pandas as pd, numpy as np
    # 실제 raw 데이터가 없으면 최소 합성 DataFrame으로 StatBridge 검증
    from src.data.stat_bridge import StatBridge
    df = pd.DataFrame({
        "depression": [0,1,0,1,0,1,0,0,1,0] * 100,
        "sex": [1,2,1,2,1,2,1,1,2,1] * 100,
        "sleep_hours": np.random.uniform(4, 10, 1000),
        "screen_time": np.random.uniform(0, 8, 1000),
        "smoking": [0,0,1,0,0,1,0,0,0,1] * 100,
        "grade": [1,2,3,1,2,3,1,2,3,1] * 100,
        "family_econ": [1,2,3,2,1,3,2,1,3,2] * 100,
    })
    spec = {"outcome": "depression", "outcome_label": "우울감", "predictors": ["sex", "sleep_hours", "screen_time"], "covariates": ["grade"], "analysis": "logistic"}
    result = StatBridge().run(df, spec)
    assert result.n_total == 1000, f"n={result.n_total}"
    assert not result.error, f"error: {result.error}"
    return f"n={result.n_total}, OR변수={len(result.model_vars)}, 유의={len(result.get_significant())}"
run("StatBridge (합성데이터)", t11)

print("\n[12] ColNameResolver")
def t12():
    import pandas as pd
    from src.data.col_name_resolver import ColNameResolver
    df = pd.DataFrame({"E_SEX": [1,2], "F_BR": [0,1], "EC_SU_HOU": [7,8], "E_S_GRADE": [1,2]})
    r = ColNameResolver(df).resolve(["sex", "depression", "sleep_hours", "grade"])
    assert r.get("sex") == "E_SEX", f"sex mapping: {r}"
    return str(r)
run("ColNameResolver", t12)

print("\n" + "="*60)
print(f"  결과: {len(PASS_L)} PASS / {len(FAIL_L)} FAIL")
print("="*60)
if FAIL_L:
    print("\n[실패 목록]")
    for name, err, tb in FAIL_L:
        print(f"\n  FAIL: {name}\n  -> {err[:250]}")
        for l in [x for x in tb.splitlines() if x.strip()][-4:]:
            print(f"     {l.strip()}")
