"""Dataset Library — 데이터셋과 변수 처리 방법을 라이브러리화

예: KYBRS, NHIS, KNHANES, Kangbuk Samsung Health Study 등
각 데이터셋의 변수 목록, 정의, 처리 방법, 분석 시 주의사항을 저장.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatasetLibrary:
    """데이터셋 변수 및 처리 방법 라이브러리.

    저장 구조 (per dataset)
    -----------------------
    {
      "name": "KYBRS",
      "full_name": "...",
      "description": "...",
      "variables": {
        "BMI": {
          "label": "Body Mass Index",
          "type": "continuous",
          "unit": "kg/m2",
          "processing": "calculated as weight/height^2",
          "cutoffs": {"underweight": <18.5, "normal": "18.5-24.9", ...},
          "missing_strategy": "exclude",
          "notes": ""
        },
        ...
      },
      "analysis_notes": [],   # 이 데이터셋 분석 시 주의사항
      "common_confounders": [], # 이 데이터에서 자주 쓰는 공변량
      "papers_using_this": []   # 이 데이터 쓴 논문 목록
    }
    """

    def __init__(self, library_dir: str = "data/libraries"):
        self._dir = Path(library_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._datasets: Dict[str, Dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_all(self):
        for f in self._dir.glob("dataset_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    ds = json.load(fp)
                    self._datasets[ds["name"]] = ds
            except Exception:
                pass

    def _save(self, name: str):
        path = self._dir / f"dataset_{name.lower()}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._datasets[name], f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------

    def add_dataset(self, name: str, full_name: str = "", description: str = "") -> Dict:
        """새 데이터셋 등록."""
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
        """변수 추가 또는 업데이트.

        kwargs 예시:
            label="Body Mass Index"
            type="continuous"  # continuous / categorical / binary / ordinal
            unit="kg/m2"
            processing="weight(kg)/height(m)^2"
            cutoffs={"underweight": "<18.5", "normal": "18.5-24.9"}
            missing_strategy="exclude"  # exclude / impute / carry_forward
            notes="WHO 기준 적용"
        """
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
        """자주 쓰는 공변량으로 등록."""
        if dataset_name in self._datasets:
            conf = self._datasets[dataset_name]["common_confounders"]
            if var_name not in conf:
                conf.append(var_name)
                self._save(dataset_name)

    def add_analysis_note(self, dataset_name: str, note: str):
        """분석 주의사항 추가."""
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
        """Claude 프롬프트에 삽입할 데이터셋 컨텍스트 생성."""
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
