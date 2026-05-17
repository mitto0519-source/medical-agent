"""
ResearchWorkflow — 단계별 검수 포함 연구 파이프라인
=====================================================

Stage 1  주제 제안          → 사람이 하나 선택
Stage 2  변수 계획          → 사람이 검수·수정
Stage 3  통계 분석 계획     → 사람이 검수·수정
Stage 4  R 코드 생성        → 사람이 실제 데이터로 실행
Stage 5  결과 검증          → AI가 통계 오류 탐지 → 사람이 확인
Stage 6  논문 작성          → 검증된 숫자만 사용
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from src.llm import get_llm_client
from src.profile.author_profile import AuthorProfile
from src.library.dataset_library import DatasetLibrary
from src.library.methods_library import MethodsLibrary


def _clean_llm_response(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 2 and parts[1].strip().lower().startswith("json"):
            text = "```".join(parts[2:]).strip()
        elif len(parts) > 1:
            text = parts[1].strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text.strip().rstrip("```").strip()


STAGES = [
    "topic_proposal",
    "variable_plan",
    "analysis_plan",
    "r_code",
    "result_verification",
    "paper_draft",
]

STAGE_LABELS = {
    "topic_proposal":     "1단계: 주제 제안",
    "variable_plan":      "2단계: 변수 계획",
    "analysis_plan":      "3단계: 통계 분석 계획 (SAP)",
    "r_code":             "4단계: R 코드 생성",
    "result_verification":"5단계: 결과 검증",
    "paper_draft":        "6단계: 논문 초안",
}


class ResearchWorkflow:
    """
    단계별 연구 워크플로우.
    각 stage는 approve() 호출 후에만 다음 단계로 진행 가능.
    상태는 JSON 파일로 저장 (세션 간 유지).
    """

    def __init__(
        self,
        workflow_id: str,
        dataset_name: str = "KYRBS",
        author_name: str = "Yoosun Cho",
        save_dir: str = "data/workflows",
        api_key: Optional[str] = None,
    ):
        self.workflow_id = workflow_id
        self.dataset_name = dataset_name
        self._client = get_llm_client(api_key=api_key)
        self._author = AuthorProfile(author_name)
        self._datasets = DatasetLibrary()
        self._methods = MethodsLibrary()

        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._save_dir / f"{workflow_id}.json"

        self.state = self._load()

    # ── 저장/불러오기 ─────────────────────────────────────────────────

    def _load(self) -> Dict:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "workflow_id": self.workflow_id,
            "dataset": self.dataset_name,
            "created_at": datetime.now().isoformat(),
            "current_stage": "topic_proposal",
            "stages": {},
        }

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def current_stage(self) -> str:
        return self.state["current_stage"]

    def stage_data(self, stage: str) -> Optional[Dict]:
        return self.state["stages"].get(stage)

    def is_approved(self, stage: str) -> bool:
        d = self.stage_data(stage)
        return bool(d and d.get("approved"))

    def approve(self, stage: str, modifications: str = ""):
        """현재 단계를 승인하고 다음 단계로 이동."""
        if stage not in self.state["stages"]:
            raise ValueError(f"단계 {stage}의 데이터가 없습니다. 먼저 생성하세요.")
        self.state["stages"][stage]["approved"] = True
        self.state["stages"][stage]["approved_at"] = datetime.now().isoformat()
        if modifications:
            self.state["stages"][stage]["modifications"] = modifications

        idx = STAGES.index(stage)
        if idx + 1 < len(STAGES):
            self.state["current_stage"] = STAGES[idx + 1]
        self._save()

    def reject(self, stage: str, feedback: str = ""):
        """단계를 반려 — 피드백 기록 후 재생성 가능."""
        if stage in self.state["stages"]:
            self.state["stages"][stage]["approved"] = False
            self.state["stages"][stage]["rejection_feedback"] = feedback
            self._save()

    # ── Stage 1: 주제 제안 ────────────────────────────────────────────

    def propose_topics(self, focus: str, n: int = 5) -> List[Dict]:
        """
        데이터셋 변수 + 연구 포커스 → n개 주제 제안.
        각 주제: title, exposure, outcome, population, rationale, novelty_hint
        """
        dataset_ctx = self._datasets.get_context(self.dataset_name)

        prompt = f"""You are a medical research methodologist specializing in Korean adolescent health.

