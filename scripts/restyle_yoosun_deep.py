"""조유선 FULL-LAYER 재첨삭 — 어휘만이 아니라 단락 전개·보고 규율·수사 구조·문장 리듬까지.

자산 활용: author_profiles/yoosun_cho.json 의 (1) system_prompt (2) raw_examples(그녀 실제 논문 초록)
를 few-shot 스타일 예시로 주입. 섹션을 '구조까지' 재작성하되 숫자·통계·[n] 인용은 전수 잠금.
무결성 미충족 시 최대 2회 재시도, 그래도 실패하면 원문 유지(규칙11).

실행: python scripts/restyle_yoosun_deep.py <in.md> <out_base>
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def cite_nums(t):  # 본문 [n] 인용 번호 집합
    return {int(n) for g in re.findall(r"\[([\d,\s\-]+)\]", t or "") for n in re.findall(r"\d+", g)}


def stat_nums(t):  # 통계 토큰 집합(OR/CI/p/%/N)
    return set(re.findall(r"\d+\.\d+|\d{1,3}(?:,\d{3})+|\d+%|p\s*[=<]\s*0?\.\d+", t or ""))


def main():
    import warnings; warnings.filterwarnings("ignore")
    from src.config.env import bootstrap; bootstrap()
    from src.llm import get_llm_client
    import os

    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exports/ZCB_final_yoosun.md")
    base = sys.argv[2] if len(sys.argv) > 2 else "ZCB_final_deep"
    text = src.read_text(encoding="utf-8")
    prof = json.loads(Path("data/author_profiles/yoosun_cho.json").read_text(encoding="utf-8"))

    # 자산: 그녀 실제 논문 초록 3편을 스타일 예시로
    exemplars = "\n\n---\n\n".join(e.strip()[:1100] for e in prof.get("raw_examples", [])[1:4])
    para_rule = prof["writing_style"]["paragraph_structure"]
    disc_rule = prof["paper_structure"]["discussion_structure"]
    res_rule = prof["paper_structure"]["results_flow"]
    intro_rule = prof["paper_structure"]["introduction_pattern"]

    mt = re.search(r"(?m)^#\s+(.+?)\s*$", text); title = mt.group(1).strip()
    mref = re.search(r"(?im)^##\s*references?\s*$", text)
    body = text[:mref.start()]; ref_block = text[mref.start():]
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", body)
    head = parts[0].rstrip()
    secs = [[parts[i].strip(), (parts[i + 1] or "").rstrip()] for i in range(1, len(parts) - 1, 2)]

    client = get_llm_client(provider=os.environ.get("RESTYLE_PROVIDER", "anthropic"), task="paper_writing")

    SECTION_GUIDE = {
        "introduction": f"Introduction pattern: {intro_rule}",
        "results": f"Results flow: {res_rule}",
        "discussion": f"Discussion structure: {disc_rule}",
    }

    def deep_rewrite(label, content):
        guide = SECTION_GUIDE.get(label.lower(), "")
        sysp = (
            prof["system_prompt"] +
            "\n\n=== AUTHOR'S REAL WRITING (style exemplars — match this voice, rhythm, and paragraph movement) ===\n"
            + exemplars +
            "\n\n=== FULL-LAYER REWRITE TASK ===\n"
            "Rewrite the section below SO IT READS AS IF WRITTEN BY THIS AUTHOR. Go beyond vocabulary — apply ALL layers:\n"
            f"1. PARAGRAPH MOVEMENT: {para_rule}\n"
            "2. REPORTING DISCIPLINE: report counts/sample before estimates; estimates with 95% CI; explicit reference categories; trend across ordered categories.\n"
            "3. RHETORICAL ARCHITECTURE: " + (guide or "match the author's section logic.") + "\n"
            "4. SENTENCE RHYTHM: vary sentence length; evidence-first; formal, confident, with rhetorical edge; remove padding and weak hedges.\n"
            "You MAY restructure sentences and reorder clauses/paragraphs for flow.\n"
            "ABSOLUTE LOCKS (the analysis is final): keep EVERY number/OR/aOR/95% CI/p-value/percentage/sample size EXACTLY; "
            "keep EVERY in-text citation number (e.g., [1], [5-7], [14, 31]) — you may regroup adjacent ones but never drop or invent a number; "
            "keep all factual/statistical claims and any '### subheaders'. Do NOT add new citations.\n"
            "Return ONLY the rewritten section body."
        )
        c0, n0 = cite_nums(content), stat_nums(content)
        for attempt in range(3):
            r = client.generate(f"SECTION: {label}\n\n{content}", system_prompt=sysp,
                                task="paper_writing", max_tokens=4096)
            if not (r and r.strip()):
                continue
            c1, n1 = cite_nums(r), stat_nums(r)
            cite_ok = c0 <= c1
            num_ok = (len(n0 & n1) >= int(len(n0) * 0.92)) if n0 else True
            if cite_ok and num_ok and len(r) > len(content) * 0.5:
                return r.strip(), f"OK(try{attempt+1}) 인용{sorted(c1)[:3]}..{sorted(c1)[-2:]} 숫자{len(n0&n1)}/{len(n0)}"
        return content, f"KEEP 무결성미충족(인용 {len(c0)}→{len(c1)}, 숫자 {len(n0&n1)}/{len(n0)})"

    report = []
    for s in secs:
        out, msg = deep_rewrite(s[0], s[1])
        s[1] = out
        report.append(f"[{'OK' if msg.startswith('OK') else 'KEEP'}] {s[0]}: {len(s[1])}자 · {msg}")

    new_md = head + "\n\n" + "\n\n".join(f"## {l}\n{c}" for l, c in secs) + "\n\n" + ref_block.strip() + "\n"
    Path(f"data/exports/{base}.md").write_text(new_md, encoding="utf-8")
    print("\n".join(report))
    print(f"\nFULL-LAYER 재첨삭: {sum(1 for r in report if r.startswith('[OK]'))}/{len(secs)} · provider={getattr(client,'model','?')} · 저장 data/exports/{base}.md")


if __name__ == "__main__":
    main()
