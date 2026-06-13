"""Quality Evaluation Harness — 자가발전의 metric layer.

외부 진단(2026-06-13) 핵심: smoke test는 "죽었나/살았나"만 본다.
출력 품질을 재는 지표가 없으면 self-improvement loop은 임의 임계치만 본다.

이 모듈이 측정하는 4축:
  1. retrieval@k          — gold 쿼리에 대해 expected PMID가 top-k에 있나
  2. style_match          — 사용자 StyleProfile 지표와 LLM 출력 통계가 얼마나 일치
  3. citation_realism     — 출력의 모든 [PMID:xxx]가 medical_graph/RAG에 실재
  4. stat_traceability    — 출력 숫자가 stat_result에서 추적 가능 (자체 검증 모듈 재사용)

실행:
    python eval/quality_harness.py                  # 전체 측정
    python eval/quality_harness.py --quick          # retrieval만
    python eval/quality_harness.py --save-history   # data/diagnostics/quality_history.json에 누적

CI 통합: scripts/test_rag_smoke.py 뒤에 묶어 자동 회귀.
"""
from __future__ import annotations

import argparse, json, sys, time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger(__name__)

_GOLD_PATH = ROOT / "eval" / "gold_set.json"
_HISTORY_PATH = ROOT / "data" / "diagnostics" / "quality_history.json"


# ──────────────────────────────────────────────────────────────────────
# Axis 1: retrieval@k
# ──────────────────────────────────────────────────────────────────────

def eval_retrieval(gold: dict, k: int = 5) -> dict:
    """gold 쿼리별 top-k 회수율 측정."""
    try:
        from src.rag.pipeline import RAGPipeline
        rag = RAGPipeline()
    except Exception as e:
        return {"error": f"RAG init fail: {e}"}

    results = []
    for q in gold.get("queries", []):
        query = q["query"]
        expected = set(str(p) for p in q.get("expected_pmids", []))
        if not expected:
            results.append({"id": q["id"], "query": query[:60],
                              "skip": "no expected_pmids"})
            continue
        try:
            hits = rag.search(query, n_results=k) or []
            hit_pmids = set()
            for h in hits:
                md = h.get("metadata") or {}
                pmid = str(md.get("pmid") or md.get("source", ""))
                if pmid:
                    hit_pmids.add(pmid)
            recall = len(expected & hit_pmids) / len(expected) if expected else 0.0
            results.append({
                "id": q["id"], "query": query[:60],
                "expected_n": len(expected),
                "retrieved_n": len(hit_pmids),
                "hit_n": len(expected & hit_pmids),
                "recall_at_k": round(recall, 3),
                "min_threshold": q.get("min_retrieval_at_5", 0.3),
                "pass": recall >= q.get("min_retrieval_at_5", 0.3),
            })
        except Exception as e:
            results.append({"id": q["id"], "error": str(e)[:120]})

    scored = [r for r in results if "recall_at_k" in r]
    avg = sum(r["recall_at_k"] for r in scored) / len(scored) if scored else 0.0
    pass_rate = sum(1 for r in scored if r.get("pass")) / len(scored) if scored else 0.0
    return {
        "axis": "retrieval@k",
        "k": k,
        "n_queries_scored": len(scored),
        "avg_recall": round(avg, 3),
        "pass_rate": round(pass_rate, 3),
        "per_query": results,
    }


# ──────────────────────────────────────────────────────────────────────
# Axis 2: style_match
# ──────────────────────────────────────────────────────────────────────

