"""ColNameResolver — DataFrame 컬럼명을 연구 스펙 변수명으로 자동 매핑.

하드코딩 딕셔너리 + LLM 폴백으로 새 데이터셋에서도 동작한다.
ResearchPipeline._build_stat_spec() 호출 전에 실행해 변수명 오류를 방지한다.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

import pandas as pd

from src.config.logging_config import get_logger

_log = get_logger(__name__)

# ── 알려진 변수 패턴 (정규식) ────────────────────────────────────────────────
# key: 표준 변수명, value: 컬럼명 패턴 목록 (우선순위 순)
_KNOWN_PATTERNS: Dict[str, List[str]] = {
    "sex":          [r"^sex$", r"^gender$", r"^E_SEX$", r"^sex_1$"],
    "sleep_hours":  [r"^sleep", r"^EC_SU_HOU", r"^M_SU_TIME", r".*sleep.*hour", r".*수면"],
    "screen_time":  [r"^screen", r"^M_SP_TIME", r"^E_SP_TIME", r".*스마트폰", r".*smartphone"],
    "smoking":      [r"^smok", r"^M_CUR_SMOK", r"^E_CUR_SMOK", r".*흡연"],
    "alcohol":      [r"^alc", r"^M_CUR_ALCO", r"^E_DRNK", r".*음주"],
    "physical_act": [r"^PA_VIG", r"^M_VIG_ACT", r"^physical", r"^exercise", r".*운동", r".*신체"],
    "bmi":          [r"^bmi$", r"^BMI$", r"^M_BMI", r".*체질량"],
    "grade":        [r"^grade$", r"^E_S_GRADE", r"^school_grade", r".*학년"],
    "family_econ":  [r"^family_econ", r"^E_PARHEA", r"^SES", r".*경제", r".*소득"],
    "academic_perf":[r"^academic", r"^E_STUDY", r".*학업", r".*성적"],
    "stress":       [r"^stress", r"^M_STR", r"^E_STR", r".*스트레스"],
    "depression":   [r"^depress", r"^M_SAD", r"^F_BR", r".*우울"],
    "suicidal":     [r"^suicid", r"^M_SUI_THINK", r".*자살"],
    "obesity":      [r"^obes", r".*비만"],
    "weight_var":   [r"^weight", r"^wt$", r"^W\d+$", r".*가중치", r"^pweight"],
    "strata":       [r"^strat", r"^STR\d*", r".*층화"],
    "cluster":      [r"^psu$", r"^cluster", r"^PSU", r".*군집"],
    "age":          [r"^age$", r"^AGE", r".*나이", r".*연령"],
    "edu":          [r"^edu", r"^EDU", r".*교육"],
    "income":       [r"^income", r"^INCOME", r".*소득"],
}


class ColNameResolver:
    """DataFrame 컬럼명 → 연구 표준 변수명 매핑.

    Usage:
        resolver = ColNameResolver(df)
        mapping = resolver.resolve(["depression", "sleep_hours", "sex", "grade"])
        # {"depression": "F_BR", "sleep_hours": "EC_SU_HOU_M", "sex": "sex", "grade": "E_S_GRADE"}
        spec_vars = resolver.remap_spec(spec)  # spec dict의 변수명 자동 교체
    """

    def __init__(self, df: pd.DataFrame, llm_client=None):
        self._cols = list(df.columns)
        self._col_lower = {c.lower(): c for c in self._cols}
        self._llm = llm_client
        self._cache: Dict[str, str] = {}  # standard_name → actual_col

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def resolve(self, wanted: List[str]) -> Dict[str, str]:
        """표준 변수명 목록 → 실제 컬럼명 매핑 반환.

        반환: {"sleep_hours": "EC_SU_HOU_M", "sex": "E_SEX", ...}
        못 찾은 변수는 딕셔너리에서 제외된다.
        """
        result = {}
        unresolved = []
        for std_name in wanted:
            col = self._resolve_one(std_name)
            if col:
                result[std_name] = col
            else:
                unresolved.append(std_name)

        if unresolved:
            _log.info("패턴 매칭 실패 — LLM 폴백: %s", unresolved)
            llm_result = self._llm_resolve(unresolved)
            result.update(llm_result)

        found = list(result.keys())
        missing = [v for v in wanted if v not in result]
        _log.info("ColNameResolver: %d/%d 해결 (found=%s, missing=%s)",
                  len(found), len(wanted), found, missing)
        return result

    def remap_spec(self, spec: dict) -> dict:
        """StatBridge spec dict의 변수명을 실제 컬럼명으로 교체한 새 spec 반환."""
        all_std = (
            spec.get("predictors", []) +
            spec.get("covariates", []) +
            [spec.get("outcome", ""), spec.get("weight_var", ""),
             spec.get("strata_var", ""), spec.get("cluster_var", "")]
        )
        all_std = [v for v in all_std if v]
        mapping = self.resolve(all_std)

        def remap_list(lst):
            return [mapping.get(v, v) for v in lst]

        new_spec = dict(spec)
        new_spec["predictors"]  = remap_list(spec.get("predictors", []))
        new_spec["covariates"]  = remap_list(spec.get("covariates", []))
        if spec.get("outcome"):
            new_spec["outcome"] = mapping.get(spec["outcome"], spec["outcome"])
        if spec.get("weight_var"):
            new_spec["weight_var"] = mapping.get(spec["weight_var"], spec["weight_var"])
        if spec.get("strata_var"):
            new_spec["strata_var"] = mapping.get(spec["strata_var"], spec["strata_var"])
        if spec.get("cluster_var"):
            new_spec["cluster_var"] = mapping.get(spec["cluster_var"], spec["cluster_var"])

        # 실제 컬럼에 없는 변수 제거 (분석 오류 방지)
        new_spec["predictors"] = [v for v in new_spec["predictors"] if v in self._cols]
        new_spec["covariates"] = [v for v in new_spec["covariates"] if v in self._cols]
        _log.info("remap_spec 완료: predictors=%s, covariates=%s",
                  new_spec["predictors"], new_spec["covariates"])
        return new_spec

    def available_cols(self) -> List[str]:
        """DataFrame의 전체 컬럼 목록."""
        return list(self._cols)

    def diagnose(self, spec: dict) -> dict:
        """spec 변수 중 실제로 있는 것/없는 것/대체 가능한 것 보고."""
        all_vars = (spec.get("predictors", []) + spec.get("covariates", []) +
                    [spec.get("outcome", "")])
        report = {"found": [], "missing": [], "remapped": {}}
        mapping = self.resolve(all_vars)
        for v in all_vars:
            if not v:
                continue
            if v in self._cols:
                report["found"].append(v)
            elif v in mapping:
                report["remapped"][v] = mapping[v]
            else:
                report["missing"].append(v)
        return report

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _resolve_one(self, std_name: str) -> Optional[str]:
        if std_name in self._cache:
            return self._cache[std_name]

        # 1. 정확 일치
        if std_name in self._cols:
            self._cache[std_name] = std_name
            return std_name

        # 2. 대소문자 무관 일치
        lower_match = self._col_lower.get(std_name.lower())
        if lower_match:
            self._cache[std_name] = lower_match
            return lower_match

        # 3. 알려진 패턴 매칭
        patterns = _KNOWN_PATTERNS.get(std_name, [])
        for pat in patterns:
            for col in self._cols:
                if re.search(pat, col, re.IGNORECASE):
                    self._cache[std_name] = col
                    return col

        # 4. 부분 문자열 포함 (관대한 폴백)
        fragments = std_name.split("_")
        for col in self._cols:
            col_l = col.lower()
            if all(f.lower() in col_l for f in fragments if len(f) > 2):
                self._cache[std_name] = col
                return col

        return None

    def _llm_resolve(self, unresolved: List[str]) -> Dict[str, str]:
        """LLM에게 컬럼 목록을 보여주고 변수 매핑 추론."""
        if not unresolved:
            return {}

        # LLM 없으면 빈 딕셔너리
        if self._llm is None:
            try:
                from src.llm import get_llm_client
                self._llm = get_llm_client()
            except Exception:
                return {}

        cols_sample = self._cols[:120]  # 너무 많으면 잘라서 전송
        prompt = f"""You are a biostatistics data analyst.

Given these DataFrame column names from a Korean health survey:
{cols_sample}

Map each of these standard variable names to the most likely actual column name:
{unresolved}

Rules:
- For each standard name, choose ONE column from the list above
- If no reasonable match exists, output null for that variable
- Korean surveys like KYRBS use prefixes: E_, M_, F_, EC_, PA_, etc.

Respond in JSON only, format:
{{"sleep_hours": "EC_SU_HOU_M", "depression": "F_BR", "sex": "E_SEX"}}
"""
        try:
            import json
            raw = self._llm.generate(user_message=prompt, max_tokens=300, task="general")
            raw = re.sub(r"```json|```", "", raw).strip()
            result = json.loads(raw)
            # 실제 컬럼에 있는 것만 반환
            valid = {k: v for k, v in result.items()
                     if v and v in self._cols and k in unresolved}
            self._cache.update(valid)
            return valid
        except Exception as e:
            _log.warning("LLM 컬럼 매핑 실패: %s", e)
            return {}


def resolve_spec_columns(df: pd.DataFrame, spec: dict, llm_client=None) -> dict:
    """편의 함수 — spec을 실제 컬럼명으로 remapping한 새 spec 반환."""
    return ColNameResolver(df, llm_client=llm_client).remap_spec(spec)
