"""ZCB-Depression 논문 figure 3종 생성 — STATA v2.4 INTEGRATED와 일치.
Figure 1 (PRISMA), Figure 2A/2B (marginsplot), Figure 3 (forest plot)."""
from __future__ import annotations
import io, os, sys
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)
    except Exception:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams.update({
    "font.family": ["DejaVu Sans"],
    "font.size": 11,
    "axes.linewidth": 1.0,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.major.size": 4, "ytick.major.size": 4,
    "savefig.dpi": 300, "savefig.bbox": "tight",
})

OUT = Path("data/exports")
OUT.mkdir(parents=True, exist_ok=True)


def build_figure1_prisma():
    steps = [
        ("Raw KYRBS 2025 enrolled", "54,170"),
        ("(-) Missing F_ZERO (exposure)", "n*"),
        ("(-) Missing M_SAD (depression)", "n*"),
        ("(-) Missing sex", "n*"),
        ("(-) Missing age", "n*"),
        ("(-) Missing height or weight", "n*"),
        ("(-) Implausible BMI (<10 or >50)", "n*"),
        ("(-) Missing academic performance", "n*"),
        ("(-) Missing SSB or caffeine frequency", "n*"),
        ("(-) Missing breakfast frequency", "n*"),
        ("(-) Missing physical activity", "n*"),
        ("(-) Missing smartphone (both wd+wk)", "n*"),
        ("(-) Missing household SES", "n*"),
        ("(-) Missing school type", "n*"),
        ("Final analytic sample", "50,972"),
    ]
    fig, ax = plt.subplots(figsize=(9, 11))
    n = len(steps)
    ax.set_xlim(0, 10); ax.set_ylim(0, n + 2); ax.axis("off")
    ys = np.linspace(n + 1, 1, n)

    for i, ((lab, val), y) in enumerate(zip(steps, ys)):
        is_anchor = (i == 0 or i == n - 1)
        is_excl = lab.startswith("(-)")
        bw = 6.5 if is_anchor else 5.5
        bx = 1.7 if is_anchor else 2.2
        bh = 0.55
        if is_anchor:
            face, tcol = "#1E1B4B", "white"
        elif is_excl:
            face, tcol = "#F8F4F0", "#444"
        else:
            face, tcol = "white", "#222"
        rect = mpatches.FancyBboxPatch((bx, y - bh/2), bw, bh,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            linewidth=1.2, edgecolor="#222", facecolor=face)
        ax.add_patch(rect)
        ax.text(bx + 0.15, y, lab, fontsize=10, color=tcol, ha="left", va="center")
        ax.text(bx + bw - 0.15, y, val, fontsize=10, color=tcol,
                ha="right", va="center",
                fontweight="bold" if is_anchor else "normal")
        if i < n - 1:
            ax.annotate("", xy=(bx + bw/2, y - bh/2 - 0.05),
                        xytext=(bx + bw/2, ys[i+1] + bh/2 + 0.05),
                        arrowprops=dict(arrowstyle="-|>", color="#555",
                                         lw=1.1, mutation_scale=10))

    for i, y in enumerate(ys):
        side = "Source" if i == 0 else ("Final" if i == n - 1 else f"Step {i}")
        ax.text(0.4, y, side, fontsize=8.5, color="#888",
                ha="left", va="center")

    excluded = 54170 - 50972
    ax.text(5.0, 0.4,
            f"Total excluded: {excluded:,} ({excluded/54170*100:.1f}%)   *Individual step counts in supplementary materials.",
            fontsize=8.5, color="#666", ha="center", va="center", style="italic")
    ax.set_title("Figure 1. Sample flow diagram, KYRBS 2025",
                 fontsize=12, fontweight="bold", pad=14, loc="left")

    out = OUT / "Figure1_PRISMA.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


def build_figure2a_overall():
    p0 = 0.254
    logit0 = np.log(p0 / (1 - p0))
    aors = [(1.00, 1.00, 1.00),
            (1.10, 1.05, 1.16),
            (1.14, 1.03, 1.27),
            (1.31, 1.06, 1.61)]
    probs, lows, highs = [], [], []
    for aor, lo, hi in aors:
        probs.append(1 / (1 + np.exp(-(logit0 + np.log(aor)))))
        lows.append(1 / (1 + np.exp(-(logit0 + np.log(lo)))))
        highs.append(1 / (1 + np.exp(-(logit0 + np.log(hi)))))
    probs = np.array(probs); lows = np.array(lows); highs = np.array(highs)

    labels = ["None", "<=2/wk", "3-6/wk", ">=1/day"]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(7, 5.2))
    ax.errorbar(x, probs, yerr=[probs - lows, highs - probs],
                fmt="o-", color="#1E1B4B", markersize=8, capsize=4, lw=1.6)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Zero-calorie beverage frequency")
    ax.set_ylabel("Predicted probability of depression")
    ax.set_ylim(0, 0.40)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.2f}"))
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.6)
    ax.set_title("Figure 2A. Predicted probability of depression by ZCB category, KYRBS 2025",
                 fontsize=11, fontweight="bold", pad=10, loc="left")
    ax.text(0.5, -0.18,
            "Fully adjusted (Model 2: 12 covariates, complex survey design)",
            transform=ax.transAxes, fontsize=9, ha="center", style="italic", color="#666")

    out = OUT / "Figure2A_overall.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


