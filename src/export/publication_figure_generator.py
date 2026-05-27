"""Publication-quality figure & table generator (FigureLabs 수준).

입력: StatBridge().run(df, spec).to_dict()
출력: data/drafts/figures/{safe_title}/ 아래 PNG (300dpi) + SVG
      + 각 그림의 자동 캡션 dict

지원 그림 종류
--------------
1. forest_plot       — 조정 OR/RR + 95%CI (로지스틱/GEE)
2. roc_curve         — 수신자 조작 특성 곡선 (AUC 표시)
3. prevalence_bar    — 그룹별 결과 유병률 막대 그래프
4. subgroup_forest   — 서브그룹별 OR 포레스트 플롯
5. table1_image      — 인구통계 특성 표 (Table 1)
6. table2_image      — 회귀 결과 표 (Table 2)
7. coefficient_plot  — 점+CI 계수 플롯 (forest 대안)
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _setup_korean_font():
    """한글 폰트 등록 (크로스플랫폼). Docker(리눅스)엔 NanumGothic 필요 — 없으면 한글이 □□□로 깨짐."""
    try:
        from pathlib import Path as _Path
        import matplotlib.font_manager as fm
        for p in [
            "C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/gulim.ttc",     # Windows
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",               # Linux (fonts-nanum)
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",        # Linux (noto-cjk)
            "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",                    # macOS
        ]:
            if _Path(p).exists():
                fm.fontManager.addfont(p)
                import matplotlib.pyplot as plt
                prop = fm.FontProperties(fname=p)
                plt.rcParams["font.family"] = prop.get_name()
                plt.rcParams["axes.unicode_minus"] = False
                return
        _log.warning("한글 폰트 미발견 — 그래프 한글이 깨질 수 있음 (Docker: apt fonts-nanum)")
    except Exception:
        pass


_setup_korean_font()


# ── manuscript_template.json 기반 스타일 (단일 진실원본) ──────────────
def _load_fig_tpl() -> dict:
    """data/templates/manuscript_template.json의 figures 섹션. 미존재 시 안전 fallback."""
    try:
        import json
        from pathlib import Path as _P
        p = _P("data/templates/manuscript_template.json")
        if p.exists():
            tpl = json.loads(p.read_text(encoding="utf-8"))
            return tpl.get("figures", {})
    except Exception:
        pass
    return {}


_FIG_TPL = _load_fig_tpl()
_PALETTE = {
    "primary":     _FIG_TPL.get("color_palette", {}).get("primary", "#1f4e79"),
    "significant": _FIG_TPL.get("color_palette", {}).get("secondary", "#7d2e2e"),
    "secondary":   _FIG_TPL.get("color_palette", {}).get("accent", "#2e7d32"),
    "neutral":     _FIG_TPL.get("color_palette", {}).get("neutral_light", "#999999"),
    "ci_line":     _FIG_TPL.get("color_palette", {}).get("neutral_dark", "#333333"),
    "null_line":   "#7d2e2e",   # OR=1 기준선
    "bg":          _FIG_TPL.get("color_palette", {}).get("background", "#FFFFFF"),
    "grid":        "#E0E0E0",
}

_FONT_SIZES = {
    "title":  _FIG_TPL.get("title_size_pt", 12),
    "label":  _FIG_TPL.get("axis_label_size_pt", 11),
    "tick":   _FIG_TPL.get("tick_label_size_pt", 9),
    "caption": _FIG_TPL.get("caption_size_pt", 10),
    "table_header": 10,
}

# matplotlib 전역 폰트 = Times New Roman (한글 미포함 텍스트만 — 한글 그래프는 _setup_korean_font 이후)
try:
    import matplotlib.pyplot as _plt
    _plt.rcParams["font.family"] = ["Times New Roman", _plt.rcParams.get("font.family", ["DejaVu Sans"])[0]]
    _plt.rcParams["axes.unicode_minus"] = False
    _plt.rcParams["mathtext.fontset"] = "stix"
except Exception:
    pass


def _apply_publication_style(ax, grid: bool = False):
    """학술지 공통 양식 — 위/오른쪽 spine 제거, 가는 axis line, 옅은 grid (optional)."""
    ax.spines["top"].set_visible(_FIG_TPL.get("spine_top_visible", False))
    ax.spines["right"].set_visible(_FIG_TPL.get("spine_right_visible", False))
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.spines["left"].set_color("#222222")
    ax.spines["bottom"].set_color("#222222")
    ax.tick_params(labelsize=_FONT_SIZES["tick"], length=4, width=0.6, color="#222222")
    show_grid = grid if grid is not None else _FIG_TPL.get("grid_visible", False)
    if show_grid:
        ax.yaxis.grid(True, linestyle="--", linewidth=0.5, color=_PALETTE["grid"], alpha=0.8)
        ax.set_axisbelow(True)


def _save(fig, out_dir: Path, stem: str, dpi: int = 300) -> Tuple[bytes, str, str]:
    """PNG + SVG 저장, PNG bytes 반환."""
    import matplotlib.pyplot as plt
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = str(out_dir / f"{stem}.png")
    svg_path = str(out_dir / f"{stem}.svg")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor=_PALETTE["bg"])
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=_PALETTE["bg"])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=_PALETTE["bg"])
    buf.seek(0)
    plt.close(fig)
    return buf.read(), png_path, svg_path


# ─────────────────────────────────────────────────────────────────────
# 1. Forest Plot (출판용 강화버전)
# ─────────────────────────────────────────────────────────────────────

def make_forest_plot(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 300,
) -> Optional[Tuple[bytes, str, str, str]]:
    """Returns (png_bytes, png_path, svg_path, caption) or None."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vars_list = stat_result.get("model_vars", [])
    if not vars_list:
        return None

    studies = [
        {
            "label": v.get("label") or v.get("variable", ""),
            "or": float(v.get("or_value") or 1.0),
            "ci_low": float(v.get("ci_lower") or 0),
            "ci_high": float(v.get("ci_upper") or 0),
            "p": float(v.get("p_value") or 1.0),
            "sig": bool(v.get("significant", False)),
        }
        for v in vars_list
        if v.get("ci_lower") and v.get("ci_upper") and v.get("label")
    ]
    if not studies:
        return None

    n = len(studies)
    fig, ax = plt.subplots(figsize=(9, max(4, n * 0.65 + 2)))
    y_pos = list(range(n, 0, -1))

    for i, s in enumerate(studies):
        y = y_pos[i]
        color = _PALETTE["significant"] if s["sig"] else _PALETTE["primary"]
        ax.plot([s["ci_low"], s["ci_high"]], [y, y],
                color=_PALETTE["ci_line"], linewidth=1.5, solid_capstyle="round")
        marker_size = 10 if s["sig"] else 8
        ax.plot(s["or"], y, "D" if s["sig"] else "s", color=color,
                markersize=marker_size, markeredgecolor="white", markeredgewidth=0.8,
                zorder=5)
        # OR 값 레이블
        ax.text(s["ci_high"] + 0.05, y,
                f'{s["or"]:.2f} ({s["ci_low"]:.2f}–{s["ci_high"]:.2f})',
                va="center", fontsize=7.5, color=color if s["sig"] else "#555555")

    ax.axvline(1.0, color=_PALETTE["null_line"], linestyle="--", linewidth=1.2, alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([s["label"] for s in studies], fontsize=_FONT_SIZES["tick"])
    ax.set_xlabel("Adjusted Odds Ratio (95% CI)", fontsize=_FONT_SIZES["label"])
    outcome_label = stat_result.get("outcome_label", "Outcome")
    ax.set_title(f"Figure. Adjusted OR for {outcome_label}",
                 fontsize=_FONT_SIZES["title"], fontweight="bold", pad=12)
    _apply_publication_style(ax)

    # 주석
    n_total = stat_result.get("n_total", "")
    ax.text(0.02, -0.08,
            f"n={n_total:,} | Adjusted logistic regression | ◆ p<0.05",
            transform=ax.transAxes, fontsize=7, color="#666666")

    plt.tight_layout()

    n_sig = sum(1 for s in studies if s["sig"])
    caption = (
        f"Forest plot showing adjusted odds ratios (OR) and 95% confidence intervals "
        f"for {outcome_label}. Diamonds (◆) indicate statistically significant associations "
        f"(p<0.05). {n_sig} of {n} predictors were significant. Total n={n_total:,}."
    )
    return _save(fig, out_dir, "forest_plot", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 2. ROC Curve
# ─────────────────────────────────────────────────────────────────────

def make_roc_curve(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 300,
) -> Optional[Tuple[bytes, str, str, str]]:
    """Returns (png_bytes, png_path, svg_path, caption) or None."""
    roc = stat_result.get("model_metrics", {}).get("roc")
    if not roc:
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fpr = roc["fpr"]
    tpr = roc["tpr"]
    auc = roc["auc"]
    outcome_label = stat_result.get("outcome_label", "Outcome")

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr, color=_PALETTE["primary"], linewidth=2.2,
            label=f"ROC (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], color=_PALETTE["neutral"], linestyle="--",
            linewidth=1, label="Random (AUC = 0.500)")
    ax.fill_between(fpr, tpr, alpha=0.08, color=_PALETTE["primary"])
    ax.set_xlabel("1 − Specificity (False Positive Rate)", fontsize=_FONT_SIZES["label"])
    ax.set_ylabel("Sensitivity (True Positive Rate)", fontsize=_FONT_SIZES["label"])
    ax.set_title(f"Figure. ROC Curve — {outcome_label}",
                 fontsize=_FONT_SIZES["title"], fontweight="bold")
    ax.legend(fontsize=_FONT_SIZES["tick"], loc="lower right")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    _apply_publication_style(ax, grid=True)
    plt.tight_layout()

    caption = (
        f"Receiver operating characteristic (ROC) curve for the logistic regression "
        f"model predicting {outcome_label}. "
        f"Area under the curve (AUC) = {auc:.3f}. "
        f"Total n = {stat_result.get('n_total', ''):,}."
    )
    return _save(fig, out_dir, "roc_curve", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 3. Prevalence Bar Chart
# ─────────────────────────────────────────────────────────────────────

def make_prevalence_bar(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 300,
) -> Optional[Tuple[bytes, str, str, str]]:
    """그룹별 유병률 막대 그래프."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    desc = stat_result.get("descriptive_stats", {})
    outcome_label = stat_result.get("outcome_label", "Outcome")
    outcome_rate = stat_result.get("outcome_rate", 0)

    # descriptive_stats에서 성별/학년별 유병률 추출 시도
    group_data: Dict[str, float] = {}
    for key, val in desc.items():
        if isinstance(val, dict) and "mean_by_group" in val:
            # format: {"sex": {"mean_by_group": {1: 0.2, 2: 0.3}}}
            for gval, gmean in val["mean_by_group"].items():
                group_data[f"{key}={gval}"] = float(gmean) * 100

    # 기본 전체 + 성별
    if not group_data:
        group_data = {"전체": outcome_rate}
        # model_vars에서 성별 OR 추출 시도
        for v in stat_result.get("model_vars", []):
            lbl = v.get("label", "")
            if "남" in lbl or "여" in lbl or "sex" in lbl.lower():
                pass  # can't compute prevalence from OR alone

    if len(group_data) < 2:
        # 단순 전체 유병률 그래프
        group_data = {"전체": outcome_rate}

    fig, ax = plt.subplots(figsize=(max(5, len(group_data) * 1.2 + 2), 5))
    x = np.arange(len(group_data))
    labels = list(group_data.keys())
    values = list(group_data.values())
    colors = [_PALETTE["significant"] if v == max(values) else _PALETTE["primary"] for v in values]

    bars = ax.bar(x, values, color=colors, width=0.6, edgecolor="white", linewidth=0.8)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val:.1f}%", ha="center", va="bottom",
                fontsize=_FONT_SIZES["tick"], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=_FONT_SIZES["tick"])
    ax.set_ylabel(f"{outcome_label} 유병률 (%)", fontsize=_FONT_SIZES["label"])
    ax.set_title(f"Figure. Prevalence of {outcome_label} by Group",
                 fontsize=_FONT_SIZES["title"], fontweight="bold")
    ax.set_ylim(0, max(values) * 1.25)
    _apply_publication_style(ax, grid=True)
    plt.tight_layout()

    caption = (
        f"Prevalence of {outcome_label} across groups. "
        f"Overall prevalence: {outcome_rate:.1f}% (n={stat_result.get('n_total', ''):,})."
    )
    return _save(fig, out_dir, "prevalence_bar", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 4. Subgroup Forest Plot
# ─────────────────────────────────────────────────────────────────────

def make_subgroup_forest(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 300,
) -> Optional[Tuple[bytes, str, str, str]]:
    """서브그룹별 OR 포레스트 플롯 (subgroup_results 사용)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    subgroup_results = stat_result.get("subgroup_results", {})
    if not subgroup_results:
        return None

    # 첫 번째 서브그룹 변수, 첫 번째 예측변수 사용
    sg_var = next(iter(subgroup_results))
    sg_data = subgroup_results[sg_var]
    if not sg_data:
        return None

    # 각 서브그룹에서 첫 번째 유의한 변수 추출
    studies = []
    outcome_label = stat_result.get("outcome_label", "Outcome")

    for sg_val, var_list in sg_data.items():
        if not var_list:
            continue
        # VariableResult objects or dicts
        for v in (var_list if isinstance(var_list[0], dict) else [vr.to_dict() for vr in var_list]):
            if v.get("variable") == stat_result.get("model_vars", [{}])[0].get("variable", ""):
                studies.append({
                    "label": f"{sg_var}={sg_val}",
                    "or": float(v.get("or_value") or 1.0),
                    "ci_low": float(v.get("ci_lower") or 0),
                    "ci_high": float(v.get("ci_upper") or 0),
                    "sig": bool(v.get("significant", False)),
                })
                break

    if not studies:
        return None

    n = len(studies)
    fig, ax = plt.subplots(figsize=(9, max(4, n * 0.7 + 2)))
    y_pos = list(range(n, 0, -1))

    for i, s in enumerate(studies):
        y = y_pos[i]
        color = _PALETTE["significant"] if s["sig"] else _PALETTE["primary"]
        ax.plot([s["ci_low"], s["ci_high"]], [y, y], color=_PALETTE["ci_line"], linewidth=1.5)
        ax.plot(s["or"], y, "D", color=color, markersize=9,
                markeredgecolor="white", markeredgewidth=0.8, zorder=5)
        ax.text(s["ci_high"] + 0.05, y,
                f'{s["or"]:.2f} ({s["ci_low"]:.2f}–{s["ci_high"]:.2f})',
                va="center", fontsize=7.5)

    ax.axvline(1.0, color=_PALETTE["null_line"], linestyle="--", linewidth=1.2)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([s["label"] for s in studies], fontsize=_FONT_SIZES["tick"])
    ax.set_xlabel("Adjusted Odds Ratio (95% CI)", fontsize=_FONT_SIZES["label"])
    ax.set_title(f"Figure. Subgroup Analysis — {outcome_label} by {sg_var}",
                 fontsize=_FONT_SIZES["title"], fontweight="bold")
    _apply_publication_style(ax)
    plt.tight_layout()

    caption = (
        f"Subgroup analysis of the association between the primary predictor and "
        f"{outcome_label}, stratified by {sg_var}. "
        f"Diamonds indicate point estimates; horizontal lines represent 95% CI."
    )
    return _save(fig, out_dir, "subgroup_forest", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 5. Table 1 Image (Demographic Characteristics)
# ─────────────────────────────────────────────────────────────────────

def make_table1_image(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 150,
) -> Optional[Tuple[bytes, str, str, str]]:
    """인구통계 특성 표 이미지 생성."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    desc = stat_result.get("descriptive_stats", {})
    if not desc:
        return None

    rows = []
    for var, stats in desc.items():
        if not isinstance(stats, dict):
            continue
        mean = stats.get("mean")
        std = stats.get("std")
        mn = stats.get("min")
        mx = stats.get("max")
        n = stats.get("count")
        if mean is not None:
            rows.append([
                var,
                f"{mean:.2f} ± {std:.2f}" if std is not None else f"{mean:.2f}",
                f"[{mn:.1f}, {mx:.1f}]" if mn is not None else "",
                str(int(n)) if n is not None else "",
            ])

    if not rows:
        return None

    col_labels = ["Variable", "Mean ± SD", "Range", "n"]
    n_rows = len(rows)

    fig, ax = plt.subplots(figsize=(9, max(2, n_rows * 0.4 + 1.5)))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        colWidths=[0.35, 0.28, 0.22, 0.15],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    # 헤더 스타일
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#CCCCCC")
        if r == 0:
            cell.set_facecolor(_PALETTE["primary"])
            cell.set_text_props(color="white", fontweight="bold",
                                fontsize=_FONT_SIZES["table_header"])
        elif r % 2 == 0:
            cell.set_facecolor("#F7F9FC")
        else:
            cell.set_facecolor("white")

    n_total = stat_result.get("n_total", "")
    ax.set_title(
        f"Table 1. Descriptive Statistics (n={n_total:,})",
        fontsize=_FONT_SIZES["title"], fontweight="bold", pad=10,
    )
    plt.tight_layout()

    caption = (
        f"Table 1. Descriptive statistics of study variables. "
        f"Total sample: n={n_total:,}. Values shown as mean ± standard deviation."
    )
    return _save(fig, out_dir, "table1", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 6. Table 2 Image (Regression Results)
# ─────────────────────────────────────────────────────────────────────

def make_table2_image(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 150,
) -> Optional[Tuple[bytes, str, str, str]]:
    """회귀 결과 표 이미지 생성."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vars_list = stat_result.get("model_vars", [])
    if not vars_list:
        return None

    rows = []
    for v in vars_list:
        label = v.get("label") or v.get("variable", "")
        or_val = v.get("or_value")
        ci_low = v.get("ci_lower")
        ci_high = v.get("ci_upper")
        p_val = v.get("p_value")
        sig = "✓" if v.get("significant") else ""

        or_str = f"{or_val:.2f}" if or_val is not None else "—"
        ci_str = f"{ci_low:.2f}–{ci_high:.2f}" if ci_low and ci_high else "—"
        p_str = (
            "<0.001" if p_val is not None and p_val < 0.001
            else f"{p_val:.3f}" if p_val is not None
            else "—"
        )
        rows.append([label, or_str, ci_str, p_str, sig])

    col_labels = ["Variable", "OR", "95% CI", "p-value", "Sig.*"]
    n_rows = len(rows)
    outcome_label = stat_result.get("outcome_label", "Outcome")

    fig, ax = plt.subplots(figsize=(10, max(2.5, n_rows * 0.42 + 2)))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        colWidths=[0.38, 0.12, 0.22, 0.15, 0.13],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#CCCCCC")
        if r == 0:
            cell.set_facecolor(_PALETTE["primary"])
            cell.set_text_props(color="white", fontweight="bold",
                                fontsize=_FONT_SIZES["table_header"])
        elif r % 2 == 0:
            cell.set_facecolor("#F7F9FC")
        else:
            cell.set_facecolor("white")
        # 유의한 행 하이라이트
        if r > 0 and rows[r - 1][-1] == "✓":
            for cc in range(len(col_labels)):
                table[r, cc].set_text_props(fontweight="bold")

    n_total = stat_result.get("n_total", "")
    ax.set_title(
        f"Table 2. Adjusted Odds Ratios for {outcome_label} (n={n_total:,})",
        fontsize=_FONT_SIZES["title"], fontweight="bold", pad=10,
    )
    ax.text(
        0.0, -0.03,
        "* Sig.: p<0.05. OR = Odds Ratio; CI = Confidence Interval.",
        transform=ax.transAxes, fontsize=7, color="#555555",
    )
    plt.tight_layout()

    caption = (
        f"Table 2. Adjusted odds ratios (OR) and 95% confidence intervals (CI) "
        f"for {outcome_label} from multivariable logistic regression. "
        f"Significant associations (p<0.05) are indicated with ✓."
    )
    return _save(fig, out_dir, "table2", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 7. Coefficient Plot (forest plot alternative)
# ─────────────────────────────────────────────────────────────────────

def make_coefficient_plot(
    stat_result: dict,
    out_dir: Path,
    dpi: int = 300,
) -> Optional[Tuple[bytes, str, str, str]]:
    """점+CI 계수 플롯 — forest plot의 수평 대안 (변수 수 ≤ 8일 때 권장)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    vars_list = stat_result.get("model_vars", [])
    if not vars_list or len(vars_list) > 15:
        return None

    labels = [v.get("label") or v.get("variable", "") for v in vars_list]
    ors = [float(v.get("or_value") or 1.0) for v in vars_list]
    ci_lows = [float(v.get("ci_lower") or 1.0) for v in vars_list]
    ci_highs = [float(v.get("ci_upper") or 1.0) for v in vars_list]
    sigs = [bool(v.get("significant", False)) for v in vars_list]
    yerr_low = [o - l for o, l in zip(ors, ci_lows)]
    yerr_high = [h - o for o, h in zip(ors, ci_highs)]
    colors = [_PALETTE["significant"] if s else _PALETTE["primary"] for s in sigs]

    x = np.arange(len(labels))
    outcome_label = stat_result.get("outcome_label", "Outcome")

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2 + 2), 5))
    ax.errorbar(x, ors, yerr=[yerr_low, yerr_high], fmt="none",
                color=_PALETTE["ci_line"], capsize=4, linewidth=1.5)
    ax.scatter(x, ors, color=colors, s=80, zorder=5,
               edgecolors="white", linewidths=0.8)
    ax.axhline(1.0, color=_PALETTE["null_line"], linestyle="--", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=_FONT_SIZES["tick"])
    ax.set_ylabel("Adjusted Odds Ratio (95% CI)", fontsize=_FONT_SIZES["label"])
    ax.set_title(f"Figure. Coefficient Plot — {outcome_label}",
                 fontsize=_FONT_SIZES["title"], fontweight="bold")
    _apply_publication_style(ax, grid=True)
    plt.tight_layout()

    caption = (
        f"Coefficient plot showing adjusted odds ratios (OR) and 95% confidence intervals "
        f"for {outcome_label}. Red dots indicate significant associations (p<0.05)."
    )
    return _save(fig, out_dir, "coefficient_plot", dpi) + (caption,)


# ─────────────────────────────────────────────────────────────────────
# 메인 진입점
# ─────────────────────────────────────────────────────────────────────

class PublicationFigureGenerator:
    """논문 완성 후 stat_result 딕셔너리에서 모든 그림/표를 자동 생성."""

    def __init__(self, out_base: str = "data/drafts/figures", dpi: int = 300):
        self._out_base = Path(out_base)
        self._dpi = dpi

    def generate_all(
        self,
        stat_result: dict,
        safe_title: str = "paper",
    ) -> Dict[str, Dict]:
        """모든 적합한 그림/표 생성.

        Returns
        -------
        {
          "forest_plot": {"png_bytes": ..., "png_path": ..., "svg_path": ..., "caption": ...},
          "roc_curve": {...},
          ...
        }
        """
        out_dir = self._out_base / safe_title
        out_dir.mkdir(parents=True, exist_ok=True)

        results: Dict[str, Dict] = {}
        generators = [
            ("forest_plot", make_forest_plot),
            ("roc_curve", make_roc_curve),
            ("prevalence_bar", make_prevalence_bar),
            ("subgroup_forest", make_subgroup_forest),
            ("table1_image", make_table1_image),
            ("table2_image", make_table2_image),
            ("coefficient_plot", make_coefficient_plot),
        ]

        for name, fn in generators:
            try:
                res = fn(stat_result, out_dir, self._dpi)
                if res:
                    png_bytes, png_path, svg_path, caption = res
                    results[name] = {
                        "png_bytes": png_bytes,
                        "png_path": png_path,
                        "svg_path": svg_path,
                        "caption": caption,
                    }
                    _log.info("그림 생성 완료: %s → %s", name, png_path)
            except Exception as e:
                _log.warning("그림 생성 실패 [%s]: %s", name, e)

        _log.info("PublicationFigureGenerator: %d개 그림/표 생성 완료", len(results))
        return results

    def generate_captions_md(self, figures: Dict[str, Dict]) -> str:
        """그림 캡션 마크다운 생성 (논문 첨부용)."""
        lines = ["## Figure & Table Captions\n"]
        name_map = {
            "forest_plot": "Figure 1",
            "roc_curve": "Figure 2",
            "prevalence_bar": "Figure 3",
            "subgroup_forest": "Figure 4",
            "coefficient_plot": "Figure 5",
            "table1_image": "Table 1",
            "table2_image": "Table 2",
        }
        for key, meta in figures.items():
            label = name_map.get(key, key)
            lines.append(f"**{label}.** {meta.get('caption', '')}\n")
        return "\n".join(lines)


def generate_figures_for_paper(
    stat_result: dict,
    safe_title: str = "paper",
    out_base: str = "data/drafts/figures",
    dpi: int = 300,
) -> Dict[str, Dict]:
    """편의 함수 — 논문 파이프라인에서 직접 호출."""
    return PublicationFigureGenerator(out_base=out_base, dpi=dpi).generate_all(
        stat_result, safe_title
    )
