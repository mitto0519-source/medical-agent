"""STATA v2.4 INTEGRATED  Python으로 그대로 재현 — 실제 KYRBS 2025로 산출.

흐름 (STATA 코드 STEP 그대로):
  STEP 0-2: KYRBS 2025 로드 + 13-step exclusion → final N
  STEP 3-6: exposure (zero_cat 4-cat) + depression + 12 covariate + complete-case
  STEP 7  : survey design (pweight + strata + cluster)
  STEP 8  : Table 1 baseline by zero_cat (요약)
  STEP 9  : Table 2 Crude/M1/M2 aOR + P_trend
  STEP 10 : Table 3 sex-stratified + sex × zero_freq interaction
  STEP 12 : Supp Table 1 stress + sleep
  STEP 13 : 7 subgroup × interaction → Figure 3 forest plot 데이터

출력: data/exports/stat_results.json (모든 추정값) + 콘솔 요약.
"""
from __future__ import annotations
import io, json, os, sys, time
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, "/app" if Path("/app").exists() else ".")
from src.config.env import bootstrap
bootstrap()

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.iolib.smpickle import save_pickle

t_start = time.time()

# ── STEP 0: KYRBS 2025 로드 ──────────────────────────────────────────────
from src.data.kyrbs_raw_loader import KYRBSLoader

sav_candidates = [
    Path("/app/data/raw/kyrbs2025.sav"),
    Path("data/raw/kyrbs2025.sav"),
]
sav = next((p for p in sav_candidates if p.exists()), None)
if sav is None:
    print("ERROR: kyrbs2025.sav not found in /app/data/raw or data/raw")
    sys.exit(1)

print(f"[STEP 0] Loading {sav}...")
df_raw, _meta = KYRBSLoader().load(sav)
raw_N = len(df_raw)
print(f"   loaded raw N = {raw_N:,}")
print(f"   columns sample: {list(df_raw.columns)[:30]}")

# ── STEP 3-6: 변수 ... + complete-case ... ──
# KYRBSLoader가 이미 표준화한 ... — 어떤 변수가 매핑됐는지 ...
mapped = sorted(c for c in df_raw.columns if not c.startswith("_"))
print(f"   total columns: {len(df_raw.columns)}, sample: {mapped[:25]}")

# STATA 코드 ... (loader ...)
# F_ZERO → zero_freq → zero_cat (4-level)
# M_SAD → depression
# sex / age → age_cat
# ht / wt → bmi / bmi_cat
# e_s_rcrd → academic3
# e_ses → ses3
# school → school_n
# tc_lt|tc_ec_lt|tc_htp_lt → ever_smoker
# ac_lt → ever_drinker
# F_SWD_A → swd_freq3
# F_CAFF_A → caff_freq3
# F_BR → br_skip
# pa_tot → pa_cat
# int_spwd_tm + int_spwk_tm → smartphone_min

# 변수명 ... — loader가 어떤 이름으로 표준화했는지 정확히 확인
# loader가 알아낸 표준 변수 ... 양식: depression, zcb_freq, ssb_freq, screen_time, smoking, ...
print()
print("[STEP 1-2] Variable mapping check:")
expected = ["zcb_freq", "depression", "stress", "insufficient_sleep",
            "sex", "age", "bmi", "smoking", "alcohol",
            "physical_act", "screen_time", "breakfast", "family_econ",
            "school_type", "academic_perf",
            "weight_var", "strata", "cluster"]
for v in expected:
    flag = "OK" if v in df_raw.columns else "MISS"
    print(f"   {flag:4s} {v}")

# ── ... ──
# Outcome
if "depression" not in df_raw.columns:
    print("ERROR: 'depression' column missing")
    sys.exit(1)
df = df_raw.copy()

# Exposure: zcb_freq (raw 1-7) → zero_cat 4 level
if "zcb_freq" not in df.columns:
    print("ERROR: 'zcb_freq' column missing")
    sys.exit(1)
zf = pd.to_numeric(df["zcb_freq"], errors="coerce")
df["zero_freq"] = zf
df["zero_cat"] = pd.cut(zf, bins=[-0.5, 1.5, 3.5, 5.5, 8],
                         labels=[1, 2, 3, 4]).astype("Int64")

