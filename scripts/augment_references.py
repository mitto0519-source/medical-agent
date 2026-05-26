"""레퍼런스 자동 보강 — PubMed에서 주제 관련 신규 논문을 찾아 차용 검수(임베딩).

기존 참고문헌과 중복 제거 후, 내 논문 본문과의 의미 유사도로 '차용 가능' 신규 후보를 제시.
LLM-무관(쿼터 무관). 실행: python scripts/augment_references.py
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

QUERIES = [
    "artificial sweetener depression adolescents",
    "non-nutritive sweetener mental health youth",
    "diet beverage depression cohort",
    "aspartame mood depression",
    "sugar-sweetened beverage adolescent depression sex difference",
    "ultra-processed food adolescent depression",
]


def main():
    import warnings; warnings.filterwarnings("ignore")
    from src.config.env import bootstrap; bootstrap()
    from src.export.reference_library import search_pubmed, _fetch_pubmed_xml, _parse_pubmed_xml
    from src.export.citation_workflow import screen_applicability

    md = Path("data/exports/ZCB_revised_YoosunCho.md").read_text(encoding="utf-8")
    body = md[:re.search(r"(?im)^##\s*references?\s*$", md).start()]
    existing = md[re.search(r"(?im)^##\s*references?\s*$", md).start():].lower()

    found, seen_pmids = [], set()
    for q in QUERIES:
        try:
            ids = search_pubmed(q, max_results=4)
            for r in _parse_pubmed_xml(_fetch_pubmed_xml(ids)):
                if not r.pmid or r.pmid in seen_pmids:
                    continue
                seen_pmids.add(r.pmid)
                # 기존 28개와 제목 중복 제거
                t = (r.title or "").lower()[:40]
                if t and t in existing:
                    continue
                found.append(r)
        except Exception as e:
            print(f"  [query 실패] {q}: {str(e)[:80]}")

    if not found:
        print("신규 후보 없음 (네트워크/검색 실패 가능)")
        return

    scored = screen_applicability(found, body, threshold=0.35)
    usable = [s for s in scored if s["usable"]]
    print(f"PubMed 신규 후보 {len(found)}개 → 차용 가능(임계 0.35) {len(usable)}개\n")
    for i, s in enumerate(usable[:12], 1):
        r = s["ref"]
        au = (r.authors[0] if r.authors else "?")
        print(f"[{s['score']:.2f}] {au} et al. {r.title[:95]}")
        print(f"        {r.journal} {r.year}  PMID:{r.pmid}")
    # 차용 부적합(낮은 점수)도 몇 개 투명하게
    weak = [s for s in scored if not s["usable"]][:3]
    if weak:
        print("\n(차용 부적합 예시 — 관련성 낮음):")
        for s in weak:
            print(f"  [{s['score']:.2f}] {s['ref'].title[:80]}")


if __name__ == "__main__":
    main()
