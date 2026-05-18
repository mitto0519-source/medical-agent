"""Korean Public Health Medical Ontology (MeSH-inspired).

한국 공중보건 연구에 특화된 의료 온톨로지.
KYRBS / KNHANES 연구 도메인의 개념 계층 및 관계를 정의한다.

계층 구조:
  Domain → Category → Concept → Synonym/Keyword

주요 용도:
  - 논문에서 핵심 개념 추출
  - 유사 개념 자동 연결 (Graph 구축)
  - 검색 쿼리 확장 (RAG 정확도 향상)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

# ── 온톨로지 정의 ─────────────────────────────────────────────────────────────

ONTOLOGY: Dict[str, Dict] = {
    # ── Domain 1: Population ─────────────────────────────────────────────────
    "D_population": {
        "label": "Population",
        "children": {
            "C_adolescent": {
                "label": "Adolescent (청소년)",
                "keywords": ["adolescent", "youth", "teenager", "student", "청소년", "학생", "중고생"],
                "mesh": "D000293",
            },
            "C_child": {
                "label": "Child (아동)",
                "keywords": ["child", "children", "pediatric", "아동", "소아"],
                "mesh": "D002648",
            },
            "C_adult": {
                "label": "Adult (성인)",
                "keywords": ["adult", "working-age", "성인", "직장인"],
                "mesh": "D000328",
            },
            "C_elderly": {
                "label": "Elderly (노인)",
                "keywords": ["elderly", "older adult", "senior", "aged", "노인", "고령"],
                "mesh": "D000368",
            },
            "C_korean": {
                "label": "Korean population",
                "keywords": ["Korean", "Korea", "한국", "KYRBS", "KNHANES"],
                "mesh": None,
            },
        },
    },

    # ── Domain 2: Health Behavior ─────────────────────────────────────────────
    "D_behavior": {
        "label": "Health Behavior",
        "children": {
            "C_sleep": {
                "label": "Sleep (수면)",
                "keywords": [
                    "sleep", "insomnia", "sleep duration", "sleep quality",
                    "sleep deprivation", "circadian", "수면", "불면", "수면시간",
                ],
                "mesh": "D012895",
            },
            "C_physical_activity": {
                "label": "Physical Activity (신체활동)",
                "keywords": [
                    "physical activity", "exercise", "sedentary", "screen time",
                    "신체활동", "운동", "좌식", "스크린타임",
                ],
                "mesh": "D015444",
            },
            "C_diet": {
                "label": "Diet / Nutrition (식이)",
                "keywords": [
                    "diet", "nutrition", "eating", "dietary", "food intake",
                    "식이", "영양", "식사", "식습관", "mukbang", "먹방",
                ],
                "mesh": "D004435",
            },
            "C_smoking": {
                "label": "Tobacco / Smoking (흡연)",
                "keywords": [
                    "smoking", "tobacco", "cigarette", "e-cigarette", "vaping",
                    "흡연", "담배", "전자담배",
                ],
                "mesh": "D013485",
            },
            "C_alcohol": {
                "label": "Alcohol (음주)",
                "keywords": ["alcohol", "drinking", "binge drinking", "음주", "알코올", "폭음"],
                "mesh": "D000428",
            },
            "C_mental_health": {
                "label": "Mental Health (정신건강)",
                "keywords": [
                    "mental health", "depression", "anxiety", "stress", "suicide",
                    "정신건강", "우울", "불안", "스트레스", "자살",
                ],
                "mesh": "D001523",
            },
            "C_substance": {
                "label": "Substance Use (약물)",
                "keywords": ["substance", "drug", "substance abuse", "약물", "마약"],
                "mesh": "D019966",
            },
        },
    },

    # ── Domain 3: Chronic Disease / Outcome ──────────────────────────────────
    "D_disease": {
        "label": "Chronic Disease & Outcome",
        "children": {
            "C_obesity": {
                "label": "Obesity / Overweight (비만)",
                "keywords": [
                    "obesity", "overweight", "BMI", "body mass index", "adiposity",
                    "비만", "과체중", "체질량지수",
                ],
                "mesh": "D009765",
            },
            "C_hypertension": {
                "label": "Hypertension (고혈압)",
                "keywords": ["hypertension", "blood pressure", "고혈압", "혈압"],
                "mesh": "D006973",
            },
            "C_diabetes": {
                "label": "Diabetes (당뇨)",
                "keywords": ["diabetes", "hyperglycemia", "insulin", "당뇨", "혈당"],
                "mesh": "D003920",
            },
            "C_cardiovascular": {
                "label": "Cardiovascular Disease (심혈관)",
                "keywords": [
                    "cardiovascular", "heart disease", "stroke", "coronary",
                    "심혈관", "심장질환", "뇌졸중",
                ],
                "mesh": "D002318",
            },
            "C_metabolic": {
                "label": "Metabolic Syndrome (대사증후군)",
                "keywords": ["metabolic syndrome", "dyslipidemia", "대사증후군", "이상지질"],
                "mesh": "D024821",
            },
        },
    },

    # ── Domain 4: Study Design ───────────────────────────────────────────────
    "D_design": {
        "label": "Study Design (연구방법)",
        "children": {
            "C_cross_sectional": {
                "label": "Cross-sectional (단면연구)",
                "keywords": ["cross-sectional", "cross sectional", "survey", "단면연구", "횡단연구"],
                "mesh": "D003430",
            },
            "C_longitudinal": {
                "label": "Longitudinal / Cohort (코호트)",
                "keywords": ["longitudinal", "cohort", "prospective", "follow-up", "코호트", "종단연구"],
                "mesh": "D015331",
            },
            "C_meta_analysis": {
                "label": "Meta-analysis / Systematic Review",
                "keywords": ["meta-analysis", "systematic review", "메타분석", "체계적 문헌고찰"],
                "mesh": "D015201",
            },
            "C_case_control": {
                "label": "Case-Control (환자-대조군)",
                "keywords": ["case-control", "case control", "환자-대조", "케이스컨트롤"],
                "mesh": "D016428",
            },
        },
    },

    # ── Domain 5: Statistical Method (통계방법) ──────────────────────────────
    "D_statistics": {
        "label": "Statistical Method",
        "children": {
            "C_logistic": {
                "label": "Logistic Regression (로지스틱 회귀)",
                "keywords": ["logistic regression", "odds ratio", "OR", "로지스틱", "교차비"],
                "mesh": None,
            },
            "C_linear": {
                "label": "Linear Regression (선형 회귀)",
                "keywords": ["linear regression", "beta coefficient", "선형 회귀", "회귀분석"],
                "mesh": None,
            },
            "C_mediation": {
                "label": "Mediation Analysis (매개분석)",
                "keywords": ["mediation", "mediator", "indirect effect", "매개", "간접효과"],
                "mesh": None,
            },
            "C_survival": {
                "label": "Survival Analysis (생존분석)",
                "keywords": ["survival", "Kaplan-Meier", "Cox regression", "hazard ratio", "생존분석"],
                "mesh": None,
            },
        },
    },

    # ── Domain 6: Dataset (데이터셋) ─────────────────────────────────────────
    "D_dataset": {
        "label": "Korean National Dataset",
        "children": {
            "C_kyrbs": {
                "label": "KYRBS (청소년건강행태조사)",
                "keywords": [
                    "KYRBS", "Korea Youth Risk Behavior",
                    "청소년건강행태", "청소년건강행태온라인조사",
                ],
                "mesh": None,
            },
            "C_knhanes": {
                "label": "KNHANES (국민건강영양조사)",
                "keywords": [
                    "KNHANES", "Korea National Health and Nutrition",
                    "국민건강영양조사",
                ],
                "mesh": None,
            },
        },
    },
}


class MedicalOntology:
    """한국 공중보건 의료 온톨로지 인터페이스."""

    def __init__(self):
        self._concept_map: Dict[str, Dict] = {}   # keyword → concept info
        self._build_index()

    def _build_index(self):
        for domain_id, domain in ONTOLOGY.items():
            for concept_id, concept in domain["children"].items():
                for kw in concept.get("keywords", []):
                    self._concept_map[kw.lower()] = {
                        "concept_id": concept_id,
                        "domain_id": domain_id,
                        "label": concept["label"],
                        "domain_label": domain["label"],
                        "mesh": concept.get("mesh"),
                    }

    def extract_concepts(self, text: str) -> List[Dict]:
        """텍스트에서 온톨로지 개념 추출."""
        text_lower = text.lower()
        found: Dict[str, Dict] = {}
        for kw, info in self._concept_map.items():
            if kw in text_lower:
                cid = info["concept_id"]
                if cid not in found:
                    found[cid] = {**info, "matched_keyword": kw}
        return list(found.values())

    def get_concept(self, concept_id: str) -> Optional[Dict]:
        for domain in ONTOLOGY.values():
            if concept_id in domain["children"]:
                return domain["children"][concept_id]
        return None

    def get_siblings(self, concept_id: str) -> List[str]:
        """같은 도메인의 형제 개념 ID 반환."""
        for domain in ONTOLOGY.values():
            if concept_id in domain["children"]:
                return [c for c in domain["children"] if c != concept_id]
        return []

    def expand_keywords(self, concept_ids: List[str]) -> List[str]:
        """개념 ID 목록 → 검색용 키워드 확장."""
        kws: Set[str] = set()
        for cid in concept_ids:
            c = self.get_concept(cid)
            if c:
                kws.update(c.get("keywords", []))
        return list(kws)

    def all_concepts(self) -> List[Dict]:
        """전체 개념 목록 반환 (domain + concept 포함)."""
        result = []
        for domain_id, domain in ONTOLOGY.items():
            for concept_id, concept in domain["children"].items():
                result.append({
                    "domain_id": domain_id,
                    "concept_id": concept_id,
                    "label": concept["label"],
                    "domain_label": domain["label"],
                    "keywords": concept.get("keywords", []),
                    "mesh": concept.get("mesh"),
                })
        return result

    def pubmed_queries_for_dataset(self, dataset: str) -> List[str]:
        """데이터셋 이름으로 PubMed 검색 쿼리 목록 생성."""
        dataset_upper = dataset.upper()
        if dataset_upper == "KYRBS":
            base_kws = ONTOLOGY["D_dataset"]["children"]["C_kyrbs"]["keywords"]
        elif dataset_upper == "KNHANES":
            base_kws = ONTOLOGY["D_dataset"]["children"]["C_knhanes"]["keywords"]
        else:
            base_kws = [dataset]

        topics = [
            ("sleep", ["sleep", "수면"]),
            ("obesity", ["obesity", "BMI", "비만"]),
            ("mental health", ["depression", "mental health", "우울"]),
            ("physical activity", ["physical activity", "exercise"]),
            ("diet", ["diet", "nutrition"]),
        ]
        queries = []
        for base_kw in base_kws[:2]:
            queries.append(f'"{base_kw}"[Title/Abstract]')
        for topic_name, kws in topics:
            q_parts = [f'"{base_kws[0]}"[Title/Abstract]']
            q_parts.append(f'("{kws[0]}"[Title/Abstract])')
            queries.append(" AND ".join(q_parts))
        return queries[:8]


_singleton: Optional[MedicalOntology] = None


def get_ontology() -> MedicalOntology:
    global _singleton
    if _singleton is None:
        _singleton = MedicalOntology()
    return _singleton
