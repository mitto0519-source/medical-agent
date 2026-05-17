"""Paper Writer — 조유선 스타일로 논문 초안 생성

AuthorProfile(스타일 시드) + MethodsLibrary + DatasetLibrary + RAG컨텍스트를
결합해 완성도 높은 논문 초안을 생성.
"""

import os
from typing import Dict, List, Optional

from src.llm import get_llm_client


class PaperWriter:
    """저자 스타일 시드를 적용한 논문 작성기.

    사용 흐름:
        writer = PaperWriter(author_profile, methods_lib, dataset_lib)
        draft = writer.write_abstract(topic, study_info, results)
        full  = writer.write_full_paper(topic, study_info, results, references)
    """

    def __init__(
        self,
        author_profile,          # AuthorProfile instance
        methods_library=None,    # MethodsLibrary instance
        dataset_library=None,    # DatasetLibrary instance
        rag_pipeline=None,       # RAGPipeline for reference retrieval
        llm_client=None,
        api_key: Optional[str] = None,
    ):
        self._profile = author_profile
        self._methods = methods_library
        self._datasets = dataset_library
        self._rag = rag_pipeline
        self._client = llm_client or get_llm_client(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_abstract(
        self,
        topic: str,
        background: str,
        objective: str,
        methods_summary: str,
        results_summary: str,
        conclusion: str,
        word_limit: int = 250,
    ) -> str:
        """저자 스타일로 Abstract 작성."""

        system = self._profile.get_system_prompt()
        prompt = f"""Write a structured abstract for the following medical research paper.
Word limit: {word_limit} words.
Use this author's exact style and formatting.

TOPIC: {topic}

SECTIONS TO INCLUDE:
Background: {background}
Objective: {objective}
Methods: {methods_summary}
Results: {results_summary}
Conclusion: {conclusion}

Write the complete abstract now. Use the standard structured format (Background / Objective / Methods / Results / Conclusion).
"""
        return self._generate(system, prompt)

    def write_introduction(
        self,
        topic: str,
        background_facts: List[str],
        knowledge_gap: str,
        hypothesis: str,
        reference_context: Optional[str] = None,
    ) -> str:
        """저자 스타일로 Introduction 작성."""

        ref_block = f"\n\nREFERENCE CONTEXT FROM LITERATURE:\n{reference_context}" if reference_context else ""
        system = self._profile.get_system_prompt()
        prompt = f"""Write the Introduction section for this medical research paper.
Match the author's exact introduction structure and style.

TOPIC: {topic}

KEY BACKGROUND FACTS:
{chr(10).join(f'- {f}' for f in background_facts)}

KNOWLEDGE GAP: {knowledge_gap}

STUDY HYPOTHESIS/AIM: {hypothesis}
{ref_block}

Write the full Introduction section. Build from broad context → specific gap → study aim.
"""
        return self._generate(system, prompt)

    def write_methods(
        self,
        study_design: str,
        population: str,
        dataset_name: Optional[str] = None,
        exposure: str = "",
        outcome: str = "",
        covariates: str = "",
        statistical_methods: List[str] = None,
    ) -> str:
        """저자 스타일로 Methods 섹션 작성."""

        dataset_ctx = ""
        if dataset_name and self._datasets:
            dataset_ctx = self._datasets.get_context(dataset_name)

        methods_ctx = ""
        if statistical_methods and self._methods:
            methods_ctx = self._methods.get_context_for_claude(statistical_methods)

        system = self._profile.get_system_prompt()
        prompt = f"""Write the Methods section for this medical research paper.
Use this author's level of detail and formatting exactly.

STUDY DESIGN: {study_design}
POPULATION: {population}
EXPOSURE: {exposure}
OUTCOME: {outcome}
COVARIATES: {covariates}

{dataset_ctx}

{methods_ctx}

Write the full Methods section including: Study Design and Population, Exposure Assessment,
Outcome Assessment, Covariate Assessment, Statistical Analysis.
"""
        return self._generate(system, prompt)

    def write_results(
        self,
        descriptive_stats: str,
        main_findings: List[str],
        subgroup_findings: Optional[str] = None,
        sensitivity_findings: Optional[str] = None,
    ) -> str:
        """저자 스타일로 Results 섹션 작성."""

        sub_block = f"\nSubgroup findings:\n{subgroup_findings}" if subgroup_findings else ""
        sens_block = f"\nSensitivity analysis findings:\n{sensitivity_findings}" if sensitivity_findings else ""

        system = self._profile.get_system_prompt()
        prompt = f"""Write the Results section for this medical research paper.
Match the author's exact results-reporting style (how they present ORs, HRs, CIs, p-values, etc.).

DESCRIPTIVE STATISTICS:
{descriptive_stats}

MAIN FINDINGS:
{chr(10).join(f'- {f}' for f in main_findings)}
{sub_block}
{sens_block}

Write the full Results section. Describe participant characteristics first, then main analyses,
then subgroup/sensitivity analyses. Use exact numeric reporting format this author uses.
"""
        return self._generate(system, prompt)

    def write_discussion(
        self,
        main_findings: List[str],
        comparison_with_literature: str,
        mechanisms: str,
        strengths: List[str],
        limitations: List[str],
        conclusion_message: str,
        reference_context: Optional[str] = None,
    ) -> str:
        """저자 스타일로 Discussion 작성."""

        ref_block = f"\nREFERENCE CONTEXT:\n{reference_context}" if reference_context else ""
        system = self._profile.get_system_prompt()
        prompt = f"""Write the Discussion section for this medical research paper.
Match the author's discussion structure and hedging language exactly.

MAIN FINDINGS TO DISCUSS:
{chr(10).join(f'- {f}' for f in main_findings)}

COMPARISON WITH EXISTING LITERATURE:
{comparison_with_literature}

PROPOSED MECHANISMS:
{mechanisms}

STRENGTHS:
{chr(10).join(f'- {s}' for s in strengths)}

LIMITATIONS:
{chr(10).join(f'- {l}' for l in limitations)}

KEY CONCLUSION MESSAGE: {conclusion_message}
{ref_block}

Write the full Discussion. Structure: summary of findings → comparison with literature →
mechanisms → strengths/limitations → conclusion.
"""
        return self._generate(system, prompt)

    def write_full_paper(
        self,
        topic: str,
        study_info: Dict,
        results: Dict,
        reference_context: Optional[str] = None,
    ) -> str:
        """전체 논문 초안 한번에 생성.

        study_info: dataset, design, sample_size, survey_year, journal,
                    population, exposure, outcome, covariates, methods_list 등
        results: summary(필수), main_findings(선택), descriptive, subgroup,
                 sensitivity, conclusion, literature_comparison, mechanisms
        """
        # ── results 정규화: summary → main_findings 자동 변환 ──────────
        results_summary = results.get("summary", "")
        main_findings = results.get("main_findings") or (
            [results_summary] if results_summary else ["Not provided"]
        )

        dataset_name = study_info.get("dataset", "")
        design = study_info.get("design", "cross-sectional")
        population = study_info.get("population", "")
        exposure = study_info.get("exposure", "")
        outcome = study_info.get("outcome", "")
        sample_size = study_info.get("sample_size", "")
        journal = study_info.get("journal", "")

        # dataset_name이 긴 서술형이면 "KYRBS" 같은 약어만 추출해 메서드에 넘김
        dataset_key = None
        if self._datasets:
            for ds_name in self._datasets.list_datasets():
                if ds_name.upper() in dataset_name.upper():
                    dataset_key = ds_name
                    break

        sections = {}

        print("[PaperWriter] Abstract 작성 중...")
        sections["abstract"] = self._generate(
            self._profile.get_system_prompt(),
            f"""Write a structured abstract for this medical research paper.
Word limit: 300 words. Use Background / Objective / Methods / Results / Conclusion format.

TOPIC: {topic}
STUDY DESIGN: {design}
DATASET: {dataset_name} (n={sample_size})
EXPOSURE: {exposure}
OUTCOME: {outcome}
POPULATION: {population}
KEY RESULTS: {results_summary}
TARGET JOURNAL: {journal}

Write the complete abstract now. Base all content strictly on the information provided above.
Do NOT substitute content from other studies.""",
        )

        print("[PaperWriter] Introduction 작성 중...")
        ref_block = f"\n\nREFERENCE CONTEXT:\n{reference_context}" if reference_context else ""
        sections["introduction"] = self._generate(
            self._profile.get_system_prompt(),
            f"""Write the Introduction section for this medical research paper.

TOPIC: {topic}
EXPOSURE: {exposure}
OUTCOME: {outcome}
POPULATION: {population}
STUDY DESIGN: {design}{ref_block}

Structure: broad public health context → specific problem → knowledge gap → study aim.
Keep strictly to this topic. Do NOT refer to other unrelated studies.
Write 4–5 paragraphs.""",
        )

        print("[PaperWriter] Methods 작성 중...")
        dataset_ctx = self._datasets.get_context(dataset_key) if (dataset_key and self._datasets) else ""
        methods_ctx = self._methods.get_context_for_claude(
            study_info.get("methods_list", ["logistic_regression"])
        ) if self._methods else ""
        sections["methods"] = self._generate(
            self._profile.get_system_prompt(),
            f"""Write the Methods section for this medical research paper.

TOPIC: {topic}
STUDY DESIGN: {design}
DATASET: {dataset_name} (n={sample_size})
EXPOSURE: {exposure}
OUTCOME: {outcome}
COVARIATES: {study_info.get("covariates", "sex, age, grade, family_econ, academic_perf, BMI, depression, physical activity")}

{dataset_ctx}
{methods_ctx}

Write subsections: Study Design and Population / Exposure / Outcome / Covariates / Statistical Analysis.
Include complex survey analysis (stratification, clustering, weights) if KYRBS data.""",
        )

        print("[PaperWriter] Results 작성 중...")
        sections["results"] = self._generate(
            self._profile.get_system_prompt(),
            f"""Write the Results section for this medical research paper.

TOPIC: {topic}
EXPOSURE: {exposure}
OUTCOME: {outcome}
DATASET: {dataset_name} (n={sample_size})

KEY FINDINGS (use these exact numbers):
{chr(10).join(f'- {f}' for f in main_findings)}

Additional subgroup findings: {results.get("subgroup", "Not provided")}
Sensitivity analyses: {results.get("sensitivity", "Not provided")}

IMPORTANT: Base the Results ONLY on the numbers above. Do NOT invent statistics.
Write in this author's exact numeric reporting style (aOR, 95% CI, P values).
Subsections: Participant characteristics → Main analysis → Subgroup → Sensitivity.""",
        )

        print("[PaperWriter] Discussion 작성 중...")
        sections["discussion"] = self._generate(
            self._profile.get_system_prompt(),
            f"""Write the Discussion section for this medical research paper.

TOPIC: {topic}
EXPOSURE: {exposure}
OUTCOME: {outcome}

KEY FINDINGS TO DISCUSS:
{chr(10).join(f'- {f}' for f in main_findings)}

COMPARISON WITH LITERATURE: {results.get("literature_comparison", "Discuss in relation to prior studies on this topic.")}
MECHANISMS: {results.get("mechanisms", "Propose biologically plausible mechanisms.")}
STRENGTHS: nationwide representative sample, large n={sample_size}, validated survey instrument
LIMITATIONS: cross-sectional design (cannot establish causality), self-reported data, residual confounding
{ref_block}

Write in this author's hedging style. Structure:
1) Summary of main findings
2) Comparison with existing literature
3) Proposed mechanisms
4) Strengths and limitations
5) Conclusion with public health implications""",
        )

        # Assemble
        author = self._profile.author_name
        separator = "=" * 70
        paper = f"""{separator}
{topic.upper()}
{separator}
By {author}

{separator}
ABSTRACT
{separator}
{sections['abstract']}

{separator}
INTRODUCTION
{separator}
{sections['introduction']}

{separator}
METHODS
{separator}
{sections['methods']}

{separator}
RESULTS
{separator}
{sections['results']}

{separator}
DISCUSSION
{separator}
{sections['discussion']}
"""
        return paper

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate(self, system_prompt: str, user_prompt: str) -> str:
        return self._client.generate(user_prompt, system_prompt=system_prompt)
