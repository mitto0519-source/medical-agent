"""KYRBS 원시자료 실제 로더 — 질병관리청 공식 .sav/.csv 파일 처리.

질병관리청(KDCA) 청소년건강행태조사(KYRBS) 원시자료를 직접 읽어서
표준 분석 스키마로 변환한다.

원시자료 다운로드:
    https://www.kdca.go.kr/yhs/
    → 자료마당 → 원시자료 신청 (무료, 회원가입 필요)
    파일 형식: SPSS (.sav) + 코드북 PDF

지원 차수: 제15차(2019) ~ 제21차(2025)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# 차수별 변수 코드 매핑 (KYRBS 공식 코드북 기준)
# ---------------------------------------------------------------------------
# 형식: {표준명: [가능한 원시 변수코드들]} — 앞쪽 코드가 우선
# 제21차(2025) 실측 컬럼명 기준으로 작성; 구버전 후보는 fallback으로 유지

_VAR_MAP: dict[str, list[str]] = {
    # ── 복합표본 설계변수 (필수) ──────────────────────────────────────────
    # 제21차(2025) 실측: W / STRATA(text) / CLUSTER
    "weight_var": ["W",       "M_wt",  "mwt",   "M_WT",  "wt"],
    "strata":     ["STRATA",  "M_str", "mstr",  "M_STR", "str"],
    "cluster":    ["CLUSTER", "M_clu", "mclu",  "M_CLU", "psu"],

    # ── 기본 인구통계 ─────────────────────────────────────────────────────
    "sex":         ["SEX",    "E_SEX", "sex",   "e_sex"],          # 1=남, 2=여
    "age":         ["AGE",    "E_AGE", "age",   "e_age"],
    "school_type": ["SCHOOL", "E_SCH", "sch",   "SCH"],            # text: 중학교/고등학교
    "grade":       ["GRADE",  "E_GR",  "gr",    "GR",  "grade"],   # 1~3학년

    # ── 가정·경제 ─────────────────────────────────────────────────────────
    "family_econ":   ["E_SES",   "E_ECO", "eco", "ECO"],           # 1=상~5=하
    "academic_perf": ["E_S_RCRD","E_SCR", "scr", "SCR"],           # 성적 1=상~5=하

    # ── 신체계측 ──────────────────────────────────────────────────────────
    # 제21차: HT(키) / WT(몸무게) — BMI는 없으므로 계산 필요
    "height":    ["HT",  "E_HT",  "ht",  "height"],
    "weight_kg": ["WT",  "E_WGT", "wgt", "WGT", "E_WG"],          # kg (BMI 계산용)

    # ── 수면 ──────────────────────────────────────────────────────────────
    # 2007~2025: M_SLP_HR(취침시각) + M_WK_HR(기상시각) → sleep_hours 계산
    # 2005~2006: M_SLP_DR(수면시간, 직접기록) — 계산 불필요
    "sleep_start_hr": ["M_SLP_HR", "J_SLS",  "SLS",  "sleep_start"], # 취침 시각(시)
    "wake_hr":        ["M_WK_HR",  "J_WK",   "WK",   "wake_hr"],     # 기상 시각(시)
    "sleep_hours_raw":["M_SLP_DR"],                                    # 직접 수면시간(2005-06)
    "sleep_satis":    ["M_SLP_EN", "J_SLS2", "J_SLSA", "sleep_sat"], # 수면 만족

    # ── 정신건강 ──────────────────────────────────────────────────────────
    # 전 연도 동일 코딩: M_SAD 1=없음, 2=있음(우울) — 2005~2025 일관
    "stress":     ["M_STR",     "C_STR",  "STR",  "stress"],
    "depression": ["M_SAD",     "C_DEP",  "DEP",  "depression"],
    "suicidal":   ["M_SUI_CON", "C_SUI",  "SUI",  "suicidal"],

    # ── 신체활동 ──────────────────────────────────────────────────────────
    # 2022~2025: PA_VIG_D (변수명 변경), 2005~2021: PA_VIG — 동일 개념
    "physical_act": ["PA_VIG_D", "PA_VIG", "J_PAT", "PAT"],         # 격렬 신체활동 일수

    # ── 스크린 타임 ───────────────────────────────────────────────────────
    # 2020~2025: INT_SPWD_TM = 스마트폰 주중 이용시간(분) — 특화
    # 2007~2019: INT_WD_MM   = 인터넷(PC+모바일) 주중 이용시간(분) — 개념 다름 ⚠️
    # meta["screen_time_concept"]로 구분 필요
    "screen_time_min": ["INT_SPWD_TM", "INT_WD_MM", "J_SMT", "SMT"], # 분/일 → hours
    "screen_time_pc":  ["INT_CPWD_TM", "INT_WD_MM2", "J_CPT"],       # PC 주중 분/일

    # ── 흡연 (제21차: TC_LT=경험, TC_DAYS=최근흡연일, 9999=해당없음) ────────
    "smoking_ever": ["TC_LT",   "D_SMS", "SMS"],                    # 1=경험있음, 2=없음
    "smoking_days": ["TC_DAYS", "D_CUR", "CUR"],                    # 최근 흡연일수

    # ── 음주 (제21차: AC_LT=경험, AC_DAYS=최근음주일, 9999=해당없음) ────────
    "alcohol_ever": ["AC_LT",   "D_DRK", "DRK"],                    # 1=경험있음, 2=없음
    "alcohol_days": ["AC_DAYS", "D_ALC", "ALC"],                    # 최근 음주일수

    # ── 식생활 ────────────────────────────────────────────────────────────
    "breakfast": ["F_BR", "B_BRF", "BRF", "B_BR", "breakfast"],    # 아침식사 일수(주간)

    # ── 음료 섭취 빈도 (조유선 ZCB 단면연구 핵심 노출/공노출) ──────────────
    # 제21차(2025) 실측: 최근 7일 섭취 빈도 1=먹지않음 ~ 7=매일3회 이상 (연속 용량-반응)
    # 결측코드 없음(1~7) → 이진화/계산 없이 빈도 그대로 보존
    "zcb_freq":      ["F_ZERO"],    # 제로(무열량) 음료 — 주노출(exposure)
    "ssb_freq":      ["F_SWD_A"],   # 단맛(가당) 음료 — 공노출(co-exposure)
    "caffeine_freq": ["F_CAFF_A"],  # 카페인 음료 — 공노출(co-exposure)

    # ── 체형 인식 ─────────────────────────────────────────────────────────
    "perceived_height": ["PR_HT", "J_PHL", "PHL"],
    "perceived_body":   ["PR_BI", "J_PBO", "PBO"],
}

# 이진화가 필요한 변수들 (원시 코드 → 0/1 변환 규칙)
# 제21차(2025) 실측 코딩:
#   M_SAD: 1=없음(74%), 2=있음(26%)  →  "==2" 가 정확
#   M_SUI_CON: 1=없음(89%), 2=있음(11%) → "==2"
#   F_BR: 1=매일~7=주1일, 8=결식(26%)   → "==8"
# smoking/alcohol: 계산 변수(_standardize 내 처리)
_BINARIZE: dict[str, str] = {
    "depression":   "==2",   # M_SAD: 2=있음→1(우울있음), 1=없음→0
    "suicidal":     "==2",   # M_SUI_CON: 2=있음→1(자살생각있음)
    "physical_act": ">=3",   # PA_VIG_D: 주 3일 이상 격렬 신체활동
    "breakfast":    "==8",   # F_BR: 8=결식(주 0일)→1, 나머지→0
}

# 결측 처리 코드 (KYRBS 코드북 표준 결측값)
_MISSING_CODES = [88, 99, 888, 999, 9999, -1, -9]


# ---------------------------------------------------------------------------
# 메인 로더 클래스
# ---------------------------------------------------------------------------

class KYRBSLoader:
    """KYRBS 원시자료(.sav/.csv) 로더 및 표준 스키마 변환기.

    사용 흐름:
        loader = KYRBSLoader()
        df, meta = loader.load("raw/kyrbs_2025.sav")
        print(meta["survey_round"], meta["n"])
        # df는 표준 컬럼명으로 변환된 DataFrame

    지원 파일:
        - SPSS (.sav)  : pyreadstat 필요 (pip install pyreadstat)
        - CSV (.csv)   : pandas 기본 지원
        - Excel (.xlsx): pandas 기본 지원
    """

    def __init__(self, data_dir: str = "data/raw"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> tuple[pd.DataFrame, dict]:
        """원시 파일을 읽어 표준 컬럼 DataFrame + 메타정보 반환.

        Returns:
            (df, meta) where meta = {
                "survey_round": str,
                "n": int,
                "mapped_vars": list[str],
                "unmapped_raw": list[str],
                "encoding_info": dict,
                "warnings": list[str],
            }
        """
        path = Path(path)
        _log.info("KYRBS 원시자료 로드: %s", path.name)

        raw_df, value_labels = self._read_file(path)
        _log.info("원시 파일 로드 완료: %d행 × %d열", len(raw_df), len(raw_df.columns))

        df_std, meta = self._standardize(raw_df, value_labels)
        meta["source_file"] = path.name
        meta["n"] = len(df_std)

        _log.info(
            "표준화 완료: %d행, 매핑변수=%d개, 미매핑=%d개",
            meta["n"], len(meta["mapped_vars"]), len(meta["unmapped_raw"]),
        )
        return df_std, meta

    def load_bytes(self, file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
        """Streamlit UploadedFile 바이트에서 직접 로드."""
        import tempfile
        suffix = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_bytes)
            tmp_path = f.name
        try:
            return self.load(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def detect_survey_round(self, df: pd.DataFrame, filename: str = "") -> str:
        """파일명 또는 데이터로 차수 추정."""
        # 파일명에서 연도/차수 추출
        m = re.search(r"(20\d{2})|(\d{2}차)", filename)
        if m:
            token = m.group()
            year_map = {
                "2019": "제15차", "2020": "제16차", "2021": "제17차",
                "2022": "제18차", "2023": "제19차", "2024": "제20차",
                "2025": "제21차", "2026": "제22차",
            }
            for yr, rnd in year_map.items():
                if yr in token:
                    return rnd
            return token
        return "알 수 없음"

    def describe(self, df: pd.DataFrame) -> dict:
        """표준화된 DataFrame 기술통계 요약."""
        out: dict = {}
        for col in df.columns:
            s = df[col].dropna()
            if len(s) == 0:
                continue
            if col in ("weight_var", "strata", "cluster"):
                continue
            if s.dtype in (float, int, np.float64, np.int64):
                out[col] = {
                    "n": int(s.count()),
                    "missing": int(df[col].isna().sum()),
                    "mean": round(float(s.mean()), 3),
                    "std": round(float(s.std()), 3),
                    "median": round(float(s.median()), 3),
                    "min": float(s.min()),
                    "max": float(s.max()),
                }
            else:
                vc = s.value_counts()
                out[col] = {
                    "n": int(s.count()),
                    "missing": int(df[col].isna().sum()),
                    "categories": vc.head(8).to_dict(),
                }
        return out

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_file(self, path: Path) -> tuple[pd.DataFrame, dict]:
        """파일 확장자에 따라 적합한 리더로 읽기."""
        suffix = path.suffix.lower()

        if suffix == ".sav":
            return self._read_spss(path)
        elif suffix in (".csv", ".txt"):
            return self._read_csv(path), {}
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path, engine="openpyxl" if suffix == ".xlsx" else "xlrd")
            return df, {}
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {suffix} (지원: .sav, .csv, .xlsx)")

    def _read_spss(self, path: Path) -> tuple[pd.DataFrame, dict]:
        """SPSS .sav 파일 읽기 (pyreadstat 사용)."""
        try:
            import pyreadstat
        except ImportError:
            raise ImportError(
                "SPSS 파일을 읽으려면 pyreadstat이 필요합니다.\n"
                "설치: pip install pyreadstat"
            )

        _log.info("pyreadstat으로 SPSS 파일 읽는 중...")
        df, meta = pyreadstat.read_sav(
            str(path),
            apply_value_formats=False,   # 원시 숫자값 유지
            dates_as_pandas_datetime=False,
        )
        value_labels = getattr(meta, "variable_value_labels", {}) or {}
        _log.info("SPSS 로드: %d행 × %d열, 값레이블 %d개", len(df), len(df.columns), len(value_labels))
        return df, value_labels

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """CSV 파일 읽기 — 한국어 인코딩 자동 감지."""
        for enc in ("utf-8-sig", "euc-kr", "cp949", "utf-8"):
            try:
                df = pd.read_csv(path, encoding=enc, low_memory=False)
                _log.info("CSV 로드 성공 (encoding=%s): %d행", enc, len(df))
                return df
            except (UnicodeDecodeError, Exception):
                continue
        raise ValueError("CSV 인코딩 감지 실패 (utf-8, euc-kr, cp949 모두 실패)")

    # ------------------------------------------------------------------
    # Standardization
    # ------------------------------------------------------------------

    def _standardize(self, raw_df: pd.DataFrame, value_labels: dict) -> tuple[pd.DataFrame, dict]:
        """원시 변수코드 → 표준 컬럼명 + 결측치 처리 + 계산 변수 + 이진화."""
        raw_cols = {c.strip(): c for c in raw_df.columns}
        raw_cols_lower = {c.strip().lower(): c for c in raw_df.columns}

        mapped: dict[str, str] = {}
        warnings: list[str] = []

        for std_name, candidates in _VAR_MAP.items():
            for cand in candidates:
                if cand in raw_cols:
                    mapped[std_name] = raw_cols[cand]
                    break
                if cand.lower() in raw_cols_lower:
                    mapped[std_name] = raw_cols_lower[cand.lower()]
                    break
            if std_name not in mapped and std_name in ("sex", "weight_var", "depression", "strata", "cluster"):
                warnings.append(f"핵심 변수 '{std_name}' 매핑 실패 — 코드북 확인 필요")

        rename_map = {v: k for k, v in mapped.items()}
        df = raw_df[[v for v in mapped.values()]].rename(columns=rename_map).copy()

        # 결측치 처리: KYRBS 표준 결측 코드 → NaN
        for col in df.columns:
            if df[col].dtype in (float, int, np.float64, np.int64):
                df[col] = df[col].replace(_MISSING_CODES, np.nan)

        # 성별: 1=남→0, 2=여→1
        if "sex" in df.columns:
            df["sex"] = (df["sex"] == 2).astype(float)
            df.loc[df["sex"].isna(), "sex"] = np.nan

        # STRATA 문자 → 숫자 팩터 (복합표본 분석용)
        if "strata" in df.columns and df["strata"].dtype == object:
            df["strata"] = pd.factorize(df["strata"])[0].astype(float)
            df["strata"] = df["strata"].replace(-1, np.nan)

        # ── 계산 변수 ─────────────────────────────────────────────────────
        # BMI: HT(cm) + WT(kg) → kg/m²
        if "height" in df.columns and "weight_kg" in df.columns:
            h = pd.to_numeric(df["height"], errors="coerce")
            w = pd.to_numeric(df["weight_kg"], errors="coerce")
            bmi = w / (h / 100) ** 2
            df["bmi"] = bmi.where((h > 100) & (h < 230) & (w > 20) & (w < 200))
            df["obesity"] = (df["bmi"] >= 25).astype(float)
            df.loc[df["bmi"].isna(), "obesity"] = np.nan
            _log.info("BMI 계산: mean=%.1f, n=%d", df["bmi"].mean(), df["bmi"].notna().sum())

        # 수면 시간
        # 방법1: M_SLP_HR + M_WK_HR → 차이 계산 (2007~2025)
        if "sleep_start_hr" in df.columns and "wake_hr" in df.columns:
            s = pd.to_numeric(df["sleep_start_hr"], errors="coerce")
            w_hr = pd.to_numeric(df["wake_hr"], errors="coerce")
            hours = np.where(s > w_hr, w_hr + 24 - s, w_hr - s)
            hours_s = pd.Series(hours, index=df.index, dtype=float)
            df["sleep_hours"] = hours_s.where((hours_s >= 1) & (hours_s <= 16))
            _log.info("수면시간 계산(시각차): mean=%.1fh, n=%d", df["sleep_hours"].mean(), df["sleep_hours"].notna().sum())
        # 방법2: M_SLP_DR 직접 수면시간 (2005~2006)
        elif "sleep_hours_raw" in df.columns:
            raw_slp = pd.to_numeric(df["sleep_hours_raw"], errors="coerce")
            df["sleep_hours"] = raw_slp.where((raw_slp >= 1) & (raw_slp <= 16))
            df.drop(columns=["sleep_hours_raw"], inplace=True, errors="ignore")
            _log.info("수면시간(직접값): mean=%.1fh, n=%d", df["sleep_hours"].mean(), df["sleep_hours"].notna().sum())

        # 스크린 타임: 분/일 → 시간/일
        # INT_SPWD_TM(스마트폰, 2020~) vs INT_WD_MM(인터넷전체, 2007~2019) — 개념 다름
        if "screen_time_min" in df.columns:
            df["screen_time"] = pd.to_numeric(df["screen_time_min"], errors="coerce") / 60
            df["screen_time"] = df["screen_time"].where(df["screen_time"] <= 24)

        # 현재 흡연 — TC_LT + TC_DAYS
        # 제21차 실측: TC_LT=1=없음(50490), TC_LT=2=있음(3680)
        # TC_DAYS: TC_LT=2인 경우 실제 흡연일수(1-30), TC_LT=1은 9999→NaN
        if "smoking_ever" in df.columns:
            se = pd.to_numeric(df["smoking_ever"], errors="coerce")
            smoking = pd.Series(np.nan, index=df.index)
            smoking[se == 1] = 0.0  # TC_LT=1=없음 → 비흡연→0
            if "smoking_days" in df.columns:
                sd = pd.to_numeric(df["smoking_days"], errors="coerce")
                smoking[(se == 2) & (sd >= 1)] = 1.0  # TC_LT=2=있음, 최근 흡연 → 1
                smoking[(se == 2) & (sd < 1)]  = 0.0  # 있음이나 최근 흡연 0일 → 0
                smoking[(se == 2) & sd.isna()]  = 0.0  # 있음이나 days=NaN → 안전처리
            else:
                smoking[se == 2] = 1.0
            df["smoking"] = smoking
        elif "smoking_days" in df.columns:
            sd = pd.to_numeric(df["smoking_days"], errors="coerce")
            df["smoking"] = (sd >= 1).astype(float)
            df.loc[sd.isna(), "smoking"] = np.nan

        # 현재 음주 — AC_LT + AC_DAYS
        # 제21차 실측: AC_LT=1=없음(39491), AC_LT=2=있음(14679)
        if "alcohol_ever" in df.columns:
            ae = pd.to_numeric(df["alcohol_ever"], errors="coerce")
            alcohol = pd.Series(np.nan, index=df.index)
            alcohol[ae == 1] = 0.0  # AC_LT=1=없음 → 비음주→0
            if "alcohol_days" in df.columns:
                ad = pd.to_numeric(df["alcohol_days"], errors="coerce")
                alcohol[(ae == 2) & (ad >= 1)] = 1.0
                alcohol[(ae == 2) & (ad < 1)]  = 0.0
                alcohol[(ae == 2) & ad.isna()]  = 0.0
            else:
                alcohol[ae == 2] = 1.0
            df["alcohol"] = alcohol
        elif "alcohol_days" in df.columns:
            ad = pd.to_numeric(df["alcohol_days"], errors="coerce")
            df["alcohol"] = (ad >= 1).astype(float)
            df.loc[ad.isna(), "alcohol"] = np.nan

        # ── 이진화 (매핑 원시 변수 직접 변환) ────────────────────────────
        # breakfast(F_BR) 코딩 자동감지:
        #   2010 이전 = 4단계(4=결식), 2011 이후 = 8단계(8=결식)
        binarize_rules = dict(_BINARIZE)
        if "breakfast" in df.columns:
            br_max = pd.to_numeric(df["breakfast"], errors="coerce").max()
            if not np.isnan(br_max):
                binarize_rules["breakfast"] = "==4" if br_max <= 4 else "==8"
                _log.info("breakfast 코딩 자동감지: max=%.0f → 결식기준=%s", br_max, binarize_rules["breakfast"])

        for std_name, rule in binarize_rules.items():
            if std_name not in df.columns:
                continue
            col = pd.to_numeric(df[std_name], errors="coerce")
            try:
                if rule.startswith("=="):
                    val = float(rule[2:])
                    df[std_name] = (col == val).astype(float)
                    df.loc[col.isna(), std_name] = np.nan
                elif rule.startswith(">="):
                    val = float(rule[2:])
                    df[std_name] = (col >= val).astype(float)
                    df.loc[col.isna(), std_name] = np.nan
            except Exception as e:
                warnings.append(f"이진화 실패 '{std_name}': {e}")

        unmapped = [c for c in raw_df.columns if c not in mapped.values()]
        computed = [v for v in ("bmi", "obesity", "sleep_hours", "screen_time", "smoking", "alcohol") if v in df.columns]

        # screen_time 개념 구분 (분석 시 주의 필요)
        screen_concept = "none"
        if "screen_time_min" in mapped:
            raw_screen_col = mapped["screen_time_min"]
            if "SPWD" in raw_screen_col:
                screen_concept = "smartphone_weekday"   # 2020+
            elif "WD_MM" in raw_screen_col or "WK_MM" in raw_screen_col:
                screen_concept = "internet_weekday"     # 2007~2019 — 개념 다름 ⚠️
            else:
                screen_concept = "other"

        # 한계점 자동 기록
        limitations: list[str] = []
        if "sleep_hours" not in df.columns:
            limitations.append("수면시간 없음 (2005~2006: 취침/기상시각 미조사)")
        if screen_concept == "none":
            limitations.append("스크린타임 없음 (2005~2006: 스마트폰/인터넷 미조사)")
        elif screen_concept == "internet_weekday":
            limitations.append("스크린타임=인터넷전체(INT_WD_MM), 스마트폰 특화값 아님 — 2020+ 데이터와 직접 비교 불가")
        if "breakfast" in binarize_rules and binarize_rules["breakfast"] == "==4":
            limitations.append("아침식사: 4단계 코딩(2010 이전) — 2011+ 8단계와 비교 시 주의")
        if "physical_act" in mapped and "PA_VIG" == mapped.get("physical_act", ""):
            limitations.append("신체활동: PA_VIG (구버전명) — PA_VIG_D(2022+)와 동일 개념")

        meta = {
            "mapped_vars": list(mapped.keys()),
            "computed_vars": computed,
            "raw_to_std": {v: k for k, v in mapped.items()},
            "unmapped_raw": unmapped[:20],
            "warnings": warnings,
            "limitations": limitations,
            "screen_time_concept": screen_concept,
            "total_raw_cols": len(raw_df.columns),
            "encoding_info": {k: list(v.keys())[:5] for k, v in list(value_labels.items())[:5]},
        }
        return df, meta

    # ------------------------------------------------------------------
    # Manual mapping support (컬럼 자동 매핑 실패 시 UI에서 수동 지정)
    # ------------------------------------------------------------------

    def apply_manual_mapping(
        self, raw_df: pd.DataFrame, manual_map: dict[str, str]
    ) -> pd.DataFrame:
        """사용자가 지정한 수동 매핑 적용.

        manual_map: {표준명: 원시_컬럼명}
        """
        df = raw_df[list(manual_map.values())].rename(columns={v: k for k, v in manual_map.items()}).copy()
        for col in df.columns:
            if df[col].dtype in (float, int, np.float64, np.int64):
                df[col] = df[col].replace(_MISSING_CODES, np.nan)
        _log.info("수동 매핑 적용: %d개 변수", len(manual_map))
        return df


# ---------------------------------------------------------------------------
# KNHANES 로더 (공통 구조)
# ---------------------------------------------------------------------------

_KNHANES_VAR_MAP: dict[str, list[str]] = {
    # 복합표본
    "weight_var": ["wt_itvex", "wt_ntr", "wt", "W_itvex", "W_ntr"],
    "strata":     ["kstrata", "strata", "KSTRATA"],
    "cluster":    ["psu", "cluster", "PSU"],

    # 인구통계
    "sex":    ["sex", "SEX", "DM_SEX"],      # 1=남, 2=여
    "age":    ["age", "AGE", "DM_AGE"],
    "edu":    ["edu", "EDU", "DM_EDU"],
    "income": ["income", "INCOME", "DM_INC"],

    # 신체계측
    "height":  ["HE_ht",  "height", "HE_HT"],
    "weight":  ["HE_wt",  "weight", "HE_WT"],
    "bmi":     ["HE_BMI", "bmi",    "BMI"],
    "waist":   ["HE_wc",  "waist",  "HE_WC"],

    # 혈압
    "sbp": ["HE_sbp1", "SBP", "sbp"],
    "dbp": ["HE_dbp1", "DBP", "dbp"],

    # 혈액검사
    "glucose":    ["HE_glu",  "glucose", "FPG"],
    "hba1c":      ["HE_HbA1c", "hba1c",  "HbA1c"],
    "total_chol": ["HE_chol",  "total_chol", "CHOL"],
    "hdl":        ["HE_HDL_st2", "HE_HDL", "HDL"],
    "ldl":        ["HE_LDL_st2", "HE_LDL", "LDL"],
    "trigly":     ["HE_TG",  "trigly", "TG"],

    # 만성질환 (진단여부)
    "diabetes":     ["DE1_dg",  "diabetes", "DM_DM"],
    "hypertension": ["HE_HP",   "hypertension", "HBP"],
    "metabolic_syn":["HE_metsyn", "metabolic_syn"],

    # 생활습관
    "smoking":      ["BS3_1", "smoking", "SM_CUR"],
    "alcohol":      ["BD1",   "alcohol", "AL_CUR"],
    "physical_act": ["PA_aerobic", "physical_act", "pa_ex"],
    "sleep_hours":  ["BP_PHms", "sleep_hours", "sleep"],
}


class KNHANESLoader(KYRBSLoader):
    """KNHANES 원시자료 로더.

    국민건강영양조사(KNHANES) 원시자료 다운로드:
        https://knhanes.kdca.go.kr/knhanes/sub03/sub03_02_05.do
        → 원시자료 및 코드북 (무료, 회원가입 필요)
    """

    def _standardize(self, raw_df: pd.DataFrame, value_labels: dict) -> tuple[pd.DataFrame, dict]:
        raw_cols = {c.strip(): c for c in raw_df.columns}
        raw_cols_lower = {c.strip().lower(): c for c in raw_df.columns}

        mapped: dict[str, str] = {}
        warnings: list[str] = []

        for std_name, candidates in _KNHANES_VAR_MAP.items():
            for cand in candidates:
                if cand in raw_cols:
                    mapped[std_name] = raw_cols[cand]
                    break
                if cand.lower() in raw_cols_lower:
                    mapped[std_name] = raw_cols_lower[cand.lower()]
                    break

        rename_map = {v: k for k, v in mapped.items()}
        df = raw_df[[v for v in mapped.values()]].rename(columns=rename_map).copy()

        for col in df.columns:
            if df[col].dtype in (float, int, np.float64, np.int64):
                df[col] = df[col].replace(_MISSING_CODES, np.nan)

        # 성별 통일 (1=남→0, 2=여→1)
        if "sex" in df.columns:
            df["sex"] = (df["sex"] == 2).astype(float)
            df.loc[df["sex"].isna(), "sex"] = np.nan

        # 당뇨/고혈압 이진화 (1=있음, 2=없음 → 1/0)
        for var in ("diabetes", "hypertension"):
            if var in df.columns:
                df[var] = (df[var] == 1).astype(float)
                df.loc[df[var].isna(), var] = np.nan

        unmapped = [c for c in raw_df.columns if c not in mapped.values()]
        meta = {
            "mapped_vars": list(mapped.keys()),
            "raw_to_std": {v: k for k, v in mapped.items()},
            "unmapped_raw": unmapped[:20],
            "warnings": warnings,
            "total_raw_cols": len(raw_df.columns),
            "encoding_info": {},
        }
        return df, meta


# ---------------------------------------------------------------------------
# 편의 함수
# ---------------------------------------------------------------------------

def load_kyrbs(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """KYRBS 원시자료를 표준 스키마로 로드."""
    return KYRBSLoader().load(path)


def load_knhanes(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """KNHANES 원시자료를 표준 스키마로 로드."""
    return KNHANESLoader().load(path)


def download_instructions() -> str:
    """원시자료 다운로드 안내 텍스트."""
    return """
## KYRBS 원시자료 다운로드 방법

1. **질병관리청 청소년건강행태조사 누리집** 접속
   → https://www.kdca.go.kr/yhs/

2. **상단 메뉴** → [자료마당] → [원시자료]

3. **회원가입** 후 원시자료 신청 (무료)
   - 연구목적 기재 필요
   - 승인 후 다운로드 가능 (즉시 또는 1~2일 소요)

4. **파일 형식**: SPSS (.sav) + 코드북 PDF

5. 다운로드한 `.sav` 파일을 이 화면에 업로드

---

## KNHANES 원시자료 다운로드 방법

1. **국민건강영양조사 누리집** 접속
   → https://knhanes.kdca.go.kr/

2. [자료실] → [원시자료 및 코드북] → 연도 선택

3. **회원가입** 후 무료 다운로드
   - ZIP 파일 → 내부의 `.sav` 파일 사용

4. 다운로드한 `.sav` 파일을 이 화면에 업로드
"""
