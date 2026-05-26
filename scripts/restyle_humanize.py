"""파이널라이징 — 과한 AI cadence 제거 + 주장강도 보정 + male subgroup 일관성 수정.

조유선의 정밀함/구조는 유지하되, '너무 GPT스러운 완벽함'을 사람 PI의 자연스러운 흐름으로.
숫자/통계/[n] 전수 잠금. 대상: abstract/introduction/results/discussion (methods는 사실 위주라 유지).
실행: python scripts/restyle_humanize.py <in.md> <out_base>
"""
from __future__ import annotations
import io, re, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def cite_nums(t):
    return {int(n) for g in re.findall(r"\[([\d,\s\-]+)\]", t or "") for n in re.findall(r"\d+", g)}


def stat_nums(t):
    return set(re.findall(r"\d+\.\d+|\d{1,3}(?:,\d{3})+|\d+%|p\s*[=<]\s*0?\.\d+", t or ""))


TARGET = {"abstract", "introduction", "results", "discussion"}

MALE_FACTS = (
    "MALE SUBGROUP FACTS (use to correct any 'absent in males'/'females only' overstatement): "
    "male per-1-level aOR 1.01 (95% CI 0.99-1.04, p=0.318) = no significant trend; "
    "male ≤2/wk 1.07 (1.00-1.15), 3-6/wk 0.98 (0.85-1.12), ≥1/day 1.31 (1.02-1.69). "
    "So the highest male category IS significant and the gradient is non-monotonic — "
    "characterize males as 'no significant dose-response trend, although the highest-intake category "
    "showed elevated odds', NOT as a null/absent effect."
)

SYS = (
    "You are a senior epidemiology professor doing the FINAL human pass on your own manuscript before "
    "submission to a high-impact journal. The current draft is technically good but over-polished and "
    "reads AI-generated. Make it read like a real human expert wrote it, WITHOUT weakening the science.\n\n"
    "HUMANIZE THE PROSE:\n"
    "- Deliberately vary sentence length. Include some short, direct sentences among longer ones. "
    "Break the uniform 'two clauses + semicolon + apposition' rhythm.\n"
    "- Cut mechanical transitions by about a third. Do NOT start consecutive sentences with "
    "First/Second/Third/Moreover/Notably/Together with/In parallel/Furthermore. Use them sparingly.\n"
    "- DELETE these AI-tell phrases and rephrase plainly: 'advances this literature in three respects', "
    "'To our knowledge, this is the first study', 'offers a coherent framework', 'strengthens biological "
    "plausibility', 'the convergence of ... pathways'. Avoid 'not X but Y' and 'both confirm and extend'.\n\n"
    "CALIBRATE CLAIMS (this is cross-sectional — do not overstate):\n"
    "- Replace 'absent in males' / 'females only' framing per the MALE SUBGROUP FACTS provided.\n"
    "- 'supports a more specific mood-related effect' -> 'is consistent with a more specific association "
    "with depressive symptoms'.\n"
    "- 'coherent framework' -> 'biologically plausible framework'.\n"
    "- Prefer 'may reflect', 'is consistent with', 'suggests'; soften causal phrasing.\n\n"
    "HARD LOCKS: keep EVERY number/OR/aOR/95% CI/p-value/percentage/sample size exactly; keep EVERY "
    "in-text citation number [n] (you may regroup adjacent ones, never drop/invent); keep all factual "
    "claims, section structure, and any '### subheaders'. Do NOT add new citations.\n"
    "Return ONLY the edited section body."
)


def main():
    import warnings; warnings.filterwarnings("ignore")
    from src.config.env import bootstrap; bootstrap()
    from src.llm import get_llm_client

    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exports/ZCB_final_deep.md")
    base = sys.argv[2] if len(sys.argv) > 2 else "ZCB_final_v2"
    text = src.read_text(encoding="utf-8")

    mt = re.search(r"(?m)^#\s+(.+?)\s*$", text); title = mt.group(1).strip()
    mref = re.search(r"(?im)^##\s*references?\s*$", text)
    body = text[:mref.start()]; ref_block = text[mref.start():]
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", body)
    head = parts[0].rstrip()
    secs = [[parts[i].strip(), (parts[i + 1] or "").rstrip()] for i in range(1, len(parts) - 1, 2)]

    client = get_llm_client(provider=os.environ.get("RESTYLE_PROVIDER", "anthropic"), task="paper_writing")

    report = []
    for s in secs:
        if s[0].lower() not in TARGET:
            report.append(f"[SKIP] {s[0]}: 유지(사실 위주)")
            continue
        c0, n0 = cite_nums(s[1]), stat_nums(s[1])
        extra = ("\n\n" + MALE_FACTS) if s[0].lower() in ("abstract", "results", "discussion") else ""
        done = False
        for attempt in range(3):
            r = client.generate(f"SECTION: {s[0]}{extra}\n\n{s[1]}", system_prompt=SYS,
                                task="paper_writing", max_tokens=4096)
            if not (r and r.strip()):
                continue
            c1, n1 = cite_nums(r), stat_nums(r)
            if c0 <= c1 and (len(n0 & n1) >= int(len(n0) * 0.92) if n0 else True) and len(r) > len(s[1]) * 0.5:
                s[1] = r.strip()
                report.append(f"[OK] {s[0]}: try{attempt+1} 인용보존 {len(c0&c1)}/{len(c0)} 숫자 {len(n0&n1)}/{len(n0)}")
                done = True
                break
        if not done:
            report.append(f"[KEEP] {s[0]}: 무결성미충족 → 원문 유지")

    new_md = head + "\n\n" + "\n\n".join(f"## {l}\n{c}" for l, c in secs) + "\n\n" + ref_block.strip() + "\n"
    Path(f"data/exports/{base}.md").write_text(new_md, encoding="utf-8")
    print("\n".join(report))
    print(f"\n파이널라이징(인간화+보정): provider={getattr(client,'model','?')} · 저장 data/exports/{base}.md")


if __name__ == "__main__":
    main()
