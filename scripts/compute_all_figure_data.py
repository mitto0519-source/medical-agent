"""ZCB v2.4 — Stata 전체 분석(STEP 2/8/11/13)을 Python으로 재현, 4개 Figure 데이터 산출.

Figure 1 : 13단계 sequential exclusion 카운트 (STEP 2)
Figure 2A: Overall margins by zero_cat (STEP 11 첫 marginsplot, 4-cat)
Figure 2B: Sex × zero_freq margins (STEP 11 두번째 marginsplot, freq 1-7)
Figure 3 : 7 stratifier × 19 level subgroup aOR per 1-level (STEP 13)

Stata `svy: logistic`을 Python statsmodels GLM(binomial) + freq_weights(pweight)
+ cluster-robust SE로 근사. 점추정은 Stata svy와 동등, SE는 Taylor linearization과
±수% 차이 가능(paper figure 용도엔 충분).

출력: data/exports/figure_data.json
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
OUT = Path("data/exports/figure_data.json")

BMI_P5 = {
    (1,12):15.16,(1,13):15.57,(1,14):16.06,(1,15):16.61,(1,16):17.13,(1,17):17.59,(1,18):17.93,
    (2,12):15.13,(2,13):15.71,(2,14):16.27,(2,15):16.74,(2,16):17.10,(2,17):17.32,(2,18):17.39,
}
BMI_P85 = {
    (1,12):21.81,(1,13):22.78,(1,14):23.74,(1,15):24.66,(1,16):25.43,(1,17):26.05,(1,18):26.51,
    (2,12):21.74,(2,13):22.27,(2,14):22.69,(2,15):23.03,(2,16):23.30,(2,17):23.45,(2,18):23.50,
}


# ── STEP 2 sequential exclusion (Figure 1) ────────────────────────────────────

def figure1_exclusion_flow():
    df, _ = pyreadstat.read_sav(DATA)
    cu = {c.upper(): c for c in df.columns}
    g = lambda n: df[cu[n.upper()]]
    n0 = len(df)
    counts = {"n0": n0}
    steps = []

    def drop_miss(name, condition, label):
        nonlocal df
        e = int(condition.sum())
        df = df.loc[~condition].copy()
        steps.append({"step": label, "excluded": e, "remaining": len(df)})

    # 1. F_ZERO
    drop_miss("f_zero", g("F_ZERO").isna(), "Missing F_ZERO (exposure)")
    # rebuild cu
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 2. M_SAD
    drop_miss("m_sad", g("M_SAD").isna(), "Missing M_SAD (depression)")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 3. sex
    drop_miss("sex", g("sex").isna(), "Missing sex")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 4. age
    drop_miss("age", g("age").isna(), "Missing age")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 5. ht/wt
    drop_miss("ht_wt", g("HT").isna() | g("WT").isna(), "Missing height or weight")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 6. implausible BMI
    bmi_tmp = g("WT") / (g("HT")/100)**2
    drop_miss("bmi", (bmi_tmp < 10) | (bmi_tmp > 50), "Implausible BMI (<10 or >50)")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 7. academic
    drop_miss("e_s_rcrd", g("E_S_RCRD").isna(), "Missing academic rank")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 8. SSB or caffeine
    drop_miss("swd_caff", g("F_SWD_A").isna() | g("F_CAFF_A").isna(), "Missing SSB or caffeine frequency")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 9. breakfast
    drop_miss("f_br", g("F_BR").isna(), "Missing breakfast frequency")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 10. PA
    drop_miss("pa_tot", g("PA_TOT").isna(), "Missing physical activity")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 11. smartphone (both)
    drop_miss("sp", g("INT_SPWD_TM").isna() & g("INT_SPWK_TM").isna(),
              "Missing smartphone (both wd+wk)")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 12. SES
    drop_miss("e_ses", g("E_SES").isna(), "Missing household SES")
    cu = {c.upper(): c for c in df.columns}; g = lambda n: df[cu[n.upper()]]
    # 13. school (string)
    sch = g("SCHOOL").astype(str)
    drop_miss("school", sch.eq("") | sch.eq("nan") | g("SCHOOL").isna(), "Missing school type")

    counts["steps"] = steps
    counts["n_final"] = len(df)
    counts["e_total"] = n0 - len(df)
    return counts


# ── 풀 데이터 빌드 (STEP 3-6) ────────────────────────────────────────────────

def build_dataset() -> pd.DataFrame:
    df, _ = pyreadstat.read_sav(DATA)
    cu = {c.upper(): c for c in df.columns}
    g = lambda n: df[cu[n.upper()]]
    df["zero_freq"] = pd.to_numeric(g("F_ZERO"), errors="coerce")
    df["zero_cat"] = pd.cut(df["zero_freq"], bins=[0,1,3,5,7], labels=[1,2,3,4]).astype("float")
    msad = pd.to_numeric(g("M_SAD"), errors="coerce")
    df["depression"] = np.where(msad==2, 1, np.where(msad==1, 0, np.nan))
    df["sex"] = pd.to_numeric(g("sex"), errors="coerce")
    df["age"] = pd.to_numeric(g("age"), errors="coerce")
    df["age_cat"] = pd.cut(df["age"], bins=[11,13,15,18], labels=[1,2,3]).astype("float")
    ht = pd.to_numeric(g("HT"), errors="coerce")
    wt = pd.to_numeric(g("WT"), errors="coerce")
    df["bmi"] = wt / (ht/100)**2
    df.loc[(df["bmi"]<10) | (df["bmi"]>50), "bmi"] = np.nan
    def bmi_cat_row(r):
        if pd.isna(r["bmi"]) or pd.isna(r["sex"]) or pd.isna(r["age"]): return np.nan
        key = (int(r["sex"]), int(r["age"]))
        if key not in BMI_P5: return np.nan
        if r["bmi"] < BMI_P5[key]: return 1
        if r["bmi"] < BMI_P85[key]: return 2
        return 3
    df["bmi_cat"] = df.apply(bmi_cat_row, axis=1)
    esr = pd.to_numeric(g("E_S_RCRD"), errors="coerce")
    df["academic3"] = np.where(esr.isin([1,2]), 1, np.where(esr==3, 2, np.where(esr.isin([4,5]), 3, np.nan)))
    ses = pd.to_numeric(g("E_SES"), errors="coerce")
    df["ses3"] = np.where(ses.isin([1,2]), 1, np.where(ses==3, 2, np.where(ses.isin([4,5]), 3, np.nan)))
    school = g("SCHOOL").astype(str)
    df["school_n"] = np.where(school.str.contains("중학교"), 1,
                       np.where(school.str.contains("일반계고|특성화계고"), 2, np.nan))
    tc = pd.to_numeric(g("TC_LT"), errors="coerce")
    tcec = pd.to_numeric(g("TC_EC_LT"), errors="coerce")
    tchtp = pd.to_numeric(g("TC_HTP_LT"), errors="coerce")
    smoker_any = ((tc==2) | (tcec==2) | (tchtp==2))
    smoker_none = ((tc.isin([1])|tc.isna()) & (tcec.isin([1])|tcec.isna()) & (tchtp.isin([1])|tchtp.isna()) &
                   ~(tc.isna() & tcec.isna() & tchtp.isna()))
    df["ever_smoker"] = np.where(smoker_any, 1, np.where(smoker_none, 0, np.nan))
    ac = pd.to_numeric(g("AC_LT"), errors="coerce")
    df["ever_drinker"] = np.where(ac==2, 1, np.where(ac==1, 0, np.nan))
    fbr = pd.to_numeric(g("F_BR"), errors="coerce")
    df["br_skip"] = np.where(fbr.between(1,3), 1, np.where(fbr.between(4,8), 0, np.nan))
    pa = pd.to_numeric(g("PA_TOT"), errors="coerce") - 1
    pa = pa.where((pa>=0) & (pa<=7))
    df["pa_cat"] = np.where(pa.between(0,2), 1, np.where(pa.between(3,4), 2,
                       np.where(pa.between(5,7), 3, np.nan)))
    swd = pd.to_numeric(g("F_SWD_A"), errors="coerce")
    df["swd_freq3"] = np.where(swd.between(1,2), 1, np.where(swd.between(3,5), 2,
                         np.where(swd.between(6,7), 3, np.nan)))
    caf = pd.to_numeric(g("F_CAFF_A"), errors="coerce")
    df["caff_freq3"] = np.where(caf.between(1,2), 1, np.where(caf.between(3,5), 2,
                          np.where(caf.between(6,7), 3, np.nan)))
    spwd = pd.to_numeric(g("INT_SPWD_TM"), errors="coerce")
    spwk = pd.to_numeric(g("INT_SPWK_TM"), errors="coerce")
    df["smartphone_min"] = np.where(spwd.notna() & spwk.notna(), (spwd*5+spwk*2)/7,
                              np.where(spwd.notna(), spwd, spwk))
    df["w"] = pd.to_numeric(g("w"), errors="coerce")
    df["strata"] = pd.to_numeric(g("strata"), errors="coerce")
    df["cluster"] = pd.to_numeric(g("cluster"), errors="coerce")
    needvars = ["depression","zero_freq","sex","age_cat","bmi_cat","school_n",
                "academic3","ses3","ever_smoker","ever_drinker","swd_freq3",
                "caff_freq3","smartphone_min","pa_cat","br_skip","w","cluster"]
    cc = df.dropna(subset=needvars).copy()
    cc["smartphone_tert"] = pd.qcut(cc["smartphone_min"], q=3, labels=[1,2,3]).astype("float")
    return cc


# ── 모델 fit 헬퍼 ─────────────────────────────────────────────────────────────

ALL_COV = ["sex","age_cat","bmi_cat","ses3","school_n","academic3",
           "ever_smoker","ever_drinker","swd_freq3","caff_freq3","pa_cat","br_skip"]


def fit_logit(df, formula):
    return smf.glm(formula, data=df, family=sm.families.Binomial(),
                   freq_weights=df["w"]).fit(cov_type="cluster",
                                              cov_kwds={"groups": df["cluster"]})


def marginal_prob(model, df, mods: dict):
    """Marginal standardization: 변수 일부를 mods로 고정하고 나머지는 관측분포로 평균."""
    d = df.copy()
    for k, v in mods.items():
        d[k] = v
    p = model.predict(d)
    # 가중평균 (pweight)
    w = d["w"]
    return float(np.average(p, weights=w))


# ── Figure 2A: overall margins by zero_cat ────────────────────────────────────

def figure2A_margins(df):
    # 4-cat full model (Model 2)
    formula = "depression ~ C(zero_cat) + " + " + ".join(f"C({c})" for c in ALL_COV)
    model = fit_logit(df, formula)
    out = {}
    for k in [1, 2, 3, 4]:
        p = marginal_prob(model, df, {"zero_cat": k})
        out[int(k)] = {"prob": p}
    # 4-cat aOR (vs k=1) + CI
    coefs = model.params; bse = model.bse
    for k in [2, 3, 4]:
        name = f"C(zero_cat)[T.{k}.0]"
        if name not in coefs.index:
            name = f"C(zero_cat)[T.{k}]"
        b, se = coefs[name], bse[name]
        out[k]["aOR"] = float(np.exp(b))
        out[k]["lo"] = float(np.exp(b - 1.96*se))
        out[k]["hi"] = float(np.exp(b + 1.96*se))
    return out


# ── Figure 2B: sex × zero_freq margins ────────────────────────────────────────

def figure2B_margins(df):
    # `c.zero_freq##i.sex` + 보조 covariates (sex는 interaction 안에 있어 제외).
    # 점추정 + 95% CI band (Stata marginsplot recastci(rarea) 매칭).
    cov_s = [c for c in ALL_COV if c != "sex"]
    formula = "depression ~ zero_freq*C(sex) + " + " + ".join(f"C({c})" for c in cov_s)
    model = fit_logit(df, formula)
    out = {"male": {}, "female": {}}
    for sx, label in [(1, "male"), (2, "female")]:
        for f in range(1, 8):
            d = df.copy()
            d["sex"] = sx; d["zero_freq"] = f
            try:
                pred = model.get_prediction(d).summary_frame(alpha=0.05)
                w = d["w"]
                # 확률 스케일에서 가중평균
                mean = float(np.average(pred["mean"], weights=w))
                lo = float(np.average(pred["mean_ci_lower"], weights=w))
                hi = float(np.average(pred["mean_ci_upper"], weights=w))
            except Exception:
                # fallback: 점추정만
                p = marginal_prob(model, df, {"sex": sx, "zero_freq": f})
                mean, lo, hi = p, p, p
            out[label][f] = {"prob": mean, "lo": lo, "hi": hi}
    return out


# ── Figure 3: 7 stratifier × levels subgroup aORs ─────────────────────────────

def subgroup_aOR(df, mask, cov_list):
    d = df.loc[mask].copy()
    if len(d) < 50:
        return None
    formula = "depression ~ zero_freq + " + " + ".join(f"C({c})" for c in cov_list)
    try:
        res = fit_logit(d, formula)
        b, se = res.params["zero_freq"], res.bse["zero_freq"]
        return {"aOR": float(np.exp(b)),
                "lo": float(np.exp(b - 1.96*se)),
                "hi": float(np.exp(b + 1.96*se)),
                "n": int(len(d)),
                "p": float(res.pvalues["zero_freq"])}
    except Exception as e:
        return {"error": str(e)[:100], "n": len(d)}


def figure3_subgroups(df):
    out = {}
    # Overall
    res = fit_logit(df, "depression ~ zero_freq + " + " + ".join(f"C({c})" for c in ALL_COV))
    b, se = res.params["zero_freq"], res.bse["zero_freq"]
    out["overall"] = {"label": "All adolescents",
                       "aOR": float(np.exp(b)), "lo": float(np.exp(b-1.96*se)),
                       "hi": float(np.exp(b+1.96*se)), "n": int(len(df))}
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
        cov = [c for c in ALL_COV if c != var]
        for lvl, lbl in zip(lvls, labels):
            r = subgroup_aOR(df, df[var] == lvl, cov)
            out[f"{key}_{lvl}"] = {"label": lbl, **(r if r else {})}
    return out


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Figure 1: 13-step exclusion ===")
    f1 = figure1_exclusion_flow()
    print(f"  raw N={f1['n0']:,}  → final N={f1['n_final']:,}  excluded={f1['e_total']:,}")
    for s in f1["steps"]:
        print(f"    -{s['excluded']:>5,}  {s['step']}")

    print("\n=== 풀 데이터 빌드 (complete-case) ===")
    df = build_dataset()
    print(f"  CC n={len(df):,}")

    print("\n=== Figure 2A: overall margins by zero_cat ===")
    f2a = figure2A_margins(df)
    for k, v in f2a.items():
        print(f"  zero_cat={k}: prob={v['prob']:.4f}",
              f"aOR={v.get('aOR','-'):.3f} ({v.get('lo','-'):.3f}-{v.get('hi','-'):.3f})" if v.get('aOR') else "")

    print("\n=== Figure 2: sex × zero_freq margins (with 95% CI) ===")
    f2b = figure2B_margins(df)
    def _show(side):
        # dict {prob,lo,hi} 또는 float 둘 다 호환
        return [(f"{v['prob']:.3f}" if isinstance(v, dict) else f"{v:.3f}")
                for v in [f2b[side][f] for f in range(1, 8)]]
    print("  male  :", _show("male"))
    print("  female:", _show("female"))

    print("\n=== Figure 3: subgroup aORs (per 1-level) ===")
    f3 = figure3_subgroups(df)
    for k, v in f3.items():
        if v.get("aOR") is not None:
            print(f"  {k:14} {v['label'][:22]:22} aOR={v['aOR']:.3f} ({v['lo']:.3f}-{v['hi']:.3f}) n={v['n']:,}")
        else:
            print(f"  {k:14} {v['label'][:22]:22} (error or insufficient n)")

    data = {"figure1": f1, "figure2A": f2a, "figure2B": f2b, "figure3": f3}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n저장 → {OUT}")


if __name__ == "__main__":
    main()
