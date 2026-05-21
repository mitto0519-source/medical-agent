"""Figure builder — matplotlib/seaborn 그림을 Word 임베드용 바이트스트림으로 변환."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _setup_korean_font():
    """Windows Malgun Gothic 한글 폰트 등록."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        _candidates = [
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/gulim.ttc",
        ]
        for path in _candidates:
            if Path(path).exists():
                fm.fontManager.addfont(path)
                prop = fm.FontProperties(fname=path)
                plt.rcParams["font.family"] = prop.get_name()
                plt.rcParams["axes.unicode_minus"] = False
                return
    except Exception:
        pass


_setup_korean_font()


def _fig_to_bytes(fig, dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def bar_chart(
    data: Dict[str, float],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    color: str = "#2563EB",
    dpi: int = 300,
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(list(data.keys()), list(data.values()), color=color, edgecolor="white")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    result = _fig_to_bytes(fig, dpi)
    plt.close(fig)
    return result


def forest_plot(
    studies: List[Dict],
    title: str = "Forest Plot",
    dpi: int = 300,
) -> bytes:
    """OR/RR forest plot.

    studies: [{"label": str, "or": float, "ci_low": float, "ci_high": float}, ...]
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(studies)
    fig, ax = plt.subplots(figsize=(9, max(4, n * 0.6 + 1)))
    y_pos = list(range(n, 0, -1))

    for i, s in enumerate(studies):
        y = y_pos[i]
        ax.plot([s["ci_low"], s["ci_high"]], [y, y], color="#374151", linewidth=1.5)
        ax.plot(s["or"], y, "s", color="#2563EB", markersize=8,
                markeredgecolor="white", markeredgewidth=0.8)

    ax.axvline(1.0, color="#EF4444", linestyle="--", linewidth=1, alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([s["label"] for s in studies], fontsize=9)
    ax.set_xlabel("Odds Ratio (95% CI)", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    result = _fig_to_bytes(fig, dpi)
    plt.close(fig)
    return result


def kaplan_meier_plot(
    time_points: List[float],
    survival_probs: List[float],
    group_label: str = "전체",
    title: str = "Kaplan-Meier Survival Curve",
    dpi: int = 300,
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.step(time_points, survival_probs, where="post", color="#2563EB",
            linewidth=2, label=group_label)
    ax.fill_between(time_points, survival_probs, alpha=0.1, color="#2563EB", step="post")
    ax.set_xlabel("Time", fontsize=11)
    ax.set_ylabel("Survival Probability", fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    result = _fig_to_bytes(fig, dpi)
    plt.close(fig)
    return result


def scatter_plot(
    x: List[float],
    y: List[float],
    xlabel: str = "X",
    ylabel: str = "Y",
    title: str = "",
    dpi: int = 300,
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(x, y, color="#2563EB", alpha=0.6, edgecolors="white", linewidth=0.5)
    if len(x) > 1:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        xline = np.linspace(min(x), max(x), 100)
        ax.plot(xline, p(xline), color="#EF4444", linewidth=1.5, linestyle="--", alpha=0.8)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    result = _fig_to_bytes(fig, dpi)
    plt.close(fig)
    return result


def stat_result_to_forest_plot(
    stat_result: dict,
    title: str = "",
    save_path: Optional[str] = None,
    dpi: int = 300,
) -> Optional[bytes]:
    """AnalysisResult.to_dict() 결과 → Forest Plot bytes.

    stat_result: StatBridge().run(...).to_dict()
    save_path: 지정하면 PNG 파일로 저장.
    Returns None if no valid variables.
    """
    vars_list = stat_result.get("model_vars", [])
    if not vars_list:
        return None

    studies = []
    for v in vars_list:
        ci_low = float(v.get("ci_lower") or 0)
        ci_high = float(v.get("ci_upper") or 0)
        or_val = float(v.get("or_value") or 1.0)
        label = v.get("label") or v.get("variable", "")
        if ci_low > 0 and ci_high > 0 and label:
            studies.append({
                "label": label,
                "or": or_val,
                "ci_low": ci_low,
                "ci_high": ci_high,
            })

    if not studies:
        return None

    outcome_label = stat_result.get("outcome_label", "Outcome")
    plot_title = title or f"Adjusted OR — {outcome_label}"
    img_bytes = forest_plot(studies, title=plot_title, dpi=dpi)

    if save_path:
        from pathlib import Path as _Path
        _Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(save_path).write_bytes(img_bytes)
        _log.info("Forest plot 저장: %s", save_path)

    return img_bytes


def heatmap(
    matrix: List[List[float]],
    row_labels: List[str],
    col_labels: List[str],
    title: str = "",
    dpi: int = 300,
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(max(6, len(col_labels)), max(4, len(row_labels) * 0.7)))
    sns.heatmap(
        np.array(matrix), annot=True, fmt=".2f",
        xticklabels=col_labels, yticklabels=row_labels,
        cmap="Blues", ax=ax, linewidths=0.5,
    )
    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    result = _fig_to_bytes(fig, dpi)
    plt.close(fig)
    return result