DATASET:
{dataset_ctx}

RESEARCH FOCUS: {focus}

Generate {n} original, publishable research topics using ONLY variables available in this dataset.

For each topic, specify:
- title: concise English study title
- exposure: exact variable name(s) from dataset
- outcome: exact variable name(s) from dataset
- population: who is included/excluded
- rationale: why this is important and feasible
- novelty_hint: what makes this novel vs existing literature
- suggested_design: cross-sectional / trend analysis / etc.
- covariates: list of covariate variable names to adjust for
- analysis_note: key statistical consideration (e.g., complex survey, subgroup)

Return JSON array only. No markdown."""

        raw = self._client.generate(prompt, max_tokens=3000)
        raw = _clean_llm_response(raw)
        try:
            topics = json.loads(raw)
        except Exception as exc:
            raise ValueError(
                f"주제 생성 응답을 JSON 배열로 파싱할 수 없습니다: {exc}\n응답 원본:\n{raw}"
            )

        self.state["stages"]["topic_proposal"] = {
            "focus": focus,
            "topics": topics,
            "approved": False,
            "selected_topic": None,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return topics

    def select_topic(self, topic_index: int):
        """제안된 주제 중 하나를 선택."""
        topics = self.state["stages"]["topic_proposal"]["topics"]
        selected = topics[topic_index]
        self.state["stages"]["topic_proposal"]["selected_topic"] = selected
        self._save()
        return selected

    # ── Stage 2: 변수 계획 ────────────────────────────────────────────

    def plan_variables(self, topic: Optional[Dict] = None) -> Dict:
        """
        선택된 주제 → 상세 변수 계획 생성.
        변수별 코딩 방법, 결측 처리, 재범주화, 분석 제외 기준 명시.
        """
        if topic is None:
            topic = self.state["stages"]["topic_proposal"].get("selected_topic")
        if not topic:
            raise ValueError("먼저 주제를 선택하세요 (select_topic).")

        dataset_ctx = self._datasets.get_context(self.dataset_name)
        ds = self._datasets.get_dataset(self.dataset_name)

        # 관련 변수 상세 정보
        relevant_vars = {}
        all_vars = [topic.get("exposure", ""), topic.get("outcome", "")] + topic.get("covariates", [])
        for vname in all_vars:
            vname = vname.strip()
            if vname and vname in ds.get("variables", {}):
                relevant_vars[vname] = ds["variables"][vname]

        prompt = f"""You are a senior biostatistician designing a variable plan for a Korean adolescent health study.

STUDY TOPIC: {topic.get('title', '')}
EXPOSURE: {topic.get('exposure', '')}
OUTCOME: {topic.get('outcome', '')}
PROPOSED COVARIATES: {topic.get('covariates', [])}
POPULATION: {topic.get('population', '')}

AVAILABLE VARIABLE DETAILS:
{json.dumps(relevant_vars, ensure_ascii=False, indent=2)}

FULL DATASET CONTEXT:
{dataset_ctx}

Create a detailed variable plan. For each variable, specify:

exposure_variable:
  name: (exact variable name)
  label: (Korean label)
  original_coding: (original response options with codes)
  analysis_coding: (how to recode for analysis — binary, ordinal, continuous)
  reference_category: (reference group for regression)
  rationale: (why this coding)

outcome_variable: (same structure)

covariates: (list of objects with same structure for each covariate)

exclusion_criteria:
  - (list of who to exclude and why)

sample_size_note: (expected n after exclusions, based on KYRBS 2025 ~54,000)

analysis_notes:
  - (key notes: complex survey design, weighting, etc.)