def eval_style_match(gold: dict, sample_text: str | None = None) -> dict:
    """StyleProfiler 지표가 gold style_targets 범위에 있는지."""
    if not sample_text:
        sample_text = (
            "Background. Caffeine intake may be associated with depressive symptoms in adolescents. "
            "Previous research has suggested potential links between sweetened beverages and mood. "
            "This study examined the association using cross-sectional KYRBS 2022 data. "
            "We hypothesized that high intake might be associated with PHQ-9 scores. "
            "Logistic regression with complex survey weights was used. "
            "The adjusted odds ratio was 1.46, suggesting a modest positive association. "
            "Limitations include cross-sectional design and possible reverse causality. "
            "Future longitudinal research is warranted."
        )
    try:
        from src.ingestion.style_profiler import StyleProfiler
        profile = StyleProfiler().extract_from_text(sample_text, owner_email="eval@harness")
    except Exception as e:
        return {"error": f"StyleProfiler fail: {e}"}

    results = []
    for target in gold.get("style_targets", []):
        in_range = lambda v, lo_hi: lo_hi[0] <= v <= lo_hi[1]
        avg_ok = in_range(profile.avg_sent_len, target["expected_avg_sent_len"])
        hedge_ok = in_range(profile.hedge_ratio, target["expected_hedge_ratio"])
        passive_ok = in_range(profile.passive_ratio, target["expected_passive_ratio"])
        score = (int(avg_ok) + int(hedge_ok) + int(passive_ok)) / 3.0
        results.append({
            "target_id": target["id"],
            "measured": {
                "avg_sent_len": profile.avg_sent_len,
                "hedge_ratio": profile.hedge_ratio,
                "passive_ratio": profile.passive_ratio,
            },
            "in_range": {"avg": avg_ok, "hedge": hedge_ok, "passive": passive_ok},
            "score": round(score, 3),
        })
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0.0
    return {
        "axis": "style_match",
        "n_targets": len(results),
        "avg_score": round(avg_score, 3),
        "per_target": results,
    }


# ──────────────────────────────────────────────────────────────────────
# Axis 3: citation_realism — 모든 [PMID:xxx]가 graph/RAG에 실재
# ──────────────────────────────────────────────────────────────────────

def eval_citation_realism(text_with_citations: str) -> dict:
    """주어진 텍스트의 [PMID:xxx] 토큰이 graph + RAG metadata에 실재하는지."""
    import re
    pmids_in_text = set(re.findall(r"\[PMID:(\d+)\]", text_with_citations))
    if not pmids_in_text:
        return {"axis": "citation_realism", "n_pmids": 0,
                 "realism_rate": 1.0, "note": "no [PMID:] tokens"}

    known = set()
    try:
        g = json.loads((ROOT / "data" / "knowledge_graph" / "graph.json")
                          .read_text(encoding="utf-8"))
        for n in g.get("nodes", []):
            if n.get("type") == "paper" and n.get("pmid"):
                known.add(str(n["pmid"]))
    except Exception:
        pass

    real = pmids_in_text & known
    fake = pmids_in_text - known
    return {
        "axis": "citation_realism",
        "n_pmids": len(pmids_in_text),
        "real": sorted(real)[:10],
        "fake": sorted(fake)[:10],
        "realism_rate": round(len(real) / len(pmids_in_text), 3),
    }


# ──────────────────────────────────────────────────────────────────────
# Axis 4: stat_traceability — 자체 검증 모듈 재사용
# ──────────────────────────────────────────────────────────────────────

def eval_stat_traceability(draft: str, stat_result: dict) -> dict:
    """draft에 적힌 OR/CI/p가 실 stat_result에서 추적 가능한가."""
    try:
        from src.diagnostics.stat_consistency import verify_stat_consistency
        rep = verify_stat_consistency(draft, stat_result)
        return {
            "axis": "stat_traceability",
            "score": rep.get("score", 0.0),
            "matched": rep.get("matched_values", []),
            "missing": rep.get("missing_values", []),
            "hallucinated": rep.get("hallucinated_values", []),
        }
    except Exception as e:
        return {"axis": "stat_traceability", "error": str(e)[:200]}


# ──────────────────────────────────────────────────────────────────────
# Manuscript structure check (gold target)
# ──────────────────────────────────────────────────────────────────────

