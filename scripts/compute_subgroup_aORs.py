"""Stata v2.4 STEP 13 — 7개 stratifier × 각 레벨의 subgroup aOR(per 1-level ZCB) 계산.

Stata `svy: logistic depression c.zero_freq [covariates]`을
Python statsmodels GLM(binomial) + freq_weights(pweight) + cluster-robust SE로 재현.
점추정은 Stata svy와 동일, SE는 Taylor linearization 차이로 ±수% 가능 (paper-grade).

출력: data/exports/Figure3_subgroup_aORs.json (build_paper_figures가 읽어 Figure 3 채움).
"""
from __future__ import annotations
import io, json, sys, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import pyreadstat
import statsmodels.api as sm
import statsmodels.formula.api as smf

DATA = "data/raw/kyrbs2025.sav"
OUT = Path("data/exports/Figure3_subgroup_aORs.json")


# ── Stata STEP 3-6 변수 빌드 ─────────────────────────────────────────────────

# 2017 KCDC growth chart cutoffs (Stata 코드와 동일)
BMI_P5 = {  # (sex, age) -> p5
    (1, 12): 15.16, (1, 13): 15.57, (1, 14): 16.06, (1, 15): 16.61,
    (1, 16): 17.13, (1, 17): 17.59, (1, 18): 17.93,
    (2, 12): 15.13, (2, 13): 15.71, (2, 14): 16.27, (2, 15): 16.74,
    (2, 16): 17.10, (2, 17): 17.32, (2, 18): 17.39,
}
BMI_P85 = {
    (1, 12): 21.81, (1, 13): 22.78, (1, 14): 23.74, (1, 15): 24.66,
    (1, 16): 25.43, (1, 17): 26.05, (1, 18): 26.51,
    (2, 12): 21.74, (2, 13): 22.27, (2, 14): 22.69, (2, 15): 23.03,
    (2, 16): 23.30, (2, 17): 23.45, (2, 18): 23.50,
}