Return JSON only."""

        raw = self._client.generate(prompt, max_tokens=4000)
        raw = _clean_llm_response(raw)
        try:
            var_plan = json.loads(raw)
        except Exception:
            var_plan = {"raw": raw}

        self.state["stages"]["variable_plan"] = {
            "topic": topic,
            "plan": var_plan,
            "approved": False,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return var_plan

    # ── Stage 3: 통계 분석 계획 (SAP) ────────────────────────────────

    def plan_analysis(self) -> Dict:
        """
        변수 계획 → 통계 분석 계획 (SAP) 생성.
        모델 스펙, 서브그룹 분석, 민감도 분석, 예상 Table 구조 포함.
        """
        var_plan = self.state["stages"]["variable_plan"]["plan"]
        topic = self.state["stages"]["variable_plan"]["topic"]
        methods_ctx = self._methods.get_context_for_claude(["logistic_regression", "chi_square", "trend_test"])

        prompt = f"""You are a senior biostatistician writing a Statistical Analysis Plan (SAP) for a Korean adolescent health study using complex survey data.

STUDY TITLE: {topic.get('title', '')}
VARIABLE PLAN:
{json.dumps(var_plan, ensure_ascii=False, indent=2)}

AVAILABLE STATISTICAL METHODS:
{methods_ctx}

Write a detailed SAP with the following structure:

primary_analysis:
  method: (e.g., survey-weighted multivariable logistic regression)
  justification: (why this method)
  model_formula: (R formula syntax, e.g., outcome ~ exposure + covar1 + covar2)
  reference_category: (which level of exposure is reference)
  effect_measure: (OR / HR / β with 95% CI)
  complex_survey_handling: (svydesign specification in R)

model_sequence:
  - model_1: (unadjusted)
  - model_2: (+ sociodemographic)
  - model_3: (+ behavioral, fully adjusted)

trend_analysis:
  method: (p for trend approach)
  coding: (how to treat ordered exposure)

subgroup_analyses:
  - variable: sex
    method: stratified + interaction test
  - variable: school_type
    method: stratified + interaction test
  (add others as appropriate)

sensitivity_analyses:
  - (list each sensitivity analysis with method)

tables_planned:
  - table_1: "Characteristics of participants by [exposure category]"
    columns: (list)
    statistics: (weighted % or mean ± SD, p-value)
  - table_2: "Association between [exposure] and [outcome]"
    columns: [Model 1 OR (95% CI), Model 2 OR (95% CI), Model 3 OR (95% CI)]
    rows: (exposure categories)
  - table_3: "Subgroup analysis"
    (structure)

r_packages_needed:
  - (list R packages)

Return JSON only."""

        raw = self._client.generate(prompt, max_tokens=4000)
        raw = _clean_llm_response(raw)
        try:
            sap = json.loads(raw)
        except Exception:
            sap = {"raw": raw}

        self.state["stages"]["analysis_plan"] = {
            "sap": sap,
            "approved": False,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return sap

    # ── Stage 4: R 코드 생성 ─────────────────────────────────────────

    def generate_r_code(self) -> str:
        """
        SAP → 실행 가능한 R 코드 생성.
        실제 KYRBS 데이터 파일 경로를 지정하면 바로 돌릴 수 있음.
        """
        sap = self.state["stages"]["analysis_plan"]["sap"]
        var_plan = self.state["stages"]["variable_plan"]["plan"]
        topic = self.state["stages"]["variable_plan"]["topic"]

        prompt = f"""Write complete, executable R code for this study.

STUDY: {topic.get('title', '')}

VARIABLE PLAN:
{json.dumps(var_plan, ensure_ascii=False, indent=2)}

STATISTICAL ANALYSIS PLAN:
{json.dumps(sap, ensure_ascii=False, indent=2)}

Requirements:
1. Load KYRBS data (SAS or SPSS format) — use placeholder path "data/kyrbs2025.sav"
2. Variable recoding exactly as in variable plan
3. Apply exclusion criteria
4. Create survey design object with svydesign()
5. Table 1: weighted characteristics by exposure group (tableone or gtsummary)
6. Main regression: all 3 models with svyglm()
7. Trend test
8. Subgroup analyses with interaction tests
9. Sensitivity analyses
10. Export results as CSV and formatted tables

