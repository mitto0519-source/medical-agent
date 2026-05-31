"""STATA v2.4 INTEGRATED 코드 그대로 — raw KYRBS 2025 .sav 직접 읽고 STATA 변수명/코딩 정확히 재현."""
from __future__ import annotations
import io, json, os, sys, time
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, ".")
from src.config.env import bootstrap; bootstrap()

import numpy as np
import pandas as pd
import pyreadstat
import statsmodels.api as sm

t0 = time.time()

sav = Path("data/raw/kyrbs2025.sav")
print(f"[load] {sav}")
df, meta = pyreadstat.read_sav(str(sav))
df.columns = [c.lower() for c in df.columns]
print(f"  raw N = {len(df):,}")
print(f"  STATA variables present: F_ZERO={('f_zero' in df.columns)}, "
      f"M_SAD={('m_sad' in df.columns)}, e_s_rcrd={('e_s_rcrd' in df.columns)}, "
      f"e_ses={('e_ses' in df.columns)}, school={('school' in df.columns)}, "
      f"weight (w)={('w' in df.columns)}, strata={('strata' in df.columns)}, "
      f"cluster={('cluster' in df.columns)}")

raw_N = len(df)

# ── STEP 2: Sequential exclusion (STATA 코드 그대로) ──
e_counts = {}
def _drop_missing(mask, label):
    before = len(df_x)
    out = df_x[~mask].copy()
    e_counts[label] = before - len(out)
    return out

df_x = df.copy()
# 1) Missing F_ZERO
df_x = _drop_missing(df_x["f_zero"].isna(), "F_ZERO")
# 2) Missing M_SAD
df_x = _drop_missing(df_x["m_sad"].isna(), "M_SAD")
# 3) Missing sex
df_x = _drop_missing(df_x["sex"].isna(), "sex")
# 4) Missing age
df_x = _drop_missing(df_x["age"].isna(), "age")
# 5) Missing ht|wt
df_x = _drop_missing(df_x["ht"].isna() | df_x["wt"].isna(), "ht|wt")
# 6) Implausible BMI
bmi_tmp = df_x["wt"] / (df_x["ht"]/100)**2
df_x = _drop_missing((bmi_tmp < 10) | (bmi_tmp > 50), "implausible BMI")
# 7) Missing e_s_rcrd (academic)
df_x = _drop_missing(df_x["e_s_rcrd"].isna(), "e_s_rcrd")
# 8) Missing F_SWD_A or F_CAFF_A
df_x = _drop_missing(df_x["f_swd_a"].isna() | df_x["f_caff_a"].isna(), "SSB|caffeine")
# 9) Missing F_BR (breakfast)
df_x = _drop_missing(df_x["f_br"].isna(), "F_BR")
# 10) Missing pa_tot
df_x = _drop_missing(df_x["pa_tot"].isna(), "pa_tot")
# 11) Missing smartphone (both wd+wk)
df_x = _drop_missing(df_x["int_spwd_tm"].isna() & df_x["int_spwk_tm"].isna(), "smartphone")
# 12) Missing e_ses
df_x = _drop_missing(df_x["e_ses"].isna(), "e_ses")
# 13) Missing school
df_x = _drop_missing(df_x["school"].isna() | (df_x["school"].astype(str) == ""), "school")

n_final = len(df_x)
print(f"\n[exclusion] step counts:")
for k, v in e_counts.items():
    print(f"  -{k}: {v:,}")
print(f"  Final N = {n_final:,} (excluded {raw_N - n_final:,}, {(raw_N-n_final)/raw_N*100:.1f}%)")

# ── STEP 3-5: Variables (STATA 코드 그대로) ──
df_x["zero_freq"] = df_x["f_zero"].astype(float)
df_x["zero_cat"] = np.select(
    [df_x["f_zero"] == 1, df_x["f_zero"].between(2, 3),
     df_x["f_zero"].between(4, 5), df_x["f_zero"].between(6, 7)],
    [1, 2, 3, 4], default=np.nan)

# depression: M_SAD 1=No, 2=Yes → 0/1
df_x["depression"] = np.where(df_x["m_sad"] == 2, 1,
                       np.where(df_x["m_sad"] == 1, 0, np.nan))

