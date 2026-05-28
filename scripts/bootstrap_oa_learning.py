"""Bootstrap 5만편 학습 — Europe PMC OA 시드 query를 backlog에 자동 enqueue.

기본 시드는 `src.knowledge.medical_ontology.pubmed_queries_for_dataset` 활용
+ KYRBS/KNHANES 주요 도메인 매핑.

사용:
    python scripts/bootstrap_oa_learning.py                       # 시드 (n=200/query)
    python scripts/bootstrap_oa_learning.py --per 500 --target 50000
    python scripts/bootstrap_oa_learning.py --queries "diabetes,depression"
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _ensure_utf8_stdout():
    """sys.stdout을 UTF-8 wrap (CLI에서만 호출 — Streamlit import 시엔 호출 X)."""
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                            errors="replace", line_buffering=True)
    except Exception:
        pass


# 주요 의학 도메인 시드 — 5만편 분산 (각 query 200-500편)
DEFAULT_SEEDS = [
    "adolescent depression Korea",
    "adolescent depression nutrition",
    "zero-calorie beverage mental health",
    "artificial sweetener depression",
    "ultra-processed food adolescent",
    "sugar-sweetened beverage adolescent depression",
    "gut microbiome depression",
    "gut brain axis adolescent",
    "physical activity adolescent mental health",
    "screen time adolescent depression",
    "smartphone use sleep adolescent",
    "breakfast skipping adolescent",
    "school stress Korea adolescent",
    "KYRBS Korea Youth Risk Behavior",
    "KNHANES Korea National Health",
    "diabetes adolescent obesity",
    "obesity BMI Korean children",
    "metabolic syndrome adolescent",
    "smoking adolescent Korea",
    "alcohol use adolescent Korea",
    "suicidal ideation adolescent",
    "anxiety disorder adolescent",
    "puberty hormone depression female",
    "BMI growth chart Korean",
    "survey weighted logistic regression epidemiology",
    "STROBE cross-sectional",
    "complex sample design adolescent survey",
    "propensity score matching observational",
    "logistic regression sex stratified",
    "subgroup analysis interaction",
    "forest plot meta-analysis",
    "Kaplan-Meier survival adolescent",
    "Cox proportional hazards Korea",
    "marginal standardization predicted probability",
    "cross-sectional study reverse causation",
    "self-reported measurement bias",
    "residual confounding observational",
    "menstrual cycle mood adolescent",
    "eating disorder body image adolescent",
    "family socioeconomic status mental health",
    "dopamine reward adolescent brain",
    "serotonin prefrontal cortex adolescent",
    "frontostriatal circuit development",
    "Eggerthella gut bacteria",
    "Whitehall II cohort depression",
    "UK Biobank depression",
    "NHANES depression diet",
    "Nurses Health Study depression",
    "longitudinal Chinese adolescent depression",
    "Malaysian adolescent dietary depression",
    "US adolescent soft drink depression",
    # ── 확장 (의학 ontology 기반 다도메인) ──────────────────────────
    # Cardiovascular / metabolic
    "hypertension adolescent prevention",
    "lipid profile dyslipidemia youth",
    "fasting glucose insulin resistance",
    "metabolic syndrome incidence cohort",
    "non-alcoholic fatty liver disease adolescent",
    # Mental health expanded
    "ADHD adolescent academic performance",
    "autism spectrum disorder Korea",
    "PTSD trauma adolescent",
    "bipolar disorder youth",
    "schizophrenia early intervention",
    "internet gaming disorder",
    "social media depression teenager",
    "loneliness isolation adolescent mental",
    "self-harm non-suicidal adolescent",
    # Sleep / circadian
    "sleep duration adolescent academic",
    "circadian rhythm chronotype student",
    "insomnia melatonin adolescent",
    "obstructive sleep apnea youth",
    # Nutrition / micronutrient
    "vitamin D deficiency adolescent depression",
    "omega 3 fatty acid mood",
    "iron deficiency anemia girl",
    "zinc magnesium mental health",
    "Mediterranean diet adolescent",
    "ketogenic diet mood disorder",
    "vegan vegetarian adolescent depression",
    "fast food consumption adolescent",
    "fruit vegetable intake youth",
    # Physical activity expanded
    "MVPA moderate vigorous physical activity",
    "sedentary behavior cardiometabolic",
    "active transport school commute",
    "team sport adolescent mental",
    "exercise dose response depression",
    "cardiorespiratory fitness youth",
    # Endocrinology
    "thyroid function adolescent",
    "polycystic ovary syndrome teenager",
    "cortisol HPA axis stress",
    "growth hormone deficiency",
    # Respiratory / allergy
    "asthma adolescent prevalence",
    "allergic rhinitis quality life",
    "atopic dermatitis depression",
    "indoor air quality school",
    # Substance / addiction
    "e-cigarette vaping adolescent",
    "cannabis use disorder youth",
    "alcohol binge drinking adolescent",
    "energy drink caffeine youth",
    "nicotine dependence adolescent",
    # Reproductive / sexual health
    "menarche timing depression",
    "PMS premenstrual syndrome adolescent",
    "contraception adolescent Korea",
    "STD sexually transmitted infection youth",
    # Oncology / pediatric
    "childhood cancer survivor mental",
    "leukemia pediatric long-term outcome",
    "screening prevention adolescent",
    # Infectious / vaccine
    "HPV vaccination adolescent uptake",
    "COVID-19 long term adolescent mental",
    "influenza adolescent absenteeism",
    "tuberculosis youth screening",
    # Environmental / social determinants
    "air pollution PM2.5 mental health",
    "neighborhood walkability depression",
    "household income mental health youth",
    "school bullying victimization",
    "cyberbullying adolescent",
    "academic stress East Asian student",
    "after school private tutoring Korea",
    # Statistical / methodological deeper
    "directed acyclic graph DAG epidemiology",
    "negative control causal inference",
    "instrumental variable Mendelian",
    "G-methods time-varying confounding",
    "missing data multiple imputation survey",
    "interaction effect modification three-way",
    "mediation analysis natural effects",
    "interrupted time series segmented regression",
    "difference in differences observational",
    "regression discontinuity design",
    # Korean public health cohorts
    "Korean Genome Epidemiology Study KoGES",
    "Korean National Health Insurance NHIS cohort",
    "Korean Longitudinal Study Aging KLoSA",
    "Korean Children Adolescents Study KoCAS",
    "Ansan Ansung cohort follow-up",
    # Mechanism deeper
    "neuroinflammation cytokine depression",
    "BDNF brain derived neurotrophic factor",
    "leptin ghrelin satiety adolescent",
    "vagus nerve enteric depression",
    "Akkermansia muciniphila depression",
    "Lactobacillus probiotic mood",
    "short chain fatty acid gut",
    "tryptophan kynurenine pathway depression",
    "neuroplasticity prefrontal cortex puberty",
    # Cross-cultural / Asian
    "Japanese adolescent depression cohort",
    "Taiwan adolescent mental health",
    "Singapore youth wellbeing",
    "Indian adolescent suicide",
    "Vietnamese adolescent nutrition",
    "East Asian academic pressure mental",
    # Pharmacology
    "SSRI fluoxetine adolescent depression",
    "antipsychotic atypical youth weight",
    "stimulant methylphenidate ADHD",
    "benzodiazepine dependence youth",
    "medication adherence chronic adolescent",
    # Digital health / intervention
    "mobile app mental health intervention",
    "digital cognitive behavioral therapy",
    "school-based intervention depression",
    "mindfulness meditation adolescent",
    "yoga mental health randomized",
    "exercise prescription depression trial",
    # Special populations
    "LGBTQ adolescent mental health",
    "refugee migrant adolescent stress",
    "disability adolescent quality of life",
    "orphan institutional care development",
    "rural urban adolescent health disparity",
    # Body composition / image
    "waist circumference adolescent metabolic",
    "body image dissatisfaction depression",
    "weight gain freshman college",
    "muscle dysmorphia adolescent boy",
    "thigh gap social media body",
    # Specific exposures
    "phthalate endocrine disruptor adolescent",
    "BPA bisphenol A puberty",
    "heavy metal lead mercury cognitive",
    "secondhand smoke adolescent",
    "noise exposure school mental",
    # Health behavior
    "health literacy adolescent intervention",
    "self-management chronic disease youth",
    "preventive care utilization adolescent",
    "vaccination hesitancy parental",
    "screen-based sedentary intervention",
    # Risk factors longitudinal
    "early life adversity ACE adolescent",
    "maternal depression child outcome",
    "preterm birth long term neurodevelopment",
    "low birth weight cardiometabolic adult",
]


def main():
    _ensure_utf8_stdout()   # CLI 전용
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=200,
                     help="각 query당 fetch할 편수 (기본 200)")
    ap.add_argument("--target", type=int, default=50000,
                     help="총 목표 편수 (기본 50000)")
    ap.add_argument("--queries", help="comma-separated query 목록 (기본: 시드 50개)")
    ap.add_argument("--year_min", type=int, default=2018, help="최소 발행 연도")
    ap.add_argument("--dry-run", action="store_true", help="enqueue 안 하고 계획만 출력")
    args = ap.parse_args()

    queries = ([q.strip() for q in args.queries.split(",") if q.strip()]
                if args.queries else DEFAULT_SEEDS)

    # 목표 편수에 맞게 query 수 조절
    n_needed_queries = max(1, args.target // max(1, args.per))
    queries = queries * (n_needed_queries // len(queries) + 1)
    queries = queries[:n_needed_queries]

    print(f"OA bootstrap — {len(queries)} queries × {args.per}/query "
          f"= 최대 {len(queries) * args.per:,}편 목표 (target {args.target:,})")

    if args.dry_run:
        for i, q in enumerate(queries[:10], 1):
            print(f"  {i}. {q}")
        if len(queries) > 10:
            print(f"  … +{len(queries)-10} more")
        return 0

    from src.runtime.backlog import enqueue
    enqueued = 0
    for q in queries:
        try:
            tid = enqueue("oa_bulk_fetch",
                           {"query": q, "n_target": args.per,
                            "year_min": args.year_min},
                           owner="bootstrap@oa")
            enqueued += 1
            if enqueued % 10 == 0:
                print(f"  enqueued {enqueued}/{len(queries)}…")
        except Exception as e:
            print(f"  enqueue fail [{q}]: {e}")

    print(f"\n✓ 백로그에 {enqueued}편의 OA bulk_fetch job 등록 완료")
    print(f"  heartbeat backlog_drain이 5분마다 처리 (high-cost job은 budget <80%일 때만)")
    print(f"  진행도: http://localhost:8501/backlog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