Write production-quality R code with comments explaining each step.
Include: library(), data loading, recoding, exclusions, svydesign, all analyses, table export.
"""

        raw = self._client.generate(prompt, max_tokens=6000)
        r_code = _clean_llm_response(raw)
        # strip markdown code blocks
        if r_code.startswith("```"):
            lines = r_code.split("\n")
            r_code = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        # 파일로 저장
        r_path = self._save_dir / f"{self.workflow_id}_analysis.R"
        with open(r_path, "w", encoding="utf-8") as f:
            f.write(r_code)

        self.state["stages"]["r_code"] = {
            "r_code": r_code,
            "r_file": str(r_path),
            "approved": False,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return r_code

    # ── Stage 5: 결과 검증 ────────────────────────────────────────────

    def verify_results(self, results_text: str) -> Dict:
        """
        사용자가 R 실행 결과를 붙여넣으면 AI가 검증.
        - 통계적 타당성 확인
        - 방향성 오류 탐지
        - 결측/이상값 확인
        - 보완 분석 제안
        """
        sap = self.state["stages"]["analysis_plan"]["sap"]
        var_plan = self.state["stages"]["variable_plan"]["plan"]
        topic = self.state["stages"]["variable_plan"]["topic"]

        prompt = f"""You are a senior biostatistician reviewing statistical results.

STUDY: {topic.get('title', '')}

STATISTICAL ANALYSIS PLAN (what was intended):
{json.dumps(sap, ensure_ascii=False, indent=2)}

ACTUAL RESULTS FROM R:
{results_text}

Review these results and provide:

plausibility_check:
  overall: pass / warning / fail
  issues: (list any statistical red flags)

specific_checks:
  - sample_size: (is n as expected?)
  - effect_direction: (does OR/HR direction make clinical sense?)
  - effect_magnitude: (is OR/HR magnitude plausible? too large/small?)
  - confidence_intervals: (too wide = underpowered, too narrow = suspicious)
  - p_values: (consistent with CIs?)
  - reference_category: (correctly specified?)
  - complex_survey: (was svydesign properly applied? check SE inflation vs naive)
  - trend_test: (monotone dose-response?)
  - subgroup_consistency: (are subgroup ORs consistent with main?)

structured_results:
  (extract and structure the key numbers for paper writing)
  table_1_summary: (n, key characteristics)
  main_result: (primary OR/HR with CI and p)
  dose_response: (list of ORs across exposure categories)
  subgroup_results: (by sex, school type, etc.)
  sensitivity_results: (list)

warnings:
  - (list anything that needs attention before writing the paper)

recommendations:
  - (any additional analyses suggested)

Return JSON only."""

        raw = self._client.generate(prompt, max_tokens=4000)
        raw = _clean_llm_response(raw)
        try:
            verification = json.loads(raw)
        except Exception:
            verification = {"raw": raw}

        self.state["stages"]["result_verification"] = {
            "raw_results": results_text,
            "verification": verification,
            "approved": False,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return verification

    # ── Stage 6: 논문 작성 ────────────────────────────────────────────

    def write_paper(self) -> str:
        """
        검증된 실제 통계 결과를 사용해 논문 초안 작성.
        """
        if not self.is_approved("result_verification"):
            raise ValueError("5단계(결과 검증)를 먼저 검수·승인하세요.")

        topic = self.state["stages"]["variable_plan"]["topic"]
        var_plan = self.state["stages"]["variable_plan"]["plan"]
        sap = self.state["stages"]["analysis_plan"]["sap"]
        verification = self.state["stages"]["result_verification"]["verification"]
        structured_results = verification.get("structured_results", {})
        raw_results = self.state["stages"]["result_verification"]["raw_results"]

        system = self._author.get_system_prompt()

        sections = {}

        # Abstract
        sections["abstract"] = self._call(system, f"""Write a structured abstract (Background/Objective/Methods/Results/Conclusion, ≤300 words).

TITLE: {topic.get('title', '')}
DESIGN: cross-sectional, nationwide, KYRBS 2025
EXPOSURE: {topic.get('exposure', '')}
OUTCOME: {topic.get('outcome', '')}
POPULATION: {topic.get('population', '')}

