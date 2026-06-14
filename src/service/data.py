"""Data service — dataset loader facade (KYRBS .sav now, KNHANES/registry-driven later).

Pure: returns DataFrame + meta. The compute layer (FastAPI) calls this; Streamlit also calls
this directly for now. No filesystem walks done from the frontend.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def load_kyrbs(year: int):
    """Load KYRBS for given year via existing kyrbs_raw_loader. Returns (df, meta) or (None, {})."""
    try:
        from src.data import kyrbs_raw_loader as krl
        df = krl.load_kyrbs(year)
        meta = {
            "dataset": "KYRBS", "year": year,
            "n_rows": len(df) if df is not None else 0,
            "vars": list(df.columns)[:30] if df is not None else [],
        }
        return df, meta
    except Exception as e:
        _log.warning("load_kyrbs(%s) fail: %s", year, e)
        return None, {"error": str(e)[:200]}


def available_kyrbs_years() -> list[int]:
    """Glob data/raw/kyrbs*.sav (canonical) and data/datasets/kyrbs/raw/*.sav (legacy)."""
    import re
    years: set[int] = set()
    for root in (Path("data/raw"), Path("data/datasets/kyrbs/raw")):
        if not root.exists():
            continue
        for p in root.glob("kyrbs*.sav"):
            m = re.search(r"20\d{2}", p.name)
            if m:
                years.add(int(m.group(0)))
    return sorted(years)


def available_knhanes_years() -> list[int]:
    """Delegate to knhanes_raw_loader."""
    try:
        from src.data import knhanes_raw_loader as kl
        return kl.list_available_years()
    except Exception as e:
        _log.warning("available_knhanes_years fail: %s", e)
        return []


def load_dataset(label: str, year: Optional[int] = None):
    """Dispatch: label='KYRBS'|'KNHANES' → loader. Year required for KYRBS."""
    label_u = (label or "").upper()
    if label_u == "KYRBS":
        if year is None:
            return None, {"error": "year required for KYRBS"}
        return load_kyrbs(year)
    if label_u == "KNHANES":
        try:
            from src.data import knhanes_raw_loader as kl
            if year is None:
                avail = kl.list_available_years()
                if not avail:
                    return None, {"error": "no KNHANES .sav in data/raw/knhanes/. "
                                              "Drop HN<YY>_ALL.sav files there."}
                year = avail[-1]
            df = kl.load_knhanes_year(year)
            meta = {"dataset": "KNHANES", "year": year,
                     "n_rows": len(df) if df is not None else 0}
            return df, meta
        except Exception as e:
            _log.warning("load_knhanes fail: %s", e)
            return None, {"error": str(e)[:200]}
    return None, {"error": f"unknown dataset: {label}"}


def load_knhanes(year: int, *, add_derived: bool = True):
    """Single-wave KNHANES with optional derived (bmi_cat, age_grp, MASLD class…)."""
    from src.data import knhanes_raw_loader as kl
    df = kl.load_knhanes_year(year)
    if df is None:
        return None, {"error": f"KNHANES {year} 파일 없음"}
    if add_derived:
        try:
            from src.data import knhanes_subgroup as sg
            df = sg.add_all(df, year=year)
        except Exception as e:
            _log.debug("knhanes_subgroup.add_all fail: %s", e)
        try:
            from src.data import knhanes_patterns as kp
            df["fli"] = kp.fli(df)
            df["hsi"] = kp.hsi(df)
            df["alc_g_week"] = kp.alcohol_g_week(df)
            df["cmd_risk_count"] = kp.cardiometabolic_risk_count(df)
            df["masld_class"] = kp.masld_classification(df)
            df["MetSx"] = kp.metsx_idf_asian(df)
            df["eGFR"] = kp.egfr_ckd_epi_2021(df)
            df["ckd_stage"] = kp.ckd_stage(df)
        except Exception as e:
            _log.debug("knhanes_patterns fail: %s", e)
    return df, {"dataset": "KNHANES", "year": year,
                  "n_rows": len(df), "derived": add_derived}


def load_knhanes_pooled(years: list, *, add_derived: bool = True,
                            phase: str = None):
    """다연도 KNHANES pool (survey_year/study_phase 추가).

    phase='IV'..'IX' 지정 시 그 phase 연도만 자동 선택.
    """
    from src.data import knhanes_subgroup as sg
    if phase:
        phase_map = {"IV": range(2007, 2010), "V": range(2010, 2013),
                       "VI": range(2013, 2016), "VII": range(2016, 2019),
                       "VIII": range(2019, 2022), "IX": range(2022, 2025)}
        years = list(phase_map.get(phase.upper(), years or []))
    dfs = {}
    for y in years:
        df, _ = load_knhanes(y, add_derived=add_derived)
        if df is not None:
            dfs[y] = df
    if not dfs:
        return None, {"error": "no waves loaded"}
    pooled = sg.pool_years(dfs)
    return pooled, {"dataset": "KNHANES pooled", "years": list(dfs.keys()),
                       "n_rows": len(pooled), "phase": phase}


def load_attachment(path):
    """범용 파일 로더 — text + (optional) vision data URI 반환."""
    from src.ingestion.universal_loader import load
    return load(path)


__all__ = ["load_kyrbs", "available_kyrbs_years",
            "available_knhanes_years",
            "load_knhanes", "load_knhanes_pooled",
            "load_dataset", "load_attachment"]