# high_stress: m_str 1-2 → 1, 3-5 → 0
df_x["high_stress"] = np.select(
    [df_x.get("m_str", pd.Series([np.nan]*len(df_x))).between(1, 2),
     df_x.get("m_str", pd.Series([np.nan]*len(df_x))).between(3, 5)],
    [1, 0], default=np.nan)

# poor_sleep: m_slp_en 1-2 → 1, 3-5 → 0
df_x["poor_sleep"] = np.select(
    [df_x.get("m_slp_en", pd.Series([np.nan]*len(df_x))).between(1, 2),
     df_x.get("m_slp_en", pd.Series([np.nan]*len(df_x))).between(3, 5)],
    [1, 0], default=np.nan)

# Age cat
df_x["age_cat"] = np.select(
    [df_x["age"].between(12, 13), df_x["age"].between(14, 15), df_x["age"].between(16, 18)],
    [1, 2, 3], default=np.nan)

# BMI + bmi_cat (KCDC sex+age specific percentile)
df_x["bmi"] = df_x["wt"] / (df_x["ht"]/100)**2
P5 = {(1,12):15.16,(1,13):15.57,(1,14):16.06,(1,15):16.61,(1,16):17.13,(1,17):17.59,(1,18):17.93,
      (2,12):15.13,(2,13):15.71,(2,14):16.27,(2,15):16.74,(2,16):17.10,(2,17):17.32,(2,18):17.39}
P85 = {(1,12):21.81,(1,13):22.78,(1,14):23.74,(1,15):24.66,(1,16):25.43,(1,17):26.05,(1,18):26.51,
       (2,12):21.74,(2,13):22.27,(2,14):22.69,(2,15):23.03,(2,16):23.30,(2,17):23.45,(2,18):23.50}
def _bmi_cat(r):
    s, a, b = r["sex"], r["age"], r["bmi"]
    key = (int(s), int(a))
    p5, p85 = P5.get(key), P85.get(key)
    if p5 is None: return np.nan
    if b < p5: return 1
    if b < p85: return 2
    return 3
df_x["bmi_cat"] = df_x.apply(_bmi_cat, axis=1)

# School type
school_str = df_x["school"].astype(str)
df_x["school_n"] = np.where(school_str == "중학교", 1,
                       np.where(school_str.isin(["일반계고", "특성화계고"]), 2, np.nan))

# Academic
df_x["academic3"] = np.select(
    [df_x["e_s_rcrd"].between(1, 2), df_x["e_s_rcrd"] == 3, df_x["e_s_rcrd"].between(4, 5)],
    [1, 2, 3], default=np.nan)

# SES
df_x["ses3"] = np.select(
    [df_x["e_ses"].between(1, 2), df_x["e_ses"] == 3, df_x["e_ses"].between(4, 5)],
    [1, 2, 3], default=np.nan)

# Ever smoker (tc_lt 2 OR tc_ec_lt 2 OR tc_htp_lt 2)
df_x["ever_smoker"] = np.where(
    (df_x.get("tc_lt") == 2) | (df_x.get("tc_ec_lt") == 2) | (df_x.get("tc_htp_lt") == 2), 1, 0)

# Ever drinker
df_x["ever_drinker"] = np.where(df_x.get("ac_lt") == 2, 1,
                          np.where(df_x.get("ac_lt") == 1, 0, np.nan))

# Breakfast skipper (F_BR 1-3 = skipper)
df_x["br_skip"] = np.where(df_x["f_br"].between(1, 3), 1, 0)

# PA cat (pa_tot - 1 → days/wk; 0-2=Low, 3-4=Mod, 5-7=High)
df_x["pa_days"] = df_x["pa_tot"] - 1
df_x["pa_cat"] = np.select(
    [df_x["pa_days"].between(0, 2), df_x["pa_days"].between(3, 4),
     df_x["pa_days"].between(5, 7)],
    [1, 2, 3], default=np.nan)

# SSB cat
df_x["swd_freq3"] = np.select(
    [df_x["f_swd_a"].between(1, 2), df_x["f_swd_a"].between(3, 5),
     df_x["f_swd_a"].between(6, 7)],
    [1, 2, 3], default=np.nan)

