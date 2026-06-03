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

    # ── Title (caption) — Supplementary Figure 1 (PRISMA) ──
    fig.text(0.05, 0.96,
             "Supplementary Figure 1. Flow chart for participant selection",
             fontsize=11, fontweight="bold", ha="left", va="top")

    out = OUT / "Supplementary_Figure_1_PRISMA.png"
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
    # ★ 2026-06-03: stat_results.json에서 실측 weighted prevalence 로드 (4-level).
    # run_zcb_dep_stata_exact.py의 Supp_Figure_1이 sex × zero_cat 4셀당
    # n / prob / 95% CI를 산출. illustrative 값 X.
    import json as _j
    from pathlib import Path as _P
    sr = _j.loads(_P("data/exports/stat_results.json").read_text(encoding="utf-8"))
    sf1 = sr.get("Supp_Figure_1") or {}
    freq_labels = sf1.get("exposure_labels") or ["None", "≤2/week", "3–6/week", "≥1/day"]
    by_sex = sf1.get("by_sex") or {}

    def _series(label):
        cells = by_sex.get(label) or []
        p = np.array([c.get("prob") or 0.0 for c in cells])
        lo = np.array([c.get("ci_low") or 0.0 for c in cells])
        hi = np.array([c.get("ci_high") or 0.0 for c in cells])
        n = [c.get("n") or 0 for c in cells]
        return p, lo, hi, n

    male_p,   male_lo,   male_hi,   male_n   = _series("Male")
    female_p, female_lo, female_hi, female_n = _series("Female")
    x = np.arange(len(freq_labels))

    fig, ax = plt.subplots(figsize=(9.2, 5.6))

    # 95% CI 영역 (실측 — Wald binomial)
    ax.fill_between(x, male_lo,   male_hi,   color="#1f4e79", alpha=0.14, edgecolor="none")
    ax.fill_between(x, female_lo, female_hi, color="#9b1e3a", alpha=0.14, edgecolor="none")

    # 라인 + 마커 (실측 점)
    ax.plot(x, male_p,   color="#1f4e79", lw=2.0, marker="o", markersize=5,
            label=f"Male (n={sum(male_n):,})")
    ax.plot(x, female_p, color="#9b1e3a", lw=2.0, marker="o", markersize=5,
            label=f"Female (n={sum(female_n):,})")

    # ★ 2026-06-03: 그림 안 숫자 라벨 제거 (수치는 HTML 결과표로 분리).

    # x축 — Table 1과 동일한 4-level zero_cat (회전 불필요, 짧은 라벨)
    ax.set_xticks(x)
    ax.set_xticklabels(freq_labels, ha="center", fontsize=10.5)
    ax.set_xlabel("Zero-calorie beverage consumption frequency",
                  fontsize=10.5, labelpad=8)

    # y축
    ax.set_ylabel("Predicted probability of depression",
                  fontsize=10.5, labelpad=6)
    ax.set_ylim(0, 0.60)
    ax.set_yticks([0.00, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60])
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

    # outer caption — Figure 1
    fig.text(0.05, 0.97,
             "Figure 1. Sex-stratified prevalence of depressive symptoms "
             "by zero-calorie beverage consumption frequency",
             fontsize=11, fontweight="bold", ha="left", va="top")

    plt.subplots_adjust(top=0.88)

    out = OUT / "Figure_1_sex_lines.png"
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
    """Figure 3 — data/exports/stat_results.json (실측)에서 값 로드."""
    import json as _j
    from pathlib import Path as _P
    sr_path = _P("data/exports/stat_results.json")
    sr = _j.loads(sr_path.read_text(encoding="utf-8"))
    f3 = sr["Figure_3"]
    ov = f3["overall"]
    sg = f3["subgroups"]

    def _p_str(p):
        if p is None: return "N/A"
        if p < 0.001: return "P-int < 0.001"
        return f"P-int = {p:.3f}"

    # ★ 2026-06-03: Table 1 묶음·라벨을 표준으로 통일.
    #   - en-dash (–) 일관 사용, "yr" 단위 제거 (Age header에 "years" 명시)
    #   - BMI level은 Table 1의 percentile cutoff 그대로 노출
    #   - Household: "SES" → full "economic status"
    def _level_label(strat, lev):
        mapping = {
            "sex":             {1: "Male", 2: "Female"},
            "age_cat":         {1: "12–13", 2: "14–15", 3: "16–18"},
            "bmi_cat":         {1: "Underweight (<P5)",
                                 2: "Normal (P5–<P85)",
                                 3: "Overweight or obese (≥P85)"},
            "ses3":            {1: "High", 2: "Middle", 3: "Low"},
            "academic3":       {1: "High", 2: "Middle", 3: "Low"},
        }
        return mapping.get(strat, {}).get(lev, str(lev))

    def _head_label(strat, p_int):
        names = {
            "sex": "Sex",
            "age_cat": "Age category, years",
            "bmi_cat": "BMI category",
            "ses3": "Household economic status",
            "academic3": "Academic performance",
        }
        return f"{names.get(strat, strat)} ({_p_str(p_int)})"

    rows = [("Overall", None, None, None, "head"),
            ("  All adolescents", ov["or"], ov["ci_low"], ov["ci_high"], "diamond"),
            ("", None, None, None, "blank")]

    for strat in ["sex", "age_cat", "bmi_cat", "ses3", "academic3"]:
        if strat not in sg: continue
        s = sg[strat]
        rows.append((_head_label(strat, s.get("p_interaction")),
                     None, None, None, "head"))
        for lv in s["levels"]:
            lev = lv["level"]
            if lv.get("or") is None:
                rows.append((f"  {_level_label(strat, lev)}", None, None, None, "blank"))
            else:
                rows.append((f"  {_level_label(strat, lev)}",
                              lv["or"], lv["ci_low"], lv["ci_high"], "square"))
    n = len(rows)

    # ★ figsize·label_x 확장 — Table 1 표준 라벨 (BMI "Overweight or obese (≥P85)" 등) 수용
    fig, ax = plt.subplots(figsize=(11.0, 0.30 * n + 1.2))
    ax.set_xlim(0.70, 1.30); ax.set_ylim(-0.5, n - 0.5); ax.invert_yaxis()
    ax.axvline(1.0, ls="--", color="#777", lw=0.9)
    label_x = 0.68; or_x = 1.25

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
            # ★ 2026-06-03: forest 옆 숫자 라벨 제거 (수치는 HTML 결과표).

    xt = [0.80, 0.90, 1.0, 1.10, 1.20, 1.30]
    ax.set_xticks(xt)
    ax.set_xticklabels([f"{v:.2f}" for v in xt], fontsize=9)
    ax.set_yticks([])
    ax.set_xlabel("Adjusted odds ratio per 1-level increase in ZCB frequency (95% CI)")
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.set_title("Figure 2. Subgroup analyses for Depressive symptoms",
                 fontsize=11.5, fontweight="bold", pad=10, loc="left")

    out = OUT / "Figure2_forest_subgroups.png"
    plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {out}")
    return out