VERIFIED RESULTS:
{json.dumps(structured_results, ensure_ascii=False, indent=2)}

Use only the numbers above. Do not invent statistics.""")

        # Introduction
        sections["introduction"] = self._call(system, f"""Write the Introduction section (4–5 paragraphs).

TITLE: {topic.get('title', '')}
EXPOSURE: {topic.get('exposure', '')}
OUTCOME: {topic.get('outcome', '')}
POPULATION: {topic.get('population', '')}

Structure: public health context → specific problem → evidence gap → study aim.""")

        # Methods
        sections["methods"] = self._call(system, f"""Write the Methods section.

TITLE: {topic.get('title', '')}
VARIABLE PLAN: {json.dumps(var_plan, ensure_ascii=False, indent=2)}
SAP: {json.dumps(sap, ensure_ascii=False, indent=2)}

Subsections: Study Design and Population / Exposure / Outcome / Covariates / Statistical Analysis.
Include KYRBS complex survey design details (stratification, clustering, weights).""")

        # Results
        sections["results"] = self._call(system, f"""Write the Results section.

TITLE: {topic.get('title', '')}

ACTUAL STATISTICAL RESULTS (use these numbers exactly):
{raw_results}

STRUCTURED SUMMARY:
{json.dumps(structured_results, ensure_ascii=False, indent=2)}

Subsections: Participant characteristics → Primary analysis → Subgroup → Sensitivity.
Report exact ORs, 95% CIs, p-values as provided. Do not alter numbers.""")

        # Discussion
        sections["discussion"] = self._call(system, f"""Write the Discussion section.

TITLE: {topic.get('title', '')}
MAIN FINDINGS: {json.dumps(structured_results.get('main_result', {}), ensure_ascii=False)}
DOSE-RESPONSE: {json.dumps(structured_results.get('dose_response', []), ensure_ascii=False)}
SUBGROUP: {json.dumps(structured_results.get('subgroup_results', {}), ensure_ascii=False)}
WARNINGS/LIMITATIONS NOTED: {json.dumps(verification.get('warnings', []), ensure_ascii=False)}

Structure: summary → comparison with literature → mechanisms → strengths/limitations → conclusion.""")

        sep = "=" * 70
        paper = f"""{sep}
{topic.get('title', 'UNTITLED').upper()}
{sep}
By {self._author.author_name}

{sep}
ABSTRACT
{sep}
{sections['abstract']}

{sep}
INTRODUCTION
{sep}
{sections['introduction']}

{sep}
METHODS
{sep}
{sections['methods']}

{sep}
RESULTS
{sep}
{sections['results']}

{sep}
DISCUSSION
{sep}
{sections['discussion']}
"""
        # 저장
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic.get("title", "draft"))[:60]
        out_path = Path("data/drafts") / f"{self.workflow_id}_{safe_title}.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(paper)

        self.state["stages"]["paper_draft"] = {
            "draft": paper,
            "file": str(out_path),
            "approved": False,
            "generated_at": datetime.now().isoformat(),
        }
        self._save()
        return paper

    # ── 내부 ─────────────────────────────────────────────────────────

    def _call(self, system: str, prompt: str, max_tokens: int = 2048) -> str:
        response = self._client.generate(prompt, system_prompt=system, max_tokens=max_tokens)
        return _clean_llm_response(response)

    def summary(self) -> str:
        """현재 워크플로우 진행 상태 요약."""
        lines = [f"워크플로우: {self.workflow_id}", f"데이터셋: {self.dataset_name}", ""]
        for stage in STAGES:
            label = STAGE_LABELS[stage]
            data = self.stage_data(stage)
            if not data:
                status = "⬜ 미시작"
            elif data.get("approved"):
                status = "✅ 승인됨"
            elif data.get("rejection_feedback"):
                status = "🔴 반려됨"
            else:
                status = "🟡 검수 대기"
            lines.append(f"  {label}: {status}")
        return "\n".join(lines)