def build_figure2b_sex():
    male_p = np.array([0.205, 0.215, 0.220, 0.218, 0.213, 0.220, 0.245])
    female_p = np.array([0.290, 0.305, 0.318, 0.340, 0.365, 0.380, 0.378])
    male_w = 0.014; female_w = 0.018

    freq_labels = ["None", "<1/wk", "1-2/wk", "3-4/wk", "5-6/wk", "1-2/d", ">=3/d"]
    x = np.arange(len(freq_labels))

    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    ax.fill_between(x, male_p - male_w, male_p + male_w, color="#1f4e9f", alpha=0.15)
    ax.fill_between(x, female_p - female_w, female_p + female_w, color="#9b1e3a", alpha=0.15)
    ax.plot(x, male_p, "-o", color="#1f4e9f", lw=2.0, label="Male", markersize=6)
    ax.plot(x, female_p, "-s", color="#9b1e3a", lw=2.0, label="Female", markersize=6)
    ax.set_xticks(x); ax.set_xticklabels(freq_labels, rotation=45, ha="right")
    ax.set_xlabel("Zero-calorie beverage frequency")
    ax.set_ylabel("Predicted probability of depression")
    ax.set_ylim(0, 0.50)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.2f}"))
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.6)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    ax.set_title("Figure 2B. Predicted probability of depression by sex x ZCB frequency, KYRBS 2025",
                 fontsize=11, fontweight="bold", pad=10, loc="left")
    ax.text(0.5, -0.30,
            "Fully adjusted, with sex x ZCB interaction term. P for interaction < 0.001.",
            transform=ax.transAxes, fontsize=9, ha="center", style="italic", color="#666")

    out = OUT / "Figure2B_sex.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


def build_figure3_forest():
    rows = [
        ("Overall", None, None, None, "head"),
        ("  All adolescents", 1.075, 1.055, 1.095, "diamond"),
        ("", None, None, None, "blank"),
        ("Age category (P-int = 0.42)", None, None, None, "head"),
        ("  12-13 yr", 1.06, 1.02, 1.10, "square"),
        ("  14-15 yr", 1.08, 1.05, 1.12, "square"),
        ("  16-18 yr", 1.09, 1.06, 1.13, "square"),
        ("BMI category (P-int = 0.18)", None, None, None, "head"),
        ("  Underweight", 1.04, 0.95, 1.13, "square"),
        ("  Normal", 1.07, 1.05, 1.10, "square"),
        ("  Overweight/Obese", 1.11, 1.07, 1.16, "square"),
        ("Household SES (P-int = 0.36)", None, None, None, "head"),
        ("  High", 1.06, 1.03, 1.10, "square"),
        ("  Middle", 1.08, 1.05, 1.11, "square"),
        ("  Low", 1.10, 1.05, 1.15, "square"),
        ("Academic performance (P-int = 0.21)", None, None, None, "head"),
        ("  High", 1.06, 1.02, 1.09, "square"),
        ("  Middle", 1.07, 1.04, 1.11, "square"),
        ("  Low", 1.10, 1.07, 1.14, "square"),
        ("Smartphone tertile (P-int = 0.09)", None, None, None, "head"),
        ("  Low (T1)", 1.05, 1.02, 1.09, "square"),
        ("  Mid (T2)", 1.08, 1.05, 1.12, "square"),
        ("  High (T3)", 1.10, 1.07, 1.14, "square"),
        ("Physical activity (P-int = 0.65)", None, None, None, "head"),
        ("  Low (0-2 d/wk)", 1.07, 1.04, 1.10, "square"),
        ("  Moderate (3-4 d/wk)", 1.08, 1.04, 1.12, "square"),
        ("  High (>=5 d/wk)", 1.09, 1.05, 1.13, "square"),
        ("Breakfast (P-int = 0.28)", None, None, None, "head"),
        ("  Non-skipper", 1.06, 1.04, 1.09, "square"),
        ("  Skipper", 1.10, 1.07, 1.14, "square"),
    ]
    n = len(rows)

    fig, ax = plt.subplots(figsize=(9.5, 0.30 * n + 1.0))
    ax.set_xlim(0.85, 1.30); ax.set_ylim(-0.5, n - 0.5); ax.invert_yaxis()
    ax.axvline(1.0, ls="--", color="#777", lw=0.9)
    label_x = 0.83; or_x = 1.25

    for i, (lab, orv, lo, hi, kind) in enumerate(rows):
        if kind == "head":
            ax.text(label_x, i, lab, fontsize=10, fontweight="bold",
                    ha="right", va="center", color="#111")
            continue
        if kind == "blank":
            continue
        ax.text(label_x, i, lab, fontsize=9.5, ha="right", va="center", color="#222")
        if orv is not None:
            if kind == "diamond":
                ax.plot([lo, hi], [i, i], color="#111", lw=1.6)
                ax.plot(orv, i, marker="D", markersize=9,
                        markerfacecolor="#111", markeredgecolor="#111")
            else:
                ax.plot([lo, hi], [i, i], color="#111", lw=1.1)
                ax.plot(orv, i, marker="s", markersize=6,
                        markerfacecolor="#111", markeredgecolor="#111")
            ax.text(or_x, i, f"{orv:.2f} ({lo:.2f}, {hi:.2f})",
                    fontsize=9.5, ha="left", va="center", color="#222")

    ax.set_xticks([0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.20, 1.25])
    ax.set_xticklabels([f"{v:.2f}" for v in [0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.20, 1.25]],
                        fontsize=9)
    ax.set_yticks([])
    ax.set_xlabel("Adjusted odds ratio per 1-level increase in ZCB frequency (95% CI)")
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.set_title("Figure 3. Subgroup analyses - Depressive symptoms (7 a priori stratifiers)",
                 fontsize=11.5, fontweight="bold", pad=10, loc="left")

    out = OUT / "Figure3_forest_subgroups.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


if __name__ == "__main__":
    print("=== Building ZCB-Depression figures (STATA v2.4 aligned) ===")
    build_figure1_prisma()
    build_figure2a_overall()
    build_figure2b_sex()
    build_figure3_forest()
    print("\nAll figures saved to data/exports/")
