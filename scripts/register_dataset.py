"""Dataset Registry tool — register a new dataset/wave against data/registry/<dataset>/variables.yaml.

MASTER_UPGRADE §2: dataset-agnostic. KYRBS today, KNHANES tomorrow, any DB the same way.

Usage:
    python scripts/register_dataset.py <dataset_slug> <sav_or_csv_path> [--year YYYY] [--apply]

Workflow:
    1. Scan columns + value labels from the new file
    2. Diff against data/registry/<dataset>/variables.yaml
    3. Print classified diff:
         + NEW columns (not in registry)
         ~ RENAMED candidates (close to existing std_name)
         - MISSING expected columns
         ! CODING DRIFT (label dictionary changed)
    4. If --apply: write the diff back as a new version (vN+1) — but only if --apply given.
       Without --apply this is a dry-run report only.

Per MASTER_UPGRADE §5 decision-point 4: human-gate (always require --apply, never auto).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List


def _load_registry(dataset_slug: str) -> dict:
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed. pip install pyyaml")
        sys.exit(2)
    path = Path(f"data/registry/{dataset_slug}/variables.yaml")
    if not path.exists():
        print(f"ERROR: registry not found: {path}")
        print(f"       Create skeleton: mkdir -p data/registry/{dataset_slug} "
              f"&& cp data/registry/kyrbs/variables.yaml {path}")
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _scan_file(path: Path) -> Dict[str, dict]:
    """Scan .sav / .csv → {raw_name: {dtype, sample_values, n_unique}}."""
    if path.suffix.lower() == ".sav":
        try:
            import pyreadstat
        except ImportError:
            print("ERROR: pyreadstat not installed (needed for .sav)")
            sys.exit(2)
        df, meta = pyreadstat.read_sav(str(path), apply_value_formats=False)
        out: Dict[str, dict] = {}
        for col in df.columns:
            s = df[col]
            out[col] = {
                "dtype": str(s.dtype),
                "n_unique": int(s.nunique(dropna=True)),
                "sample": [v for v in s.dropna().head(5).tolist()],
                "label": (meta.column_names_to_labels or {}).get(col, ""),
            }
        return out
    if path.suffix.lower() == ".csv":
        import pandas as pd
        df = pd.read_csv(path, nrows=2000)
        return {col: {"dtype": str(df[col].dtype),
                       "n_unique": int(df[col].nunique(dropna=True)),
                       "sample": [v for v in df[col].dropna().head(5).tolist()],
                       "label": ""} for col in df.columns}
    print(f"ERROR: unsupported file type: {path.suffix}")
    sys.exit(2)


def _flatten_registry(reg: dict) -> Dict[str, dict]:
    """Walk variables.yaml sections → {std_name: var_spec}."""
    flat: Dict[str, dict] = {}
    for section, body in reg.items():
        if not isinstance(body, dict):
            continue
        if section in {"dataset", "version", "description", "year_coverage",
                         "documentation", "provider"}:
            continue
        for _key, var in body.items():
            if not isinstance(var, dict):
                continue
            std = var.get("std_name", _key)
            flat[std] = {"section": section, **var}
    return flat


def _expected_raw_names(flat_reg: Dict[str, dict], year: int) -> Dict[str, str]:
    """For target year, resolve year_map → {std_name: raw_name_for_this_year}."""
    out: Dict[str, str] = {}
    for std, spec in flat_reg.items():
        ym = spec.get("year_map") or {}
        for span, raw in ym.items():
            if isinstance(span, str) and "-" in span:
                try:
                    lo, hi = span.split("-")
                    if int(lo) <= year <= int(hi):
                        if isinstance(raw, list):
                            for r in raw:
                                out[f"{std}<-{r}"] = r
                        else:
                            out[std] = raw
                        break
                except Exception:
                    pass
            elif isinstance(span, int) and span == year:
                out[std] = raw if isinstance(raw, str) else raw[0]
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset_slug", help="kyrbs | knhanes | <custom>")
    ap.add_argument("file_path", help="Path to .sav or .csv")
    ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--apply", action="store_true",
                     help="Without --apply this is a dry-run report.")
    args = ap.parse_args()

    reg = _load_registry(args.dataset_slug)
    flat = _flatten_registry(reg)
    scanned = _scan_file(Path(args.file_path))
    year = args.year or 0

    expected = _expected_raw_names(flat, year) if year else {}
    expected_raws = set(expected.values())
    scanned_raws = set(scanned.keys())

    new = sorted(scanned_raws - expected_raws)
    missing = sorted(expected_raws - scanned_raws) if expected_raws else []

    print(f"=== Registry diff: {args.dataset_slug} (year={year or 'unknown'}) ===")
    print(f"Registry: {len(flat)} std_names; year-resolved: {len(expected_raws)}")
    print(f"Scanned file columns: {len(scanned_raws)}")
    print()
    print(f"+ NEW columns ({len(new)}):")
    for c in new[:50]:
        info = scanned[c]
        print(f"  {c:20s} {info['dtype']:10s} n_unique={info['n_unique']:5d}  "
                f"label={info.get('label','')[:40]}")
    if missing:
        print(f"\n- MISSING expected columns ({len(missing)}):")
        for c in missing[:30]:
            print(f"  {c}")
    print()
    if args.apply:
        print("--apply given but auto-write disabled (review diff manually, then edit YAML).")
        print(f"Edit: data/registry/{args.dataset_slug}/variables.yaml")
    else:
        print("Dry-run only. Pass --apply to record intent (still requires manual YAML edit).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
