"""revised .md(제목 + '## 섹션' + '## References') → Word + EndNote + BibTeX 풀셋.

citation_workflow의 검증된 빌더(build_cited_docx/endnote_bytes/bibtex_bytes)와
레퍼런스 파서(_parse_vancouver_entry)를 재사용 — 본문 [n] 넘버링 보존, 번호순 참고문헌.

실행: python scripts/build_revised_fullset.py <input.md> [out_basename]
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exports/ZCB_revised_YoosunCho.md")
    base = sys.argv[2] if len(sys.argv) > 2 else src.stem
    text = src.read_text(encoding="utf-8")

    from src.export.citation_workflow import (
        _parse_vancouver_entry, build_cited_docx, endnote_bytes, bibtex_bytes,
    )

    # 제목 = 첫 '# ' 라인
    mt = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    title = mt.group(1).strip() if mt else "Revised Paper"

    # References 분리
    mref = re.search(r"(?im)^##\s*references?\s*$", text)
    body = text[:mref.start()] if mref else text
    ref_block = text[mref.end():] if mref else ""

    # 본문 섹션: '## Label' 단위 (References 제외)
    _LABELS = {"abstract": "abstract", "introduction": "introduction",
               "methods": "methods", "results": "results", "discussion": "discussion"}
    sections = {}
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", body)
    for i in range(1, len(parts) - 1, 2):
        key = _LABELS.get(parts[i].strip().lower())
        seg = (parts[i + 1] or "").strip()
        if key and seg:
            sections[key] = seg

    # 참고문헌 파싱 (번호 머리 제거 후 밴쿠버 파서)
    refs = []
    for line in ref_block.splitlines():
        s = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
        if len(s) > 15:
            refs.append(_parse_vancouver_entry(s))

    docx = build_cited_docx(title, sections, refs)
    en = endnote_bytes(refs)
    bib = bibtex_bytes(refs)

    out = Path("data/exports")
    (out / f"{base}.docx").write_bytes(docx)
    (out / f"{base}.xml").write_bytes(en)
    (out / f"{base}.bib").write_bytes(bib)

    print("제목:", title)
    print(f"섹션: {list(sections.keys())} (각 길이 {[len(v) for v in sections.values()]})")
    print(f"참고문헌: {len(refs)}개 — 예) {refs[0].authors[:2]} | {refs[0].title[:50]} | {refs[0].year}")
    # 본문 [n] 마커 보존 확인
    markers = sorted({int(n) for grp in re.findall(r"\[(\d+(?:[\-,\s]*\d+)*)\]", body)
                      for n in re.findall(r"\d+", grp)})
    print(f"본문 인용 마커: {markers[:12]}{'...' if len(markers) > 12 else ''} (총 {len(markers)})")
    print(f"출력: {base}.docx({len(docx)}b), {base}.xml({len(en)}b), {base}.bib({len(bib)}b) → data/exports/")
    # EndNote/구조 검증
    import zipfile
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    print("DOCX 검증: References 포함=%s, 본문 [n] 포함=%s, EndNote record=%s" % (
        "References" in xml, "[1" in xml, (b"<record>" in en)))


if __name__ == "__main__":
    main()
