"""KNHANES domain patterns — FLI/HSI/MASLD/MetALD/ALD/MetSx/CKD/NOVA.

KYRBS의 F_BR coding / sleep / PA_VIG 등 domain logic과 같은 수준의 KNHANES 도메인 모듈.

API:
    fli(df) -> pd.Series                 # Fatty Liver Index (Bedogni 2006)
    hsi(df) -> pd.Series                 # Hepatic Steatosis Index (Lee 2010)
    masld_classification(df) -> pd.Series  # MASLD / MetALD / ALD / not_steatosis (2023 def)
    metsx_idf_asian(df) -> pd.Series     # IDF Asian Metabolic Syndrome (Korean cutoff)
    egfr_ckd_epi_2021(df) -> pd.Series   # eGFR + CKD stage
    alcohol_g_week(df) -> pd.Series      # KNHANES 음주 빈도×양 → g/주

모든 함수는 KNHANES 표준 컬럼명을 입력으로 받는다.
누락 컬럼은 NaN으로 처리하고 warning 로그 남김 (강제 raise 안 함).
"""
from __future__ import annotations

import math
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _has_cols(df, cols: list[str], where: str) -> bool:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        _log.warning("%s: missing %s — NaN으로 처리", where, missing)
    return not missing


# ── 1. Fatty Liver Index (Bedogni 2006) ─────────────────────────────────────
def fli(df):
    """FLI = e^L / (1 + e^L) × 100; L = 0.953*ln(TG) + 0.139*BMI + 0.718*ln(GGT) + 0.053*wc − 15.745

    FLI ≥ 60 → likely steatosis. 30 ≤ FLI < 60 → indeterminate. < 30 → unlikely.
    """
    import pandas as pd
    import numpy as np
    required = ["HE_TG", "HE_BMI", "HE_GGT", "HE_wc"]
    if not _has_cols(df, required, "fli"):
        return pd.Series([np.nan] * len(df), index=df.index, name="FLI")
    tg = df["HE_TG"].astype(float).clip(lower=1)   # ln 안전
    bmi = df["HE_BMI"].astype(float)
    ggt = df["HE_GGT"].astype(float).clip(lower=1)
    wc = df["HE_wc"].astype(float)
    L = 0.953 * np.log(tg) + 0.139 * bmi + 0.718 * np.log(ggt) + 0.053 * wc - 15.745
    out = (np.exp(L) / (1 + np.exp(L))) * 100
    return pd.Series(out, index=df.index, name="FLI")


# ── 2. Hepatic Steatosis Index (Lee 2010) ───────────────────────────────────
def hsi(df):
    """HSI = 8 × (ALT/AST) + BMI (+2 여성, +2 DM). HSI ≥ 36 → likely steatosis."""
    import pandas as pd
    import numpy as np
    required = ["HE_ALT", "HE_AST", "HE_BMI", "sex"]
    if not _has_cols(df, required, "hsi"):
        return pd.Series([np.nan] * len(df), index=df.index, name="HSI")
    alt = df["HE_ALT"].astype(float).clip(lower=0.1)
    ast = df["HE_AST"].astype(float).clip(lower=0.1)
    bmi = df["HE_BMI"].astype(float)
    out = 8.0 * (alt / ast) + bmi
    out = out + (df["sex"] == 2).astype(float) * 2.0
    if "DE1_dg" in df.columns:
        out = out + (df["DE1_dg"] == 1).astype(float) * 2.0
    return pd.Series(out, index=df.index, name="HSI")


# ── 3. 알코올 섭취 g/주 (KNHANES coding) ────────────────────────────────────
def alcohol_g_week(df):
    """KNHANES 음주 빈도(BD1_11) × 1회 잔수(BD2_1) × 표준잔 g (≈14g) = g/주

    BD1_11 코딩: 1=평생거의 안 마심 2=1회/월 3=2-4회/월 4=2-3회/주 5=4회+/주
    → freq/week 환산: {1:0, 2:0.23, 3:0.69, 4:2.5, 5:4.5}
    BD2_1 코딩: 1=1-2잔 2=3-4잔 3=5-6잔 4=7-9잔 5=10잔+
    → 잔수: {1:1.5, 2:3.5, 3:5.5, 4:8, 5:11}
    표준잔 ≈ 14g 알코올.
    """
    import pandas as pd
    import numpy as np
    if "BD1_11" not in df.columns or "BD2_1" not in df.columns:
        _log.warning("alcohol_g_week: BD1_11/BD2_1 missing")
        return pd.Series([np.nan] * len(df), index=df.index, name="alc_g_week")
    freq_map = {1: 0.0, 2: 0.23, 3: 0.69, 4: 2.5, 5: 4.5,
                 8: 0.0, 9: np.nan}
    amt_map = {1: 1.5, 2: 3.5, 3: 5.5, 4: 8.0, 5: 11.0,
                8: 0.0, 9: np.nan}
    freq = df["BD1_11"].map(freq_map)
    amt = df["BD2_1"].map(amt_map)
    out = freq * amt * 14.0   # g/주
    return pd.Series(out, index=df.index, name="alc_g_week")


