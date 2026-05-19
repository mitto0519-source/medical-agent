"""지식 그래프 대량 채우기 — 목표 노드 수까지 PubMed 수집.

사용법:
    python scripts/bulk_fill_graph.py              # 기본 목표 10,000 노드
    python scripts/bulk_fill_graph.py --target 5000
    python scripts/bulk_fill_graph.py --dry-run    # 쿼리 수만 확인

작동 원리:
  1. 광범위한 한국 공중보건 PubMed 쿼리 (~200개)를 순회
  2. 쿼리당 최대 100편씩 수집, 이미 수집된 PMID는 스킵
  3. 각 논문에 대해 온톨로지 개념 추출 → 그래프에 노드/엣지 추가
  4. 목표 노드 수 도달 시 자동 종료
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.trend_learner import _search_pmids, _fetch_papers, _load_state, _save_state
from src.knowledge.medical_graph import get_graph
from src.knowledge.medical_ontology import get_ontology
from src.config.logging_config import get_logger

_log = get_logger("bulk_fill")

# ── 광범위 쿼리 목록 (한국 공중보건 전 영역) ───────────────────────────────
BULK_QUERIES = [
    # ── KYRBS 핵심 ──
    '"KYRBS"[Title/Abstract]',
    '"Korea Youth Risk Behavior Survey"[Title/Abstract]',
    '"청소년건강행태조사"[Title/Abstract]',
    '"KYRBS" AND sleep[Title/Abstract]',
    '"KYRBS" AND depression[Title/Abstract]',
    '"KYRBS" AND obesity[Title/Abstract]',
    '"KYRBS" AND smoking[Title/Abstract]',
    '"KYRBS" AND alcohol[Title/Abstract]',
    '"KYRBS" AND physical activity[Title/Abstract]',
    '"KYRBS" AND mental health[Title/Abstract]',
    '"KYRBS" AND screen time[Title/Abstract]',
    '"KYRBS" AND suicidal[Title/Abstract]',
    '"KYRBS" AND stress[Title/Abstract]',
    '"KYRBS" AND diet[Title/Abstract]',
    '"KYRBS" AND sedentary[Title/Abstract]',
    '"KYRBS" AND BMI[Title/Abstract]',
    '"KYRBS" AND breakfast[Title/Abstract]',
    '"KYRBS" AND socioeconomic[Title/Abstract]',
    '"KYRBS" AND gender[Title/Abstract]',
    '"KYRBS" AND COVID[Title/Abstract]',
    '"KYRBS" AND hygiene[Title/Abstract]',
    '"KYRBS" AND sexual health[Title/Abstract]',
    '"KYRBS" AND e-cigarette[Title/Abstract]',
    '"KYRBS" AND vaping[Title/Abstract]',
    '"KYRBS" AND energy drink[Title/Abstract]',
    '"KYRBS" AND internet addiction[Title/Abstract]',
    '"KYRBS" AND bullying[Title/Abstract]',
    '"KYRBS" AND violence[Title/Abstract]',
    '"KYRBS" AND academic performance[Title/Abstract]',
    '"KYRBS" AND overweight[Title/Abstract]',

    # ── KNHANES 핵심 ──
    '"KNHANES"[Title/Abstract]',
    '"Korea National Health and Nutrition Examination Survey"[Title/Abstract]',
    '"국민건강영양조사"[Title/Abstract]',
    '"KNHANES" AND diabetes[Title/Abstract]',
    '"KNHANES" AND hypertension[Title/Abstract]',
    '"KNHANES" AND obesity[Title/Abstract]',
    '"KNHANES" AND metabolic syndrome[Title/Abstract]',
    '"KNHANES" AND cardiovascular[Title/Abstract]',
    '"KNHANES" AND diet[Title/Abstract]',
    '"KNHANES" AND physical activity[Title/Abstract]',
    '"KNHANES" AND depression[Title/Abstract]',
    '"KNHANES" AND sleep[Title/Abstract]',
    '"KNHANES" AND cancer[Title/Abstract]',
    '"KNHANES" AND smoking[Title/Abstract]',
    '"KNHANES" AND alcohol[Title/Abstract]',
    '"KNHANES" AND kidney[Title/Abstract]',
    '"KNHANES" AND liver[Title/Abstract]',
    '"KNHANES" AND thyroid[Title/Abstract]',
    '"KNHANES" AND osteoporosis[Title/Abstract]',
    '"KNHANES" AND sarcopenia[Title/Abstract]',
    '"KNHANES" AND anemia[Title/Abstract]',
    '"KNHANES" AND dental[Title/Abstract]',
    '"KNHANES" AND vision[Title/Abstract]',
    '"KNHANES" AND hearing[Title/Abstract]',
    '"KNHANES" AND cognitive[Title/Abstract]',
    '"KNHANES" AND dementia[Title/Abstract]',
    '"KNHANES" AND arthritis[Title/Abstract]',
    '"KNHANES" AND asthma[Title/Abstract]',
    '"KNHANES" AND COPD[Title/Abstract]',
    '"KNHANES" AND dyslipidemia[Title/Abstract]',
    '"KNHANES" AND gout[Title/Abstract]',
    '"KNHANES" AND fatty liver[Title/Abstract]',
    '"KNHANES" AND inflammation[Title/Abstract]',
    '"KNHANES" AND socioeconomic[Title/Abstract]',
    '"KNHANES" AND elderly[Title/Abstract]',
    '"KNHANES" AND women[Title/Abstract]',
    '"KNHANES" AND men[Title/Abstract]',
    '"KNHANES" AND vitamin D[Title/Abstract]',
    '"KNHANES" AND iron deficiency[Title/Abstract]',
    '"KNHANES" AND nutrient[Title/Abstract]',
    '"KNHANES" AND food intake[Title/Abstract]',
    '"KNHANES" AND waist circumference[Title/Abstract]',
    '"KNHANES" AND grip strength[Title/Abstract]',

    # ── 한국 청소년 건강 (광의) ──
    'Korean adolescent obesity[Title/Abstract]',
    'Korean adolescent depression[Title/Abstract]',
    'Korean adolescent sleep[Title/Abstract]',
    'Korean adolescent smoking[Title/Abstract]',
    'Korean adolescent alcohol[Title/Abstract]',
    'Korean adolescent physical activity[Title/Abstract]',
    'Korean adolescent mental health[Title/Abstract]',
    'Korean adolescent suicidal ideation[Title/Abstract]',
    'Korean adolescent stress[Title/Abstract]',
    'Korean adolescent screen time[Title/Abstract]',
    'Korean adolescent smartphone[Title/Abstract]',
    'Korean adolescent eating disorder[Title/Abstract]',
    'Korean adolescent asthma[Title/Abstract]',
    'Korean adolescent diabetes[Title/Abstract]',
    'Korean adolescent hypertension[Title/Abstract]',
    'Korean adolescent sexual behavior[Title/Abstract]',
    'Korean adolescent drug use[Title/Abstract]',
    'Korean high school health[Title/Abstract]',
    'Korean middle school health[Title/Abstract]',
    'Korean student academic stress[Title/Abstract]',
    'Korean youth well-being[Title/Abstract]',
    'Korean youth sedentary behavior[Title/Abstract]',
    'Korean youth vitamin D[Title/Abstract]',
    'Korean youth breakfast skipping[Title/Abstract]',
    'Korean youth soft drink[Title/Abstract]',
    'Korean youth fast food[Title/Abstract]',

    # ── 한국 성인 만성질환 ──
    'Korean adults type 2 diabetes[Title/Abstract]',
    'Korean adults hypertension[Title/Abstract]',
    'Korean adults metabolic syndrome[Title/Abstract]',
    'Korean adults cardiovascular disease[Title/Abstract]',
    'Korean adults obesity[Title/Abstract]',
    'Korean adults dyslipidemia[Title/Abstract]',
    'Korean adults chronic kidney disease[Title/Abstract]',
    'Korean adults non-alcoholic fatty liver[Title/Abstract]',
    'Korean adults cancer risk[Title/Abstract]',
    'Korean adults colorectal cancer[Title/Abstract]',
    'Korean adults gastric cancer[Title/Abstract]',
    'Korean adults lung cancer[Title/Abstract]',
    'Korean adults breast cancer[Title/Abstract]',
    'Korean adults cervical cancer[Title/Abstract]',
    'Korean adults thyroid cancer[Title/Abstract]',
    'Korean adults liver cancer[Title/Abstract]',
    'Korean adults depression[Title/Abstract]',
    'Korean adults anxiety[Title/Abstract]',
    'Korean adults sleep disorder[Title/Abstract]',
    'Korean adults insomnia[Title/Abstract]',
    'Korean adults dementia[Title/Abstract]',
    'Korean adults Alzheimer[Title/Abstract]',
    'Korean adults stroke[Title/Abstract]',
    'Korean adults osteoporosis[Title/Abstract]',
    'Korean adults sarcopenia[Title/Abstract]',
    'Korean adults gout[Title/Abstract]',
    'Korean adults rheumatoid arthritis[Title/Abstract]',
    'Korean adults COPD[Title/Abstract]',
    'Korean adults asthma[Title/Abstract]',
    'Korean adults atopic dermatitis[Title/Abstract]',

    # ── 한국 노인 건강 ──
    'Korean elderly health[Title/Abstract]',
    'Korean elderly falls[Title/Abstract]',
    'Korean elderly frailty[Title/Abstract]',
    'Korean elderly cognitive decline[Title/Abstract]',
    'Korean elderly physical function[Title/Abstract]',
    'Korean elderly nutrition[Title/Abstract]',
    'Korean elderly depression[Title/Abstract]',
    'Korean elderly diabetes[Title/Abstract]',
    'Korean elderly cardiovascular[Title/Abstract]',
    'Korean elderly sarcopenia[Title/Abstract]',
    'Korean elderly social isolation[Title/Abstract]',
    'Korean elderly medication[Title/Abstract]',
    'Korean elderly polypharmacy[Title/Abstract]',

    # ── 한국 여성/산모 건강 ──
    'Korean women breast cancer[Title/Abstract]',
    'Korean women cervical cancer[Title/Abstract]',
    'Korean women menopause[Title/Abstract]',
    'Korean women osteoporosis[Title/Abstract]',
    'Korean women depression[Title/Abstract]',
    'Korean women obesity[Title/Abstract]',
    'Korean pregnant women[Title/Abstract]',
    'Korean maternal health[Title/Abstract]',
    'Korean gestational diabetes[Title/Abstract]',
    'Korean preterm birth[Title/Abstract]',
    'Korean low birth weight[Title/Abstract]',

    # ── 영양/식이 ──
    'Korean dietary pattern[Title/Abstract]',
    'Korean food intake[Title/Abstract]',
    'Korean sodium intake[Title/Abstract]',
    'Korean sugar intake[Title/Abstract]',
    'Korean fat intake[Title/Abstract]',
    'Korean vegetable intake[Title/Abstract]',
    'Korean fruit intake[Title/Abstract]',
    'Korean red meat consumption[Title/Abstract]',
    'Korean processed food[Title/Abstract]',
    'Korean traditional diet health[Title/Abstract]',
    'Korean fermented food[Title/Abstract]',
    'Korean kimchi health[Title/Abstract]',
    'Korean Mediterranean diet[Title/Abstract]',

    # ── 신체활동/좌식행동 ──
    'Korean physical activity guidelines[Title/Abstract]',
    'Korean sedentary behavior[Title/Abstract]',
    'Korean exercise intervention[Title/Abstract]',
    'Korean walking[Title/Abstract]',
    'Korean aerobic exercise[Title/Abstract]',
    'Korean resistance training[Title/Abstract]',
    'Korean sports participation[Title/Abstract]',

    # ── 흡연/음주/약물 ──
    'Korean smoking prevalence[Title/Abstract]',
    'Korean tobacco use[Title/Abstract]',
    'Korean e-cigarette[Title/Abstract]',
    'Korean electronic cigarette[Title/Abstract]',
    'Korean vaping[Title/Abstract]',
    'Korean second-hand smoke[Title/Abstract]',
    'Korean smoking cessation[Title/Abstract]',
    'Korean alcohol consumption[Title/Abstract]',
    'Korean heavy drinking[Title/Abstract]',
    'Korean binge drinking[Title/Abstract]',
    'Korean alcohol use disorder[Title/Abstract]',

    # ── 정신건강 ──
    'Korean mental health service[Title/Abstract]',
    'Korean suicide rate[Title/Abstract]',
    'Korean suicide prevention[Title/Abstract]',
    'Korean depression treatment[Title/Abstract]',
    'Korean anxiety disorder[Title/Abstract]',
    'Korean PTSD[Title/Abstract]',
    'Korean schizophrenia[Title/Abstract]',
    'Korean bipolar disorder[Title/Abstract]',
    'Korean attention deficit[Title/Abstract]',
    'Korean ADHD[Title/Abstract]',
    'Korean autism[Title/Abstract]',
    'Korean gambling addiction[Title/Abstract]',
    'Korean internet addiction[Title/Abstract]',
    'Korean smartphone addiction[Title/Abstract]',

    # ── 환경/사회결정인자 ──
    'Korean air pollution health[Title/Abstract]',
    'Korean fine particulate matter[Title/Abstract]',
    'Korean PM2.5 health[Title/Abstract]',
    'Korean socioeconomic health inequality[Title/Abstract]',
    'Korean income health[Title/Abstract]',
    'Korean education health[Title/Abstract]',
    'Korean rural urban health[Title/Abstract]',
    'Korean occupational health[Title/Abstract]',
    'Korean work-related disease[Title/Abstract]',
    'Korean noise exposure health[Title/Abstract]',
    'Korean heat stroke Korea[Title/Abstract]',
    'Korean climate change health[Title/Abstract]',

    # ── 의료이용/스크리닝 ──
    'Korean cancer screening[Title/Abstract]',
    'Korean health screening[Title/Abstract]',
    'Korean healthcare utilization[Title/Abstract]',
    'Korean health checkup[Title/Abstract]',
    'Korean vaccination coverage[Title/Abstract]',
    'Korean unmet medical needs[Title/Abstract]',
    'Korean preventive care[Title/Abstract]',

    # ── 방법론 ──
    'complex survey weighted analysis Korea[Title/Abstract]',
    'propensity score matching Korean health[Title/Abstract]',
    'Joinpoint regression trend Korea[Title/Abstract]',
    'interrupted time series Korea health[Title/Abstract]',
    'mediation analysis Korean population[Title/Abstract]',
    'multilevel analysis Korean health[Title/Abstract]',
    'structural equation model Korean health[Title/Abstract]',
    'machine learning Korean disease prediction[Title/Abstract]',
    'deep learning Korean clinical[Title/Abstract]',

    # ── COVID-19 관련 ──
    'COVID-19 Korea health behavior[Title/Abstract]',
    'pandemic Korean adolescent mental health[Title/Abstract]',
    'COVID-19 Korean obesity[Title/Abstract]',
    'COVID-19 Korean physical activity[Title/Abstract]',
    'COVID-19 Korean sleep[Title/Abstract]',
    'COVID-19 Korean screen time[Title/Abstract]',
    'COVID-19 Korean depression[Title/Abstract]',
    'post-COVID Korean health[Title/Abstract]',
    'long COVID Korea[Title/Abstract]',

    # ── 2차 배치: 한국 임상/중재 연구 ──
    'Korean randomized controlled trial[Title/Abstract]',
    'Korean clinical trial health intervention[Title/Abstract]',
    'Korean cohort study[Title/Abstract]',
    'Korean prospective study chronic disease[Title/Abstract]',
    'Korean longitudinal study health[Title/Abstract]',
    'Korean case-control study[Title/Abstract]',
    'Korean meta-analysis health[Title/Abstract]',
    'Korean systematic review public health[Title/Abstract]',
    'Korean population-based study[Title/Abstract]',
    'Korea Health Panel Survey[Title/Abstract]',
    'Korean Community Health Survey[Title/Abstract]',
    'Korean National Cancer Registry[Title/Abstract]',
    'Korean National Health Insurance[Title/Abstract]',
    'Korean Health Insurance Review[Title/Abstract]',
    'Korean medical records analysis[Title/Abstract]',

    # ── 한국 특이 질환/상황 ──
    'Korean stomach cancer epidemiology[Title/Abstract]',
    'Korean Helicobacter pylori[Title/Abstract]',
    'Korean hepatitis B[Title/Abstract]',
    'Korean hepatitis C[Title/Abstract]',
    'Korean tuberculosis incidence[Title/Abstract]',
    'Korean influenza[Title/Abstract]',
    'Korean hand foot mouth disease[Title/Abstract]',
    'Korean scrub typhus[Title/Abstract]',
    'Korean hantavirus[Title/Abstract]',
    'Korean dengue fever[Title/Abstract]',
    'Korean COVID mortality[Title/Abstract]',
    'Korean pandemic vaccination[Title/Abstract]',

    # ── 한국 의약품/치료 ──
    'Korean antihypertensive treatment outcome[Title/Abstract]',
    'Korean diabetes medication adherence[Title/Abstract]',
    'Korean statin therapy outcome[Title/Abstract]',
    'Korean antidepressant prescription[Title/Abstract]',
    'Korean cancer chemotherapy outcome[Title/Abstract]',
    'Korean traditional medicine[Title/Abstract]',
    'Korean herbal medicine adverse effect[Title/Abstract]',
    'Korean acupuncture clinical[Title/Abstract]',

    # ── 동아시아 비교 ──
    'East Asian adolescent mental health comparison[Title/Abstract]',
    'East Asian obesity trend[Title/Abstract]',
    'Asian American Korean health[Title/Abstract]',
    'Japan Korea Taiwan health comparison[Title/Abstract]',
    'Asian metabolic syndrome prevalence[Title/Abstract]',
    'Asian cardiovascular risk factor[Title/Abstract]',
    'Asian diabetes prevalence trend[Title/Abstract]',
    'Asian colorectal cancer incidence[Title/Abstract]',
    'Asian sleep duration health[Title/Abstract]',
    'Asian dietary pattern disease[Title/Abstract]',

    # ── 특정 바이오마커/검사 ──
    'Korean serum vitamin D deficiency[Title/Abstract]',
    'Korean HbA1c control[Title/Abstract]',
    'Korean blood pressure control[Title/Abstract]',
    'Korean LDL cholesterol[Title/Abstract]',
    'Korean CRP inflammation marker[Title/Abstract]',
    'Korean bone mineral density[Title/Abstract]',
    'Korean lean body mass[Title/Abstract]',
    'Korean body fat percentage[Title/Abstract]',
    'Korean waist-hip ratio health[Title/Abstract]',
    'Korean appendicular skeletal muscle[Title/Abstract]',

    # ── 한국 소아/신생아 ──
    'Korean infant feeding breastfeeding[Title/Abstract]',
    'Korean child growth development[Title/Abstract]',
    'Korean childhood obesity prevention[Title/Abstract]',
    'Korean school health program[Title/Abstract]',
    'Korean pediatric asthma[Title/Abstract]',
    'Korean pediatric allergy[Title/Abstract]',
    'Korean child dental caries[Title/Abstract]',
    'Korean neonatal outcome[Title/Abstract]',
    'Korean congenital anomaly[Title/Abstract]',
    'Korean birth cohort study[Title/Abstract]',

    # ── 한국 직업/사회경제 세부 ──
    'Korean shift work health[Title/Abstract]',
    'Korean night shift worker[Title/Abstract]',
    'Korean job stress burnout[Title/Abstract]',
    'Korean farmer health[Title/Abstract]',
    'Korean migrant worker health[Title/Abstract]',
    'Korean income inequality health outcome[Title/Abstract]',
    'Korean low-income health[Title/Abstract]',
    'Korean disability health[Title/Abstract]',
    'Korean healthcare cost expenditure[Title/Abstract]',
    'Korean health behavior socioeconomic[Title/Abstract]',

    # ── 한국 환경/생태 세부 ──
    'Korean radon exposure cancer[Title/Abstract]',
    'Korean heavy metal exposure[Title/Abstract]',
    'Korean lead mercury cadmium Korea[Title/Abstract]',
    'Korean water fluoride dental[Title/Abstract]',
    'Korean endocrine disruptor[Title/Abstract]',
    'Korean pesticide exposure health[Title/Abstract]',
    'Korean indoor air quality[Title/Abstract]',
    'Korean green space health[Title/Abstract]',
    'Korean urban heat island health[Title/Abstract]',
    'Korean noise pollution sleep[Title/Abstract]',

    # ── 한국 정신건강 세부 ──
    'Korean post-traumatic stress disorder[Title/Abstract]',
    'Korean panic disorder[Title/Abstract]',
    'Korean social phobia Korea[Title/Abstract]',
    'Korean obsessive compulsive[Title/Abstract]',
    'Korean eating disorder[Title/Abstract]',
    'Korean anorexia nervosa Korea[Title/Abstract]',
    'Korean bulimia nervosa Korea[Title/Abstract]',
    'Korean anger management Korea[Title/Abstract]',
    'Korean loneliness social support[Title/Abstract]',
    'Korean quality of life mental[Title/Abstract]',

    # ── 한국 노인 세부 ──
    'Korean older adults fall prevention[Title/Abstract]',
    'Korean older adults balance exercise[Title/Abstract]',
    'Korean older adults polypharmacy[Title/Abstract]',
    'Korean older adults hospital readmission[Title/Abstract]',
    'Korean older adults end of life[Title/Abstract]',
    'Korean nursing home quality[Title/Abstract]',
    'Korean dementia caregiver[Title/Abstract]',
    'Korean successful aging[Title/Abstract]',
    'Korean older adults functional independence[Title/Abstract]',
    'Korean older adults social participation[Title/Abstract]',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=10_000, help="목표 노드 수")
    parser.add_argument("--max-per-query", type=int, default=100, help="쿼리당 최대 수집 편수")
    parser.add_argument("--days", type=int, default=3650, help="최근 N일 이내 논문")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"총 쿼리 수: {len(BULK_QUERIES)}개")
        print(f"최대 수집 가능: ~{len(BULK_QUERIES) * args.max_per_query:,}편 (중복 전)")
        return

    ontology = get_ontology()
    graph    = get_graph()
    state    = _load_state()

    ingested_set = set(state.get("ingested_pmids", []))

    def current_nodes() -> int:
        return graph.stats().get("total_nodes", 0)

    start_nodes = current_nodes()
    print(f"\n=== 지식 그래프 대량 채우기 ===")
    print(f"시작 노드: {start_nodes:,}  →  목표: {args.target:,}")
    print(f"쿼리: {len(BULK_QUERIES)}개 / 쿼리당 최대: {args.max_per_query}편 / 기간: {args.days}일\n")

    total_new    = 0
    total_skip   = 0
    query_done   = 0

    for query in BULK_QUERIES:
        nodes_now = current_nodes()
        if nodes_now >= args.target:
            print(f"\n목표 달성! {nodes_now:,} 노드")
            break

        pmids = _search_pmids(query, days=args.days, max_results=args.max_per_query)
        new_pmids = [p for p in pmids if p not in ingested_set]
        total_skip += len(pmids) - len(new_pmids)
        query_done += 1

        if not new_pmids:
            continue

        papers = _fetch_papers(new_pmids)
        for paper in papers:
            text = f"{paper.get('title','')} {paper.get('abstract','')}"
            concepts = ontology.extract_concepts(text)
            datasets = []
            tl = text.lower()
            if any(k in tl for k in ["kyrbs","korea youth risk behavior","청소년건강행태"]):
                datasets.append("KYRBS")
            if any(k in tl for k in ["knhanes","korea national health and nutrition","국민건강영양조사"]):
                datasets.append("KNHANES")
            graph.ingest_paper({
                **paper,
                "datasets": datasets,
                "concepts": [
                    {"concept_id": c["concept_id"], "label": c["label"],
                     "domain_label": c["domain_label"], "weight": 1.0}
                    for c in concepts
                ],
            })
            ingested_set.add(paper["pmid"])
            total_new += 1

        graph.save()
        nodes_now = current_nodes()
        print(f"[{query_done:3d}/{len(BULK_QUERIES)}] {nodes_now:,} 노드 | "
              f"+{total_new} 신규 | 스킵 {total_skip} | {query[:55]}", flush=True)

        time.sleep(0.4)

    # 최종 상태 저장
    state["ingested_pmids"] = list(ingested_set)[-5000:]
    _save_state(state)

    final_nodes = current_nodes()
    print(f"\n=== 완료 ===")
    print(f"노드: {start_nodes:,} → {final_nodes:,} (+{final_nodes - start_nodes:,})")
    print(f"신규 논문: {total_new}편  스킵: {total_skip}편")


if __name__ == "__main__":
    main()