# Depression: M_SAD 1=No, 2=Yes → 0/1
dep = pd.to_numeric(df["depression"], errors="coerce")
unique_dep = sorted(dep.dropna().unique())
print(f"\n[STEP 4] depression raw values: {unique_dep[:6]}")
# StatBridge ... 자동 binarize ... — ...
if set(unique_dep) <= {0.0, 1.0}:
    df["dep01"] = dep
else:
    # ... (1=No, 2=Yes) → max ... 1
    pos = max(unique_dep)
    df["dep01"] = (dep == pos).astype(float)
print(f"   binarized: 0={(df['dep01']==0).sum():,}, 1={(df['dep01']==1).sum():,}")

# ... — STATA ...
# Age cat (12-13, 14-15, 16-18)
age_raw = pd.to_numeric(df.get("age"), errors="coerce")
df["age_cat"] = pd.cut(age_raw, bins=[11.5, 13.5, 15.5, 18.5],
                        labels=[1, 2, 3]).astype("Int64")

# BMI cat (under, normal, over) — KCDC ...
bmi_raw = pd.to_numeric(df.get("bmi"), errors="coerce")
# ... — ...
bmi_p5_table = {  # (sex, age): p5
    (1, 12): 15.16, (1, 13): 15.57, (1, 14): 16.06, (1, 15): 16.61,
    (1, 16): 17.13, (1, 17): 17.59, (1, 18): 17.93,
    (2, 12): 15.13, (2, 13): 15.71, (2, 14): 16.27, (2, 15): 16.74,
    (2, 16): 17.10, (2, 17): 17.32, (2, 18): 17.39,
}
bmi_p85_table = {
    (1, 12): 21.81, (1, 13): 22.78, (1, 14): 23.74, (1, 15): 24.66,
    (1, 16): 25.43, (1, 17): 26.05, (1, 18): 26.51,
    (2, 12): 21.74, (2, 13): 22.27, (2, 14): 22.69, (2, 15): 23.03,
    (2, 16): 23.30, (2, 17): 23.45, (2, 18): 23.50,
}
sex_int = pd.to_numeric(df.get("sex"), errors="coerce").astype("Int64")
age_int = pd.to_numeric(df.get("age"), errors="coerce").astype("Int64")
def _bmi_cat(row):
    b, s, a = row["bmi"], row["sex"], row["age"]
    if pd.isna(b) or pd.isna(s) or pd.isna(a):
        return np.nan
    key = (int(s), int(a))
    p5 = bmi_p5_table.get(key); p85 = bmi_p85_table.get(key)
    if p5 is None or p85 is None or b < 10 or b > 50:
        return np.nan
    if b < p5: return 1
    if b < p85: return 2
    return 3
df["bmi_cat"] = df.apply(_bmi_cat, axis=1).astype("Int64")

# ... (3 level)
def _to3(s, lo_map):
    """lo_map: {'1,2': 1, '3': 2, '4,5': 3} 같은 ..."""
    r = pd.to_numeric(s, errors="coerce")
    return r

# School type
if "school_type" in df.columns:
    s_raw = df["school_type"].astype(str)
    df["school_n"] = np.where(s_raw.str.contains("중", na=False), 1,
                       np.where(s_raw.str.contains("고", na=False), 2, np.nan))
else:
    df["school_n"] = np.nan

# Academic performance (e_s_rcrd 1-5) → high/middle/low
if "academic_perf" in df.columns:
    ap = pd.to_numeric(df["academic_perf"], errors="coerce")
    df["academic3"] = np.select(
        [ap.between(1, 2), ap == 3, ap.between(4, 5)],
        [1, 2, 3], default=np.nan)
else:
    df["academic3"] = np.nan

# SES (e_ses 1-5) → high/middle/low
if "family_econ" in df.columns:
    se = pd.to_numeric(df["family_econ"], errors="coerce")
    df["ses3"] = np.select(
        [se.between(1, 2), se == 3, se.between(4, 5)],
        [1, 2, 3], default=np.nan)
else:
    df["ses3"] = np.nan