def alcohol_category_masld(df):
    """Returns 'no'/'moderate'/'heavy' per MASLD-MetALD 2023 cutoff.

    Male:   moderate = 140-350 g/wk, heavy = >350
    Female: moderate = 70-210 g/wk,  heavy = >210
    """
    import pandas as pd
    g = alcohol_g_week(df)
    sex_M = (df.get("sex", 0) == 1)
    out = pd.Series(index=df.index, dtype=object)
    out[g.isna()] = None
    out[(g < 140) & sex_M] = "no"
    out[(g >= 140) & (g <= 350) & sex_M] = "moderate"
    out[(g > 350) & sex_M] = "heavy"
    out[(g < 70) & ~sex_M] = "no"
    out[(g >= 70) & (g <= 210) & ~sex_M] = "moderate"
    out[(g > 210) & ~sex_M] = "heavy"
    out.name = "alcohol_category"
    return out


# ── 4. Cardiometabolic risk count (MASLD 5축) ───────────────────────────────
def cardiometabolic_risk_count(df):
    """5 cardiometabolic criteria (MASLD 2023) → 충족 개수 (0~5)."""
    import pandas as pd
    import numpy as np
    sex_M = (df.get("sex", 0) == 1)

    # 1. Adiposity: BMI ≥ 23 OR wc > 90M/85F
    bmi_ok = df.get("HE_BMI", 0) >= 23
    wc_ok = ((df.get("HE_wc", 0) > 90) & sex_M) | ((df.get("HE_wc", 0) > 85) & ~sex_M)
    adi = (bmi_ok | wc_ok).astype(int)

    # 2. Dysglycemia: glucose ≥ 100 OR hba1c ≥ 5.7 OR DM_dx/tx
    gly = ((df.get("HE_glu", 0) >= 100) |
           (df.get("HE_HbA1c", 0) >= 5.7) |
           (df.get("DE1_dg", 0) == 1) |
           (df.get("DE1_pr", 0) == 1)).astype(int)

    # 3. Hypertension: SBP ≥ 130 OR DBP ≥ 85 OR HT_dx/tx
    bp = ((df.get("HE_sbp", 0) >= 130) |
          (df.get("HE_dbp", 0) >= 85) |
          (df.get("DI1_dg", 0) == 1) |
          (df.get("DI1_pr", 0) == 1)).astype(int)

    # 4. TG ≥ 150 or lipid-lowering
    tg = ((df.get("HE_TG", 0) >= 150) | (df.get("DI2_pr", 0) == 1)).astype(int)

    # 5. HDL ≤ 40M/50F or lipid-lowering
    # HE_HDL_st2 (2019+) → HE_HDLc (2007-2018) fallback
    hdl_col = "HE_HDL_st2" if "HE_HDL_st2" in df.columns else "HE_HDLc"
    hdl_low = ((df.get(hdl_col, 999) <= 40) & sex_M) | ((df.get(hdl_col, 999) <= 50) & ~sex_M)
    hdl = (hdl_low | (df.get("DI2_pr", 0) == 1)).astype(int)

    out = adi + gly + bp + tg + hdl
    return pd.Series(out, index=df.index, name="cmd_risk_count")


# ── 5. MASLD/MetALD/ALD 분류 (Rinella 2023) ─────────────────────────────────
def masld_classification(df,
                            *, steatosis_method: str = "fli",
                            fli_cutoff: float = 60.0,
                            hsi_cutoff: float = 36.0):
    """MASLD 2023 분류.

    steatosis_method='fli'|'hsi'|'either'.
    Returns: 'MASLD' / 'MetALD' / 'ALD' / 'not_steatosis' / 'steatosis_only'.

    Logic:
      1. steatosis = FLI≥60 OR HSI≥36 (method 따라)
      2. cmd_risk = cardiometabolic_risk_count ≥ 1
      3. alc = alcohol_category_masld
      4. 분기:
         no steatosis → 'not_steatosis'
         steatosis + cmd_risk + alc=='no'        → 'MASLD'
         steatosis + cmd_risk + alc=='moderate'  → 'MetALD'
         steatosis + alc=='heavy'                → 'ALD'
         steatosis + 그 외                        → 'steatosis_only'
    """
    import pandas as pd
    fli_v = fli(df) if steatosis_method in ("fli", "either") else None
    hsi_v = hsi(df) if steatosis_method in ("hsi", "either") else None
    if steatosis_method == "fli":
        steatosis = fli_v >= fli_cutoff
    elif steatosis_method == "hsi":
        steatosis = hsi_v >= hsi_cutoff
    else:
        steatosis = (fli_v >= fli_cutoff) | (hsi_v >= hsi_cutoff)
    cmd = cardiometabolic_risk_count(df) >= 1
    alc = alcohol_category_masld(df)

    out = pd.Series(index=df.index, dtype=object)
    out[~steatosis] = "not_steatosis"
    out[steatosis & cmd & (alc == "no")] = "MASLD"
    out[steatosis & cmd & (alc == "moderate")] = "MetALD"
    out[steatosis & (alc == "heavy")] = "ALD"
    out[steatosis & out.isna()] = "steatosis_only"
    out.name = "masld_classification"
    return out


