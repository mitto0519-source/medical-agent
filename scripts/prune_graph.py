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

# PMID 1~5 digit이 명백히 placeholder. 6~9 digit은 모두 valid (오래된 PMC 포함).
_VALID_PMID = re.compile(r"^\d{6,9}$")
_VALID_PMCID = re.compile(r"^PMC\d{6,9}$")
_TEST_TITLE = re.compile(r"^Test:|^TEST:|^test:|placeholder|^Dummy:", re.IGNORECASE)


def is_dummy_node(node: dict) -> tuple[bool, str]:
    """더미 판정 + 사유 반환.

    제거 대상:
      - title이 'Test:'로 시작 (콜론 양식 — 'Testing' 같은 정상 paper와 구분)
      - pmid가 placeholder ('12345', '00000', '1', '99999' 등 1~5 digit)
      - pmid가 명백히 비PMID 형식
    제외 (정상):
      - 'Testing the...' 같은 정상 paper 양식
      - 244666 같은 6-digit PMID (old PubMed)
    """
    title = str(node.get("title", "")).strip()
    pmid = str(node.get("pmid", "")).strip()
    typ = node.get("type", "")

    if typ != "paper":
        return False, ""

    if _TEST_TITLE.match(title):
        return True, f"test title: {title[:60]}"
    if pmid == "12345" or pmid == "00000" or pmid == "1":
        return True, f"placeholder pmid: {pmid}"
    if pmid and not (_VALID_PMID.match(pmid) or _VALID_PMCID.match(pmid)):
        # 5 digit 이하 또는 비숫자
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
