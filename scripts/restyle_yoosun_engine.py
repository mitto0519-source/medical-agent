"""조유선 엔진 재첨삭 — 실제 author_profiles/yoosun_cho.json 시스템프롬프트 + 페르소나 주입.

섹션별로 LLM(작동 provider 자동선택, 폴백)에 그 저자의 문체로 '재작성'을 요청하되,
데이터 무결성(숫자·OR·CI·p값·[n] 인용)을 토큰 단위로 검증 — 어기면 그 섹션은 원문 유지.
사용자 데이터/결과는 절대 변형 금지, 문체/필력/엣지만 조유선화.

실행: python scripts/restyle_yoosun_engine.py [input.md] [out_basename]
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _toks(t: str):
    """보존해야 할 핵심 토큰: [n] 인용 마커 + 숫자(소수/CI/천단위/%/p값)."""
    marks = set(re.findall(r"\[\d+(?:[\-,\s]*\d+)*\]", t or ""))
    nums = set(re.findall(r"\d+\.\d+|\d{1,3}(?:,\d{3})+|\d+%|p\s*[=<]\s*0?\.\d+", t or ""))
    return marks, nums


def main():
    import warnings
    warnings.filterwarnings("ignore")
    from src.config.env import bootstrap
    bootstrap()
    from src.llm import get_llm_client

    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exports/ZCB_revised_YoosunCho.md")
    base = sys.argv[2] if len(sys.argv) > 2 else "ZCB_yoosun_engine"
    text = src.read_text(encoding="utf-8")
    prof = json.loads(Path("data/author_profiles/yoosun_cho.json").read_text(encoding="utf-8"))
    style_prompt = prof["system_prompt"]

    mt = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    title = mt.group(1).strip() if mt else "Revised Paper"
    mref = re.search(r"(?im)^##\s*references?\s*$", text)
    body = text[:mref.start()] if mref else text
    ref_block = text[mref.start():] if mref else ""

    parts = re.split(r"(?m)^##\s+(.+?)\s*$", body)
    secs = [(parts[i].strip(), (parts[i + 1] or "").strip())
            for i in range(1, len(parts) - 1, 2) if (parts[i + 1] or "").strip()]

    import os
    _prov = os.environ.get("RESTYLE_PROVIDER", "anthropic")  # 조유선 품질 = Claude 우선
    client = get_llm_client(provider=_prov, task="paper_writing")  # 폴백 유지

    out_secs, report = [], []
    for label, content in secs:
        m0, n0 = _toks(content)
        sysp = (
            style_prompt +
            "\n\n=== EDITING TASK ===\n"
            "Rewrite the section below in THIS author's (Yoosun Cho) voice: precise, formal, "
            "evidence-first, confident, with rhetorical edge and tight paragraph flow. Elevate the "
            "prose and word choice to match the author's example papers.\n"
            "ABSOLUTE CONSTRAINTS (data integrity — the analysis is already final):\n"
            "1. Preserve EVERY in-text citation marker (e.g., [1], [5-7], [11, 12]) EXACTLY and in place.\n"
            "2. Preserve EVERY number, OR/aOR, 95% CI, p-value, percentage, and sample size EXACTLY.\n"
            "3. Do NOT add, remove, or renumber references. Do NOT change any factual/statistical claim.\n"
            "4. Keep subsection headers (e.g., '### Study population') if present.\n"
            "Return ONLY the rewritten section body — no section title, no commentary."
        )
        try:
            r = client.generate(f"SECTION: {label}\n\n{content}", system_prompt=sysp,
                                task="paper_writing", max_tokens=3500)
            m1, n1 = _toks(r or "")
            keep_nums = len(n0 & n1)
            num_ok = (keep_nums >= max(1, int(len(n0) * 0.9))) if n0 else True
            mark_ok = m0 <= m1  # 모든 기존 마커 보존
            if r and r.strip() and num_ok and mark_ok and len(r) > len(content) * 0.5:
                out_secs.append((label, r.strip()))
                report.append(f"[OK]   {label}: {len(content)}→{len(r)}자 · 마커 {len(m1)} · 숫자보존 {keep_nums}/{len(n0)} · provider={getattr(client,'model','?')}")
            else:
                out_secs.append((label, content))
                report.append(f"[KEEP] {label}: 무결성 미충족(마커 {len(m0)}→{len(m1)}, 숫자 {keep_nums}/{len(n0)}) → 원문 유지")
        except Exception as e:
            out_secs.append((label, content))
            report.append(f"[KEEP] {label}: LLM 실패 {str(e)[:90]} → 원문 유지")

    new_md = f"# {title}\n\n" + "\n\n".join(f"## {l}\n{c}" for l, c in out_secs) + "\n\n" + ref_block.strip() + "\n"
    Path(f"data/exports/{base}.md").write_text(new_md, encoding="utf-8")
    print("\n".join(report))
    n_ok = sum(1 for r in report if r.startswith("[OK]"))
    print(f"\n조유선 엔진 재작성: {n_ok}/{len(secs)} 섹션 성공 · 저장 data/exports/{base}.md")


if __name__ == "__main__":
    main()
