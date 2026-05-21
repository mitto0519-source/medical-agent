"""StataExporter — 연구 스펙에서 STATA .do 파일 자동 생성.

연구 주제(topic) + StatBridge 스펙(stat_spec) + 데이터셋 정보를 받아
복제 가능한 STATA 분석 코드를 생성한다.

지원 분석:
  - logistic regression (복합표본 svy: logistic 포함)
  - multiple logistic regression with covariates
  - subgroup analysis by sex/age group
  - sensitivity analysis (complete case, alternate cutoff)
  - Table 1 descriptive statistics (tabstat, tab1)
  - Table 2 regression results export (outreg2 / esttab)
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_OUTPUT_DIR = Path("data/drafts/stata")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# KYRBS 복합표본 설계 변수 (차수별 동일 구조)
_KYRBS_SVY_SETUP = """\
* ── 복합표본 설계 선언 (KYRBS 표준) ────────────────────────────────────────
* 주의: 실제 층화변수/군집변수 이름은 데이터 코드북을 확인 후 수정하십시오.
svyset psu [pweight=weight], strata(strata) vce(linearized) singleunit(centered)
"""

_VARIABLE_LABELS: Dict[str, str] = {
    "sex":          "성별 (1=남성, 2=여성)",
    "sleep_hours":  "평일 수면 시간 (시간/일)",
    "screen_time":  "스마트폰 사용 시간 (시간/일)",
    "smoking":      "현재 흡연 여부 (0=비흡연, 1=흡연)",
    "alcohol":      "음주 여부 (0=비음주, 1=음주)",
    "physical_act": "신체활동 일수 (일/주)",
    "bmi":          "체질량지수 (kg/m²)",
    "grade":        "학년",
    "family_econ":  "가구 경제 수준 (1=상~5=하)",
    "academic_perf":"학업 성취도 (1=매우좋음~5=매우나쁨)",
    "stress":       "스트레스 인지 (0=없음, 1=높음)",
    "depression":   "우울감 경험 (0=없음, 1=있음)",
    "suicidal":     "자살 생각 (0=없음, 1=있음)",
    "obesity":      "비만 여부 (BMI≥25: 0=정상, 1=비만)",
    "hypertension": "고혈압 (0=없음, 1=있음)",
    "diabetes":     "당뇨 (0=없음, 1=있음)",
    "metabolic_syn":"대사 증후군 (0=없음, 1=있음)",
    "physical_act_yn": "신체활동 여부 (0=불충분, 1=충분)",
}


def _var_label(v: str) -> str:
    return _VARIABLE_LABELS.get(v, v.replace("_", " "))


class StataExporter:
    """연구 스펙 → STATA .do 파일 생성기.

    Usage:
        exp = StataExporter()
        path = exp.export(
            topic={"title": "...", "exposure": "screen_time", "outcome": "depression",
                   "population": "Korean adolescents"},
            stat_spec={"outcome": "depression", "predictors": ["screen_time", "sex"],
                       "covariates": ["grade", "family_econ"], "analysis": "logistic",
                       "weight_var": "weight_var", "subgroups": ["sex"]},
            study_info={"dataset": "KYRBS 2025", "design": "Cross-sectional",
                        "sample_size": "54633"},
            data_path="data/raw/kyrbs2025.sav",
        )
    """

    def __init__(self):
        pass

    def export(
        self,
        topic: Dict,
        stat_spec: Dict,
        study_info: Dict,
        data_path: str = "",
        output_path: Optional[str] = None,
        use_complex_survey: bool = True,
    ) -> str:
        """STATA .do 파일 생성 후 파일 경로 반환."""
        code = self._build_do_file(topic, stat_spec, study_info, data_path, use_complex_survey)

        if not output_path:
            safe = re.sub(r"[^\w]", "_", topic.get("title", "paper"))[:50]
            output_path = str(_OUTPUT_DIR / f"{safe}.do")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(code, encoding="utf-8")
        _log.info("STATA do-file 저장: %s", output_path)
        return output_path

    def export_string(
        self,
        topic: Dict,
        stat_spec: Dict,
        study_info: Dict,
        data_path: str = "",
        use_complex_survey: bool = True,
    ) -> str:
        """STATA .do 파일 내용을 문자열로 반환 (Streamlit 다운로드용)."""
        return self._build_do_file(topic, stat_spec, study_info, data_path, use_complex_survey)

    # ── 코어 빌더 ─────────────────────────────────────────────────────────────

    def _build_do_file(
        self,
        topic: Dict,
        stat_spec: Dict,
        study_info: Dict,
        data_path: str,
        use_complex_survey: bool,
    ) -> str:
        outcome   = stat_spec.get("outcome", "depression")
        predictors = stat_spec.get("predictors", [])
        covariates = stat_spec.get("covariates", [])
        analysis   = stat_spec.get("analysis", "logistic")
        weight_var = stat_spec.get("weight_var", "weight_var")
        subgroups  = stat_spec.get("subgroups", [])

        all_vars = list(dict.fromkeys([outcome] + predictors + covariates))
        rhs_vars = " ".join(v for v in predictors + covariates if v != outcome)

        title = topic.get("title", "Research Paper")
        dataset = study_info.get("dataset", "KYRBS")
        design  = study_info.get("design", "Cross-sectional")
        n       = study_info.get("sample_size", "N/A")
        exposure = topic.get("exposure", predictors[0] if predictors else "")
        pop      = topic.get("population", "Korean adolescents")

        parts = [self._header(title, dataset, design, n, data_path)]
        parts.append(self._data_load(data_path, dataset))
        parts.append(self._variable_labels(all_vars, outcome))
        parts.append(self._missing_exclusion(all_vars))

        if use_complex_survey and "kyrbs" in dataset.lower():
            parts.append(_KYRBS_SVY_SETUP)

        parts.append(self._table1(all_vars, outcome, weight_var, use_complex_survey))
        parts.append(self._regression(
            outcome, rhs_vars, analysis, weight_var, use_complex_survey
        ))

        if subgroups:
            parts.append(self._subgroup_analysis(
                outcome, rhs_vars, subgroups, analysis, weight_var, use_complex_survey
            ))

        parts.append(self._sensitivity_analysis(
            outcome, rhs_vars, analysis, weight_var, use_complex_survey, exposure
        ))
        parts.append(self._export_tables(title))
        parts.append(self._footer())

        return "\n\n".join(parts)

    # ── 섹션 빌더들 ────────────────────────────────────────────────────────────

    @staticmethod
    def _header(title: str, dataset: str, design: str, n: str, data_path: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""\
/*============================================================================
  STATA Analysis Do-File
  Title   : {title}
  Dataset : {dataset}
  Design  : {design}
  N       : {n}
  Created : {today}
  Note    : Auto-generated by Medical-Agent StataExporter.
            Review variable names against your codebook before running.
============================================================================*/

version 17
clear all
set more off
capture log close
log using "output/analysis_{today}.log", replace text
""".rstrip()

    @staticmethod
    def _data_load(data_path: str, dataset: str) -> str:
        if data_path and data_path.endswith(".sav"):
            load_cmd = f'import spss using "{data_path}", clear'
        elif data_path and data_path.endswith(".dta"):
            load_cmd = f'use "{data_path}", clear'
        elif data_path and data_path.endswith(".csv"):
            load_cmd = f'import delimited using "{data_path}", clear encoding("UTF-8")'
        else:
            load_cmd = f'* TODO: 데이터 경로를 지정하십시오\n* use "경로/{dataset}.dta", clear'

        return f"""\
* ── 데이터 로드 ────────────────────────────────────────────────────────────
{load_cmd}

* 데이터 확인
describe
codebook, compact
""".rstrip()

    @staticmethod
    def _variable_labels(all_vars: List[str], outcome: str) -> str:
        label_cmds = []
        for v in all_vars:
            lbl = _var_label(v)
            label_cmds.append(f'label variable {v} "{lbl}"')

        value_labels = []
        if "sex" in all_vars:
            value_labels += [
                'label define sex_lbl 1 "Male" 2 "Female"',
                "label values sex sex_lbl",
            ]
        if outcome in all_vars and outcome in ("depression", "suicidal", "smoking",
                                                "alcohol", "obesity"):
            value_labels += [
                f'label define {outcome}_lbl 0 "No" 1 "Yes"',
                f"label values {outcome} {outcome}_lbl",
            ]

        lines = ["* ── 변수 레이블 설정 ──────────────────────────────────────────────────"]
        lines += label_cmds
        if value_labels:
            lines.append("")
            lines += value_labels
        return "\n".join(lines)

    @staticmethod
    def _missing_exclusion(all_vars: List[str]) -> str:
        cond = " | ".join(f"missing({v})" for v in all_vars)
        return f"""\
* ── 결측값 처리 및 분석 대상 선정 ──────────────────────────────────────────
* 주요 변수 결측값 현황
misstable summarize {" ".join(all_vars)}, all

* 완전 데이터 분석을 위한 마킹
mark nonmissing if {cond}
markout nonmissing {" ".join(all_vars)}
display "분석 대상: " as result string(count if nonmissing) " 명"
""".rstrip()

    @staticmethod
    def _table1(all_vars: List[str], outcome: str, weight_var: str, svy: bool) -> str:
        cont_vars = [v for v in all_vars if v not in (
            "sex", "smoking", "alcohol", "depression", "suicidal",
            "obesity", "hypertension", "diabetes", "metabolic_syn"
        ) and v != outcome]
        cat_vars  = [v for v in all_vars if v in (
            "sex", "smoking", "alcohol", "obesity"
        ) and v != outcome]

        svy_pfx = "svy: " if svy else f"[pw={weight_var}] "

        lines = ["* ── Table 1: 기술통계 ─────────────────────────────────────────────────"]
        if cont_vars:
            lines.append(f"tabstat {' '.join(cont_vars)} [aw={weight_var}], "
                         "statistics(n mean sd median min max) columns(statistics)")
        if cat_vars:
            lines.append(f"tab1 {' '.join(cat_vars)} [aw={weight_var}]")
        lines.append(f"\n* 결과변수별 층화 기술통계")
        if cont_vars:
            lines.append(f"tabstat {' '.join(cont_vars)} [aw={weight_var}], "
                         f"by({outcome}) statistics(mean sd) columns(statistics)")
        return "\n".join(lines)

    @staticmethod
    def _regression(
        outcome: str, rhs_vars: str, analysis: str, weight_var: str, svy: bool
    ) -> str:
        if svy:
            cmd = f"svy: logistic {outcome} {rhs_vars}" if analysis == "logistic" else \
                  f"svy: regress {outcome} {rhs_vars}"
        else:
            cmd = f"logistic {outcome} {rhs_vars} [pw={weight_var}]" if analysis == "logistic" else \
                  f"regress {outcome} {rhs_vars} [pw={weight_var}]"

        return f"""\
* ── Table 2: 로지스틱 회귀분석 ──────────────────────────────────────────────

* 모형 1: 비보정 (crude)
{cmd.split()[0]} {cmd.split()[1]} {cmd.split()[2] if len(cmd.split()) > 2 else ""}
estimates store crude

* 모형 2: 보정 (adjusted)
{cmd}
estimates store adjusted

* OR 및 95% CI 출력
lrtest crude adjusted
estat gof, group(10)
""".rstrip()

    @staticmethod
    def _subgroup_analysis(
        outcome: str,
        rhs_vars: str,
        subgroups: List[str],
        analysis: str,
        weight_var: str,
        svy: bool,
    ) -> str:
        lines = ["* ── 하위군 분석 (Subgroup Analysis) ──────────────────────────────────"]
        for sg in subgroups:
            if sg == "sex":
                lines.append(f"\n* 성별 하위군 — 남성")
                if svy:
                    lines.append(f"svy, subpop(if sex==1): logistic {outcome} {rhs_vars}")
                    lines.append(f"estimates store sub_male")
                    lines.append(f"* 성별 하위군 — 여성")
                    lines.append(f"svy, subpop(if sex==2): logistic {outcome} {rhs_vars}")
                    lines.append(f"estimates store sub_female")
                else:
                    lines.append(f"logistic {outcome} {rhs_vars} [pw={weight_var}] if sex==1")
                    lines.append(f"logistic {outcome} {rhs_vars} [pw={weight_var}] if sex==2")
            else:
                lines.append(f"\n* {sg} 하위군")
                levels = f"levelsof {sg}, local({sg}_levels)"
                lines.append(levels)
                lines.append(f'foreach lev of local {sg}_levels {{')
                if svy:
                    lines.append(f'    svy, subpop(if {sg}==`lev\'): logistic {outcome} {rhs_vars}')
                else:
                    lines.append(f'    logistic {outcome} {rhs_vars} [pw={weight_var}] if {sg}==`lev\'')
                lines.append("}")

        return "\n".join(lines)

    @staticmethod
    def _sensitivity_analysis(
        outcome: str,
        rhs_vars: str,
        analysis: str,
        weight_var: str,
        svy: bool,
        exposure: str,
    ) -> str:
        cmd = f"svy: logistic {outcome} {rhs_vars}" if svy else \
              f"logistic {outcome} {rhs_vars} [pw={weight_var}]"

        return f"""\
* ── 민감도 분석 (Sensitivity Analysis) ───────────────────────────────────────

* 1. 완전 사례 분석 (listwise deletion)
{cmd} if nonmissing==1
estimates store sensitivity_cc

* 2. 노출변수 대체 임계값 분석 (exposure cutoff sensitivity)
*    예: screen_time >= 3시간 vs >= 4시간 (노출에 맞게 수정)
* gen exposure_alt = ({exposure} >= 4) if !missing({exposure})
* {cmd.replace(exposure, 'exposure_alt').replace('svy: ', 'svy: ')}

* 3. 연령/학년 보정 모형 비교
{cmd}
estimates store sensitivity_full
""".rstrip()

    @staticmethod
    def _export_tables(title: str) -> str:
        safe = re.sub(r"[^\w]", "_", title)[:40]
        return f"""\
* ── 결과 테이블 내보내기 ─────────────────────────────────────────────────────

* esttab 사용 (ssc install estout 필요)
capture which esttab
if _rc == 0 {{
    esttab crude adjusted using "output/{safe}_Table2.csv", ///
        eform ci(2) b(2) p(3) ///
        title("Table 2. Logistic Regression Results") ///
        replace label
}}

* outreg2 사용 대안 (ssc install outreg2 필요)
* outreg2 using "output/{safe}_Table2.doc", eform replace

* Excel 출력
putexcel set "output/{safe}_results.xlsx", replace sheet("Table2")
""".rstrip()

    @staticmethod
    def _footer() -> str:
        return """\
* ── 세션 정보 및 로그 마무리 ────────────────────────────────────────────────
log close
display "분석 완료"
"""


# ── 편의 함수 (ResearchPipeline에서 직접 호출) ─────────────────────────────

def generate_stata_code(
    topic: Dict,
    stat_spec: Dict,
    study_info: Dict,
    data_path: str = "",
    use_complex_survey: bool = True,
) -> str:
    """StataExporter 래퍼 — 코드 문자열 반환."""
    return StataExporter().export_string(
        topic=topic,
        stat_spec=stat_spec,
        study_info=study_info,
        data_path=data_path,
        use_complex_survey=use_complex_survey,
    )


def save_stata_do_file(
    topic: Dict,
    stat_spec: Dict,
    study_info: Dict,
    data_path: str = "",
    output_path: Optional[str] = None,
    use_complex_survey: bool = True,
) -> str:
    """StataExporter 래퍼 — 파일 저장 후 경로 반환."""
    return StataExporter().export(
        topic=topic,
        stat_spec=stat_spec,
        study_info=study_info,
        data_path=data_path,
        output_path=output_path,
        use_complex_survey=use_complex_survey,
    )
