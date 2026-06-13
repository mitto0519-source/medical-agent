"""FIX-0 (REVIEW_FIX_SPEC) — CURRENT_STATE.json 진실원본 자동 동기화.

문서가 거짓말하지 않도록 실데이터 카운트를 매번 새로 측정해 권위 메모리에 박는다.
prepromt hook이 CURRENT_STATE.json을 prepend하므로 갱신 즉시 에이전트 추론에 반영.

실행:
    python scripts/reconcile_state.py
    python scripts/reconcile_state.py --dry-run   # 측정만, 파일 안 씀

규칙10: 중복 카운터 만들지 말 것 — assess_maturity.py·self_model.refresh가 이 측정값을
재사용하도록 `measure_truth()`를 공개 API로 제공.
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_PATH = ROOT / "CURRENT_STATE.json"


def measure_truth() -> dict:
    """실파일/실DB에서 권위 카운트 측정. assess_maturity·self_model이 재사용."""
    result: dict = {"measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # 1) 논문 코퍼스
    oa = ROOT / "data" / "oa_papers"
    if oa.exists():
        meta_files = list(oa.glob("*.meta.json"))
        full_files = list(oa.glob("*.txt"))
        full_real = [f for f in full_files if f.stat().st_size > 5 * 1024]
        # PMID 양식 양식: meta_json 양식 양식 양식 1 paper = 1 entry
        result["papers"] = {
            "meta_json_files": len(meta_files),
            "full_text_files": len(full_files),
            "full_text_above_5kb": len(full_real),
            "full_text_completion_pct": round(
                len(full_real) / max(1, len(meta_files)) * 100, 1),
            "comment": "1 paper = 1 .meta.json + 1 .txt pair. ~3% of .txt are stubs <5KB.",
        }
    else:
        result["papers"] = {"error": "data/oa_papers/ missing"}

    # 2) ChromaDB
    db_paths = glob.glob(str(ROOT / "data" / "chromadb" / "*.sqlite3"))
    if db_paths:
        try:
            c = sqlite3.connect(db_paths[0])
            chunks = c.execute("SELECT count(*) FROM embeddings").fetchone()[0]
            try:
                queue = c.execute("SELECT count(*) FROM embeddings_queue").fetchone()[0]
            except sqlite3.OperationalError:
                queue = 0
            try:
                em_meta = c.execute("SELECT count(*) FROM embedding_metadata").fetchone()[0]
            except sqlite3.OperationalError:
                em_meta = 0
            c.close()
            result["chromadb"] = {
                "embeddings": chunks,
                "queue_pending": queue,
                "embedding_metadata_rows": em_meta,
            }
        except Exception as e:
            result["chromadb"] = {"error": str(e)[:120]}
    else:
        result["chromadb"] = {"error": "no chromadb sqlite found"}

    # 3) 지식 그래프 (NetworkX json — nodes/links)
    gpath = ROOT / "data" / "knowledge_graph" / "graph.json"
    if gpath.exists():
        try:
            g = json.loads(gpath.read_text(encoding="utf-8"))
            nodes = g.get("nodes", [])
            links = g.get("links") or g.get("edges") or []
            ntypes = Counter(n.get("type") for n in nodes)
            ltypes = Counter(l.get("relation") or l.get("rel") for l in links)
            result["knowledge_graph"] = {
                "file": "data/knowledge_graph/graph.json",
                "nodes_total": len(nodes),
                "node_types": dict(ntypes),
                "edges_total": len(links),
                "edge_relations": dict(ltypes),
            }
        except Exception as e:
            result["knowledge_graph"] = {"error": str(e)[:120]}
    else:
        result["knowledge_graph"] = {"error": "graph.json missing"}

    # 4) 온톨로지 (concept ceiling — 그래프 패턴화의 천장)
    try:
        from src.knowledge.medical_ontology import MedicalOntology
        mo = MedicalOntology()
        concepts = mo.all_concepts()
        result["ontology"] = {
            "concept_count": len(concepts),
            "sample": list(concepts)[:8] if concepts else [],
        }
    except Exception as e:
        result["ontology"] = {"error": str(e)[:120]}

    # 5) 페르소나·시드 (key는 'papers_analysed', 'papers' 아님)
    try:
        yp = ROOT / "data" / "author_profiles" / "yoosun_cho.json"
        if yp.exists():
            yd = json.loads(yp.read_text(encoding="utf-8"))
            result["yoosun_seed"] = {
                "analyzed_papers": len(yd.get("papers_analysed") or yd.get("papers") or []),
                "raw_examples": len(yd.get("raw_examples") or []),
                "vocabulary_items": len(yd.get("vocabulary") or []),
                "study_focus_items": len(yd.get("study_focus") or []),
                "system_prompt_chars": len(yd.get("system_prompt", "") or ""),
            }
    except Exception as e:
        result.setdefault("yoosun_seed", {})["error"] = str(e)[:120]

    # 6) per-user style profiles (FIX-1 wire 검증)
    pdir = ROOT / "data" / "profiles"
    if pdir.exists():
        profs = list(pdir.glob("*/style_profile.json"))
        result["style_profiles"] = {"per_user_profiles": len(profs)}

    # 7) Supabase live state (cloud_available 양식 양식)
    try:
        from src.cloud.db import cloud_available
        result["supabase"] = {"cloud_available": bool(cloud_available())}
    except Exception:
        result["supabase"] = {"cloud_available": False}

    return result


def apply_to_state(truth: dict, dry_run: bool = False) -> dict:
    """CURRENT_STATE.json 의 verified_counts 블록을 측정값으로 덮어쓴다."""
    if not STATE_PATH.exists():
        return {"error": "CURRENT_STATE.json missing"}
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["verified_counts"] = truth
    # key_assets_by_size 갱신 (기존 dict이면 유지하고 양식 양식 양식)
    if isinstance(state.get("key_assets_by_size"), dict):
        kab = state["key_assets_by_size"]
    else:
        kab = state["key_assets_by_size"] = {}
    p = truth.get("papers", {})
    if p and "error" not in p:
        kab["oa_papers_full_text"] = p.get("full_text_files")
        kab["oa_papers_full_text_above_5kb"] = p.get("full_text_above_5kb")
        kab["oa_papers_meta_stubs"] = p.get("meta_json_files")
    ch = truth.get("chromadb", {})
    if ch and "error" not in ch:
        kab["chromadb_embeddings"] = ch.get("embeddings")
        kab["chromadb_queue_pending"] = ch.get("queue_pending")
    kg = truth.get("knowledge_graph", {})
    if kg and "error" not in kg:
        kab["knowledge_graph_nodes"] = kg.get("nodes_total")
        kab["knowledge_graph_edges"] = kg.get("edges_total")
    ont = truth.get("ontology", {})
    if ont and "error" not in ont:
        kab["medical_ontology_concepts"] = ont.get("concept_count")

    # known_seed_bias 양식 양식
    if isinstance(state.get("known_seed_bias"), dict):
        state["known_seed_bias"].setdefault("verified_at", truth["measured_at"])

    if dry_run:
        return {"dry_run": True, "preview_keys_updated":
                list(kab.keys()) + ["verified_counts"]}

    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": str(STATE_PATH), "verified_counts_keys": list(truth.keys())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                     help="측정만, CURRENT_STATE.json 안 씀")
    args = ap.parse_args()

    truth = measure_truth()
    apply_result = apply_to_state(truth, dry_run=args.dry_run)

    print(json.dumps({"truth": truth, "apply": apply_result},
                       ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
