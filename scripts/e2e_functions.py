"""함수 레벨 E2E 검수 — 각 핵심 function을 '실제 실행'해서 pass/fail 표로.

렌더/스모크가 아니라 기능 본체를 실데이터로 돌려 결과를 검증한다.
LLM-무관 기능은 쿼터와 무관하게 항상 검증 가능. LLM-의존은 시도 후 quota면 명시.

실행: python scripts/e2e_functions.py
"""
from __future__ import annotations
import io, sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS = []


def check(name: str, fn):
    try:
        ok, detail = fn()
        RESULTS.append((name, bool(ok), str(detail)[:140]))
    except Exception as e:
        RESULTS.append((name, False, f"EXC {type(e).__name__}: {str(e)[:110]}"))


def main():
    import warnings
    warnings.filterwarnings("ignore")
    from src.config.env import bootstrap
    bootstrap()

    # ── 1. 데이터 자동로드 ────────────────────────────────────────────
    _df_holder = {}

    def _t_data():
        from src.research.research_pipeline import _find_real_data
        df = _find_real_data("kyrbs")
        _df_holder["df"] = df
        cols = set(df.columns) if df is not None else set()
        need = {"depression", "sex", "smoking", "grade"}
        return (df is not None and len(df) > 1000 and need <= cols,
                f"{0 if df is None else len(df)}행 {len(cols)}열, 핵심컬럼 {need <= cols}")
    check("데이터 자동로드(_find_real_data)", _t_data)

    # ── 2. StatBridge 실분석 ──────────────────────────────────────────
    _res_holder = {}

    def _t_stat():
        from src.data.stat_bridge import StatBridge
        df = _df_holder.get("df")
        if df is None:
            return False, "데이터 없음(1번 실패)"
        spec = {"outcome": "depression", "outcome_label": "우울감",
                "predictors": ["sex", "smoking"], "covariates": ["grade", "family_econ"],
                "analysis": "logistic", "weight_var": "weight_var", "subgroups": ["sex"]}
        r = StatBridge().run(df, spec).to_dict()
        _res_holder["r"] = r
        return (not r.get("error") and r.get("n_total", 0) > 0 and len(r.get("model_vars", [])) > 0,
                f"n={r.get('n_total')}, 변수={len(r.get('model_vars',[]))}, err={r.get('error')}")
    check("StatBridge 로지스틱 실행", _t_stat)

    # ── 3. 그림 생성 + 한글폰트 ───────────────────────────────────────
    def _t_fig():
        from src.export.publication_figure_generator import generate_figures_for_paper
        r = _res_holder.get("r")
        if not r:
            return False, "stat result 없음"
        figs = generate_figures_for_paper(r, safe_title="e2e_fn")
        valid = [k for k, v in figs.items() if isinstance(v, dict) and len(v.get("png_bytes", b"") or b"") > 2000]
        # 한글 폰트 적용 여부
        import matplotlib.pyplot as plt
        fam = plt.rcParams.get("font.family")
        kor = any(x in str(fam).lower() for x in ("nanum", "malgun", "gothic", "noto"))
        return (len(valid) >= 3 and kor, f"유효PNG {len(valid)}개 {list(figs.keys())[:4]}, 한글폰트={fam}({kor})")
    check("그림 생성 + 한글폰트(두부방지)", _t_fig)

    # ── 4. 표 (markdown + docx) ───────────────────────────────────────
    def _t_table():
        from src.export.table_builder import (stat_result_to_table1_markdown,
                                              stat_result_to_table2_markdown, stat_result_to_tables_docx_bytes)
        r = _res_holder.get("r")
        if not r:
            return False, "stat result 없음"
        t1 = stat_result_to_table1_markdown(r); t2 = stat_result_to_table2_markdown(r)
        dx = stat_result_to_tables_docx_bytes(r)
        return (len(t1) > 50 and len(t2) > 50 and len(dx) > 1000, f"t1={len(t1)} t2={len(t2)} docx={len(dx)}bytes")
    check("표 생성(Table1/2 md + DOCX)", _t_table)

    # ── 5. 논문 저장/불러오기 ─────────────────────────────────────────
    def _t_store():
        from src.storage import working_paper_store as w
        pid = w.save_paper("e2e@test.com", {"title": "E2E", "introduction": "본문초안 내용입니다."},
                           meta={"_status": {"introduction": "locked"}})
        rec = w.load_paper("e2e@test.com", pid)
        ok = rec and rec["sections"].get("introduction") == "본문초안 내용입니다."
        w.delete_paper("e2e@test.com", pid)
        return ok, f"roundtrip={ok}"
    check("논문 영속 저장/불러오기", _t_store)

    # ── 6. 대화 의미메모리 ────────────────────────────────────────────
    def _t_mem():
        from src.memory import conversation_memory as cm
        cm.record("스마트폰 과사용과 청소년 수면", "블루라이트가 멜라토닌 억제로 수면위상지연 유발.",
                  owner_email="e2e@test.com", context_type="qa")
        out = cm.recall_relevant("디지털기기와 불면증", owner_email="e2e@test.com")
        return len(out) > 20, f"의미회수 길이={len(out)}"
    check("대화 의미메모리 record/recall", _t_mem)

    # ── 7. State Registry 잠금 ────────────────────────────────────────
    def _t_state():
        from src.research.research_state import ResearchState
        s = ResearchState(); s.set_section("methods", "원본"); s.lock("methods")
        blocked = not s.set_section("methods", "덮어쓰기")  # 잠겨서 거부돼야 True
        return blocked and s.get_section("methods") == "원본", f"잠금차단={blocked}"
    check("State Registry 섹션 잠금(drift차단)", _t_state)

    # ── 8. 메모리 게이트 ──────────────────────────────────────────────
    def _t_gate():
        from src.memory.memory_gate import assess
        q = assess("짧")["tier"] == "quarantine"
        h = assess("As an AI language model I cannot help with that request here.")["tier"] == "quarantine"
        v = assess("청소년 ZCB와 우울 용량반응(KYRBS).", source="observation")["tier"] == "verified"
        return q and h and v, f"짧음차단={q} 환각차단={h} 정상통과={v}"
    check("메모리 위생 게이트", _t_gate)

    # ── 9. 계층 청킹 ──────────────────────────────────────────────────
    def _t_chunk():
        from src.ingestion.hierarchical_chunker import chunk_paper
        ab = "Background: x. Methods: logistic regression with survey weights. Results: aOR 1.05. Conclusion: y."
        cs = chunk_paper(ab, base_meta={"pmid": "1"})
        secs = {c["metadata"]["section"] for c in cs}
        stat = any(c["metadata"]["statistical_method"] for c in cs)
        return (len(cs) >= 3 and "methods" in secs and stat, f"{len(cs)}청크 섹션={secs} stat탐지={stat}")
    check("계층 RAG 청킹(섹션/통계메타)", _t_chunk)

    # ── 10. LLM-의존 (쿼터면 명시) ────────────────────────────────────
    def _t_llm():
        from src.llm import get_llm_client
        out = get_llm_client(task="fast").generate("Reply one word: OK", task="fast", max_tokens=30)
        return bool(out and out.strip()), f"응답={out.strip()[:40]!r}"
    check("LLM 생성(폴백) — 쿼터의존", _t_llm)

    # ── 리포트 ────────────────────────────────────────────────────────
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 64)
    print(f"  함수 레벨 E2E: {n_ok}/{len(RESULTS)} PASS")
    print("=" * 64)
    for name, ok, detail in RESULTS:
        print(f"  {'✅' if ok else '❌'} {name}")
        print(f"       {detail}")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
