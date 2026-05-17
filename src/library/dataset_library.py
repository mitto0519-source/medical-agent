"""Dataset Library — Supabase (cloud) + local JSON fallback.

Cloud: ma_datasets table (name PRIMARY KEY, JSONB columns)
Local: data/libraries/dataset_*.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _cloud():
    from src.cloud.db import cloud_available
    return cloud_available()


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


class DatasetLibrary:
    """데이터셋 변수 및 처리 방법 라이브러리 — Supabase + 로컬 이중 저장."""

    def __init__(self, library_dir: str = "data/libraries"):
        self._dir = Path(library_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._datasets: Dict[str, Dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_all(self):
        # ── Cloud read ─────────────────────────────────────────────────
        if _cloud():
            try:
                from sqlalchemy import text
                with _engine().connect() as conn:
                    rows = conn.execute(text("SELECT * FROM ma_datasets")).mappings().all()
                for row in rows:
                    self._datasets[row["name"]] = {
                        "name": row["name"],
                        "full_name": row["full_name"] or "",
                        "description": row["description"] or "",
                        "variables": row["variables"] or {},
                        "analysis_notes": row["analysis_notes"] or [],
                        "common_confounders": row["common_confounders"] or [],
                        "papers_using_this": row["papers_using_this"] or [],
                    }
            except Exception as e:
                _log.warning(f"Cloud dataset load failed: {e}")

        # ── Always merge local JSON files (fills gaps not in cloud) ────
        for f in self._dir.glob("dataset_*.json"):
            try:
                ds = json.loads(f.read_text(encoding="utf-8"))
                name = ds.get("name")
                if name and name not in self._datasets:
                    self._datasets[name] = ds
            except Exception:
                pass

    def _save(self, name: str):
        # ── Always write local JSON ────────────────────────────────────
        path = self._dir / f"dataset_{name.lower()}.json"
        path.write_text(
            json.dumps(self._datasets[name], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # ── Cloud UPSERT ───────────────────────────────────────────────
        if _cloud():
            try:
                from sqlalchemy import text
                ds = self._datasets[name]
                with _engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ma_datasets
                            (name, full_name, description, variables,
                             analysis_notes, common_confounders, papers_using_this, updated_at)
                        VALUES
                            (:name, :full_name, :description,
                             CAST(:variables AS jsonb), CAST(:analysis_notes AS jsonb),
                             CAST(:common_confounders AS jsonb), CAST(:papers_using_this AS jsonb),
                             NOW())
                        ON CONFLICT (name) DO UPDATE SET
                            full_name          = EXCLUDED.full_name,
                            description        = EXCLUDED.description,
                            variables          = EXCLUDED.variables,
                            analysis_notes     = EXCLUDED.analysis_notes,
                            common_confounders = EXCLUDED.common_confounders,
                            papers_using_this  = EXCLUDED.papers_using_this,
                            updated_at         = NOW()
                    """), {
                        "name": name,
                        "full_name": ds.get("full_name", ""),
                        "description": ds.get("description", ""),
                        "variables": json.dumps(ds.get("variables", {}), ensure_ascii=False),
                        "analysis_notes": json.dumps(ds.get("analysis_notes", []), ensure_ascii=False),
                        "common_confounders": json.dumps(ds.get("common_confounders", []), ensure_ascii=False),
                        "papers_using_this": json.dumps(ds.get("papers_using_this", []), ensure_ascii=False),
                    })
            except Exception as e:
                _log.warning(f"Cloud dataset save failed for '{name}': {e}")

    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------

    def add_dataset(self, name: str, full_name: str = "", description: str = "") -> Dict:
        if name not in self._datasets:
            self._datasets[name] = {
                "name": name,
                "full_name": full_name or name,
                "description": description,
                "variables": {},
                "analysis_notes": [],
                "common_confounders": [],
                "papers_using_this": [],
            }
            self._save(name)
        return self._datasets[name]

    def get_dataset(self, name: str) -> Optional[Dict]:
        return self._datasets.get(name)

    def list_datasets(self) -> List[str]:
        return list(self._datasets.keys())

    # ------------------------------------------------------------------
    # Variable management
    # ------------------------------------------------------------------

    def add_variable(self, dataset_name: str, var_name: str, **kwargs) -> Dict:
        if dataset_name not in self._datasets:
            self.add_dataset(dataset_name)

        self._datasets[dataset_name]["variables"][var_name] = {
            "label": kwargs.get("label", var_name),
            "type": kwargs.get("type", "unknown"),
            "unit": kwargs.get("unit", ""),
            "processing": kwargs.get("processing", ""),
            "cutoffs": kwargs.get("cutoffs", {}),
            "missing_strategy": kwargs.get("missing_strategy", "exclude"),
            "notes": kwargs.get("notes", ""),
        }
        self._save(dataset_name)
        return self._datasets[dataset_name]["variables"][var_name]

    def get_variable(self, dataset_name: str, var_name: str) -> Optional[Dict]:
        ds = self._datasets.get(dataset_name, {})
        return ds.get("variables", {}).get(var_name)

    def add_confounder(self, dataset_name: str, var_name: str):
        if dataset_name in self._datasets:
            conf = self._datasets[dataset_name]["common_confounders"]
            if var_name not in conf:
                conf.append(var_name)
                self._save(dataset_name)

    def add_analysis_note(self, dataset_name: str, note: str):
        if dataset_name in self._datasets:
            self._datasets[dataset_name]["analysis_notes"].append(note)
            self._save(dataset_name)

    def add_paper_reference(self, dataset_name: str, paper_title: str):
        if dataset_name in self._datasets:
            refs = self._datasets[dataset_name]["papers_using_this"]
            if paper_title not in refs:
                refs.append(paper_title)
                self._save(dataset_name)

    # ------------------------------------------------------------------
    # Context builder for Claude prompts
    # ------------------------------------------------------------------

    def get_context(self, dataset_name: str, variables: Optional[List[str]] = None) -> str:
        ds = self._datasets.get(dataset_name)
        if not ds:
            return f"Dataset '{dataset_name}' not found in library."

        vars_to_show = ds["variables"]
        if variables:
            vars_to_show = {k: v for k, v in vars_to_show.items() if k in variables}

        lines = [
            f"DATASET: {ds['full_name']} ({ds['name']})",
            f"Description: {ds['description']}",
            "",
            "VARIABLES:",
        ]
        for var, info in vars_to_show.items():
            lines.append(f"  {var} ({info['label']}): {info['type']}, unit={info['unit']}")
            if info["processing"]:
                lines.append(f"    Processing: {info['processing']}")
            if info["cutoffs"]:
                lines.append(f"    Cutoffs: {info['cutoffs']}")
            if info["notes"]:
                lines.append(f"    Notes: {info['notes']}")

        if ds["common_confounders"]:
            lines.append(f"\nCOMMON CONFOUNDERS: {', '.join(ds['common_confounders'])}")

        if ds["analysis_notes"]:
            lines.append("\nANALYSIS NOTES:")
            for note in ds["analysis_notes"]:
                lines.append(f"  - {note}")

        return "\n".join(lines)