def build_dataset() -> pd.DataFrame:
    df, _ = pyreadstat.read_sav(DATA)
    # 대문자 매칭 헬퍼
    cu = {c.upper(): c for c in df.columns}
    def col(name):
        return df[cu[name.upper()]]

    # Exposure
    df["zero_freq"] = pd.to_numeric(col("F_ZERO"), errors="coerce")
    df["zero_cat"] = pd.cut(df["zero_freq"], bins=[0, 1, 3, 5, 7],
                            labels=[1, 2, 3, 4]).astype("float")

    # Primary outcome: depression (M_SAD: 1=No → 0, 2=Yes → 1)
    msad = pd.to_numeric(col("M_SAD"), errors="coerce")
    df["depression"] = np.where(msad == 2, 1, np.where(msad == 1, 0, np.nan))

    # Sex / age
    df["sex"] = pd.to_numeric(col("sex"), errors="coerce")
    df["age"] = pd.to_numeric(col("age"), errors="coerce")
    df["age_cat"] = pd.cut(df["age"], bins=[11, 13, 15, 18], labels=[1, 2, 3]).astype("float")

    # Height/weight + BMI
    ht = pd.to_numeric(col("HT"), errors="coerce")
    wt = pd.to_numeric(col("WT"), errors="coerce")
    df["bmi"] = wt / (ht / 100) ** 2
    df.loc[(df["bmi"] < 10) | (df["bmi"] > 50), "bmi"] = np.nan
    # bmi_cat by sex+age via lookup
    def bmi_cat_row(r):
        if pd.isna(r["bmi"]) or pd.isna(r["sex"]) or pd.isna(r["age"]):
            return np.nan
        key = (int(r["sex"]), int(r["age"]))
        if key not in BMI_P5:
            return np.nan
        if r["bmi"] < BMI_P5[key]:
            return 1
        if r["bmi"] < BMI_P85[key]:
            return 2
        return 3
    df["bmi_cat"] = df.apply(bmi_cat_row, axis=1)

    # Academic (E_S_RCRD: 1-2 High, 3 Mid, 4-5 Low)
    esr = pd.to_numeric(col("E_S_RCRD"), errors="coerce")
    df["academic3"] = np.where(esr.isin([1, 2]), 1,
                       np.where(esr == 3, 2,
                       np.where(esr.isin([4, 5]), 3, np.nan)))

    # SES (E_SES: 1-2 High, 3 Mid, 4-5 Low)
    ses = pd.to_numeric(col("E_SES"), errors="coerce")
    df["ses3"] = np.where(ses.isin([1, 2]), 1,
                  np.where(ses == 3, 2,
                  np.where(ses.isin([4, 5]), 3, np.nan)))

    # School type
    school = col("SCHOOL").astype(str)
    df["school_n"] = np.where(school.str.contains("중학교"), 1,
                       np.where(school.str.contains("일반계고|특성화계고"), 2, np.nan))

    # Smoker (any of tc_lt, tc_ec_lt, tc_htp_lt == 2)
    tc = pd.to_numeric(col("TC_LT"), errors="coerce")
    tcec = pd.to_numeric(col("TC_EC_LT"), errors="coerce")
    tchtp = pd.to_numeric(col("TC_HTP_LT"), errors="coerce")
    smoker_any = ((tc == 2) | (tcec == 2) | (tchtp == 2))
    smoker_none = ((tc.isin([1]) | tc.isna()) &
                   (tcec.isin([1]) | tcec.isna()) &
                   (tchtp.isin([1]) | tchtp.isna()) &
                   ~(tc.isna() & tcec.isna() & tchtp.isna()))
    df["ever_smoker"] = np.where(smoker_any, 1, np.where(smoker_none, 0, np.nan))

    # Drinker
    ac = pd.to_numeric(col("AC_LT"), errors="coerce")
    df["ever_drinker"] = np.where(ac == 2, 1, np.where(ac == 1, 0, np.nan))

    # Breakfast (F_BR 1-3 = skipper, 4-8 = regular)
    fbr = pd.to_numeric(col("F_BR"), errors="coerce")
    df["br_skip"] = np.where(fbr.between(1, 3), 1,
                       np.where(fbr.between(4, 8), 0, np.nan))

    # PA (pa_tot - 1; cat 1=0-2, 2=3-4, 3=5-7)
    pa = pd.to_numeric(col("PA_TOT"), errors="coerce") - 1
    pa = pa.where((pa >= 0) & (pa <= 7))
    df["pa_cat"] = np.where(pa.between(0, 2), 1,
                      np.where(pa.between(3, 4), 2,
                      np.where(pa.between(5, 7), 3, np.nan)))

    # SSB, caffeine (3-cat: 1-2=<1/wk, 3-5=weekly, 6-7=daily)
    swd = pd.to_numeric(col("F_SWD_A"), errors="coerce")
    df["swd_freq3"] = np.where(swd.between(1, 2), 1,
                         np.where(swd.between(3, 5), 2,
                         np.where(swd.between(6, 7), 3, np.nan)))
    caf = pd.to_numeric(col("F_CAFF_A"), errors="coerce")
    df["caff_freq3"] = np.where(caf.between(1, 2), 1,
                          np.where(caf.between(3, 5), 2,
                          np.where(caf.between(6, 7), 3, np.nan)))

    # Smartphone (weighted weekly avg)
    spwd = pd.to_numeric(col("INT_SPWD_TM"), errors="coerce")
    spwk = pd.to_numeric(col("INT_SPWK_TM"), errors="coerce")
    df["smartphone_min"] = np.where(spwd.notna() & spwk.notna(), (spwd*5 + spwk*2)/7,
                              np.where(spwd.notna(), spwd, spwk))

    # Survey design
    df["w"] = pd.to_numeric(col("w"), errors="coerce")
    df["strata"] = pd.to_numeric(col("strata"), errors="coerce")
    df["cluster"] = pd.to_numeric(col("cluster"), errors="coerce")

    # Complete-case
    needvars = ["depression", "zero_freq", "sex", "age_cat", "bmi_cat", "school_n",
                "academic3", "ses3", "ever_smoker", "ever_drinker", "swd_freq3",
                "caff_freq3", "smartphone_min", "pa_cat", "br_skip", "w", "cluster"]
    cc = df.dropna(subset=needvars).copy()
    # Smartphone tertile
    cc["smartphone_tert"] = pd.qcut(cc["smartphone_min"], q=3, labels=[1, 2, 3]).astype("float")
    return cc


