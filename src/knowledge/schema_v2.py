"""KNOWLEDGE_MODEL_SPEC schema v2 — standards-anchored definitions.

Implements §3 (axis catalog), §5 (chunk meta), §6 (edge catalog), §9 conservative defaults.
This module is *definitions only* — no DB writes, no data mutations.

Consumed by:
  - src/knowledge/medical_ontology.py (concept record schema)
  - src/knowledge/orchestrator.py (chunk meta passed to ChromaDB)
  - src/knowledge/medical_graph.py (edge type enum)
  - scripts/migrate_concepts_to_cui.py (future: backfill cui field)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

SCHEMA_VERSION = "2.0.0-2026-06-14"

# ─────────────────────────────────────────────────────────────────────
# §2 STANDARDS ADOPTION (§9.1 default: UMLS CUI hub + MeSH/LOINC/RxNorm/MedDRA)
# ─────────────────────────────────────────────────────────────────────

ADOPTED_STANDARDS = {
    "primary": ["UMLS_CUI", "MeSH", "LOINC", "RxNorm", "ATC", "MedDRA",
                "ICD-10", "HPO", "HGNC"],
    "deferred": ["SNOMED-CT"],   # §9.1 — staged adoption
    "frameworks": ["PICO", "PECO", "STROBE", "CONSORT", "PRISMA", "STARD",
                    "TRIPOD", "GRADE", "Oxford_CEBM"],
}


# ─────────────────────────────────────────────────────────────────────
# §3 AXIS CATALOG (16 axes)
# ─────────────────────────────────────────────────────────────────────

AXES = {
    "D_population":    {"label": "Population (인구·생애·특수집단)",      "anchor": ["MeSH"]},
    "D_disease":       {"label": "Disease (질환)",                       "anchor": ["ICD-10", "MeSH"]},
    "D_exposure":      {"label": "Exposure / Risk factor",               "anchor": ["MeSH"]},
    "D_intervention":  {"label": "Intervention",                         "anchor": ["ATC"]},
    "D_outcome":       {"label": "Outcome",                              "anchor": ["MeSH", "MedDRA"]},
    "D_biomarker_lab": {"label": "Biomarker / Lab",                      "anchor": ["LOINC"]},
    "D_drug":          {"label": "Drug",                                 "anchor": ["RxNorm", "ATC"]},
    "D_genetics":      {"label": "Genetics / Molecular",                 "anchor": ["HGNC"]},
    "D_methodology":   {"label": "Statistical Methodology",              "anchor": ["internal"]},
    "D_study_design":  {"label": "Study Design",                         "anchor": ["STROBE", "PRISMA"]},
    "D_data_source":   {"label": "Data Source",                          "anchor": ["internal"]},
    "D_setting":       {"label": "Clinical Setting",                     "anchor": ["MeSH"]},
    "D_discipline":    {"label": "Discipline (★다학제 교차축)",         "anchor": ["internal"]},
    "D_evidence":      {"label": "Evidence Level",                       "anchor": ["GRADE", "Oxford_CEBM"]},
    "D_temporal":      {"label": "Temporal",                             "anchor": ["internal"]},
    "D_mechanism":     {"label": "Mechanism (★다학제 교차축)",          "anchor": ["MeSH"]},
}


# §9.3 — Full discipline list (24 disciplines)
DISCIPLINES = [
    "cardiology", "endocrinology", "nephrology", "neurology", "psychiatry",
    "oncology", "infectious-disease", "pulmonology", "gastroenterology",
    "pediatrics", "ob-gyn", "surgery", "rheumatology-immunology",
    "pharmacology", "genomics",
    "epidemiology", "biostatistics", "health-policy", "health-economics",
    "public-health", "preventive-medicine", "nutrition",
    "environmental-occupational-health", "medical-informatics",
]


# ─────────────────────────────────────────────────────────────────────
# §3 CONCEPT RECORD — extended schema (backward-compatible)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ConceptRecord:
    """One concept entry — backward compatible with current ONTOLOGY dict."""
    concept_id: str              # internal id, e.g. "C_adolescent"
    label: str                   # human-readable label
    axis: str                    # D_population / D_disease / ...
    keywords: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)   # multi-lang
    # ── standard anchors (None if not yet mapped — null, NOT fabricated) ──
    cui: Optional[str] = None     # UMLS CUI — master cross-walk key
    mesh: Optional[str] = None
    snomed: Optional[str] = None
    icd: Optional[str] = None
    loinc: Optional[str] = None
    rxcui: Optional[str] = None
    atc: Optional[str] = None
    meddra: Optional[str] = None
    hgnc: Optional[str] = None
    hpo: Optional[str] = None
    # ── relationships ──
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    discipline: List[str] = field(default_factory=list)  # ★ §3-M cross-axis
    # ── embedding ──
    embed_centroid: Optional[List[float]] = None
    # ── governance ──
    source: str = "manual"        # "manual" | "umls_link" | "embed_llm"
    confidence: float = 1.0
    added_at: str = ""


# ─────────────────────────────────────────────────────────────────────
# §5 CHUNK META SCHEMA — full catalog
# ─────────────────────────────────────────────────────────────────────

CHUNK_META_FIELDS = [
    # provenance
    "pmid", "pmcid", "doi", "journal", "year", "section_char_span",
    # section / rhetorical
    "section", "subsection", "rhetorical_role",
    # study identification
    "study_design", "population", "exposure", "outcome", "intervention",
    "biomarker", "drug", "gene",
    # statistical
    "statistical_method", "effect_measure", "effect_estimate",
    "sample_size", "events", "follow_up", "covariates",
    # evidence
    "evidence_level", "risk_of_bias",
    # cross-axis
    "discipline", "mechanism",
    # text features
    "citation_density",
    # extraction confidence — each axis above can have *_conf
]


REQUIRED_META_FIELDS = ["pmid", "section"]   # everything else nullable


# Rhetorical role — AZ/CoreSC enum
RHETORICAL_ROLES = [
    "background", "hypothesis", "method", "result", "finding",
    "interpretation", "limitation", "implication", "comparison",
    "definition", "motivation",
]


# Section labels — IMRaD+
SECTION_LABELS = [
    "title", "abstract", "background", "introduction", "methods",
    "statistical-analysis", "results", "discussion", "limitation",
    "conclusion", "funding", "ethics", "supplementary",
]


# Effect measures — controlled vocabulary
EFFECT_MEASURES = [
    "OR", "aOR", "RR", "aRR", "HR", "aHR", "IRR", "MD", "SMD",
    "beta", "correlation", "AUC", "sensitivity", "specificity",
    "prevalence_ratio", "PR",
]


# ─────────────────────────────────────────────────────────────────────
# §6 EDGE CATALOG — graph relations
# ─────────────────────────────────────────────────────────────────────

NODE_TYPES = [
    "Paper", "Author", "Journal", "Dataset", "Study",
    "Concept",   # subtype = axis
    "Finding", "Hypothesis", "Method", "Guideline", "Discipline",
    # MASTER_UPGRADE §3 #1 — Evidence Graph close: Claim sits between generated
    # manuscript sentences and the Finding/Paper/Dataset/Citation chain.
    "Claim",
]


# §6.2 — full edge taxonomy
EDGE_CATALOG = {
    # ── bibliographic / measurement ─────────────────────
    "REPORTS":              {"from": "Paper",      "to": "Finding"},
    "USES_DESIGN":          {"from": "Paper",      "to": "Study_design"},
    "USES_DATASET":         {"from": "Paper",      "to": "Dataset"},
    "USES_METHOD":          {"from": "Paper",      "to": "Method"},
    "MEASURES":             {"from": "Study",      "to": "Biomarker"},

    # ── association / causal ────────────────────────────
    "EXPOSURE_TO_OUTCOME":  {"from": "Exposure",   "to": "Outcome",
                              "attrs": ["effect_measure", "estimate",
                                          "ci_low", "ci_high", "p", "direction"]},
    "RISK_FACTOR_FOR":      {"from": "Exposure",   "to": "Disease"},
    "PROTECTS_AGAINST":     {"from": "Exposure",   "to": "Disease"},
    "MECHANISM_OF":         {"from": "Mechanism",  "to": "Edge"},
    "MEDIATES":             {"from": "Concept",    "to": "Edge"},
    "MODERATES":            {"from": "Concept",    "to": "Edge"},
    "CONFOUNDS":            {"from": "Concept",    "to": "Edge"},
    "DOSE_RESPONSE":        {"from": "Exposure",   "to": "Outcome",
                              "attrs": ["p_for_trend"]},

    # ── clinical ────────────────────────────────────────
    "TREATS":               {"from": "Intervention", "to": "Disease"},
    "CAUSES_AE":            {"from": "Drug",       "to": "AdverseEvent",
                              "attrs": ["meddra_pt", "frequency"]},
    "CONTRAINDICATED_WITH": {"from": "Drug",       "to": "Drug"},
    "INTERACTS_WITH":       {"from": "Drug",       "to": "Drug"},
    "DIAGNOSES":            {"from": "Biomarker",  "to": "Disease",
                              "attrs": ["sensitivity", "specificity", "auc"]},
    "PROGNOSTIC_FOR":       {"from": "Biomarker",  "to": "Disease"},
    "BIOMARKER_OF":         {"from": "Biomarker",  "to": "Mechanism"},

    # ── scientific discourse ────────────────────────────
    "SUPPORTS":             {"from": "Finding",    "to": "Finding"},
    "CONTRADICTS":          {"from": "Finding",    "to": "Finding"},
    "REPLICATES":           {"from": "Paper",      "to": "Paper"},
    "EXTENDS":              {"from": "Paper",      "to": "Paper"},
    "CITES":                {"from": "Paper",      "to": "Paper"},
    "RESEARCH_GAP":         {"from": "Concept",    "to": "Concept"},

    # ── cross-discipline (translational) ────────────────
    "SHARED_MECHANISM":     {"from": "Disease",    "to": "Disease"},
    "SHARED_POPULATION":    {"from": "Study",      "to": "Study"},
    "TRANSLATES_TO":        {"from": "Gene",       "to": "Outcome"},
    "SPANS_DISCIPLINE":     {"from": "Paper",      "to": "Discipline"},

    # ── legacy compat (current graph) ───────────────────
    "HAS_CONCEPT":          {"from": "Paper",      "to": "Concept"},
    "RELATED_TO":           {"from": "Concept",    "to": "Concept"},

    # ── Evidence Graph close (MASTER_UPGRADE §3 #1) ─────
    # Claim emitted by writer → traceable chain to Finding/Paper/Dataset.
    "CLAIMS":               {"from": "Paper",      "to": "Claim"},          # manuscript→claim
    "EVIDENCED_BY":         {"from": "Claim",      "to": "Finding"},        # claim → prior finding
    "DERIVED_FROM":         {"from": "Claim",      "to": "Dataset",
                              "attrs": ["n", "year_range"]},                # claim → own dataset
    "CITES_FOR":            {"from": "Claim",      "to": "Paper"},          # claim → cited paper
    "CONFIDENCE_OF":        {"from": "Claim",      "to": "Confidence",
                              "attrs": ["overall", "citation", "stat", "novelty"]},
}


# §9.4 — edge confidence default
def edge_confidence(sample_size: int, evidence_level: str = "low",
                       source_count: int = 1) -> float:
    """Single-paper edges allowed; confidence reflects evidence weight."""
    n_score = min(1.0, (sample_size or 0) / 10000)
    ev_w = {"high": 1.0, "moderate": 0.7, "low": 0.4, "verylow": 0.2}.get(
        evidence_level, 0.4)
    src_score = min(1.0, (source_count or 1) / 3)
    return round(0.4 * n_score + 0.4 * ev_w + 0.2 * src_score, 3)


VERIFIED_THRESHOLD_N_SOURCES = 3   # §9.4 — verified=true when n_sources>=3


# ─────────────────────────────────────────────────────────────────────
# §9 DEFAULTS — user can override
# ─────────────────────────────────────────────────────────────────────

USER_DEFAULTS = {
    "standards_scope": "UMLS_hub_plus_mesh_loinc_rxnorm_meddra",  # §9.1
    "concept_granularity": "current_plus_severity_for_top_diagnoses",  # §9.2
    "discipline_list": "full_24",   # §9.3 — DISCIPLINES above
    "edge_threshold": "single_paper_with_confidence",  # §9.4
    "auto_extraction_review_threshold": 0.6,  # §9.5 — review below 0.6
}


# ─────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────

def validate_chunk_meta(meta: Dict[str, Any]) -> List[str]:
    """Returns list of validation errors (empty = OK)."""
    errors = []
    for f in REQUIRED_META_FIELDS:
        if f not in meta or meta[f] is None:
            errors.append(f"missing required field: {f}")
    if meta.get("rhetorical_role") and meta["rhetorical_role"] not in RHETORICAL_ROLES:
        errors.append(f"unknown rhetorical_role: {meta['rhetorical_role']}")
    if meta.get("section") and meta["section"] not in SECTION_LABELS:
        errors.append(f"unknown section: {meta['section']}")
    if meta.get("effect_measure") and meta["effect_measure"] not in EFFECT_MEASURES:
        errors.append(f"unknown effect_measure: {meta['effect_measure']}")
    return errors


def is_known_edge(edge_type: str) -> bool:
    return edge_type in EDGE_CATALOG


def is_known_axis(axis: str) -> bool:
    return axis in AXES
