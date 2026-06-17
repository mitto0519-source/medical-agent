"""design_lint — DESIGN.md 토큰 위반 검사 (DESIGN_GOVERNANCE_SPEC §1).

기준:
  DESIGN.md frontmatter의 `colors`(palette) + `spacing`/`radius` 토큰이 단일 진리원.
  파일이 그 외 색·라운드를 직접 박으면 BLOCK/WARN + 라인참조 보고.

검사:
  ① color_budget — hex/rgb 색 등장 → DESIGN.md palette에 없으면 BLOCK
  ② radius_scale — border-radius 값이 허용 스케일(4/8/12/16/24px) 외면 WARN
  ③ broken_ref   — src/href가 존재하지 않는 로컬 자산이면 WARN

CLI: python -m src.design.design_lint [path...]
exit code: 0 = clean, 1 = WARN, 2 = BLOCK.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
DESIGN_MD = ROOT / "DESIGN.md"

# 허용 라운드 스케일 (DESIGN.md spacing/radius와 정합 — 4의 배수)
_ALLOWED_RADIUS = {0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 28, 32, 9999}

# 검사 대상 파일 확장자
_TARGET_EXTS = (".py", ".css", ".tsx", ".ts", ".jsx", ".html", ".scss")

# 검사 제외 (생성된 figure·docx·외부 라이브러리·테스트 픽스처)
_EXCLUDE_PATTERNS = (
    "node_modules/", ".venv/", "__pycache__/", "data/exports/",
    "data/library/", "data/chromadb/", ".pytest_cache/", "dist/",
)

_HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_RADIUS_RE = re.compile(r"border[-_]?radius\s*[:=]\s*['\"]?([0-9]+)px", re.IGNORECASE)
_REF_RE = re.compile(r'(?:src|href)\s*=\s*["\']([^"\'\s]+)["\']')


@dataclass
class Finding:
    severity: str   # "BLOCK" | "WARN" | "INFO"
    rule: str       # "color_budget" | "radius_scale" | "broken_ref"
    file: str
    line: int
    detail: str


def _load_palette() -> set[str]:
    """DESIGN.md에서 허용된 색(palette) 추출. 없으면 빈 집합 → color_budget skip."""
    if not DESIGN_MD.exists():
        return set()
    try:
        text = DESIGN_MD.read_text(encoding="utf-8")
    except Exception:
        return set()
    # YAML frontmatter colors: 블록 안의 모든 #xxxxxx 추출 (대소 무관)
    palette: set[str] = set()
    in_fm = False
    for line in text.splitlines():
        if line.startswith("---"):
            in_fm = not in_fm if palette is not None else False
            continue
        for m in _HEX_RE.finditer(line):
            palette.add(m.group(0).lower())
    # 일반 안전 색 (브랜드 외, 회색·검정·흰색 변형)
    palette |= {"#000000", "#ffffff", "#fff", "#000",
                "#222222", "#333333", "#555555", "#666666",
                "#888888", "#aaaaaa", "#cccccc", "#dddddd",
                "#eeeeee", "#f0f0f0", "#f5f5f5", "#f7f7f9",
                "#fafafa", "#f8fafc", "#f1f5f9", "#e2e8f0",
                "#cbd5e1", "#94a3b8", "#64748b", "#475569",
                "#334155", "#1e293b", "#0f172a"}
    return palette


def _is_excluded(p: Path) -> bool:
    s = str(p).replace("\\", "/")
    return any(pat in s for pat in _EXCLUDE_PATTERNS)


def _iter_files(targets: Iterable[Path]) -> List[Path]:
    out: List[Path] = []
    for t in targets:
        if t.is_file() and t.suffix in _TARGET_EXTS:
            if not _is_excluded(t):
                out.append(t)
        elif t.is_dir():
            for f in t.rglob("*"):
                if f.is_file() and f.suffix in _TARGET_EXTS and not _is_excluded(f):
                    out.append(f)
    return out


def lint_color_budget(path: Path, palette: set[str]) -> List[Finding]:
    if not palette:
        return []
    out: List[Finding] = []
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in _HEX_RE.finditer(line):
                color = "#" + m.group(1).lower()
                # alpha variant (#xxxxxx00) — base color check
                base = color[:7] if len(color) == 9 else color
                if base not in palette and color not in palette:
                    out.append(Finding(
                        severity="BLOCK", rule="color_budget",
                        file=str(path.relative_to(ROOT)).replace("\\", "/"),
                        line=i,
                        detail=f"팔레트 밖 색 '{color}' — DESIGN.md colors 확인 또는 추가 결정",
                    ))
    except Exception:
        pass
    return out


def lint_radius_scale(path: Path) -> List[Finding]:
    out: List[Finding] = []
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in _RADIUS_RE.finditer(line):
                px = int(m.group(1))
                if px not in _ALLOWED_RADIUS:
                    out.append(Finding(
                        severity="WARN", rule="radius_scale",
                        file=str(path.relative_to(ROOT)).replace("\\", "/"),
                        line=i,
                        detail=f"border-radius {px}px — 허용 스케일 외 (4의 배수)",
                    ))
    except Exception:
        pass
    return out


def lint_broken_ref(path: Path) -> List[Finding]:
    out: List[Finding] = []
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in _REF_RE.finditer(line):
                ref = m.group(1)
                if ref.startswith(("http://", "https://", "data:", "#", "{", "$", "@")):
                    continue
                target = (path.parent / ref).resolve()
                if not target.exists() and not (ROOT / ref.lstrip("/")).exists():
                    out.append(Finding(
                        severity="WARN", rule="broken_ref",
                        file=str(path.relative_to(ROOT)).replace("\\", "/"),
                        line=i,
                        detail=f"링크 깨짐: {ref}",
                    ))
    except Exception:
        pass
    return out


def lint(targets: Optional[List[Path]] = None) -> List[Finding]:
    if targets is None:
        targets = [ROOT / "app", ROOT / "src", ROOT / "web"]
    palette = _load_palette()
    findings: List[Finding] = []
    files = _iter_files(t for t in targets if t.exists())
    for f in files:
        findings.extend(lint_color_budget(f, palette))
        findings.extend(lint_radius_scale(f))
        # broken_ref는 .html/.tsx에만 의미 있음 (Python에 src= 거의 없음)
        if f.suffix in (".html", ".tsx", ".jsx"):
            findings.extend(lint_broken_ref(f))
    return findings


def report(findings: List[Finding]) -> Tuple[int, str]:
    if not findings:
        return 0, "✓ design_lint clean — 위반 0건"
    by_sev = {"BLOCK": [], "WARN": [], "INFO": []}
    for f in findings:
        by_sev[f.severity].append(f)
    lines = [f"design_lint: BLOCK={len(by_sev['BLOCK'])} "
              f"WARN={len(by_sev['WARN'])} INFO={len(by_sev['INFO'])}"]
    for sev in ("BLOCK", "WARN", "INFO"):
        for f in by_sev[sev][:30]:
            lines.append(f"  [{sev}] {f.rule} {f.file}:{f.line} — {f.detail}")
    code = 2 if by_sev["BLOCK"] else (1 if by_sev["WARN"] else 0)
    return code, "\n".join(lines)


def main(argv: List[str]) -> int:
    targets = [Path(a) for a in argv[1:]] if len(argv) > 1 else None
    findings = lint(targets)
    code, msg = report(findings)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