# ── Subgroup logistic with cluster SE + pweight ──────────────────────────────

def subgroup_aOR(df: pd.DataFrame, subset_mask, cov_list: list) -> tuple:
    """반환: (aOR, ci_lo, ci_hi, n, p)"""
    d = df.loc[subset_mask].copy()
    if len(d) < 50:
        return (None, None, None, len(d), None)
    formula = "depression ~ zero_freq + " + " + ".join(f"C({c})" for c in cov_list)
    try:
        model = smf.glm(formula, data=d, family=sm.families.Binomial(),
                        freq_weights=d["w"])
        res = model.fit(cov_type="cluster", cov_kwds={"groups": d["cluster"]})
        beta = res.params["zero_freq"]
        se = res.bse["zero_freq"]
        p = res.pvalues["zero_freq"]
        aOR = float(np.exp(beta))
        lo = float(np.exp(beta - 1.96 * se))
        hi = float(np.exp(beta + 1.96 * se))
        return (aOR, lo, hi, len(d), float(p))
    except Exception as e:
        return (None, None, None, len(d), f"ERR: {e}")


def main():
    print("KYRBS 2025 로드 + 변수 빌드 …")
    df = build_dataset()
    print(f"  complete-case n = {len(df):,}")

    # 전체 covariate 세트
    all_cov = ["sex", "age_cat", "bmi_cat", "ses3", "school_n", "academic3",
               "ever_smoker", "ever_drinker", "swd_freq3", "caff_freq3",
               "pa_cat", "br_skip"]

    results = {}

    # Overall (per 1-level, full model)
    aOR, lo, hi, n, p = subgroup_aOR(df, df.index == df.index, all_cov)
    results["overall"] = {"label": "All adolescents", "aOR": aOR, "lo": lo, "hi": hi, "n": n, "p": p}
    print(f"  Overall: aOR={aOR:.3f} ({lo:.3f}-{hi:.3f}) n={n:,}")

    # 7 stratifiers × levels — 각 stratum 모델은 그 stratifier 제외
    strata_def = [
        ("age",       "age_cat",         [1, 2, 3], ["12-13 yr", "14-15 yr", "16-18 yr"]),
        ("bmi",       "bmi_cat",         [1, 2, 3], ["Underweight", "Normal", "Overweight/Obese"]),
        ("ses",       "ses3",            [1, 2, 3], ["High", "Middle", "Low"]),
        ("aca",       "academic3",       [1, 2, 3], ["High", "Middle", "Low"]),
        ("sm",        "smartphone_tert", [1, 2, 3], ["Low (T1)", "Mid (T2)", "High (T3)"]),
        ("pa",        "pa_cat",          [1, 2, 3], ["Low (0-2 d/wk)", "Moderate (3-4)", "High (≥5)"]),
        ("br",        "br_skip",         [0, 1],    ["Non-skipper", "Skipper"]),
    ]

    for key, var, lvls, labels in strata_def:
        cov = [c for c in all_cov if c != var]  # stratifier 자체는 모델에서 제외
        for lvl, lbl in zip(lvls, labels):
            mask = (df[var] == lvl)
            aOR, lo, hi, n, p = subgroup_aOR(df, mask, cov)
            results[f"{key}_{lvl}"] = {"label": lbl, "aOR": aOR, "lo": lo, "hi": hi, "n": n, "p": p}
            print(f"  {key}_{lvl} ({lbl[:18]:18}): aOR={aOR:.3f} ({lo:.3f}-{hi:.3f}) n={n:,}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 → {OUT}")


if __name__ == "__main__":
    main()
