"""figure_style — 출판급 figure 톤 단일 스타일시트.

문제: default matplotlib = 촌스러운 학술체(박스 축·디폴트 색·Arial·그리드).
해결: DESIGN.md(data_viz/figure 토큰)를 단일소스로 읽어 rcParams를 일괄 세팅.
      despine + 1강조색 + 클린 타이포 + 넉넉한 여백 = Nature/JAMA급 톤.

★ 불변식(DESIGN_GOVERNANCE §8.5): LLM은 명세만, 렌더는 이 엔진. 색·폰트·DPI는 DESIGN.md 단일소스.
사용:
    from src.export.figure_style import apply_publication_style, save_figure, despine, PALETTE
    apply_publication_style()                 # 모든 figure 생성 진입에서 1회
    fig, ax = plt.subplots()
    ...; despine(ax)
    save_figure(fig, "Figure3_forest")        # → SVG + PDF + PNG(300dpi)

배선: publication_figure_generator.py / figure_builder.py / medical_plots.py 의
      import 직후 apply_publication_style() 호출. (DESIGN_GOVERNANCE §8.5-D)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# ── DESIGN.md 단일소스 로드 (실패 시 하드코딩 폴백 = DESIGN.md v2.0.0 값) ──────────
_DEFAULT = {
    "data_viz": {
        "male": "#1f4e79", "female": "#7d2e2e",
        "male_ci": "#1f4e7922", "female_ci": "#7d2e2e22",
        "overall_diamond": "#000000", "ref_line": "#000000",
    },
    "neutral": {"text": "#222222", "text_subtle": "#555555", "border": "#dddddd"},
    "figure": {"title_size": 12.0, "axis_label_size": 11.0, "tick_size": 10.0,
               "value_annotation_size": 10.0, "dpi": 300},
    "accent": "#1f4e79",
}


def _load_design_tokens() -> dict:
    """repo 루트 DESIGN.md frontmatter에서 data_viz/figure 토큰 파싱. 실패 시 폴백."""
    try:
        root = Path(__file__).resolve().parents[2]   # src/export/ → repo root
        md = (root / "DESIGN.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", md, re.DOTALL)
        if not m:
            return _DEFAULT
        import yaml  # type: ignore
        fm = yaml.safe_load(m.group(1)) or {}
        colors = fm.get("colors", {})
        tok = dict(_DEFAULT)
        if colors.get("data_viz"):
            tok["data_viz"] = {**_DEFAULT["data_viz"], **colors["data_viz"]}
        if colors.get("neutral"):
            tok["neutral"] = {**_DEFAULT["neutral"], **colors["neutral"]}
        typ = (fm.get("typography") or {}).get("figure")
        if typ:
            tok["figure"] = {**_DEFAULT["figure"], **typ}
        # 강조색 = data_viz.male (navy)
        tok["accent"] = tok["data_viz"].get("male", _DEFAULT["accent"])
        return tok
    except Exception:
        return _DEFAULT


_TOK = _load_design_tokens()
PALETTE = _TOK["data_viz"]                       # figure 색 (navy/maroon 고정)
_PROP_CYCLE = [PALETTE["male"], PALETTE["female"], "#5a7da3", "#a86a6a",
               _TOK["neutral"]["text_subtle"], "#9b9b9b"]
_TEXT = "#2A2A2A"                                # 순흑 금지(DESIGN-LANGUAGE)


def _korean_font() -> Optional[str]:
    """한글 라벨용 폰트 탐지(있으면). 영문 전용이면 None."""
    try:
        import matplotlib.font_manager as fm
        for name in ("Pretendard", "Apple SD Gothic Neo", "Malgun Gothic",
                     "NanumGothic", "Noto Sans CJK KR"):
            for f in fm.fontManager.ttflist:
                if name.lower() in f.name.lower():
                    return f.name
    except Exception:
        pass
    return None


def apply_publication_style(*, font: str = "sans", korean: bool = False) -> None:
    """모든 figure에 출판급 톤 일괄 적용. figure 생성 진입에서 1회 호출.

    font="sans"(Nature/JAMA 톤, 기본) | "serif"(Times — 일부 저널).
    korean=True 면 한글 폰트 우선(한글 라벨 figure).
    """
    import matplotlib as mpl
    from cycler import cycler

    if font == "serif":
        family = ["Source Serif Pro", "Noto Serif KR", "Times New Roman", "serif"]
    else:
        family = ["Helvetica Neue", "Arial", "Inter", "DejaVu Sans", "sans-serif"]
    kf = _korean_font() if korean else None
    if kf:
        family = [kf] + family

    fg = _TOK["figure"]
    mpl.rcParams.update({
        # 타이포 (DESIGN.md figure 토큰)
        "font.family": family,
        "font.size": fg["tick_size"],
        "axes.titlesize": fg["title_size"], "axes.titleweight": "bold",
        "axes.labelsize": fg["axis_label_size"],
        "xtick.labelsize": fg["tick_size"], "ytick.labelsize": fg["tick_size"],
        "legend.fontsize": fg["tick_size"],
        "axes.unicode_minus": False,
        "mathtext.fontset": "stix",
        # ★ despine — 박스 제거(촌스러움의 90%)
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": True, "axes.spines.bottom": True,
        "axes.edgecolor": _TEXT, "axes.linewidth": 0.8,
        "axes.titlecolor": _TEXT, "axes.labelcolor": _TEXT,
        "text.color": _TEXT, "xtick.color": _TEXT, "ytick.color": _TEXT,
        # 눈금·선
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": 0.8, "ytick.major.width": 0.8,
        "xtick.major.size": 4, "ytick.major.size": 4,
        "lines.linewidth": 1.6, "lines.solid_capstyle": "round",
        "lines.markersize": 6,
        # 그리드: 끄거나 아주 옅은 가로만 (chartjunk 최소)
        "axes.grid": False, "grid.color": _TOK["neutral"]["border"],
        "grid.linewidth": 0.5, "grid.alpha": 0.5,
        # 색 사이클 (navy/maroon 우선 — DESIGN.md data_viz)
        "axes.prop_cycle": cycler(color=_PROP_CYCLE),
        # 여백·해상도·배경
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "figure.dpi": 110,
        "savefig.dpi": int(fg["dpi"]), "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "figure.constrained_layout.use": True,
        # 범례: 박스 제거
        "legend.frameon": False, "legend.handlelength": 1.6,
    })


def despine(ax, *, left: bool = True, bottom: bool = True) -> None:
    """위/오른쪽 축 제거 + 남길 축 정리. 모든 ax에 호출 권장."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.tick_params(top=False, right=False)


def save_figure(fig, stem: str, out_dir: str = "data/exports",
                dpi: Optional[int] = None) -> dict:
    """벡터 우선 저장: SVG(편집용) + PDF(벡터) + PNG(미리보기). 경로 dict 반환.
    ★ 벡터를 주산출물로(DESIGN_GOVERNANCE §8.5-A)."""
    d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)
    dpi = dpi or int(_TOK["figure"]["dpi"])
    paths = {}
    for ext in ("svg", "pdf", "png"):
        p = d / f"{stem}.{ext}"
        fig.savefig(p, format=ext, dpi=dpi, bbox_inches="tight", facecolor="white")
        paths[ext] = str(p)
    return paths


# 모듈 import 시 기본 스타일 자동 적용(영문 sans). 한글/serif 필요 시 재호출.
try:
    apply_publication_style()
except Exception:
    pass