# Caffeine cat
df_x["caff_freq3"] = np.select(
    [df_x["f_caff_a"].between(1, 2), df_x["f_caff_a"].between(3, 5),
     df_x["f_caff_a"].between(6, 7)],
    [1, 2, 3], default=np.nan)

# Smartphone min (weighted weekly avg)
df_x["smartphone_min"] = np.where(
    df_x["int_spwd_tm"].notna() & df_x["int_spwk_tm"].notna(),
    (df_x["int_spwd_tm"] * 5 + df_x["int_spwk_tm"] * 2) / 7,
    np.where(df_x["int_spwd_tm"].notna(), df_x["int_spwd_tm"],
             df_x["int_spwk_tm"]))

# ── Complete-case flag ──
needvars = ["depression", "zero_freq", "zero_cat", "sex", "age_cat", "bmi_cat",
            "school_n", "academic3", "ses3", "ever_smoker", "ever_drinker",
            "swd_freq3", "caff_freq3", "smartphone_min", "pa_cat", "br_skip",
            "W"]
cc = df_x.copy()
for v in needvars:
    cc = cc[cc[v].notna()]
n_cc = len(cc)
print(f"\n[complete-case] N = {n_cc:,}")

# Smartphone tertile
cc["smartphone_tert"] = pd.qcut(cc["smartphone_min"], q=3, labels=[1, 2, 3]).astype(int)

# ── Dummies ──
def _dummies(d, col, ref, prefix=None):
    p = prefix or col
    out = pd.DataFrame(index=d.index)
    for v in sorted(d[col].dropna().unique()):
        v = int(v)
        if v == ref: continue
        out[f"{p}_{v}"] = (d[col] == v).astype(float)
    return out

dum_specs = [("sex", 1), ("age_cat", 1), ("bmi_cat", 2), ("school_n", 1),
             ("academic3", 1), ("ses3", 1), ("swd_freq3", 1), ("caff_freq3", 1),
             ("pa_cat", 1), ("zero_cat", 1), ("smartphone_tert", 1)]
for col, ref in dum_specs:
    cc = pd.concat([cc, _dummies(cc, col, ref)], axis=1)

cov_m1 = ["sex_2", "age_cat_2", "age_cat_3", "school_n_2",
          "academic3_2", "academic3_3", "ses3_2", "ses3_3"]
cov_m2 = cov_m1 + ["bmi_cat_1", "bmi_cat_3", "ever_smoker", "ever_drinker",
                    "swd_freq3_2", "swd_freq3_3", "caff_freq3_2", "caff_freq3_3",
                    "pa_cat_2", "pa_cat_3", "br_skip"]
cov_m1 = [c for c in cov_m1 if c in cc.columns]
cov_m2 = [c for c in cov_m2 if c in cc.columns]

# ── Fit helper (survey-weighted Binomial GLM → Stata svy:logistic 등가) ──
# KYRBS .sav의 `W` 컬럼은 sample weight (mean ≈ 48.8). 미적용 시 작은 subgroup에서
# 추정치가 unweighted로 편향 → 이미지(svy)와 ±0.02 이상 차이가 남.
# GLM Binomial + freq_weights = Stata pweight 등가 (Korn-Graubard SE는 미지원이나
# cluster-robust SE로 svy linearized SE의 근사를 얻음).
def _fit(y, X_cols, data):
    sub = data[[y] + X_cols].dropna().copy()
    if "W" in data.columns:
        w = data.loc[sub.index, "W"].astype(float)
        # weight 결측은 1.0으로 (분석 모집단 유지)
        w = w.fillna(1.0).clip(lower=1e-6)
    else:
        w = None
    X = sm.add_constant(sub[X_cols].astype(float))
    yv = sub[y].astype(float)
    try:
        if w is not None:
            m = sm.GLM(yv, X, family=sm.families.Binomial(),
                       freq_weights=w.values).fit(disp=0, maxiter=300)
            if "cluster" in data.columns:
                cl = data.loc[sub.index, "cluster"].astype(float)
                m2 = sm.GLM(yv, X, family=sm.families.Binomial(),
                             freq_weights=w.values).fit(
                                disp=0, maxiter=300,
                                cov_type="cluster", cov_kwds={"groups": cl.values})
                return m2
            return m
        if "cluster" in data.columns:
            cl = data.loc[sub.index, "cluster"].astype(float)
            return sm.Logit(yv, X).fit(disp=0, maxiter=300,
                cov_type="cluster", cov_kwds={"groups": cl.values})
        return sm.Logit(yv, X).fit(disp=0, maxiter=300)
    except Exception as e:
        print(f"  fit fail ({y}): {e}")
        return None

