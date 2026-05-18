"""Survey Data Loader — KYRBS/KNHANES CSV 로더 + 합성 데모 데이터 생성기.

실제 공공데이터 CSV 업로드 시 자동 스키마 감지 + 표준화.
데이터 없을 때는 연구 설계와 동일한 구조의 합성 데이터를 생성해
파이프라인 시연 및 테스트에 사용.

사용:
    loader = SurveyLoader()
    df = loader.load_csv("kyrbs_2022.csv")
    # 또는
    df = loader.generate_synthetic("KYRBS", n=5000, seed=42)
    info = loader.describe(df)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
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
    """KYRBS/KNHANES 데이터 로더 및 합성 데이터 생성기."""

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
            # Try common Korean encodings
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

    def generate_synthetic(
        self,
        dataset: str = "KYRBS",
        n: int = 5000,
        seed: int = 42,
        study_spec: Optional[Dict] = None,
    ) -> pd.DataFrame:
        """연구 설계에 맞는 합성 서베이 데이터 생성.

        실제 KYRBS/KNHANES 통계치를 기반으로 현실적 분포로 생성.
        """
        rng = np.random.default_rng(seed)
        spec = study_spec or {}

        if dataset == "KYRBS":
            return self._synthetic_kyrbs(rng, n, spec)
        elif dataset == "KNHANES":
            return self._synthetic_knhanes(rng, n, spec)
        else:
            raise ValueError(f"지원하지 않는 데이터셋: {dataset}")

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

    def _synthetic_kyrbs(self, rng: np.random.Generator, n: int, spec: Dict) -> pd.DataFrame:
        """실제 KYRBS 분포 기반 합성 데이터 (2019-2022 통계치 참조)."""
        sex = rng.choice([1, 2], n, p=[0.51, 0.49])
        grade = rng.choice([1,2,3,4,5,6], n)
        school_type = rng.choice([1,2,3], n, p=[0.37, 0.33, 0.30])
        family_econ = rng.choice([1,2,3,4,5], n, p=[0.06, 0.18, 0.45, 0.22, 0.09])
        academic_perf = rng.choice([1,2,3,4,5], n, p=[0.11, 0.24, 0.32, 0.23, 0.10])

        # 신체계측 (성별-연령 보정)
        height_base = np.where(sex==1, 170.5, 158.8)
        height = height_base + rng.normal(0, 6, n)
        weight = np.where(sex==1, 64.2, 53.1) + rng.normal(0, 10, n)
        bmi = weight / ((height / 100) ** 2)
        obesity = (bmi >= 25).astype(int)

        # 수면
        sleep_hours = np.clip(rng.normal(6.8, 1.2, n), 3, 12)
        sleep_satis = (sleep_hours >= 7).astype(int) + 1  # 1=불충족, 2=충족

        # 스마트폰
        screen_time = np.clip(rng.lognormal(1.5, 0.7, n), 0, 16)

        # 신체활동
        physical_act = np.clip(rng.normal(3.2, 2.1, n), 0, 7)

        # 흡연/음주 (실제 유병률 반영)
        smoking_prob = 0.066 + 0.03 * (sex == 1)
        smoking = rng.binomial(1, smoking_prob, n)
        alcohol_prob = 0.152 + 0.02 * (sex == 1)
        alcohol = rng.binomial(1, alcohol_prob, n)

        # 정신건강 (수면, 스마트폰과 상관 반영)
        stress_base = 0.35 + 0.08 * (sleep_hours < 6) + 0.05 * (screen_time > 4)
        stress_base = np.clip(stress_base + 0.05 * (sex == 2), 0.1, 0.9)
        stress = rng.choice([1,2,3,4,5], n,
                            p=None)  # simplified
        stress = np.clip(np.round(rng.normal(3.0 + 0.5*(sleep_hours<6) + 0.1*(sex==2), 0.8)), 1, 5).astype(int)

        depr_logit = -2.2 + 0.4*(sex==2) + 0.5*(sleep_hours<6) + 0.3*(screen_time>4) + 0.3*smoking
        depression = rng.binomial(1, _sigmoid(depr_logit), n)

        suicide_logit = -3.5 + 0.6*depression + 0.3*(sleep_hours<6) + 0.2*(family_econ<=2)
        suicidal = rng.binomial(1, _sigmoid(suicide_logit), n)

        loneliness_logit = -2.0 + 0.5*(screen_time>5) + 0.3*(physical_act<1) + 0.3*(family_econ<=2)
        loneliness = rng.binomial(1, _sigmoid(loneliness_logit), n)

        # 식이
        breakfast = np.clip(rng.normal(4.5, 2.0, n), 0, 7)

        # 가중치 (복합표본설계)
        weight_var = rng.lognormal(np.log(n/n), 0.3, n)
        strata = rng.integers(1, 50, n)
        cluster = rng.integers(1, 200, n)

        df = pd.DataFrame({
            "sex": sex, "grade": grade, "school_type": school_type,
            "family_econ": family_econ, "academic_perf": academic_perf,
            "height": height.round(1), "weight": weight.round(1),
            "bmi": bmi.round(2), "obesity": obesity,
            "sleep_hours": sleep_hours.round(1), "sleep_satis": sleep_satis,
            "screen_time": screen_time.round(1), "physical_act": physical_act.round(1),
            "smoking": smoking, "alcohol": alcohol,
            "stress": stress, "depression": depression,
            "suicidal": suicidal, "loneliness": loneliness,
            "breakfast": breakfast.round(1),
            "weight_var": weight_var.round(4),
            "strata": strata, "cluster": cluster,
        })
        return df

    def _synthetic_knhanes(self, rng: np.random.Generator, n: int, spec: Dict) -> pd.DataFrame:
        """실제 KNHANES 분포 기반 합성 데이터 (7기 2016-2018 통계치 참조)."""
        sex = rng.choice([1, 2], n, p=[0.49, 0.51])
        age = np.clip(rng.normal(46.5, 16.2, n), 19, 80).round().astype(int)
        edu = rng.choice([1,2,3,4], n, p=[0.15, 0.25, 0.38, 0.22])
        income = rng.choice([1,2,3,4], n, p=[0.25, 0.25, 0.25, 0.25])

        # 신체계측
        bmi = np.clip(rng.normal(24.2, 3.8, n), 16, 42)
        waist = np.clip(
            np.where(sex==1, rng.normal(85.2, 9.5, n), rng.normal(76.5, 9.2, n)),
            55, 130
        )

        # 혈압 (나이 상관)
        sbp = np.clip(rng.normal(119 + 0.4*age, 16, n), 80, 200)
        dbp = np.clip(rng.normal(76 + 0.15*age, 11, n), 50, 130)

        # 혈액검사
        glucose = np.clip(rng.lognormal(np.log(98), 0.18, n), 70, 400)
        hba1c = np.clip(rng.normal(5.7, 0.6, n), 4.5, 14)
        total_chol = np.clip(rng.normal(196, 38, n), 100, 350)
        hdl = np.clip(np.where(sex==1, rng.normal(50, 12, n), rng.normal(58, 13, n)), 20, 100)
        ldl = np.clip(rng.normal(118, 34, n), 40, 280)
        trigly = np.clip(rng.lognormal(np.log(130), 0.55, n), 30, 600)

        # 질환 유병
        diab_logit = -4.5 + 0.05*age + 0.4*(bmi>=25) + 0.6*(glucose>=100)
        diabetes = rng.binomial(1, _sigmoid(diab_logit), n)
        htn_logit = -3.2 + 0.06*age + 0.5*(bmi>=25) + 0.01*(sbp-120)
        hypertension = rng.binomial(1, _sigmoid(htn_logit), n)
        ms_criteria = ((waist >= np.where(sex==1, 90, 85)).astype(int)
                       + (trigly >= 150).astype(int)
                       + (hdl < np.where(sex==1, 40, 50)).astype(int)
                       + (sbp >= 130).astype(int)
                       + (glucose >= 100).astype(int))
        metabolic_syn = (ms_criteria >= 3).astype(int)

        smoking = rng.choice([0,1,2], n, p=[0.62, 0.15, 0.23])
        alcohol = rng.choice([1,2,3,4,5], n, p=[0.18, 0.25, 0.28, 0.20, 0.09])
        physical_act = rng.binomial(1, 0.45, n)
        sleep_hours = np.clip(rng.normal(6.9, 1.3, n), 3, 12)

        weight_var = rng.lognormal(np.log(n/n), 0.35, n)
        strata = rng.integers(1, 100, n)
        cluster = rng.integers(1, 500, n)

        df = pd.DataFrame({
            "sex": sex, "age": age, "edu": edu, "income": income,
            "bmi": bmi.round(2), "waist": waist.round(1),
            "sbp": sbp.round(1), "dbp": dbp.round(1),
            "glucose": glucose.round(1), "hba1c": hba1c.round(2),
            "total_chol": total_chol.round(1), "hdl": hdl.round(1),
            "ldl": ldl.round(1), "trigly": trigly.round(1),
            "diabetes": diabetes, "hypertension": hypertension,
            "metabolic_syn": metabolic_syn,
            "smoking": smoking, "alcohol": alcohol,
            "physical_act": physical_act, "sleep_hours": sleep_hours.round(1),
            "weight_var": weight_var.round(4),
            "strata": strata, "cluster": cluster,
        })
        return df


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -20, 20)))
