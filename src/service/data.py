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
        df = krl.load_kyrbs_year(year)
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


__all__ = ["load_kyrbs", "available_kyrbs_years",
           "available_knhanes_years", "load_dataset"]