def _or(m, v):
    if m is None or v not in m.params: return None
    b, se = m.params[v], m.bse[v]
    return {"or": float(np.exp(b)), "ci_low": float(np.exp(b - 1.96*se)),
            "ci_high": float(np.exp(b + 1.96*se)), "p": float(m.pvalues[v])}

# ── Table 2 ──
zc = ["zero_cat_2", "zero_cat_3", "zero_cat_4"]
m1 = _fit("depression", zc + cov_m1, cc)
m2 = _fit("depression", zc + cov_m2, cc)
m1_tr = _fit("depression", ["zero_freq"] + cov_m1, cc)
m2_tr = _fit("depression", ["zero_freq"] + cov_m2, cc)

print(f"\n[Table 2] aOR by zero_cat:")
print(f"           Model 1                       Model 2")
for v, lab in zip(zc, ["<=2/wk", "3-6/wk", ">=1/day"]):
    r1, r2 = _or(m1, v), _or(m2, v)
    print(f"  {lab:>10}: {r1['or']:.2f} ({r1['ci_low']:.2f}-{r1['ci_high']:.2f})    "
          f"{r2['or']:.2f} ({r2['ci_low']:.2f}-{r2['ci_high']:.2f})")
print(f"  P_trend M1={m1_tr.pvalues['zero_freq']:.2e}, M2={m2_tr.pvalues['zero_freq']:.2e}")