# Ever smoker / drinker
df["ever_smoker"] = pd.to_numeric(df.get("smoking"), errors="coerce")
df["ever_drinker"] = pd.to_numeric(df.get("alcohol"), errors="coerce")

# SSB freq3, caffeine freq3 (1-7 raw → 3 cat)
def _bev3(c):
    r = pd.to_numeric(c, errors="coerce")
    return np.select([r.between(1, 2), r.between(3, 5), r.between(6, 7)],
                     [1, 2, 3], default=np.nan)
df["swd_freq3"]  = _bev3(df.get("ssb_freq", pd.Series([np.nan]*len(df))))
df["caff_freq3"] = _bev3(df.get("caffeine_freq", pd.Series([np.nan]*len(df))))

# PA cat
if "physical_act" in df.columns:
    pa = pd.to_numeric(df["physical_act"], errors="coerce")
    df["pa_cat"] = np.select(
        [pa.between(0, 2), pa.between(3, 4), pa.between(5, 7)],
        [1, 2, 3], default=np.nan)
else:
    df["pa_cat"] = np.nan

# Breakfast skip
if "breakfast" in df.columns:
    br = pd.to_numeric(df["breakfast"], errors="coerce")
    df["br_skip"] = (br <= 3).astype(int)
else:
    df["br_skip"] = np.nan

# Smartphone minutes (loader가 ... screen_time ...)
df["smartphone_min"] = pd.to_numeric(df.get("screen_time"), errors="coerce")

# Stress, sleep (양식 ...)
df["high_stress"] = pd.to_numeric(df.get("stress"), errors="coerce")
df["poor_sleep"] = pd.to_numeric(df.get("insufficient_sleep"), errors="coerce")

# ── STEP 6: complete-case flag ──
needvars = ["dep01", "zero_freq", "zero_cat", "sex", "age_cat", "bmi_cat",
            "school_n", "academic3", "ses3", "ever_smoker", "ever_drinker",
            "swd_freq3", "caff_freq3", "smartphone_min", "pa_cat", "br_skip"]

cc_mask = pd.Series(True, index=df.index)
for v in needvars:
    if v not in df.columns:
        print(f"   WARN missing column: {v}")
        continue
    cc_mask &= df[v].notna()
df_cc = df.loc[cc_mask].copy()
print(f"\n[STEP 6] Complete-case sample: N = {len(df_cc):,} (raw {raw_N:,}, excluded {raw_N - len(df_cc):,})")

# Smartphone tertile
df_cc["smartphone_tert"] = pd.qcut(df_cc["smartphone_min"], q=3, labels=[1, 2, 3])

# ── STEP 9: Table 2 — Crude / M1 / M2 logistic regression ──
print(f"\n[STEP 9] Table 2 analysis (continuous zero_freq + 4-cat zero_cat)...")

def _logit_with_results(y_col, X_cols, data, label=""):
    """logit regression — sm.Logit + robust SE (양식 ...)."""
    sub = data[[y_col] + X_cols].dropna().copy()
    y = sub[y_col].astype(float)
    X = sub[X_cols].astype(float)
    X = sm.add_constant(X)
    try:
        # cluster robust SE — STATA의 svy:logistic ...
        if "cluster" in data.columns:
            clust = data.loc[sub.index, "cluster"].astype("Int64").astype(float)
            model = sm.Logit(y, X).fit(disp=0, maxiter=200,
                                         cov_type="cluster",
                                         cov_kwds={"groups": clust.values})
        else:
            model = sm.Logit(y, X).fit(disp=0, maxiter=200)
    except Exception as e:
        print(f"   {label} fit fail: {e}")
        return None
    return model

# zero_cat 4-cat — dummy 양식 (ref=1=None)
def _add_cat_dummies(d, col, base=1, prefix=None):
    p = prefix or col
    out = pd.DataFrame(index=d.index)
    cats = sorted(d[col].dropna().unique())
    for c in cats:
        if c == base:
            continue
        out[f"{p}_{int(c)}"] = (d[col] == c).astype(float)
    return out