# ── 6. IDF Metabolic Syndrome (Asian / Korean cutoff) ───────────────────────
def metsx_idf_asian(df):
    """IDF Asian MetSx (central obesity 필수 + 2 추가 = MetSx).

    Required:  wc > 90M/85F
    Plus ≥ 2 of:
      - TG ≥ 150 or lipid-lowering
      - HDL ≤ 40M/50F or lipid-lowering
      - SBP ≥ 130 / DBP ≥ 85 or HT_tx
      - Glucose ≥ 100 or DM_dx/tx
    """
    import pandas as pd
    sex_M = (df.get("sex", 0) == 1)
    central = ((df.get("HE_wc", 0) > 90) & sex_M) | ((df.get("HE_wc", 0) > 85) & ~sex_M)

    tg = ((df.get("HE_TG", 0) >= 150) | (df.get("DI2_pr", 0) == 1)).astype(int)
    hdl_col = "HE_HDL_st2" if "HE_HDL_st2" in df.columns else "HE_HDLc"
    hdl_low = ((df.get(hdl_col, 999) <= 40) & sex_M) | ((df.get(hdl_col, 999) <= 50) & ~sex_M)
    hdl = (hdl_low | (df.get("DI2_pr", 0) == 1)).astype(int)
    bp = ((df.get("HE_sbp", 0) >= 130) | (df.get("HE_dbp", 0) >= 85) |
          (df.get("DI1_pr", 0) == 1)).astype(int)
    gly = ((df.get("HE_glu", 0) >= 100) | (df.get("DE1_dg", 0) == 1) |
           (df.get("DE1_pr", 0) == 1)).astype(int)
    score = tg + hdl + bp + gly
    out = central & (score >= 2)
    return pd.Series(out.astype(int), index=df.index, name="MetSx")


# ── 7. eGFR + CKD stage (CKD-EPI 2021) ──────────────────────────────────────
def egfr_ckd_epi_2021(df):
    """CKD-EPI 2021 (race-free) eGFR.

    eGFR = 142 × min(Scr/k, 1)^a × max(Scr/k, 1)^-1.200 × 0.9938^age × 1.012(여성)
      k = 0.7(여) / 0.9(남); a = -0.241(여) / -0.302(남)
    """
    import pandas as pd
    import numpy as np
    required = ["HE_crea", "age", "sex"]
    if not _has_cols(df, required, "egfr"):
        return pd.Series([np.nan] * len(df), index=df.index, name="eGFR")
    scr = df["HE_crea"].astype(float).clip(lower=0.1)
    age = df["age"].astype(float)
    sex_F = (df["sex"] == 2)
    k = np.where(sex_F, 0.7, 0.9)
    a = np.where(sex_F, -0.241, -0.302)
    min_term = np.minimum(scr / k, 1) ** a
    max_term = np.maximum(scr / k, 1) ** -1.200
    egfr = 142 * min_term * max_term * (0.9938 ** age)
    egfr = egfr * np.where(sex_F, 1.012, 1.0)
    return pd.Series(egfr, index=df.index, name="eGFR")


def ckd_stage(df):
    """eGFR → KDIGO G1~G5."""
    import pandas as pd
    egfr = egfr_ckd_epi_2021(df)
    out = pd.Series(index=df.index, dtype=object)
    out[egfr >= 90] = "G1"
    out[(egfr >= 60) & (egfr < 90)] = "G2"
    out[(egfr >= 45) & (egfr < 60)] = "G3a"
    out[(egfr >= 30) & (egfr < 45)] = "G3b"
    out[(egfr >= 15) & (egfr < 30)] = "G4"
    out[egfr < 15] = "G5"
    return out


__all__ = [
    "fli", "hsi",
    "alcohol_g_week", "alcohol_category_masld",
    "cardiometabolic_risk_count", "masld_classification",
    "metsx_idf_asian",
    "egfr_ckd_epi_2021", "ckd_stage",
]