# ── Table 3: Sex-stratified ──
print(f"\n[Table 3] Sex-stratified:")
results = {"raw_N": raw_N, "final_N": n_cc, "exclusion": e_counts,
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S")}
results["Table_2"] = {
    "Model_1": {v: _or(m1, v) for v in zc},
    "Model_2": {v: _or(m2, v) for v in zc},
    "p_trend_M1": float(m1_tr.pvalues["zero_freq"]) if m1_tr else None,
    "p_trend_M2": float(m2_tr.pvalues["zero_freq"]) if m2_tr else None,
}

cov_s = [c for c in cov_m2 if c != "sex_2"]   # sex 빼고
sex_results = {}
for sex_val, label in [(1, "Male"), (2, "Female")]:
    sub = cc[cc["sex"] == sex_val].copy()
    m = _fit("depression", zc + cov_s, sub)
    mt = _fit("depression", ["zero_freq"] + cov_s, sub)
    sex_results[label] = {v: _or(m, v) for v in zc}
    sex_results[label]["p_trend"] = float(mt.pvalues["zero_freq"]) if mt else None
    print(f"  {label} (n={len(sub):,}):")
    for v, lab in zip(zc, ["<=2/wk", "3-6/wk", ">=1/day"]):
        r = _or(m, v)
        if r: print(f"    {lab:>10}: {r['or']:.2f} ({r['ci_low']:.2f}-{r['ci_high']:.2f}), p={r['p']:.3g}")
    print(f"    P_trend = {sex_results[label]['p_trend']:.3g}")

# Sex × zero_freq interaction
cc["zf_x_sex2"] = cc["zero_freq"] * cc["sex_2"]
m_int = _fit("depression", ["zero_freq", "sex_2", "zf_x_sex2"] + cov_s, cc)
p_sex_int = float(m_int.pvalues["zf_x_sex2"]) if m_int else None
print(f"  P_interaction (sex × zero_freq) = {p_sex_int:.3g}")
results["Table_3"] = {**sex_results, "p_interaction_sex": p_sex_int}

# ── Supp Table 1: stress, sleep ──
print(f"\n[Supp Table 1]:")
supp = {}
for out_col, lab in [("high_stress", "stress"), ("poor_sleep", "sleep")]:
    sub = cc[cc[out_col].notna()].copy()
    m = _fit(out_col, zc + cov_m2, sub)
    mt = _fit(out_col, ["zero_freq"] + cov_m2, sub)
    supp[lab] = {v: _or(m, v) for v in zc}
    supp[lab]["p_trend"] = float(mt.pvalues["zero_freq"]) if mt else None
    print(f"  {lab}:")
    for v, vlab in zip(zc, ["<=2/wk", "3-6/wk", ">=1/day"]):
        r = _or(m, v)
        if r: print(f"    {vlab:>10}: {r['or']:.2f} ({r['ci_low']:.2f}-{r['ci_high']:.2f})")
    print(f"    P_trend = {supp[lab]['p_trend']:.3g}")
results["Supp_Table_1"] = supp

# ── Figure 3: 7 subgroup × interaction ──
print(f"\n[Figure 3] Subgroup analysis:")
overall = _fit("depression", ["zero_freq"] + cov_m2, cc)
overall_or = _or(overall, "zero_freq")
print(f"  Overall: aOR per 1-level = {overall_or['or']:.3f} ({overall_or['ci_low']:.3f}-{overall_or['ci_high']:.3f})")

fig3 = {"overall": overall_or, "subgroups": {}}

SUBGROUPS = [
    ("sex",             [1, 2],       [c for c in cov_m2 if c != "sex_2"]),
    ("age_cat",         [1, 2, 3],    [c for c in cov_m2 if not c.startswith("age_cat_")]),
    ("bmi_cat",         [1, 2, 3],    [c for c in cov_m2 if not c.startswith("bmi_cat_")]),
    ("ses3",            [1, 2, 3],    [c for c in cov_m2 if not c.startswith("ses3_")]),
    ("academic3",       [1, 2, 3],    [c for c in cov_m2 if not c.startswith("academic3_")]),
]

from scipy import stats as _st
for col, levels, cov_set in SUBGROUPS:
    print(f"  {col}:")
    lvls = []
    for lev in levels:
        sub = cc[cc[col] == lev].copy()
        if len(sub) < 200:
            lvls.append({"level": lev, "n": int(len(sub)), "or": None})
            print(f"    level {lev}: n={len(sub):,} (skip - too small)")
            continue
        cov_use = [c for c in cov_set if c in sub.columns]
        m_l = _fit("depression", ["zero_freq"] + cov_use, sub)
        or_l = _or(m_l, "zero_freq")
        lvls.append({"level": lev, "n": int(len(sub)), **(or_l or {})})
        if or_l:
            print(f"    level {lev}: aOR={or_l['or']:.3f} ({or_l['ci_low']:.3f}-{or_l['ci_high']:.3f}), n={len(sub):,}")

    # P_interaction (Wald test)
    strat_dums, inter_cols = [], []
    for lev in levels[1:]:
        dum = f"{col}_{int(lev)}"
        if dum in cc.columns:
            strat_dums.append(dum)
            inter = f"zf_x_{dum}"
            cc[inter] = cc["zero_freq"] * cc[dum]
            inter_cols.append(inter)
    cov_use = [c for c in cov_set if c in cc.columns]
    full = _fit("depression", ["zero_freq"] + strat_dums + inter_cols + cov_use, cc)
    p_int = None
    if full is not None and all(c in full.params for c in inter_cols):
        try:
            R = np.zeros((len(inter_cols), len(full.params)))
            for i, c in enumerate(inter_cols):
                R[i, list(full.params.index).index(c)] = 1
            beta = full.params.values; cov_b = full.cov_params().values
            wald = beta @ R.T @ np.linalg.inv(R @ cov_b @ R.T) @ R @ beta
            p_int = float(1 - _st.chi2.cdf(wald, df=len(inter_cols)))
        except Exception as e:
            print(f"    Wald fail: {e}")
    print(f"    P_interaction = {p_int}")
    fig3["subgroups"][col] = {"levels": lvls, "p_interaction": p_int}

results["Figure_3"] = fig3

# Save
out = Path("data/exports/stat_results.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nsaved: {out}  elapsed: {time.time()-t0:.1f}s")
