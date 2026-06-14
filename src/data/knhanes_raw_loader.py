"""KNHANES raw .sav loader — registry-driven, mirrors kyrbs_raw_loader pattern.

Drop HN<year>_ALL.sav into data/raw/knhanes/ (e.g. HN23_ALL.sav for 2023). This loader
resolves canonical std_names from data/registry/knhanes/variables.yaml so the rest of the
pipeline (stat_bridge, survey_weighted, paper_writer) treats KNHANES and KYRBS the same.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_RAW_DIR = Path("data/raw/knhanes")
_REGISTRY_PATH = Path("data/registry/knhanes/variables.yaml")
# User-organised subfolders (2026-06-14 drop):
_SAV_SUBDIR = Path("data/raw/knhanes/통합파일(SPSS기준만들기)")
_STATA_SUBDIR = Path("data/raw/knhanes/통합본(STATA)")
_GUIDE_SUBDIR = Path("data/raw/knhanes/지침서")


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    if not _REGISTRY_PATH.exists():
        _log.warning("KNHANES registry missing: %s", _REGISTRY_PATH)
        return {}
    try:
        import yaml
        return yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        _log.warning("KNHANES registry load fail: %s", e)
        return {}


def list_available_years() -> list[int]:
    """Detect downloaded HN<YY>_all.sav files in canonical or user subfolder."""
    import re
    out: set[int] = set()
    search_dirs = [_SAV_SUBDIR, _RAW_DIR]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.iterdir():
            if p.suffix.lower() != ".sav":
                continue
            m = re.match(r"HN(\d{2})_ALL\.sav$", p.name, re.IGNORECASE)
            if m:
                yy = int(m.group(1))
                year = 2000 + yy if yy < 80 else 1900 + yy
                out.add(year)
    return sorted(out)


def _file_for_year(year: int) -> Optional[Path]:
    yy = str(year)[2:].zfill(2)
    search_dirs = [_SAV_SUBDIR, _RAW_DIR]
    variants = [
        f"HN{yy}_ALL.sav", f"HN{yy}_all.sav", f"hn{yy}_all.sav",
        f"HN{yy}.sav", f"knhanes{year}.sav",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for v in variants:
            q = d / v
            if q.exists():
                return q
        # case-insensitive scan as last resort
        for p in d.iterdir():
            if p.name.lower() == f"hn{yy}_all.sav":
                return p
    return None


def stata_integrated_path() -> Optional[Path]:
    """Pre-built KNHANES 2013-2024 STATA integrated file (user dropped)."""
    p = _STATA_SUBDIR / "KNHANES_2013_2024.dta"
    return p if p.exists() else None


def guide_pdfs() -> list[Path]:
    """KNHANES official guide PDFs (지침서). For RAG indexing."""
    if not _GUIDE_SUBDIR.exists():
        return []
    return sorted([p for p in _GUIDE_SUBDIR.iterdir()
                    if p.suffix.lower() == ".pdf"])


def _expected_raw_names(year: int) -> Dict[str, str]:
    """Resolve registry → {std_name: raw_name_for_this_year}."""
    reg = _load_registry()
    out: Dict[str, str] = {}
    for section, body in reg.items():
        if not isinstance(body, dict) or section in {"dataset", "version", "description",
                                                       "year_coverage", "documentation",
                                                       "provider", "file_pattern"}:
            continue
        for _key, var in body.items():
            if not isinstance(var, dict):
                continue
            std = var.get("std_name", _key)
            ym = var.get("year_map") or {}
            for span, raw in ym.items():
                if not isinstance(span, str) or "-" not in span:
                    continue
                try:
                    lo, hi = span.split("-")
                    if int(lo) <= year <= int(hi):
                        out[std] = raw if isinstance(raw, str) else (raw[0] if raw else "")
                        break
                except Exception:
                    continue
    return out


def load_knhanes_year(year: int):
    """Load HN<YY>_ALL.sav → DataFrame with std_name columns added.

    Original raw columns are preserved; canonical std_names are added as new columns
    pointing at the same data. So downstream code can query either name.
    """
    path = _file_for_year(year)
    if path is None:
        avail = list_available_years()
        _log.warning("KNHANES %s .sav not found in %s. Available years: %s",
                       year, _RAW_DIR, avail)
        return None
    try:
        import pyreadstat
        df, _meta = pyreadstat.read_sav(str(path), apply_value_formats=False)
    except Exception as e:
        _log.error("pyreadstat read_sav fail (%s): %s", path, e)
        return None

    # Add canonical std_name columns mirroring raw columns
    raw_to_std: Dict[str, str] = {v: k for k, v in _expected_raw_names(year).items()}
    for raw, std in raw_to_std.items():
        if raw in df.columns and std not in df.columns:
            df[std] = df[raw]
    _log.info("KNHANES %s loaded: %d rows, %d cols (%d std-name aliases added)",
                year, len(df), len(df.columns), len(raw_to_std))
    return df


def variable_compatibility_summary() -> dict:
    """Diagnostic: which std_names resolve in which years."""
    years = list_available_years()
    summary: Dict[str, dict] = {}
    for y in years:
        path = _file_for_year(y)
        if path is None:
            continue
        try:
            import pyreadstat
            cols, _ = pyreadstat.read_sav(str(path), metadataonly=True)
        except Exception:
            continue
        expected = _expected_raw_names(y)
        present = sum(1 for raw in expected.values() if raw in cols.columns)
        summary[str(y)] = {"path": str(path), "n_cols": len(cols.columns),
                            "expected": len(expected), "present": present}
    return summary


def load_knhanes_integrated_stata():
    """Load pre-built KNHANES 2013-2024 STATA integrated file (single DataFrame).

    Faster than year-by-year reading when full multi-year analysis is needed.
    """
    p = stata_integrated_path()
    if p is None:
        _log.warning("KNHANES STATA integrated file not present: %s", _STATA_SUBDIR)
        return None
    try:
        import pandas as pd
        df = pd.read_stata(str(p), convert_categoricals=False)
        _log.info("KNHANES STATA integrated loaded: %d rows, %d cols", len(df), len(df.columns))
        return df
    except Exception as e:
        _log.error("STATA load fail: %s", e)
        return None


__all__ = ["load_knhanes_year", "list_available_years",
            "variable_compatibility_summary",
            "stata_integrated_path", "guide_pdfs",
            "load_knhanes_integrated_stata"]
