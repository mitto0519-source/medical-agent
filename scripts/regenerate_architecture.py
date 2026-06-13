"""ARCHITECTURE.md를 실 파일 시스템에서 자동 재생성.

수동 작성으로 인한 정합성 결함 차단:
  - 파일명 오기 (graph.json → medical_graph.json 양식)
  - 인벤토리 누락 (data/runtime/ 15개 중 5개만 적힘)
  - 환각 (safety/text_sanitize.py 없는데 있다고 적힘)

매주 cron + pre-commit hook으로 실행 권장.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "ARCHITECTURE.md"

IGNORE_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache",
                ".dockerignore", ".hf_cache", "_archive"}


def _count_py(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0
    return sum(1 for f in dir_path.glob("*.py") if not f.name.startswith("_"))


def _list_data_dir(d: Path) -> tuple[int, str]:
    """폴더의 파일 수 + 대표 확장자 분포 요약."""
    if not d.exists():
        return 0, "(missing)"
    files = list(d.rglob("*"))
    files = [f for f in files if f.is_file()]
    n = len(files)
    exts = {}
    for f in files:
        ext = f.suffix.lower() or "(no-ext)"
        exts[ext] = exts.get(ext, 0) + 1
    top = ", ".join(f"{e}:{c}" for e, c in sorted(exts.items(), key=lambda x: -x[1])[:4])
    return n, top


def build_section_modules() -> str:
    lines = ["## src/ — Python modules (auto-enumerated)\n",
              "| Module | py files | content |", "|---|---|---|"]
    for d in sorted((ROOT / "src").iterdir()):
        if not d.is_dir() or d.name in IGNORE_DIRS:
            continue
        n = _count_py(d)
        pys = [p.stem for p in sorted(d.glob("*.py")) if not p.stem.startswith("_")]
        sample = ", ".join(pys[:5]) + (" …" if len(pys) > 5 else "")
        lines.append(f"| `{d.name}/` | {n} | {sample} |")
    return "\n".join(lines)


def build_section_data() -> str:
    lines = ["## data/ — Storage layout (auto-enumerated)\n",
              "| Folder | file count | extensions (top 4) |", "|---|---|---|"]
    for d in sorted((ROOT / "data").iterdir()):
        if not d.is_dir() or d.name in IGNORE_DIRS:
            continue
        n, exts = _list_data_dir(d)
        lines.append(f"| `data/{d.name}/` | {n} | {exts} |")
    return "\n".join(lines)


def build_section_runtime_details() -> str:
    """data/runtime/ 정확 인벤토리 — 이전에 5/15 만 적었던 결함 차단."""
    rt = ROOT / "data" / "runtime"
    if not rt.exists():
        return "## data/runtime/\n\n(missing)\n"
    lines = ["## data/runtime/ — Single-core memory backend (full inventory)\n",
              "| File | Bytes | Purpose hint |", "|---|---|---|"]
    purpose = {
        "events.db": "Append-only audit log (CLAUDE.md 규칙 12)",
        "memory.db": "Typed memory (scorer/lifecycle/gate)",
        "conversation_memory": "ChromaDB cross-session 대화",
        "procedural.db": "Procedural memory (5층 중 4번째)",
        "lifecycle.db": "Memory TTL + decay scheduler",
        "longitudinal.db": "Time-series trends",
        "idempotency.db": "Tool call cache (재현성)",
        "physician_review.db": "Review queue + decisions",
        "tasks.db": "TaskRun state machine",
        "user_edits.sqlite": "User correction few-shot store",
        "heartbeat_state.json": "Heartbeat 7 jobs catch-up state",
        "alerts.log": "Runtime alerts",
        "notifications.json": "Pending user notifications",
    }
    for f in sorted(rt.iterdir()):
        if not f.is_file():
            continue
        sz = f.stat().st_size
        key = next((k for k in purpose if k in f.name), "")
        lines.append(f"| `{f.name}` | {sz:,} | {purpose.get(key, '—')} |")
    return "\n".join(lines)


def build_section_knowledge_graph() -> str:
    kg = ROOT / "data" / "knowledge_graph"
    if not kg.exists():
        return "## data/knowledge_graph/\n\n(missing)\n"
    lines = ["## data/knowledge_graph/ — Graphs (actual filenames)\n",
              "| File | Bytes | Type |", "|---|---|---|"]
    type_hint = {
        "graph.json": "Main medical knowledge graph (NetworkX)",
        "citation_graph.json": "Citation network (paper ↔ paper)",
        "code_graph.json": "Code asset graph (e2e_diagnose 자가진단)",
        "trend_state.json": "PubMed 24h trend cache",
        "meta.json": "Graph metadata + last_updated",
    }
    for f in sorted(kg.iterdir()):
        if not f.is_file():
            continue
        sz = f.stat().st_size
        lines.append(f"| `{f.name}` | {sz:,} | {type_hint.get(f.name, '—')} |")
    return "\n".join(lines)


def build_section_oa_papers() -> str:
    oa = ROOT / "data" / "oa_papers"
    if not oa.exists():
        return "## data/oa_papers/\n\n(missing)\n"
    counts = {"metadata": 0, "txt": 0, "json": 0, "other": 0}
    for f in oa.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".metadata":
            counts["metadata"] += 1
        elif ext == ".txt":
            counts["txt"] += 1
        elif ext == ".json":
            counts["json"] += 1
        else:
            counts["other"] += 1
    metadata = counts["metadata"]
    full_text = counts["txt"]
    full_text_rate = (full_text / metadata * 100) if metadata else 0
    return (
        "## data/oa_papers/ — OA paper collection (정직 통계)\n\n"
        f"- Total metadata sweep: **{metadata:,}** papers\n"
        f"- Full text collected (.txt): **{full_text:,}** ({full_text_rate:.1f}%)\n"
        f"- Metadata-only (no body): **{metadata - full_text:,}** ← backfill 대상\n"
        f"- Sidecar JSON: {counts['json']:,}\n"
        f"- Other (sqlite/.gitignore): {counts['other']}\n"
    )


def build_section_prompts() -> str:
    p = ROOT / "prompts"
    if not p.exists():
        return "## prompts/\n\n(missing)\n"
    lines = ["## prompts/ — Versioned system prompts (each auto-injected via prompt_loader)\n",
              "| File | Bytes | Role |", "|---|---|---|"]
    role = {
        "medical_core.md": "Core medical persona",
        "safety_constraints.md": "Hard safety bounds",
        "yoosun_style.md": "조유선 writing style",
        "style_polish.md": "Polish patterns (NEJM/Lancet)",
        "curated_seed.md": "Curated 2,100 paper seed exemplars",
    }
    for f in sorted(p.glob("*.md")):
        lines.append(f"| `{f.name}` | {f.stat().st_size:,} | {role.get(f.name, '—')} |")
    return "\n".join(lines)


def build_section_text_sanitize() -> str:
    """text_sanitize 중복 환각 차단 — 실 경로만 적시."""
    found = []
    for r, _, fs in os.walk(ROOT / "src"):
        for n in fs:
            if "text_sanitize" in n and n.endswith(".py"):
                found.append(os.path.relpath(os.path.join(r, n), ROOT))
    return (
        "## text_sanitize canonical path (정정)\n\n"
        f"실 위치 ({len(found)} file): " + (", ".join(f"`{p}`" for p in found) or "(none)") +
        "\n\n이전 문서가 `src/safety/text_sanitize.py` 도 있다고 표기한 건 환각. "
        "canonical 위치는 위 한 곳뿐.\n"
    )


def main():
    sections = OrderedDict()
    sections["modules"] = build_section_modules()
    sections["data"] = build_section_data()
    sections["runtime"] = build_section_runtime_details()
    sections["knowledge_graph"] = build_section_knowledge_graph()
    sections["oa_papers"] = build_section_oa_papers()
    sections["prompts"] = build_section_prompts()
    sections["text_sanitize"] = build_section_text_sanitize()

    header = (
        "# ARCHITECTURE.md — Auto-generated\n\n"
        f"> Last regenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> Source: `scripts/regenerate_architecture.py`\n"
        f"> 수동 편집 금지 — 인벤토리·파일명·count는 실 파일 시스템에서 매번 다시 채움.\n"
        f"> 디자인·아키텍처 결정 같은 prose는 별도 ARCHITECTURE_SHORT.md 에 작성.\n\n"
    )

    body = "\n\n".join(sections.values())
    TARGET.write_text(header + body + "\n", encoding="utf-8")
    print(f"wrote {TARGET}  ({TARGET.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
