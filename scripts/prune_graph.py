"""FIX-4 (REVIEW_FIX_SPEC) — graph.json 테스트 더미 노드 제거.

문제: pmid=12345, title="Test:..." 같은 더미가 운영 그래프에 섞여 있음.
변경: 백업 후 더미 노드 + 그 엣지 모두 제거. graph.json 무결성 확보.

실행:
    python scripts/prune_graph.py            # 백업 + 제거
    python scripts/prune_graph.py --dry-run  # 미리보기만
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "data" / "knowledge_graph" / "graph.json"

# 실 PMID는 7-8 digit, PMC는 PMC + 7-8 digit
_VALID_PMID = re.compile(r"^\d{7,9}$")
_VALID_PMCID = re.compile(r"^PMC\d{6,9}$")


def is_dummy_node(node: dict) -> tuple[bool, str]:
    """더미 판정 + 사유 반환."""
    title = str(node.get("title", "")).strip()
    pmid = str(node.get("pmid", "")).strip()
    node_id = str(node.get("id", "")).strip()
    typ = node.get("type", "")

    # paper 노드만 검사
    if typ != "paper":
        return False, ""

    if title.startswith("Test:") or title.startswith("test:"):
        return True, f"title starts with 'Test:': {title[:60]}"
    if pmid == "12345" or pmid == "00000":
        return True, f"placeholder pmid: {pmid}"
    if pmid and not (_VALID_PMID.match(pmid) or _VALID_PMCID.match(pmid)):
        # 짧은 임의 숫자 (1~5 digit) 같은 비정상 pmid
        return True, f"invalid pmid format: {pmid}"
    return False, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not GRAPH.exists():
        print(f"graph not found: {GRAPH}"); sys.exit(1)

    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = g.get("nodes", [])
    links = g.get("links") or g.get("edges") or []

    dummy_ids = set()
    dummy_reasons = {}
    for n in nodes:
        dummy, reason = is_dummy_node(n)
        if dummy:
            dummy_ids.add(n.get("id"))
            dummy_reasons[n.get("id")] = reason

    print(f"total nodes: {len(nodes)}, total edges: {len(links)}")
    print(f"dummies found: {len(dummy_ids)}")
    for nid in list(dummy_ids)[:10]:
        print(f"  - {nid}  ({dummy_reasons[nid]})")
    if not dummy_ids:
        print("nothing to prune.")
        return

    # 더미 노드의 엣지도 제거
    edges_removed = sum(1 for e in links
                          if e.get("source") in dummy_ids or e.get("target") in dummy_ids)
    print(f"edges to remove: {edges_removed}")

    if args.dry_run:
        print("dry-run: no write.")
        return

    # 백업
    backup = GRAPH.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shutil.copy2(GRAPH, backup)
    print(f"backup: {backup}")

    # 제거
    new_nodes = [n for n in nodes if n.get("id") not in dummy_ids]
    new_links = [e for e in links if e.get("source") not in dummy_ids
                                       and e.get("target") not in dummy_ids]
    g["nodes"] = new_nodes
    if "links" in g: g["links"] = new_links
    if "edges" in g: g["edges"] = new_links
    GRAPH.write_text(json.dumps(g, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"pruned: nodes {len(nodes)} → {len(new_nodes)}, "
          f"edges {len(links)} → {len(new_links)}")


if __name__ == "__main__":
    main()