results = {"raw_N": raw_N, "final_N": int(len(df_cc))}
results["computed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

# Model 1 covariates: sex age_cat school_n academic3 ses3
cov_m1 = ["sex_2", "age_cat_2", "age_cat_3", "school_n_2",
          "academic3_2", "academic3_3", "ses3_2", "ses3_3"]
# Model 2 covariates: M1 + bmi_cat ever_smoker ever_drinker swd_freq3 caff_freq3 pa_cat br_skip
cov_m2_extra = ["bmi_cat_2", "bmi_cat_3", "ever_smoker", "ever_drinker",
                "swd_freq3_2", "swd_freq3_3", "caff_freq3_2", "caff_freq3_3",
                "pa_cat_2", "pa_cat_3", "br_skip"]

# build dummies once
d2 = df_cc.copy()
for c, base in [("sex", 1), ("age_cat", 1), ("school_n", 1), ("academic3", 1),
                ("ses3", 1), ("bmi_cat", 2), ("swd_freq3", 1), ("caff_freq3", 1),
                ("pa_cat", 1), ("zero_cat", 1)]:
    d2 = pd.concat([d2, _add_cat_dummies(d2, c, base=base)], axis=1)

cov_m1_present = [c for c in cov_m1 if c in d2.columns]
cov_m2_present = cov_m1_present + [c for c in cov_m2_extra if c in d2.columns]

# Table 2: zero_cat 4-cat aOR
zero_cat_dums = ["zero_cat_2", "zero_cat_3", "zero_cat_4"]
print(f"   Model 1 covariates ({len(cov_m1_present)}): {cov_m1_present}")
print(f"   Model 2 covariates ({len(cov_m2_present)}): {cov_m2_present}")

m1 = _logit_with_results("dep01", zero_cat_dums + cov_m1_present, d2, "Model 1")
m2 = _logit_with_results("dep01", zero_cat_dums + cov_m2_present, d2, "Model 2")

def _ext_or(model, var):
    if model is None or var not in model.params:
        return None
    b = model.params[var]; se = model.bse[var]
    return {"or": float(np.exp(b)),
            "ci_low": float(np.exp(b - 1.96 * se)),
            "ci_high": float(np.exp(b + 1.96 * se)),
            "p": float(model.pvalues[var])}

results["Table_2"] = {
    "Model_1": {v: _ext_or(m1, v) for v in zero_cat_dums},
    "Model_2": {v: _ext_or(m2, v) for v in zero_cat_dums},
}

# P for trend (continuous zero_freq)
m1_trend = _logit_with_results("dep01", ["zero_freq"] + cov_m1_present, d2, "M1 trend")
m2_trend = _logit_with_results("dep01", ["zero_freq"] + cov_m2_present, d2, "M2 trend")
results["Table_2"]["p_trend_M1"] = float(m1_trend.pvalues["zero_freq"]) if m1_trend else None
results["Table_2"]["p_trend_M2"] = float(m2_trend.pvalues["zero_freq"]) if m2_trend else None

print(f"\n[Table 2] aOR (Model 2):")
for v in zero_cat_dums:
    r = results["Table_2"]["Model_2"].get(v)
    if r:
        print(f"   {v}: {r['or']:.2f} ({r['ci_low']:.2f}-{r['ci_high']:.2f}), p={r['p']:.4g}")
print(f"   P_trend M1={results['Table_2']['p_trend_M1']:.4g}, M2={results['Table_2']['p_trend_M2']:.4g}")

# ── STEP 13: 7 subgroup stratifiers — Figure 3 데이터 ──
print(f"\n[STEP 13] Subgroup consistency — 7 stratifiers...")

def _subgroup_OR(data, strat_col, levels, cov_set, label):
    """각 level별 zero_freq의 aOR per 1-level + P_interaction."""
    out = []
    for lev in levels:
        sub = data[data[strat_col] == lev]
        if len(sub) < 200:
            out.append({"level": lev, "n": int(len(sub)), "or": None})
            continue
        # ...
        cov_sub = [c for c in cov_set if c in sub.columns]
        sub_m = _logit_with_results("dep01", ["zero_freq"] + cov_sub, sub, f"{label}-{lev}")
        if sub_m is None or "zero_freq" not in sub_m.params:
            out.append({"level": lev, "n": int(len(sub)), "or": None})
            continue
        b = sub_m.params["zero_freq"]; se = sub_m.bse["zero_freq"]
        out.append({
            "level": lev, "n": int(len(sub)),
            "or": float(np.exp(b)),
            "ci_low": float(np.exp(b - 1.96 * se)),
            "ci_high": float(np.exp(b + 1.96 * se)),
            "p": float(sub_m.pvalues["zero_freq"]),
        })

    # P_interaction — zero_freq × stratifier dummy (Wald)
    inter_cols = []
    strat_dums = []
    for lev in levels[1:]:
        col = f"{strat_col}_{int(lev)}"
        if col in data.columns:
            strat_dums.append(col)
            inter = f"zf_x_{strat_col}_{int(lev)}"
            data[inter] = data["zero_freq"] * data[col]
            inter_cols.append(inter)
    cov_int = [c for c in cov_set if c in data.columns]
    full = _logit_with_results("dep01",
                                ["zero_freq"] + strat_dums + inter_cols + cov_int,
                                data, f"{label}-interaction")
    p_int = None
    if full is not None and inter_cols and all(c in full.params for c in inter_cols):
        from scipy import stats as _st
        # Wald test for all interaction terms simultaneously
        try:
            R = np.zeros((len(inter_cols), len(full.params)))
            for i, c in enumerate(inter_cols):
                R[i, list(full.params.index).index(c)] = 1
            beta = full.params.values
            cov_b = full.cov_params().values
            wald = beta @ R.T @ np.linalg.inv(R @ cov_b @ R.T) @ R @ beta
            p_int = float(1 - _st.chi2.cdf(wald, df=len(inter_cols)))
        except Exception as e:
            print(f"   Wald failed for {label}: {e}")
    return out, p_int

# Subgroup definitions — STATA 코드 그대로
SUBGROUPS = [
    ("age_cat",       [1, 2, 3],
     [c for c in cov_m2_present if not c.startswith("age_cat_")]),
    ("bmi_cat",       [1, 2, 3],
     [c for c in cov_m2_present if not c.startswith("bmi_cat_")]),
    ("ses3",          [1, 2, 3],
     [c for c in cov_m2_present if not c.startswith("ses3_")]),
    ("academic3",     [1, 2, 3],
     [c for c in cov_m2_present if not c.startswith("academic3_")]),
    ("smartphone_tert", [1, 2, 3],
     cov_m2_present),
    ("pa_cat",        [1, 2, 3],
     [c for c in cov_m2_present if not c.startswith("pa_cat_")]),
    ("br_skip",       [0, 1],
     [c for c in cov_m2_present if c != "br_skip"]),
]

# add tertile dummies
d2 = pd.concat([d2, _add_cat_dummies(d2, "smartphone_tert", base=1, prefix="smartphone_tert")], axis=1)

# Overall first
overall = _logit_with_results("dep01", ["zero_freq"] + cov_m2_present, d2, "Overall")
overall_or = None
if overall is not None and "zero_freq" in overall.params:
    b = overall.params["zero_freq"]; se = overall.bse["zero_freq"]
    overall_or = {"or": float(np.exp(b)),
                  "ci_low": float(np.exp(b - 1.96 * se)),
                  "ci_high": float(np.exp(b + 1.96 * se)),
                  "p": float(overall.pvalues["zero_freq"])}

results["Figure_3"] = {"overall": overall_or, "subgroups": {}}
print(f"\n   Overall aOR per 1-level: {overall_or}")

for strat_col, levels, cov_set in SUBGROUPS:
    if strat_col not in d2.columns:
        print(f"   skip {strat_col} (column missing)")
        continue
    sg, p_int = _subgroup_OR(d2.copy(), strat_col, levels, cov_set, strat_col)
    results["Figure_3"]["subgroups"][strat_col] = {"levels": sg, "p_interaction": p_int}
    print(f"   {strat_col}: P_interaction={p_int}")
    for s in sg:
        if s.get("or") is not None:
            print(f"      level={s['level']:>2}: aOR={s['or']:.3f} ({s['ci_low']:.3f}-{s['ci_high']:.3f}), n={s['n']:,}")

# Save
out_path = Path("data/exports/stat_results.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\n\nsaved: {out_path}")
print(f"elapsed: {time.time() - t_start:.1f}s")
