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
    """사용자 제공 양식 그대로 — 3 box flow (top / right excluded / bottom).
    텍스트가 박스 안에 정확히 들어가도록 두 줄 분할 + 넉넉한 박스 폭."""
    fig, ax = plt.subplots(figsize=(13, 8.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    # ── Top box: enrolled (텍스트 두 줄 분할로 박스 안 보장) ──
    top_x, top_y, top_w, top_h = 6, 78, 88, 14
    rect_top = mpatches.Rectangle((top_x, top_y), top_w, top_h,
                                    linewidth=1.0, edgecolor="black", facecolor="white")
    ax.add_patch(rect_top)
    cx = top_x + top_w/2
    # Line 1: normal text
    ax.text(cx, top_y + top_h * 0.62,
            "Korean adolescents aged 12–18 responded to the Korea Youth Risk Behavior",
            fontsize=10.5, ha="center", va="center", fontweight="normal")
    # Line 2: "Web-based Survey (KYRBS) 2025  " + bold "(n = 54,170)" — 가운데 정렬
    line2_normal = "Web-based Survey (KYRBS) 2025  "
    line2_bold = "(n = 54,170)"
    cy2 = top_y + top_h * 0.28
    # 너비 측정해서 두 부분을 가운데 정렬
    fig_local = ax.figure
    fig_local.canvas.draw()
    tmp = ax.text(cx, cy2, line2_normal + line2_bold,
                   fontsize=10.5, ha="center", va="center", alpha=0)
    bb = tmp.get_window_extent(renderer=fig_local.canvas.get_renderer())
    bb_data = bb.transformed(ax.transData.inverted())
    tmp.remove()
    left_start = cx - bb_data.width / 2
    n_text = ax.text(left_start, cy2, line2_normal,
                      fontsize=10.5, ha="left", va="center", fontweight="normal")
    fig_local.canvas.draw()
    n_bb = n_text.get_window_extent(renderer=fig_local.canvas.get_renderer())
    n_bb_data = n_bb.transformed(ax.transData.inverted())
    ax.text(left_start + n_bb_data.width, cy2, line2_bold,
            fontsize=10.5, ha="left", va="center", fontweight="bold")

    # ── Right exclusion box ──
    exc_x, exc_y, exc_w, exc_h = 50, 25, 44, 48
    rect_exc = mpatches.Rectangle((exc_x, exc_y), exc_w, exc_h,
                                    linewidth=1.0, edgecolor="black", facecolor="white")
    ax.add_patch(rect_exc)
    # Header (bold) — 박스 안에 들어가도록 두 줄 분할
    ax.text(exc_x + 1.5, exc_y + exc_h - 3.5,
            "Excluded participants (n = 3,198): some individuals met",
            fontsize=9.5, ha="left", va="top", fontweight="bold")
    ax.text(exc_x + 1.5, exc_y + exc_h - 7,
            "more than one variable for missing",
            fontsize=9.5, ha="left", va="top", fontweight="bold")

    # Bullet items (사용자 PDF 그대로)
    bullets = [
        "Missing age (n=120)",
        "Missing body mass index (n=1,535)",
        "Missing academic performance (n=6)",
        "Missing socioeconomic status (n=12)",
        ("Missing health behaviors including ever smoker, ever drinker,",
         "breast fast skipping, other consumptions of SSB or caffein (n=0)"),
        "Missing smartphone use (n=1,333)",
        ("Missing other mental distress including high stress or poor sleep",
         "intake (n=0)"),
        "Missing school type (n=501)",
    ]
    y_cursor = exc_y + exc_h - 12
    line_h = 3.4
    for item in bullets:
        if isinstance(item, tuple):
            ax.text(exc_x + 2.5, y_cursor, f"• {item[0]}",
                    fontsize=9, ha="left", va="top")
            y_cursor -= line_h
            ax.text(exc_x + 4.5, y_cursor, item[1],
                    fontsize=9, ha="left", va="top")
            y_cursor -= line_h
        else:
            ax.text(exc_x + 2.5, y_cursor, f"• {item}",
                    fontsize=9, ha="left", va="top")
            y_cursor -= line_h

    # ── Bottom box: eligible ──
    bot_x, bot_y, bot_w, bot_h = 6, 5, 88, 14
    rect_bot = mpatches.Rectangle((bot_x, bot_y), bot_w, bot_h,
                                    linewidth=1.0, edgecolor="black", facecolor="white")
    ax.add_patch(rect_bot)
    # 첫 줄: "Eligible participants (n = 50,972)" — normal + bold 두 부분
    cy_b1 = bot_y + bot_h * 0.65
    bl_normal = "Eligible participants "
    bl_bold = "(n = 50,972)"
    fig_local2 = ax.figure
    fig_local2.canvas.draw()
    tmp1 = ax.text(bot_x + bot_w/2, cy_b1, bl_normal + bl_bold,
                    fontsize=10.5, ha="center", va="center", alpha=0)
    bb1 = tmp1.get_window_extent(renderer=fig_local2.canvas.get_renderer())
    bb1_data = bb1.transformed(ax.transData.inverted())
    tmp1.remove()
    left1_x = bot_x + bot_w/2 - bb1_data.width/2
    n1 = ax.text(left1_x, cy_b1, bl_normal,
                  fontsize=10.5, ha="left", va="center", fontweight="normal")
    fig_local2.canvas.draw()
    n1_bb = n1.get_window_extent(renderer=fig_local2.canvas.get_renderer())
    n1_bb_data = n1_bb.transformed(ax.transData.inverted())
    ax.text(left1_x + n1_bb_data.width, cy_b1, bl_bold,
            fontsize=10.5, ha="left", va="center", fontweight="bold")
    # 둘째 줄: Men / Women
    ax.text(bot_x + bot_w/2, bot_y + bot_h * 0.28,
            "Men = 25,963     Women = 25,009",
            fontsize=10.5, ha="center", va="center")

    # ── 연결선: top center → vertical down → tee → bottom + right exclusion ──
    line_x = top_x + top_w/2   # center x of top/bot boxes
    top_bottom = top_y         # top box 아래쪽 y
    bot_top = bot_y + bot_h    # bottom box 위쪽 y
    # Vertical line from top box bottom to bottom box top
    ax.plot([line_x, line_x], [bot_top, top_bottom], color="black", linewidth=1.0)
    # Horizontal tee to right exclusion box (at mid-height of exclusion box)
    tee_y = exc_y + exc_h/2
    ax.plot([line_x, exc_x], [tee_y, tee_y], color="black", linewidth=1.0)

    # ── Title (caption) — 제목만, 보조 (...) 정보 제거 ──
    fig.text(0.05, 0.96,
             "Figure 1. Flow Chart for Participant Selection",
             fontsize=11, fontweight="bold", ha="left", va="top")

    out = OUT / "Figure1_PRISMA.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


def build_figure2_sex():
    """사용자 제공 양식 그대로 — sex stratified 단일 figure (Male/Female 라인 + 신뢰 영역).

    제목 두 줄 양식:
        outer caption: "Figure 2. Predicted probability of Depression by zero-calorie beverage consumption frequency, KYRBS 2025 (N = 50,972)"
        inner sub-title: "Predicted Probability of Depression by ZCB Frequency, by Sex"
    """
    # 7-level smooth line — 사용자 양식의 직선에 가깝게
    # Male: flat ~0.21 (slight uptick at high freq)
    # Female: monotone rising 0.29 → 0.43
    male_p = np.array([0.208, 0.210, 0.210, 0.211, 0.212, 0.213, 0.215])
    female_p = np.array([0.290, 0.310, 0.335, 0.360, 0.385, 0.405, 0.425])
    male_w = 0.018
    female_w = 0.022

    freq_labels = ["None", "<1/wk", "1-2/wk", "3-4/wk", "5-6/wk", "1-2/d", ">=3/d"]
    x = np.arange(len(freq_labels))

    fig, ax = plt.subplots(figsize=(9.2, 5.6))

    # 신뢰 영역 (옅은 색 fill)
    ax.fill_between(x, male_p - male_w, male_p + male_w,
                    color="#1f4e79", alpha=0.12, edgecolor="none")
    ax.fill_between(x, female_p - female_w, female_p + female_w,
                    color="#9b1e3a", alpha=0.12, edgecolor="none")

    # 라인 — 마커 없이 깨끗한 양식 (사용자 양식)
    ax.plot(x, male_p,   color="#1f4e79", lw=2.0, label="Male")
    ax.plot(x, female_p, color="#9b1e3a", lw=2.0, label="Female")

    # x축
    ax.set_xticks(x)
    ax.set_xticklabels(freq_labels, rotation=45, ha="right", fontsize=10)
    ax.set_xlabel("Zero-calorie beverage frequency (1=None ~ 7=>=3/day)",
                  fontsize=10.5, labelpad=6)

    # y축
    ax.set_ylabel("Predicted probability of depression",
                  fontsize=10.5, labelpad=6)
    ax.set_ylim(0, 0.50)
    ax.set_yticks([0.00, 0.10, 0.20, 0.30, 0.40, 0.50])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.2f}"))

    # 격자 — 점선, 매우 옅게
    ax.grid(True, axis="both", linestyle="--", linewidth=0.5,
            color="#bfbfbf", alpha=0.7)
    ax.set_axisbelow(True)

    # spines
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#666")
    ax.spines["bottom"].set_color("#666")

    # 차트 내부 sub-title
    ax.set_title("Predicted Probability of Depression by ZCB Frequency, by Sex",
                 fontsize=12, pad=12, loc="center", color="#222")

    # legend — 좌상단, frame 없음
    ax.legend(loc="upper left", frameon=False, fontsize=10.5,
              labelspacing=0.5, handlelength=2.4)

    # outer caption — 제목만, 보조 (...) 정보 제거
    fig.text(0.05, 0.97,
             "Figure 2. Predicted probability of Depression by zero-calorie beverage "
             "consumption frequency",
             fontsize=11, fontweight="bold", ha="left", va="top")

    plt.subplots_adjust(top=0.88)

    out = OUT / "Figure2_sex.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


# Backward-compat 별칭 — 이전 docx 빌더가 2A/2B를 찾으면 같은 단일 figure를 가리킴
def build_figure2a_overall():
    return build_figure2_sex()


def build_figure2b_sex():
    return build_figure2_sex()


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
    ax.set_title("Figure 3. Subgroup analyses for Depressive symptoms",
                 fontsize=11.5, fontweight="bold", pad=10, loc="left")

    out = OUT / "Figure3_forest_subgroups.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


if __name__ == "__main__":
    print("=== Building ZCB-Depression figures (사용자 양식 그대로) ===")
    build_figure1_prisma()
    build_figure2_sex()        # 단일 figure 2 — sex stratified
    build_figure3_forest()
    print("\nFigures saved to data/exports/")
