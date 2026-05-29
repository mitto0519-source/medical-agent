"""기존 12,258편 자산을 더 깊이 활용 — Ontology 매핑 + Citation graph + Seed enrichment.

사용자 통찰 (2026-05-29): "기존 자산 활용해서 시드화 RAG화 ontology화 더 많이 하면 되는거 아닌가".

3개 단계:
  1. ontology_remap     — 각 paper의 abstract+title을 medical_ontology.extract_concepts로
                          concept ID 매핑 → medical_graph에 paper↔concept edge 추가
  2. citation_postbuild — fast_mode로 skip한 citation_graph를 12,258 PMID에 대해
                          별도 batch로 빌드 (eLink rate-limited)
  3. seed_enrich        — 12,258편에서 high-quality paper 자동 선별 (인용수·journal·
                          length 기준) → yoosun_style raw_examples 확장 후보 생성

호출:
    python scripts/enrich_assets.py --step ontology   # 매핑만
    python scripts/enrich_assets.py --step citation --max 500  # citation 500편만
    python scripts/enrich_assets.py --step seed --top 100      # seed top 100
    python scripts/enrich_assets.py --step all --max 500
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _ensure_utf8():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)


# ── Step 1: Ontology remapping ──────────────────────────────────────────────

def step_ontology(limit: int = 0) -> dict:
    """각 paper의 abstract+title에서 concept 추출 → medical_graph에 edge 추가."""
    from src.knowledge.medical_ontology import get_ontology
    from src.knowledge.medical_graph import get_graph

    ont = get_ontology()
    g = get_graph()
    if not ont or not g:
        return {"error": "ontology or graph unavailable"}

    oa_dir = Path("data/oa_papers")
    metas = sorted(oa_dir.glob("PMC*.meta.json"))
    if limit:
        metas = metas[:limit]

    print(f"=== Step 1 · Ontology remap · {len(metas):,} paper ===", flush=True)
    n_concepts_added, n_edges_added = 0, 0
    t0 = time.time()

    for i, mp in enumerate(metas, 1):
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
            pmid = meta.get("pmid", "") or mp.stem.replace("PMC", "")
            title = meta.get("title", "")
            # abstract: body에서 첫 2000자 또는 meta에 있는 경우
            txt = f"{title}\n{meta.get('journal','')}"
            try:
                body = (oa_dir / f"{mp.stem}.txt").read_text(encoding="utf-8",
                                                                errors="replace")[:3000]
                txt = txt + "\n" + body
            except Exception:
                pass
            concepts = ont.extract_concepts(txt) or []
            paper_node = f"paper:{pmid}"
            if not g._G.has_node(paper_node):
                continue   # paper node가 없으면 skip (orchestrator가 등록했어야)
            for c in concepts[:20]:
                cid = c.get("id") or c.get("concept_id")
                if not cid:
                    continue
                cnode = g.add_concept(cid, label=c.get("label", cid),
                                       domain=c.get("domain", ""))
                if not g._G.has_edge(paper_node, cnode):
                    g._G.add_edge(paper_node, cnode, type="discusses")
                    n_edges_added += 1
                n_concepts_added += 1
        except Exception as e:
            continue
        if i % 500 == 0:
            elapsed = (time.time() - t0)
            rate = i / max(elapsed, 0.1)
            print(f"[{i:,}/{len(metas):,}] edges+={n_edges_added:,} · "
                   f"concepts touched={n_concepts_added:,} · rate={rate:.1f}/s",
                   flush=True)

    try:
        if hasattr(g, "save"):
            g.save()
    except Exception:
        pass
    print(f"=== Step 1 DONE: edges added={n_edges_added:,}, concepts touched={n_concepts_added:,} "
          f"elapsed={(time.time()-t0)/60:.1f}min ===", flush=True)
    return {"edges_added": n_edges_added, "concepts_touched": n_concepts_added}


# ── Step 2: Citation graph post-build ──────────────────────────────────────

def step_citation(limit: int = 0) -> dict:
    """fast_mode로 skip한 citation_graph를 12,258 PMID에 대해 후처리 빌드."""
    from src.knowledge.citation_graph import build_citation_graph

    oa_dir = Path("data/oa_papers")
    metas = sorted(oa_dir.glob("PMC*.meta.json"))
    if limit:
        metas = metas[:limit]

    pmids = []
    for mp in metas:
        try:
            d = json.loads(mp.read_text(encoding="utf-8"))
            pmid = d.get("pmid") or ""
            if pmid:
                pmids.append(pmid)
        except Exception:
            continue
    print(f"=== Step 2 · Citation graph · {len(pmids):,} PMID ===", flush=True)
    t0 = time.time()
    # batch 단위로 build_citation_graph 호출 (각 호출은 eLink rate limited)
    BATCH = 50
    total_nodes, total_edges = 0, 0
    for i in range(0, len(pmids), BATCH):
        chunk = pmids[i:i + BATCH]
        try:
            g = build_citation_graph(chunk, depth=1, max_per_ref=5, use_cache=True)
            if g is not None:
                total_nodes = g.number_of_nodes()
                total_edges = g.number_of_edges()
        except Exception as e:
            print(f"  batch {i}: {e}", flush=True)
        if (i // BATCH + 1) % 5 == 0:
            elapsed = (time.time() - t0) / 60
            print(f"[batch {i//BATCH+1}/{len(pmids)//BATCH+1}] graph nodes={total_nodes:,} "
                   f"edges={total_edges:,} elapsed={elapsed:.1f}min", flush=True)

    print(f"=== Step 2 DONE: nodes={total_nodes:,}, edges={total_edges:,} "
          f"elapsed={(time.time()-t0)/60:.1f}min ===", flush=True)
    return {"nodes": total_nodes, "edges": total_edges}


# ── Step 3: Seed enrichment (high-quality paper 자동 선별) ─────────────────

_HQ_JOURNALS = {
    "lancet", "n engl j med", "jama", "bmj", "annu rev",
    "nat med", "nat rev", "nature medicine", "circulation",
    "j am coll cardiol", "ann intern med", "diabetes care",
    "lancet diabetes endocrinol", "lancet child adolesc health",
    "lancet psychiatry", "jama psychiatry", "jama netw open",
    "j adolesc health", "pediatrics", "bmc med", "plos med",
    "am j epidemiol", "int j epidemiol", "j epidemiol community health",
    "j affect disord", "psychol med", "soc sci med", "prev med",
}


def _hq_score(meta: dict) -> float:
    """간단 품질 점수: journal 명성 + 최근성 + 인용 cluster 잠재."""
    score = 0.0
    j = (meta.get("journal", "") or "").lower()
    for hq in _HQ_JOURNALS:
        if hq in j:
            score += 0.5
            break
    year = meta.get("year")
    try:
        y = int(year) if year else 0
        if 2018 <= y <= 2026:
            score += 0.2 + (y - 2018) * 0.05
    except Exception:
        pass
    # figure/table 풍부도 (학술 가치)
    n_fig = len(meta.get("figures", []) or [])
    n_tbl = len(meta.get("tables", []) or [])
    score += min(0.3, (n_fig + n_tbl) * 0.02)
    return score


def step_seed(top_n: int = 100) -> dict:
    """high-quality top_n paper 자동 선별 → yoosun_style seed 후보 저장."""
    oa_dir = Path("data/oa_papers")
    metas = list(oa_dir.glob("PMC*.meta.json"))
    print(f"=== Step 3 · Seed enrichment · {len(metas):,} paper에서 top {top_n} 선별 ===", flush=True)

    ranked = []
    for mp in metas:
        try:
            d = json.loads(mp.read_text(encoding="utf-8"))
            d["_score"] = _hq_score(d)
            d["_pmcid"] = mp.stem
            ranked.append(d)
        except Exception:
            continue
    ranked.sort(key=lambda x: x["_score"], reverse=True)
    top = ranked[:top_n]

    # 저장: data/author_profiles/oa_curated_top{N}.json
    out_dir = Path("data/author_profiles")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"oa_curated_top{top_n}.json"
    curated = [{
        "pmcid": d["_pmcid"], "pmid": d.get("pmid", ""),
        "title": d.get("title", ""), "year": d.get("year"),
        "journal": d.get("journal", ""), "doi": d.get("doi", ""),
        "score": round(d["_score"], 3),
        "n_figures": len(d.get("figures", []) or []),
        "n_tables": len(d.get("tables", []) or []),
    } for d in top]
    out_path.write_text(json.dumps(curated, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    # prompts/curated_seed.md 자동 생성 (yoosun_style 확장 후보)
    md_path = Path("prompts/curated_seed.md")
    md_lines = [
        "---",
        "name: curated_seed",
        f"version: 1.0.0-top{top_n}",
        f"applies_to: [paper_write]",
        f"last_updated: {time.strftime('%Y-%m-%d')}",
        f"source: auto-curated from {len(metas):,} OA papers (top {top_n} by HQ score)",
        "---",
        "",
        f"# Curated Top-{top_n} Seed (Auto-generated)",
        "",
        f"From {len(metas):,} OA full-text papers, automatically selected top {top_n} by "
        "high-quality journal + recency + structure (figures/tables) score.",
        "",
        "## High-quality reference list (use for citation grounding)",
        "",
    ]
    for d in top[:50]:   # md에는 top 50만
        title = (d.get("title", "") or "Untitled")[:160]
        j = (d.get("journal", "") or "")[:80]
        y = d.get("year", "")
        pmid = d.get("pmid", "") or d["_pmcid"]
        md_lines.append(f"- **{title}** · *{j}* {y} · PMID:{pmid}")
    md_lines.append("")
    md_lines.append(f"## Use\n")
    md_lines.append(f"Reference this curated list as primary citation pool. Avoid citing")
    md_lines.append(f"outside this list unless extension_required. Cross-link with")
    md_lines.append(f"`data/author_profiles/oa_curated_top{top_n}.json`.")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"=== Step 3 DONE: top {top_n} 선별 ===", flush=True)
    print(f"  data/author_profiles/oa_curated_top{top_n}.json", flush=True)
    print(f"  prompts/curated_seed.md (v1.0.0-top{top_n})", flush=True)
    return {"top_n": top_n, "curated_path": str(out_path), "prompt_path": str(md_path)}


def main():
    _ensure_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["ontology", "citation", "seed", "all"],
                     default="all")
    ap.add_argument("--limit", type=int, default=0, help="paper 수 제한 (0=전체)")
    ap.add_argument("--top", type=int, default=100, help="seed step의 top N")
    args = ap.parse_args()

    out = {}
    if args.step in ("ontology", "all"):
        out["ontology"] = step_ontology(limit=args.limit)
    if args.step in ("citation", "all"):
        out["citation"] = step_citation(limit=args.limit or 1000)   # citation은 500편만 기본
    if args.step in ("seed", "all"):
        out["seed"] = step_seed(top_n=args.top)

    print("\n=== Summary ===", flush=True)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