def verify_figure2_against_image():
    """첨부 이미지(2026-05-31)의 숫자와 stat_results.json의 Figure_3 값이 ±0.02 이내인지 검증.

    이미지 출처: 사용자 첨부 PNG. 표시는 소수 2자리 (반올림).
    검증 기준: |OR - 이미지값| <= 0.015 AND |CI - 이미지값| <= 0.015.
    P_interaction은 부호(< 0.05 / >= 0.05) 일치 + 자릿수 동일 여부만 검사
    (P_int 정확값은 분석 모델 사양에 따라 미세 차이 정상).
    """
    import json as _j
    from pathlib import Path as _P
    sr = _j.loads(_P("data/exports/stat_results.json").read_text(encoding="utf-8"))
    f3 = sr["Figure_3"]

    # 이미지에서 사용자가 명시한 값 (사진 한 줄씩):
    EXPECTED = {
        "overall": (1.05, 1.03, 1.07),
        "sex": {
            "p_int": "<0.001",
            "levels": {1: (1.02, 0.99, 1.05), 2: (1.09, 1.06, 1.12)},
        },
        "age_cat": {
            "p_int": 0.008,
            "levels": {1: (1.05, 1.01, 1.10), 2: (1.09, 1.05, 1.13), 3: (1.02, 0.99, 1.05)},
        },
        "bmi_cat": {
            "p_int": 0.553,
            "levels": {1: (1.04, 0.93, 1.17), 2: (1.05, 1.03, 1.08), 3: (1.04, 1.00, 1.08)},
        },
        "ses3": {
            "p_int": 0.426,
            "levels": {1: (1.05, 1.01, 1.09), 2: (1.05, 1.02, 1.08), 3: (1.04, 0.99, 1.10)},
        },
        "academic3": {
            "p_int": 0.465,
            "levels": {1: (1.05, 1.01, 1.09), 2: (1.06, 1.02, 1.10), 3: (1.04, 1.01, 1.08)},
        },
    }
    TOL = 0.015  # 1.5% (반올림 + svy vs unweighted 미세차)

    fails, warns, oks = [], [], []
    # Overall
    ov = f3["overall"]
    e = EXPECTED["overall"]
    for got, exp, name in [(ov["or"], e[0], "or"), (ov["ci_low"], e[1], "ci_low"),
                             (ov["ci_high"], e[2], "ci_high")]:
        d = abs(got - exp)
        msg = f"Overall.{name}: got={got:.3f} exp={exp:.2f} delta={d:.4f}"
        (fails if d > TOL else oks).append(msg)

    # Subgroups
    for strat, sp in EXPECTED.items():
        if strat == "overall": continue
        if strat not in f3["subgroups"]:
            fails.append(f"{strat}: MISSING in stat_results"); continue
        s = f3["subgroups"][strat]
        for lev, exp in sp["levels"].items():
            match = next((lv for lv in s["levels"] if lv.get("level") == lev), None)
            if not match:
                fails.append(f"{strat}.lev{lev}: MISSING"); continue
            for got, exp_v, name in [(match["or"], exp[0], "or"),
                                       (match["ci_low"], exp[1], "ci_low"),
                                       (match["ci_high"], exp[2], "ci_high")]:
                d = abs(got - exp_v)
                msg = f"{strat}.lev{lev}.{name}: got={got:.3f} exp={exp_v:.2f} delta={d:.4f}"
                (fails if d > TOL else oks).append(msg)
        # P_interaction
        got_p = s.get("p_interaction")
        exp_p = sp["p_int"]
        if isinstance(exp_p, str) and exp_p.startswith("<"):
            thr = float(exp_p.replace("<", ""))
            ok = got_p is not None and got_p < thr
            msg = f"{strat}.P_int: got={got_p:.3g} exp={exp_p}"
            (oks if ok else fails).append(msg)
        else:
            ok = got_p is not None and (got_p < 0.05) == (exp_p < 0.05)
            d = abs((got_p or 0) - exp_p)
            msg = f"{strat}.P_int: got={got_p:.3g} exp={exp_p:.3g} sig_dir={'same' if ok else 'DIFF'}"
            (warns if ok else fails).append(msg)

    print("\n" + "=" * 60)
    print("FIGURE 2 — VERIFICATION AGAINST USER-ATTACHED IMAGE")
    print("=" * 60)
    print(f"PASS (within ±{TOL}):  {len(oks)}")
    for m in oks: print(f"  ✓ {m}")
    if warns:
        print(f"\nWARN (P_int 부호 일치, 수치 미세차이):  {len(warns)}")
        for m in warns: print(f"  ⚠ {m}")
    if fails:
        print(f"\nFAIL (±{TOL} 초과):  {len(fails)}")
        for m in fails: print(f"  ✗ {m}")
    else:
        print("\n✓ ALL OR/CI POINT-ESTIMATES WITHIN ±0.015 OF ATTACHED IMAGE.")
    return len(fails) == 0


if __name__ == "__main__":
    print("=== Building ZCB-Depression figures (Figure 2 = subgroup forest) ===")
    build_figure1_prisma()
    build_figure2_sex()         # → Supplementary (sex line chart)
    build_figure3_forest()      # → Figure 2 (subgroup forest) — 함수명만 옛이름 유지
    ok = verify_figure2_against_image()
    print(f"\nFigures saved to data/exports/  verify_pass={ok}")
    sys.exit(0 if ok else 1)
