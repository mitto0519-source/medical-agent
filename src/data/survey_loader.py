"""Survey Data Loader — KYRBS/KNHANES CSV/Excel 로더 + 스키마 표준화.

실제 공공데이터 파일 업로드 시 자동 스키마 감지 + 컬럼명 표준화.
합성 데이터 생성 기능 없음 — 반드시 실제 원시자료를 사용해야 함.

사용:
    loader = SurveyLoader()
    df, dataset = loader.load_csv("kyrbs_2022.csv")
    info = loader.describe(df)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from src.config.logging_config import get_logger

_log = get_logger(__name__)

# ── KYRBS 표준 컬럼 스키마 ────────────────────────────────────────────────────
KYRBS_SCHEMA: Dict[str, Dict] = {
    # 인구학적
    "sex":          {"label": "성별", "type": "binary", "values": [1, 2], "labels": ["남", "여"]},
    "grade":        {"label": "학년", "type": "ordinal", "values": [1,2,3,4,5,6]},
    "school_type":  {"label": "학교유형", "type": "categorical", "values": [1,2,3], "labels": ["초","중","고"]},
    "region":       {"label": "지역", "type": "categorical"},
    "family_econ":  {"label": "가정경제상태", "type": "ordinal", "values": [1,2,3,4,5]},
    "academic_perf":{"label": "학업성적", "type": "ordinal", "values": [1,2,3,4,5]},
    # 신체계측
    "height":       {"label": "신장(cm)", "type": "continuous"},
    "weight":       {"label": "체중(kg)", "type": "continuous"},
    "bmi":          {"label": "BMI(kg/m²)", "type": "continuous"},
    "obesity":      {"label": "비만여부", "type": "binary", "values": [0,1]},
    # 건강행태
    "sleep_hours":  {"label": "수면시간(h)", "type": "continuous"},
    "sleep_satis":  {"label": "수면충족감", "type": "binary", "values": [1,2]},
    "screen_time":  {"label": "스마트폰이용시간(h)", "type": "continuous"},
    "physical_act": {"label": "신체활동일수(days/week)", "type": "continuous"},
    "smoking":      {"label": "현재흡연", "type": "binary", "values": [0,1]},
    "alcohol":      {"label": "현재음주", "type": "binary", "values": [0,1]},
    # 정신건강
    "stress":       {"label": "스트레스인지율", "type": "ordinal", "values": [1,2,3,4,5]},
    "depression":   {"label": "우울감경험", "type": "binary", "values": [0,1]},
    "suicidal":     {"label": "자살생각", "type": "binary", "values": [0,1]},
    "loneliness":   {"label": "외로움", "type": "binary", "values": [0,1]},
    # 식이
    "breakfast":    {"label": "아침식사빈도(days/week)", "type": "continuous"},
    "fruit":        {"label": "과일섭취빈도", "type": "ordinal"},
    "vegetable":    {"label": "채소섭취빈도", "type": "ordinal"},
    "fast_food":    {"label": "패스트푸드섭취빈도", "type": "ordinal"},
    # 가중치
    "weight_var":   {"label": "표본가중치", "type": "continuous"},
    "strata":       {"label": "층화변수", "type": "categorical"},
    "cluster":      {"label": "군집변수", "type": "categorical"},
}

KNHANES_SCHEMA: Dict[str, Dict] = {
    "sex":          {"label": "성별", "type": "binary", "values": [1, 2]},
    "age":          {"label": "연령", "type": "continuous"},
    "edu":          {"label": "교육수준", "type": "ordinal"},
    "income":       {"label": "소득수준(사분위)", "type": "ordinal", "values": [1,2,3,4]},
    "bmi":          {"label": "BMI", "type": "continuous"},
    "waist":        {"label": "허리둘레(cm)", "type": "continuous"},
    "sbp":          {"label": "수축기혈압(mmHg)", "type": "continuous"},
    "dbp":          {"label": "이완기혈압(mmHg)", "type": "continuous"},
    "glucose":      {"label": "공복혈당(mg/dL)", "type": "continuous"},
    "hba1c":        {"label": "당화혈색소(%)", "type": "continuous"},
    "total_chol":   {"label": "총콜레스테롤(mg/dL)", "type": "continuous"},
    "hdl":          {"label": "HDL콜레스테롤", "type": "continuous"},
    "ldl":          {"label": "LDL콜레스테롤", "type": "continuous"},
    "trigly":       {"label": "중성지방(mg/dL)", "type": "continuous"},
    "diabetes":     {"label": "당뇨진단", "type": "binary", "values": [0,1]},
    "hypertension": {"label": "고혈압진단", "type": "binary", "values": [0,1]},
    "metabolic_syn":{"label": "대사증후군", "type": "binary", "values": [0,1]},
    "smoking":      {"label": "흡연상태", "type": "categorical"},
    "alcohol":      {"label": "음주빈도", "type": "ordinal"},
    "physical_act": {"label": "신체활동", "type": "binary"},
    "sleep_hours":  {"label": "수면시간", "type": "continuous"},
    "weight_var":   {"label": "검진가중치", "type": "continuous"},
    "strata":       {"label": "층화변수", "type": "categorical"},
    "cluster":      {"label": "군집PSU", "type": "categorical"},
}


class SurveyLoader:
    """KYRBS/KNHANES 데이터 로더 — 실제 원시자료 전용."""

    SCHEMAS = {"KYRBS": KYRBS_SCHEMA, "KNHANES": KNHANES_SCHEMA}

    def load_csv(self, path: str, dataset: str = "auto") -> Tuple[pd.DataFrame, str]:
        """CSV/Excel 파일 로드 + 데이터셋 자동 감지.

        Returns:
            (DataFrame, detected_dataset_name)
        """
        p = Path(path)
        if p.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    df = pd.read_csv(path, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(path, encoding="utf-8", errors="replace")

        if dataset == "auto":
            dataset = self._detect_dataset(df)

        df = self._standardize(df, dataset)
        _log.info("로드 완료: %d행 × %d열 (%s)", df.shape[0], df.shape[1], dataset)
        return df, dataset

    def describe(self, df: pd.DataFrame) -> Dict:
        """데이터 요약 통계 반환."""
        desc: Dict = {
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "columns": list(df.columns),
            "missing": df.isnull().sum().to_dict(),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        }
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            desc["summary"] = df[numeric_cols].describe().round(3).to_dict()
        return desc

    # ── 내부 ─────────────────────────────────────────────────────────────

    def _detect_dataset(self, df: pd.DataFrame) -> str:
        cols_lower = {c.lower() for c in df.columns}
        kyrbs_hints = {"grade", "school_type", "sleep_satis", "academic_perf"}
        knhanes_hints = {"sbp", "dbp", "hba1c", "total_chol", "waist"}
        kyrbs_score = len(kyrbs_hints & cols_lower)
        knhanes_score = len(knhanes_hints & cols_lower)
        return "KYRBS" if kyrbs_score >= knhanes_score else "KNHANES"

    def _standardize(self, df: pd.DataFrame, dataset: str) -> pd.DataFrame:
        """컬럼명 표준화 (한글/영문 컬럼 → 스키마 키로 매핑)."""
        schema = self.SCHEMAS.get(dataset, {})
        rename_map = {}
        for col in df.columns:
            col_l = col.lower().strip()
            for key, meta in schema.items():
                if col_l == key or col_l == meta.get("label", "").lower():
                    rename_map[col] = key
                    break
        if rename_map:
            df = df.rename(columns=rename_map)
        return df
