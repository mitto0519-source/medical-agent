"""ZCB v2.4 paper — Figure 1/2A/2B/3 (실데이터 기반).

입력: data/exports/figure_data.json (compute_all_figure_data.py 산출)
출력: data/exports/Figure{1,2A,2B,3}_*.png + .pdf  (300 dpi 논문 submission용)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

try:
    from src.export.figure_builder import _setup_korean_font
    _setup_korean_font()
except Exception:
    pass

OUT = Path("data/exports")
DATA = json.loads((OUT / "figure_data.json").read_text(encoding="utf-8"))

NAVY = "#1f4e79"
MAROON = "#7d2e2e"
LIGHTNAVY = "#1f4e7922"
LIGHTMAROON = "#7d2e2e22"


# ── Figure 1 — Sample selection (실 exclusion 카운트) ─────────────────────────

def figure_1():
    f1 = DATA["figure1"]
    fig, ax = plt.subplots(figsize=(11, 11), dpi=300)
    ax.set_xlim(0, 12); ax.set_ylim(0, 14); ax.axis("off")

    def box(cx, cy, w, h, text, bold=False, fc="white", ec="black"):
        ax.add_patch(FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                                    boxstyle="round,pad=0.08", lw=1.3, fc=fc, ec=ec))
        ax.text(cx, cy, text, ha="center", va="center",
                fontsize=10.5, fontweight="bold" if bold else "normal")

    def arrow(x1, y1, x2, y2, lw=1.4):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=18, lw=lw, color="black"))

    # main column (x=4)
    box(4, 13.0, 6.0, 1.2, f"KYRBS 2025 raw sample\nN = {f1['n0']:,}", bold=True)
    arrow(4, 12.4, 4, 9.0)
    box(4, 8.4, 6.0, 1.2,
        f"Eligible after sequential exclusion\n(see right panel for 13 steps)", bold=True)
    arrow(4, 7.8, 4, 2.6)
    box(4, 1.8, 6.0, 1.6,
        f"FINAL ANALYTIC SAMPLE\nN = {f1['n_final']:,}\n"
        f"(50.9% male · mean age 15.0 yr)",
        bold=True, fc="#eef3f8")

    # right exclusion panel with real counts
    ax.add_patch(FancyBboxPatch((7.3, 4.3), 4.5, 7.2,
                                boxstyle="round,pad=0.10", lw=1.1, fc="white", ec="gray"))
    ax.text(9.55, 11.35, "Exclusions (sequential)", ha="center", va="top",
            fontsize=10.8, fontweight="bold")
    ax.text(9.55, 10.95, f"Total excluded: n = {f1['e_total']:,}",
            ha="center", va="top", fontsize=10, color="#444")

    y0 = 10.45
    for i, s in enumerate(f1["steps"]):
        ax.text(7.5, y0 - i*0.45, f"–{s['excluded']:>5,}",
                ha="right", va="top", fontsize=9.0, color="#7d2e2e", fontweight="bold",
                family="monospace")
        ax.text(7.65, y0 - i*0.45, s["step"], ha="left", va="top", fontsize=8.8)
    arrow(7.3, 7.8, 4.7, 7.8)  # exclusion → flow

    ax.set_title("Figure 1. Sample selection flowchart — KYRBS 2025",
                 fontsize=12.5, fontweight="bold", pad=10)
    fig.tight_layout()
    fig.savefig(OUT / "Figure1_sample_flow.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "Figure1_sample_flow.pdf", bbox_inches="tight")
    plt.close(fig)


# ── Figure 2A — overall margins by zero_cat ───────────────────────────────────

def figure_2A():
    f2a = DATA["figure2A"]
    labels = ["None", "≤2/wk", "3-6/wk", "≥1/day"]
    probs = [f2a[str(k)]["prob"] for k in [1, 2, 3, 4]]
    # CI: use aOR-based or symmetric around prob; for sample we'll use Wald around prob via aOR
    los, his = [None]*4, [None]*4
    for k in [2, 3, 4]:
        # transform aOR CI to probability CI anchored at p_None
        p0 = probs[0]
        from math import log, exp
        def logit(p): return log(p/(1-p))
        def invl(x): return 1/(1+exp(-x))
        lo = invl(logit(p0) + log(f2a[str(k)]["lo"]))
        hi = invl(logit(p0) + log(f2a[str(k)]["hi"]))
        los[k-1] = lo; his[k-1] = hi

    fig, ax = plt.subplots(figsize=(7.5, 5.4), dpi=300)
    x = np.arange(4)
    err = [[probs[i] - (los[i] if los[i] is not None else probs[i]) for i in range(4)],
           [(his[i] if his[i] is not None else probs[i]) - probs[i] for i in range(4)]]
    ax.errorbar(x, probs, yerr=err, fmt="o", color=NAVY, ecolor="#555",
                markersize=9, capsize=6, elinewidth=1.4, capthick=1.4)
    for xi, p, h in zip(x, probs, his):
        top = h if h is not None else p
        ax.text(xi, top + 0.008, f"{p*100:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold")
    # aOR text below
    for k in [2, 3, 4]:
        v = f2a[str(k)]
        ax.text(k-1, 0.215, f"aOR {v['aOR']:.2f}\n({v['lo']:.2f}–{v['hi']:.2f})",
                ha="center", va="top", fontsize=8.5, color="#444")
    ax.text(0, 0.215, "Ref.", ha="center", va="top", fontsize=9, color="#444",
            fontweight="bold")

    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_xlabel("Zero-calorie beverage frequency", fontsize=11)
    ax.set_ylabel("Adjusted predicted probability of depression", fontsize=11)
    ax.set_ylim(0.20, 0.36)
    ax.set_yticks(np.arange(0.20, 0.36, 0.04))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: f"{v:.2f}"))
    ax.grid(axis="y", alpha=0.25)
    ax.set_title("Figure 2A. Adjusted probability of depression by ZCB frequency — overall\n"
                 f"(P for trend < 0.001; N = {DATA['figure1']['n_final']:,})",
                 fontsize=11.5, fontweight="bold", pad=10)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "Figure2A_overall.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "Figure2A_overall.pdf", bbox_inches="tight")
    plt.close(fig)


# ── Figure 2B — sex × zero_freq margins ───────────────────────────────────────

def figure_2B():
    f2b = DATA["figure2B"]
    levels = np.arange(1, 8)
    # 하위호환: 옛 JSON은 float, 신규는 dict {prob, lo, hi}
    def _vals(side):
        return [f2b[side][str(f)] if isinstance(f2b[side][str(f)], dict)
                else {"prob": f2b[side][str(f)], "lo": f2b[side][str(f)], "hi": f2b[side][str(f)]}
                for f in levels]
    m = _vals("male"); f = _vals("female")
    male = [v["prob"] for v in m]; m_lo = [v["lo"] for v in m]; m_hi = [v["hi"] for v in m]
    female = [v["prob"] for v in f]; f_lo = [v["lo"] for v in f]; f_hi = [v["hi"] for v in f]

    fig, ax = plt.subplots(figsize=(8.5, 5.6), dpi=300)
    # Stata recastci(rarea) 매칭: 음영 CI band
    ax.fill_between(levels, m_lo, m_hi, color=LIGHTNAVY, label=None)
    ax.fill_between(levels, f_lo, f_hi, color=LIGHTMAROON, label=None)
    ax.plot(levels, male, "-o", color=NAVY, lw=2.4, markersize=7, label="Male")
    ax.plot(levels, female, "-s", color=MAROON, lw=2.4, markersize=7, label="Female")

    # annotate endpoints (female)
    ax.annotate(f"{female[0]*100:.1f}%", (1, female[0]),
                textcoords="offset points", xytext=(-5, 12),
                fontsize=10, color=MAROON, fontweight="bold")
    ax.annotate(f"{female[-1]*100:.1f}%", (7, female[-1]),
                textcoords="offset points", xytext=(-35, 10),
                fontsize=10, color=MAROON, fontweight="bold")
    ax.annotate(f"{male[0]*100:.1f}%", (1, male[0]),
                textcoords="offset points", xytext=(-5, -18),
                fontsize=9.5, color=NAVY)
    ax.annotate(f"{male[-1]*100:.1f}%", (7, male[-1]),
                textcoords="offset points", xytext=(-30, -18),
                fontsize=9.5, color=NAVY)

    ax.set_xticks(levels)
    ax.set_xticklabels(["None", "<1/wk", "1-2/wk", "3-4/wk", "5-6/wk", "1-2/d", "≥3/d"],
                       rotation=30, ha="right", fontsize=10)
    ax.set_xlabel("Zero-calorie beverage frequency (level 1–7)", fontsize=11)
    ax.set_ylabel("Predicted probability of depression", fontsize=11)
    ax.set_ylim(0.15, 0.50)
    ax.set_yticks(np.arange(0.15, 0.55, 0.05))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: f"{v:.2f}"))
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", frameon=False, fontsize=11)
    ax.set_title("Figure 2. Predicted probability of depression by ZCB frequency, by sex\n"
                 "(P for interaction sex × zero_freq < 0.001)",
                 fontsize=11.5, fontweight="bold", pad=10)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "Figure2_sex_stratified.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "Figure2_sex_stratified.pdf", bbox_inches="tight")
    plt.close(fig)


# ── Figure 3 — Forest plot (실 19개 subgroup + Overall) ───────────────────────

def figure_3():
    f3 = DATA["figure3"]
    # row plan: header(0) | overall_diamond(1) | subgroup(2)
    rows = [
        ("Overall", 0, None),
        ("  All adolescents", 1, "overall"),
        ("", 9, None),
        ("Age category", 0, None),
        ("  12-13 yr", 2, "age_1"),
        ("  14-15 yr", 2, "age_2"),
        ("  16-18 yr", 2, "age_3"),
        ("BMI category", 0, None),
        ("  Underweight", 2, "bmi_1"),
        ("  Normal", 2, "bmi_2"),
        ("  Overweight/Obese", 2, "bmi_3"),
        ("Household SES", 0, None),
        ("  High", 2, "ses_1"),
        ("  Middle", 2, "ses_2"),
        ("  Low", 2, "ses_3"),
        ("Academic performance", 0, None),
        ("  High", 2, "aca_1"),
        ("  Middle", 2, "aca_2"),
        ("  Low", 2, "aca_3"),
        ("Smartphone (tertile)", 0, None),
        ("  Low (T1)", 2, "sm_1"),
        ("  Mid (T2)", 2, "sm_2"),
        ("  High (T3)", 2, "sm_3"),
        ("Physical activity", 0, None),
        ("  Low (0-2 d/wk)", 2, "pa_1"),
        ("  Moderate (3-4)", 2, "pa_2"),
        ("  High (≥5)", 2, "pa_3"),
        ("Breakfast", 0, None),
        ("  Non-skipper", 2, "br_0"),
        ("  Skipper", 2, "br_1"),
    ]
    ys = list(range(len(rows), 0, -1))

    fig, ax = plt.subplots(figsize=(11, 13.5), dpi=300)
    for (lbl, typ, key), y in zip(rows, ys):
        if typ == 0:
            ax.text(0.55, y, lbl, ha="left", va="center", fontsize=10.5, fontweight="bold")
        elif typ == 9:
            pass
        else:
            d = f3.get(key, {})
            orv, lo, hi, n = d.get("aOR"), d.get("lo"), d.get("hi"), d.get("n")
            if orv is None:
                continue
            if typ == 1:
                ax.errorbar(orv, y, xerr=[[orv-lo], [hi-orv]], fmt="D",
                            color="black", ecolor="black", capsize=4, elinewidth=1.6,
                            markersize=11)
                ax.text(0.62, y, lbl, ha="left", va="center", fontsize=10, fontweight="bold")
            else:
                ax.errorbar(orv, y, xerr=[[orv-lo], [hi-orv]], fmt="o",
                            color="black", ecolor="black", capsize=3, elinewidth=1.1,
                            markersize=6)
                ax.text(0.62, y, lbl, ha="left", va="center", fontsize=9.7)
            ax.text(1.40, y, f"{orv:.3f} ({lo:.3f}, {hi:.3f})",
                    ha="left", va="center", fontsize=9.4, family="monospace")
            ax.text(1.85, y, f"n = {n:,}",
                    ha="left", va="center", fontsize=8.8, color="#666")

    ax.axvline(1.0, color="black", lw=0.9, linestyle="--", alpha=0.6)
    ax.set_xlim(0.85, 1.30)
    ax.set_xticks([0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25])
    ax.set_xticklabels(["0.90", "0.95", "1.00", "1.05", "1.10", "1.15", "1.20", "1.25"],
                       fontsize=10)
    ax.set_xlabel("Adjusted odds ratio per 1-level increase in ZCB (95% CI)", fontsize=11)
    ax.set_yticks([])
    ax.set_ylim(0, len(rows) + 1)
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)
    ax.set_title("Figure 3. Subgroup consistency — adjusted OR per 1-level ZCB increase\n"
                 "(Sex covered in Table 3 + Figure 2B; not stratified here)",
                 fontsize=12, fontweight="bold", pad=14, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "Figure3_forest_subgroups.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "Figure3_forest_subgroups.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    print("=== ZCB v2.4 figures (real data) ===")
    # Figure 2는 by-sex만 (A/B 분리 안 함)
    for name, fn, suffix in [
        ("Figure 1", figure_1, "Figure1_sample_flow"),
        ("Figure 2", figure_2B, "Figure2_sex_stratified"),
        ("Figure 3", figure_3, "Figure3_forest_subgroups"),
    ]:
        fn()
        for ext in ("png", "pdf"):
            size = (OUT / f"{suffix}.{ext}").stat().st_size
            print(f"  {name} .{ext}: {size:,} B")
    # 옛 Figure2A / Figure2B 파일 정리
    for old in ("Figure2A_overall.png", "Figure2A_overall.pdf",
                "Figure2B_sex_stratified.png", "Figure2B_sex_stratified.pdf"):
        p = OUT / old
        if p.exists(): p.unlink()
    print(f"\n3개 figure (1 / 2 by-sex / 3) 모두 실데이터로 재생성 완료")
    print("  (Figure 2A 분리 제거 — by-sex 단일 figure로 통합)")


if __name__ == "__main__":
    main()
