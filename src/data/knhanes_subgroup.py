"""KNHANES subgroup / stratification helpers — KYRBS의 학년·성별 분류와 동격 레벨.

API:
    bmi_category(bmi)             # WHO Asian: <18.5/18.5-22.9/23-24.9/25-29.9/30+
    age_group(age, scheme="decade"|"who"|"chronic")
    income_quartile_label(incm)
    education_group(edu)
    urban_rural(region)
    pool_years(dfs)               # 다연도 pool + design 무결성 표시
    study_phase_label(year)       # IV/V/VI/VII/VIII/IX
    add_all(df, year=None)        # 한 번에 모든 derived col을 df에 추가
"""
from __future__ import annotations

from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def bmi_category(bmi):
    """WHO Asian cutoff (KSSO 2020 표준)."""
    import pandas as pd
    import numpy as np
    out = pd.Series(index=getattr(bmi, "index", None), dtype=object)
    out[bmi.isna()] = None
    out[bmi < 18.5] = "underweight"
    out[(bmi >= 18.5) & (bmi < 23)] = "normal"
    out[(bmi >= 23) & (bmi < 25)] = "overweight"
    out[(bmi >= 25) & (bmi < 30)] = "obese_I"
    out[bmi >= 30] = "obese_II_III"
    out.name = "bmi_cat"
    return out


def age_group(age, *, scheme: str = "decade"):
    """scheme:
       'decade'    -> 19-29 / 30-39 / 40-49 / 50-59 / 60-69 / 70+
       'who'       -> 19-39 young / 40-64 middle / 65+ elderly
       'chronic'   -> 19-44 / 45-64 / 65-74 / 75+
       'adolescent'-> KNHANES 청소년: 12-14 / 15-18
    """
    import pandas as pd
    out = pd.Series(index=getattr(age, "index", None), dtype=object)
    a = age
    if scheme == "decade":
        out[(a >= 19) & (a < 30)] = "19-29"
        out[(a >= 30) & (a < 40)] = "30-39"
        out[(a >= 40) & (a < 50)] = "40-49"
        out[(a >= 50) & (a < 60)] = "50-59"
        out[(a >= 60) & (a < 70)] = "60-69"
        out[a >= 70] = "70+"
    elif scheme == "who":
        out[(a >= 19) & (a < 40)] = "young"
        out[(a >= 40) & (a < 65)] = "middle"
        out[a >= 65] = "elderly"
    elif scheme == "chronic":
        out[(a >= 19) & (a < 45)] = "19-44"
        out[(a >= 45) & (a < 65)] = "45-64"
        out[(a >= 65) & (a < 75)] = "65-74"
        out[a >= 75] = "75+"
    elif scheme == "adolescent":
        out[(a >= 12) & (a <= 14)] = "12-14"
        out[(a >= 15) & (a <= 18)] = "15-18"
    out.name = f"age_grp_{scheme}"
    return out


def income_quartile_label(incm):
    """KNHANES incm: 1=Q1 lowest → 4=Q4 highest."""
    import pandas as pd
    m = {1: "Q1_lowest", 2: "Q2", 3: "Q3", 4: "Q4_highest"}
    out = incm.map(m) if hasattr(incm, "map") else pd.Series([m.get(int(v)) for v in incm])
    out.name = "income_q_lbl"
    return out


def education_group(edu):
    """KNHANES edu: 1=elementary 2=middle 3=high 4=college+."""
    import pandas as pd
    m = {1: "elementary", 2: "middle", 3: "high", 4: "college_plus"}
    out = edu.map(m) if hasattr(edu, "map") else pd.Series([m.get(int(v)) for v in edu])
    out.name = "edu_grp"
    return out


def urban_rural(region):
    """region 17 시도 코드 → 7대 광역시 vs 도 (urban vs rural proxy).

    Korean region codes (KNHANES standard):
    1=서울 2=부산 3=대구 4=인천 5=광주 6=대전 7=울산 → urban
    8=세종 9=경기 10=강원 11=충북 12=충남 13=전북 14=전남 15=경북 16=경남 17=제주 → rural
    """
    import pandas as pd
    urban_set = {1, 2, 3, 4, 5, 6, 7}
    out = pd.Series(["urban" if (int(r) in urban_set) else "rural"
                       if pd.notna(r) else None for r in region],
                      index=getattr(region, "index", None))
    out.name = "urban_rural"
    return out


def study_phase_label(year):
    """KNHANES phase: IV(2007-09) / V(2010-12) / VI(2013-15) / VII(2016-18) / VIII(2019-21) / IX(2022-24)."""
    y = int(year) if isinstance(year, (int, float, str)) else year
    if 2007 <= y <= 2009: return "IV"
    if 2010 <= y <= 2012: return "V"
    if 2013 <= y <= 2015: return "VI"
    if 2016 <= y <= 2018: return "VII"
    if 2019 <= y <= 2021: return "VIII"
    if 2022 <= y <= 2024: return "IX"
    return f"unknown_{y}"


def pool_years(dfs: dict):
    """{year: df} → 통합 df + 'survey_year' / 'study_phase' 컬럼 추가.

    가중치는 그대로 (각 wave의 wt_itvex). 분석 시 design.update_wt 호출 권장.
    """
    import pandas as pd
    pooled = []
    for y, df in sorted(dfs.items()):
        df = df.copy()
        df["survey_year"] = y
        df["study_phase"] = study_phase_label(y)
        pooled.append(df)
    return pd.concat(pooled, ignore_index=True, sort=False)


def add_all(df, year: Optional[int] = None):
    """한 번에 모든 derived columns를 df에 in-place 추가."""
    import pandas as pd
    if "HE_BMI" in df.columns:
        df["bmi_cat"] = bmi_category(df["HE_BMI"])
    if "age" in df.columns:
        df["age_grp_decade"] = age_group(df["age"], scheme="decade")
        df["age_grp_who"] = age_group(df["age"], scheme="who")
    if "incm" in df.columns:
        df["income_q_lbl"] = income_quartile_label(df["incm"])
    if "edu" in df.columns:
        df["edu_grp"] = education_group(df["edu"])
    if "region" in df.columns:
        df["urban_rural"] = urban_rural(df["region"])
    if year is not None:
        df["study_phase"] = study_phase_label(year)
        df["survey_year"] = year
    return df


__all__ = [
    "bmi_category", "age_group",
    "income_quartile_label", "education_group", "urban_rural",
    "study_phase_label", "pool_years", "add_all",
]
