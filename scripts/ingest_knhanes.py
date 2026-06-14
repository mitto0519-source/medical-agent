"""KNHANES one-shot DB ingest — auto-detect HN<YY>_ALL.sav, extract, persist.

Pipeline (per year file detected):
    1. read .sav via pyreadstat
    2. resolve std_name aliases via data/registry/knhanes/variables.yaml
    3. compute coverage report (n_rows, n_cols, n_std_names_present)
    4. register wave in data/library/dataset_knhanes.json (LOCAL catalog)
    5. mirror catalog row to Supabase ma_datasets (if cloud_available)
    6. append events.db audit record
    7. emit summary

Usage:
    python scripts/ingest_knhanes.py           # all years detected
    python scripts/ingest_knhanes.py --year 2023   # one year

User flow:
    1. Apply on https://knhanes.kdca.go.kr (KDCA approval needed, ~1-3 days)
    2. Download HN<YY>_ALL.sav for each wave
    3. Drop files into data/raw/knhanes/  → run this script.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def _ingest_one(year: int) -> dict:
    from src.data import knhanes_raw_loader as kl
    df = kl.load_knhanes_year(year)
    if df is None:
        return {"year": year, "ok": False, "error": "load failed (file missing or unreadable)"}

    expected = kl._expected_raw_names(year)
    present_raw = [r for r in expected.values() if r in df.columns]
    n_rows = len(df)
    n_cols = len(df.columns)

    report = {
        "year": year,
        "ok": True,
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "expected_std_vars": len(expected),
        "present_std_vars": len(present_raw),
        "missing_std_vars": sorted(set(expected.values()) - set(present_raw))[:20],
        "ingested_at": time.time(),
    }
    return report


def _register_in_catalog(reports: list[dict]) -> None:
    """Append to data/library/dataset_knhanes.json."""
    catalog_path = _ROOT / "data" / "library" / "dataset_knhanes.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        existing = {"dataset": "KNHANES", "waves": []}
    waves = {w.get("year"): w for w in existing.get("waves", [])}
    for r in reports:
        if r.get("ok"):
            waves[r["year"]] = r
    existing["waves"] = sorted(waves.values(), key=lambda x: x.get("year", 0))
    existing["updated_at"] = time.time()
    catalog_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"  ✓ catalog updated: {catalog_path}")


def _push_to_supabase(reports: list[dict]) -> None:
    try:
        from src.cloud.db import cloud_available, get_supabase
        if not cloud_available():
            print("  ~ Supabase unavailable — local catalog only.")
            return
        sb = get_supabase()
        for r in reports:
            if not r.get("ok"):
                continue
            row = {
                "dataset": "KNHANES",
                "year": r["year"],
                "n_rows": r["n_rows"],
                "n_cols": r["n_cols"],
                "present_std_vars": r["present_std_vars"],
                "ingested_at": int(r["ingested_at"]),
            }
            try:
                sb.table("ma_datasets").upsert(row,
                    on_conflict="dataset,year").execute()
            except Exception as e:
                print(f"  ! Supabase upsert {r['year']} fail: {e}")
        print(f"  ✓ Supabase ma_datasets upserted: {sum(1 for r in reports if r.get('ok'))} rows")
    except Exception as e:
        print(f"  ! Supabase push fail: {e}")


def _audit_record(reports: list[dict]) -> None:
    try:
        from src.runtime.events import append as _evt
        _evt(type="knhanes_ingest",
              payload={"reports": reports},
              actor="ingest_knhanes")
        from src.memory import change_log
        change_log.log(
            title=f"KNHANES ingest: {sum(1 for r in reports if r.get('ok'))} waves",
            action_type="data_pipeline",
            description=f"Auto-detected {len(reports)} files; "
                          f"{sum(1 for r in reports if r.get('ok'))} succeeded.",
            why_better="KNHANES catalog mirrors KYRBS coverage; registry-driven std_name aliases applied.",
            impact={"dataset": "KNHANES",
                     "years": [r['year'] for r in reports if r.get('ok')]},
        )
    except Exception as e:
        print(f"  ! audit record fail: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=0,
                    help="One year only. Default: all detected years.")
    args = ap.parse_args()

    from src.data import knhanes_raw_loader as kl
    avail = kl.list_available_years()
    if not avail:
        print("⚠ No HN<YY>_ALL.sav files found in data/raw/knhanes/")
        print("  Place files there first. See data/registry/knhanes/variables.yaml for naming.")
        return 1

    targets = [args.year] if args.year else avail
    print(f"=== KNHANES ingest — targets: {targets} ===\n")
    reports: list[dict] = []
    for y in targets:
        print(f"  → ingest {y} ...")
        r = _ingest_one(y)
        reports.append(r)
        if r["ok"]:
            print(f"    rows={r['n_rows']:,}  cols={r['n_cols']}  "
                  f"std_vars={r['present_std_vars']}/{r['expected_std_vars']}")
        else:
            print(f"    FAIL: {r.get('error')}")

    print("\n--- persisting ---")
    _register_in_catalog(reports)
    _push_to_supabase(reports)
    _audit_record(reports)

    ok = sum(1 for r in reports if r.get("ok"))
    print(f"\n=== done: {ok}/{len(reports)} years ingested ===")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