def eval_manuscript_structure(gold: dict, draft: str) -> dict:
    """gold manuscript_targets 기준 IMRAD 양식 + overclaim 차단 검사."""
    import re
    results = []
    for tg in gold.get("manuscript_targets", []):
        present_secs = []
        for sec in tg.get("must_have_sections", []):
            if re.search(rf"(?im)^##?\s*\d*\.?\s*{re.escape(sec)}\b", draft):
                present_secs.append(sec)
        n_cites = len(re.findall(r"\[(?:PMID:)?\d+\]", draft))
        method_kws_present = [k for k in tg.get("min_methodology_keywords", [])
                                if re.search(rf"\b{re.escape(k)}\b", draft, re.IGNORECASE)]
        overclaim_hits = [p for p in tg.get("no_overclaim_patterns", [])
                           if re.search(rf"\b{re.escape(p)}\b", draft, re.IGNORECASE)]
        sec_score = len(present_secs) / max(1, len(tg.get("must_have_sections", [])))
        cite_pass = n_cites >= tg.get("min_inline_citations", 0)
        method_score = len(method_kws_present) / max(1, len(tg.get("min_methodology_keywords", [])))
        overclaim_pass = len(overclaim_hits) == 0
        composite = (sec_score * 0.4 + (1.0 if cite_pass else 0.0) * 0.2
                      + method_score * 0.2 + (1.0 if overclaim_pass else 0.0) * 0.2)
        results.append({
            "target_id": tg["id"],
            "sections_present": present_secs,
            "section_coverage": round(sec_score, 3),
            "n_citations": n_cites,
            "citation_pass": cite_pass,
            "method_kws_present": method_kws_present,
            "overclaim_hits": overclaim_hits,
            "composite_score": round(composite, 3),
        })
    avg = sum(r["composite_score"] for r in results) / len(results) if results else 0.0
    return {
        "axis": "manuscript_structure",
        "n_targets": len(results),
        "avg_score": round(avg, 3),
        "per_target": results,
    }


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

def run_all(quick: bool = False, draft: str = "", stat_result: dict = None) -> dict:
    gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
    t0 = time.time()
    out = {
        "started_at": datetime.now().isoformat(),
        "gold_set_version": gold.get("version"),
        "axes": {},
    }
    out["axes"]["retrieval_at_5"] = eval_retrieval(gold, k=5)
    if not quick:
        out["axes"]["style_match"] = eval_style_match(gold)
    if draft:
        out["axes"]["citation_realism"] = eval_citation_realism(draft)
        out["axes"]["manuscript_structure"] = eval_manuscript_structure(gold, draft)
        if stat_result:
            out["axes"]["stat_traceability"] = eval_stat_traceability(draft, stat_result)
    out["elapsed_sec"] = round(time.time() - t0, 2)
    # composite quality
    scores = []
    if "retrieval_at_5" in out["axes"]:
        scores.append(("retrieval", out["axes"]["retrieval_at_5"].get("avg_recall", 0.0)))
    if "style_match" in out["axes"]:
        scores.append(("style", out["axes"]["style_match"].get("avg_score", 0.0)))
    if "citation_realism" in out["axes"]:
        scores.append(("citation", out["axes"]["citation_realism"].get("realism_rate", 0.0)))
    if "manuscript_structure" in out["axes"]:
        scores.append(("manuscript", out["axes"]["manuscript_structure"].get("avg_score", 0.0)))
    if scores:
        out["composite"] = round(sum(v for _, v in scores) / len(scores), 3)
        out["scores_by_axis"] = dict(scores)
    return out


def save_history(report: dict) -> None:
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if _HISTORY_PATH.exists():
        try:
            history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.insert(0, report)
    _HISTORY_PATH.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2),
                                  encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--save-history", action="store_true")
    args = ap.parse_args()
    report = run_all(quick=args.quick)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.save_history:
        save_history(report)
        print(f"\nhistory saved → {_HISTORY_PATH}")


if __name__ == "__main__":
    main()
