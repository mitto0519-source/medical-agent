"""
KYRBS 2025 DatasetLibrary 구축 스크립트
=========================================
청소년건강행태조사 (Korea Youth Risk Behavior Survey)
제21차 (2025년) — 14개 영역, 88개 문항, 약 150개 변수

출처: 질병관리청 원시자료 이용지침서 (2025)
"""

import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from dotenv import load_dotenv
load_dotenv()

from src.library.dataset_library import DatasetLibrary

lib = DatasetLibrary("data/libraries")

# ── 데이터셋 기본 등록 ───────────────────────────────────────────────────
lib.add_dataset(
    name="KYRBS",
    full_name="Korea Youth Risk Behavior Survey (청소년건강행태조사)",
    description=(
        "질병관리청이 2005년부터 매년 실시하는 전국 규모 학교기반 건강행태 조사. "
        "전국 800개 중‧고등학교 재학생 약 6만 명 대상, 익명 자기기입식 온라인 설문. "
        "복합표본 설계(층화집락추출): 층=시도×학교급×학교유형, 집락=학교/학급. "
        "2025년(제21차): 14개 영역 88개 문항, 약 150개 변수. "
        "가중치 변수(wt) 필수 적용 — svydesign(id=~class_id, strata=~strata_id, weights=~wt)."
    ),
)

print("KYRBS 데이터셋 등록 완료")

# ─────────────────────────────────────────────────────────────────────────
# 1. 인구사회학적 변수 (건강형평성 영역, 13문항)
# ─────────────────────────────────────────────────────────────────────────
demo_vars = [
    {
        "name": "sex",
        "label": "성별",
        "type": "categorical",
        "unit": "",
        "categories": {"1": "남자", "2": "여자"},
        "processing": "그대로 사용",
        "missing_strategy": "제외",
        "notes": "모든 분석의 기본 층화변수",
    },
    {
        "name": "grade",
        "label": "학년",
        "type": "categorical",
        "unit": "",
        "categories": {
            "1": "중1", "2": "중2", "3": "중3",
            "4": "고1", "5": "고2", "6": "고3",
        },
        "processing": "중학생(1-3)/고등학생(4-6)으로 이분화 가능",
        "missing_strategy": "제외",
        "notes": "school_type 변수와 함께 사용",
    },
    {
        "name": "school_type",
        "label": "학교급",
        "type": "categorical",
        "unit": "",
        "categories": {"1": "중학교", "2": "고등학교"},
        "processing": "그대로 사용",
        "missing_strategy": "제외",
        "notes": "grade에서 파생 가능: school_type = ifelse(grade<=3,1,2)",
    },
    {
        "name": "region",
        "label": "지역 규모",
        "type": "categorical",
        "unit": "",
        "categories": {"1": "대도시", "2": "중소도시", "3": "군지역"},
        "processing": "그대로 사용",
        "missing_strategy": "제외",
        "notes": "층화변수로 사용됨",
    },
    {
        "name": "family_type",
        "label": "가족 구성",
        "type": "categorical",
        "unit": "",
        "categories": {
            "1": "양친가족", "2": "편부가족", "3": "편모가족",
            "4": "조부모가족", "5": "기타",
        },
        "processing": "양친가족(1) vs. 기타(2+)로 이분화 가능",
        "missing_strategy": "결측 범주로 처리",
        "notes": "2025년 친부모/양부모 동거 여부 항목 포함",
    },
    {
        "name": "father_edu",
        "label": "아버지 학력",
        "type": "ordinal",
        "unit": "",
        "categories": {
            "1": "중학교 졸업 이하", "2": "고등학교 졸업",
            "3": "대학교 졸업 이상", "4": "모름",
        },
        "processing": "모름(4)은 결측 처리 또는 별도 범주",
        "missing_strategy": "결측 범주로 처리",
        "notes": "사회경제적 지위 대리 지표",
    },
    {
        "name": "mother_edu",
        "label": "어머니 학력",
        "type": "ordinal",
        "unit": "",
        "categories": {
            "1": "중학교 졸업 이하", "2": "고등학교 졸업",
            "3": "대학교 졸업 이상", "4": "모름",
        },
        "processing": "모름(4)은 결측 처리",
        "missing_strategy": "결측 범주로 처리",
        "notes": "부모학력 중 높은 쪽을 대표값으로 사용하는 경우 多",
    },
    {
        "name": "family_econ",
        "label": "주관적 경제적 상태",
        "type": "ordinal",
        "unit": "",
        "categories": {
            "1": "상", "2": "중상", "3": "중", "4": "중하", "5": "하",
        },
        "processing": "상/중상(1-2) vs. 중(3) vs. 중하/하(4-5) 로 3분위 처리 多",
        "missing_strategy": "결측 범주로 처리",
        "notes": "가장 많이 쓰이는 SES 대리변수",
    },
    {
        "name": "academic_perf",
        "label": "주관적 학업성적",
        "type": "ordinal",
        "unit": "",
        "categories": {
            "1": "상", "2": "중상", "3": "중", "4": "중하", "5": "하",
        },
        "processing": "5점 척도 그대로 또는 3분위 처리",
        "missing_strategy": "결측 범주로 처리",
        "notes": "학업 스트레스 분석 시 통제 변수",
    },
    {
        "name": "residence_type",
        "label": "현재 거주 형태",
        "type": "categorical",
        "unit": "",
        "categories": {
            "1": "가족과 함께", "2": "친척 집",
            "3": "하숙/자취/기숙사", "4": "보호시설",
        },
        "processing": "가족동거(1) vs. 비가족(2-4) 이분화",
        "missing_strategy": "결측 범주",
        "notes": "주거환경이 건강행태에 미치는 영향 분석",
    },
    {
        "name": "parent_nationality",
        "label": "부모 한국 국적 여부",
        "type": "categorical",
        "unit": "",
        "categories": {"1": "모두 한국", "2": "한 명 외국", "3": "모두 외국"},
        "processing": "다문화 여부(1 vs. 2+)로 이분화",
        "missing_strategy": "결측 범주",
        "notes": "다문화 청소년 건강불평등 연구",
    },
    {
        "name": "birth_year",
        "label": "출생연도",
        "type": "continuous",
        "unit": "년",
        "categories": {},
        "processing": "나이 계산: 2025 - birth_year",
        "missing_strategy": "제외",
        "notes": "grade와 함께 연령 파악",
    },
]

for v in demo_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"], unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy=v.get("missing_strategy","제외"),
        notes=v.get("notes",""),
    )

print(f"  → 인구사회학적 변수 {len(demo_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 2. 흡연 (15문항)
# ─────────────────────────────────────────────────────────────────────────
smoking_vars = [
    {
        "name": "cig_lifetime",
        "label": "평생 일반담배(궐련) 흡연 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "흡연 경험률 지표",
    },
    {
        "name": "cig_current",
        "label": "현재 일반담배(궐련) 흡연 여부 (최근 30일)",
        "type": "binary",
        "categories": {"1": "예(1일 이상)", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "현재흡연율 핵심 지표",
    },
    {
        "name": "cig_amount",
        "label": "월간 일반담배(궐련) 흡연량",
        "type": "categorical",
        "categories": {
            "1": "주 1일 미만", "2": "주 1-2일",
            "3": "주 3-4일", "4": "주 5-6일", "5": "매일",
        },
        "processing": "현재흡연자만 해당; 매일흡연(5) vs. 가끔흡연(1-4)",
        "notes": "흡연 빈도 및 양 지표",
    },
    {
        "name": "cig_start_age",
        "label": "처음 일반담배(궐련) 흡연 경험 연령",
        "type": "continuous",
        "unit": "세",
        "categories": {},
        "processing": "평생흡연 경험자만 해당",
        "notes": "흡연 시작 연령: 조기 흡연 위험 분석",
    },
    {
        "name": "ecig_lifetime",
        "label": "평생 액상형 전자담배 사용 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "전자담배 사용 경험률",
    },
    {
        "name": "ecig_current",
        "label": "현재 액상형 전자담배 사용 여부 (최근 30일)",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "액상형 전자담배 현재 사용률",
    },
    {
        "name": "ecig_start_period",
        "label": "처음 액상형 전자담배 사용 시기",
        "type": "categorical",
        "categories": {
            "1": "초등학교 이전", "2": "초등학교", "3": "중학교", "4": "고등학교",
        },
        "processing": "사용 경험자만 해당",
        "notes": "2025년 신규/수정 항목 (굵게 표시)",
    },
    {
        "name": "iqos_lifetime",
        "label": "평생 궐련형 전자담배(가열담배) 사용 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "IQOS/아이코스 등 가열담배",
    },
    {
        "name": "iqos_current",
        "label": "현재 궐련형 전자담배 사용 여부 (최근 30일)",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "현재 궐련형 전자담배 사용률",
    },
    {
        "name": "iqos_amount",
        "label": "월간 궐련형 전자담배 사용량",
        "type": "categorical",
        "categories": {
            "1": "주 1일 미만", "2": "주 1-2일",
            "3": "주 3-4일", "4": "주 5-6일", "5": "매일",
        },
        "processing": "현재 사용자만",
        "notes": "가열담배 사용 빈도",
    },
    {
        "name": "tobacco_purchase",
        "label": "담배 구매 용이성",
        "type": "categorical",
        "categories": {
            "1": "매우 쉽다", "2": "쉽다", "3": "어렵다", "4": "매우 어렵다",
        },
        "processing": "쉽다(1-2) vs. 어렵다(3-4) 이분화",
        "notes": "담배 접근성 정책 관련 지표",
    },
    {
        "name": "quit_attempt",
        "label": "금연 시도 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "현재흡연자만 해당",
        "notes": "금연 의도 지표",
    },
    {
        "name": "secondhand_home",
        "label": "가정 실내 간접흡연 (최근 7일)",
        "type": "categorical",
        "categories": {
            "0": "없음", "1": "1-2일", "2": "3-4일", "3": "5-7일",
        },
        "processing": "있음(1-3) vs. 없음(0) 이분화",
        "notes": "비흡연자에서도 적용 가능한 지표",
    },
    {
        "name": "secondhand_public",
        "label": "공공장소 실내 간접흡연 (최근 7일)",
        "type": "categorical",
        "categories": {
            "0": "없음", "1": "1-2일", "2": "3-4일", "3": "5-7일",
        },
        "processing": "있음(1-3) vs. 없음(0) 이분화",
        "notes": "간접흡연 노출 지표",
    },
    {
        "name": "iqos_start_period",
        "label": "처음 궐련형 전자담배 사용 시기",
        "type": "categorical",
        "categories": {
            "1": "초등학교 이전", "2": "초등학교", "3": "중학교", "4": "고등학교",
        },
        "processing": "사용 경험자만",
        "notes": "2025년 신규/수정 항목",
    },
]

for v in smoking_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 흡연 변수 {len(smoking_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 3. 음주 (6문항)
# ─────────────────────────────────────────────────────────────────────────
alcohol_vars = [
    {
        "name": "alc_lifetime",
        "label": "평생 음주 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형",
        "notes": "음주 경험률 지표",
    },
    {
        "name": "alc_current",
        "label": "현재 음주 여부 (최근 30일 1잔 이상)",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "현재음주율 핵심 지표",
    },
    {
        "name": "alc_start_age",
        "label": "처음 음주 경험 연령",
        "type": "continuous",
        "unit": "세",
        "categories": {},
        "processing": "평생음주 경험자만",
        "notes": "조기 음주 시작 연령 분석",
    },
    {
        "name": "alc_amount",
        "label": "월간 음주량 (1회 평균 잔 수)",
        "type": "categorical",
        "categories": {
            "1": "1-2잔", "2": "3-4잔", "3": "5-6잔",
            "4": "7-9잔", "5": "10잔 이상",
        },
        "processing": "현재음주자만; 위험음주(≥5잔=3-5) 이분화",
        "notes": "1회 음주량 지표",
    },
    {
        "name": "alc_binge",
        "label": "최근 30일 만취 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "현재음주자만",
        "notes": "위험음주 지표",
    },
    {
        "name": "alc_purchase",
        "label": "주류 구매 용이성",
        "type": "categorical",
        "categories": {
            "1": "매우 쉽다", "2": "쉽다", "3": "어렵다", "4": "매우 어렵다",
        },
        "processing": "쉽다(1-2) vs. 어렵다(3-4)",
        "notes": "주류 접근성 정책 지표",
    },
]

for v in alcohol_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 음주 변수 {len(alcohol_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 4. 신체활동 (10문항)
# ─────────────────────────────────────────────────────────────────────────
pa_vars = [
    {
        "name": "pa_vigorous_days",
        "label": "고강도 신체활동 일수 (최근 7일)",
        "type": "continuous",
        "unit": "일/주",
        "categories": {},
        "processing": "0-7일; ≥3일을 충족 기준으로 사용",
        "notes": "고강도 신체활동 충족률",
    },
    {
        "name": "pa_vigorous_time",
        "label": "고강도 신체활동 1일 평균 시간",
        "type": "categorical",
        "categories": {
            "1": "20분 미만", "2": "20-39분", "3": "40-59분", "4": "1시간 이상",
        },
        "processing": "pa_vigorous_days와 함께 활동량 계산",
        "notes": "WHO 권고: 주 3일 이상 고강도 60분",
    },
    {
        "name": "pa_60min",
        "label": "하루 60분 이상 신체활동 일수 (최근 7일)",
        "type": "continuous",
        "unit": "일/주",
        "categories": {},
        "processing": "=7이면 권고량 충족; ≥5일로 느슨한 기준 사용도 있음",
        "notes": "WHO 청소년 신체활동 권고 충족률 핵심 지표",
    },
    {
        "name": "pa_muscle",
        "label": "근력강화운동 일수 (최근 7일)",
        "type": "continuous",
        "unit": "일/주",
        "categories": {},
        "processing": "≥3일을 충족 기준으로 사용",
        "notes": "근력운동 실천율",
    },
    {
        "name": "sit_weekday",
        "label": "주중 하루 앉아서 보내는 시간",
        "type": "categorical",
        "categories": {
            "1": "2시간 미만", "2": "2-4시간 미만", "3": "4-6시간 미만",
            "4": "6-8시간 미만", "5": "8시간 이상",
        },
        "processing": "좌식행동: ≥8시간(5) 과다 기준",
        "notes": "좌식행동 지표",
    },
    {
        "name": "sit_weekend",
        "label": "주말 하루 앉아서 보내는 시간",
        "type": "categorical",
        "categories": {
            "1": "2시간 미만", "2": "2-4시간 미만", "3": "4-6시간 미만",
            "4": "6-8시간 미만", "5": "8시간 이상",
        },
        "processing": "sit_weekday와 동일한 기준 적용",
        "notes": "좌식행동 지표",
    },
    {
        "name": "pe_class_freq",
        "label": "주간 체육 시간 운동 횟수",
        "type": "categorical",
        "categories": {
            "1": "0회", "2": "1회", "3": "2회", "4": "3회 이상",
        },
        "processing": "체육수업 참여도 지표",
        "notes": "학교 체육 참여",
    },
    {
        "name": "sports_team",
        "label": "스포츠 활동 팀 수",
        "type": "continuous",
        "unit": "개",
        "categories": {},
        "processing": "0개(미참여) vs. 1개 이상(참여) 이분화",
        "notes": "학교/지역 스포츠팀 참여 지표",
    },
    {
        "name": "commute_pa_days",
        "label": "등하교·하원 시 신체활동 일수 (최근 7일)",
        "type": "continuous",
        "unit": "일/주",
        "categories": {},
        "processing": "이동 중 신체활동 빈도",
        "notes": "2025년 신규/수정 항목",
    },
    {
        "name": "commute_pa_time",
        "label": "등하교·하원 시 신체활동 1일 평균 시간",
        "type": "categorical",
        "categories": {
            "1": "10분 미만", "2": "10-20분 미만",
            "3": "20-30분 미만", "4": "30분 이상",
        },
        "processing": "commute_pa_days와 함께 통근 신체활동 계산",
        "notes": "2025년 신규/수정 항목",
    },
]

for v in pa_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 신체활동 변수 {len(pa_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 5. 식생활 (10문항)
# ─────────────────────────────────────────────────────────────────────────
diet_vars = [
    {
        "name": "breakfast_skip",
        "label": "아침식사 결식 (최근 7일)",
        "type": "categorical",
        "categories": {
            "0": "0일(매일 먹음)", "1": "1일", "2": "2일",
            "3": "3일", "4": "4일", "5": "5일", "6": "6일", "7": "7일(매일 굶음)",
        },
        "processing": "주 5일 이상 결식(5-7)을 아침결식으로 정의 多",
        "notes": "아침결식률 지표",
    },
    {
        "name": "fruit_intake",
        "label": "과일 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 먹지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일 1회",
            "6": "매일 2회 이상",
        },
        "processing": "매일 섭취(5-6) vs. 미달(1-4)",
        "notes": "과일 섭취율",
    },
    {
        "name": "vegetable_intake",
        "label": "채소 섭취 빈도 (최근 7일, 김치 포함)",
        "type": "categorical",
        "categories": {
            "1": "전혀 먹지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일 1회",
            "6": "매일 2회 이상",
        },
        "processing": "매일 2회 이상(6)을 권고 충족으로 사용 多",
        "notes": "채소 섭취율",
    },
    {
        "name": "fastfood_intake",
        "label": "패스트푸드 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 먹지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "주 3회 이상(3-5)을 고빈도 섭취로 정의",
        "notes": "가공식품/패스트푸드 섭취",
    },
    {
        "name": "caffeine_intake",
        "label": "고카페인 음료 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 마시지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "섭취 있음(2-5) vs. 없음(1) 이분화",
        "notes": "에너지드링크, 커피 등 고카페인 음료",
    },
    {
        "name": "sweet_drink_intake",
        "label": "단맛 나는 음료 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 마시지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "고빈도(주 3회 이상: 3-5) 이분화",
        "notes": "가당음료 섭취 지표",
    },
    {
        "name": "water_intake",
        "label": "물 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 마시지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "매일(5) 섭취 충족률",
        "notes": "수분 섭취 충족 지표",
    },
    {
        "name": "night_snack",
        "label": "야식 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 먹지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "섭취 있음(2-5) vs. 없음(1)",
        "notes": "야식 섭취 습관",
    },
    {
        "name": "dairy_intake",
        "label": "우유 및 유제품 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 먹지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "매일(5) 섭취 충족률",
        "notes": "칼슘 섭취 대리 지표",
    },
    {
        "name": "zero_drink_intake",
        "label": "제로음료 섭취 빈도 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 마시지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "섭취 있음(2-5) vs. 없음(1)",
        "notes": "2025년 신규 항목 — 무설탕 인공감미료 음료",
    },
]

for v in diet_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 식생활 변수 {len(diet_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 6. 비만 및 체중조절 (7문항)
# ─────────────────────────────────────────────────────────────────────────
obesity_vars = [
    {
        "name": "height",
        "label": "신장",
        "type": "continuous",
        "unit": "cm",
        "categories": {},
        "processing": "자기보고 신장. 비현실적 값(< 100cm, > 220cm) 제외",
        "notes": "BMI 계산에 사용",
    },
    {
        "name": "weight",
        "label": "체중",
        "type": "continuous",
        "unit": "kg",
        "categories": {},
        "processing": "자기보고 체중. 비현실적 값(< 20kg, > 200kg) 제외",
        "notes": "BMI 계산에 사용. 측정치 아님(자기보고 오류 가능)",
    },
    {
        "name": "bmi",
        "label": "체질량지수 (파생변수)",
        "type": "continuous",
        "unit": "kg/m²",
        "categories": {},
        "processing": "bmi = weight / (height/100)^2. 소수점 1자리",
        "notes": "이용지침서에서 제공하는 파생변수. 직접 계산과 동일",
    },
    {
        "name": "bmi_category",
        "label": "BMI 분류 (연령·성별 기준, 파생변수)",
        "type": "categorical",
        "categories": {
            "1": "저체중 (5백분위 미만)",
            "2": "정상 (5-85백분위 미만)",
            "3": "과체중 (85-95백분위 미만)",
            "4": "비만 (95백분위 이상)",
        },
        "processing": "2017 소아청소년 성장도표 성별·연령별 백분위 기준 적용",
        "notes": "성인 BMI 기준(25/30) 미적용; 반드시 성장도표 기준 사용",
    },
    {
        "name": "body_image",
        "label": "주관적 체형 인식",
        "type": "categorical",
        "categories": {
            "1": "매우 마른 편", "2": "약간 마른 편", "3": "보통",
            "4": "약간 살찐 편", "5": "매우 살찐 편",
        },
        "processing": "왜곡 인식: 실제 BMI vs. 인식 체형 불일치",
        "notes": "신체이미지 왜곡 분석 (body image distortion)",
    },
    {
        "name": "weight_control",
        "label": "최근 30일 체중 조절 노력 여부",
        "type": "categorical",
        "categories": {
            "1": "감량 시도", "2": "유지 시도", "3": "증량 시도", "4": "노력 안 함",
        },
        "processing": "감량 시도(1) vs. 기타(2-4) 이분화가 일반적",
        "notes": "체중조절 행동 지표",
    },
    {
        "name": "mukbang_watch",
        "label": "먹방·쿡방 시청 횟수 (최근 7일)",
        "type": "categorical",
        "categories": {
            "1": "전혀 보지 않음", "2": "주 1-2회",
            "3": "주 3-4회", "4": "주 5-6회", "5": "매일",
        },
        "processing": "시청 있음(2-5) vs. 없음(1)",
        "notes": "2025년 신규/수정 항목 — 먹방이 식습관에 미치는 영향",
    },
]

for v in obesity_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 비만/체중조절 변수 {len(obesity_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 7. 정신건강 (5문항)
# ─────────────────────────────────────────────────────────────────────────
mental_vars = [
    {
        "name": "stress",
        "label": "주관적 스트레스 인지율",
        "type": "categorical",
        "categories": {
            "1": "대단히 많이 느낀다", "2": "많이 느낀다",
            "3": "조금 느낀다", "4": "거의 느끼지 않는다",
        },
        "processing": "스트레스 인지(1-2) vs. 비인지(3-4) 이분화",
        "notes": "주관적 스트레스 인지율 핵심 지표",
    },
    {
        "name": "depression",
        "label": "우울감 경험 (최근 12개월, 2주 이상 연속)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "우울감 경험률 핵심 지표",
    },
    {
        "name": "suicidal_ideation",
        "label": "자살 생각 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "자살 생각 경험률",
    },
    {
        "name": "suicidal_plan",
        "label": "자살 계획 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "자살 생각자만 해당",
        "notes": "자살 계획 경험률",
    },
    {
        "name": "suicidal_attempt",
        "label": "자살 시도 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "자살 시도율 핵심 지표",
    },
]

for v in mental_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 정신건강 변수 {len(mental_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 8. 수면건강 (3문항)
# ─────────────────────────────────────────────────────────────────────────
sleep_vars = [
    {
        "name": "sleep_weekday",
        "label": "주중 평균 수면 시간 (파생변수)",
        "type": "continuous",
        "unit": "시간",
        "categories": {},
        "processing": "잠든 시각, 일어난 시각으로 계산. < 6시간 수면 부족",
        "notes": "주중 수면시간. < 8시간을 청소년 수면 부족으로 정의 多",
    },
    {
        "name": "sleep_weekend",
        "label": "주말 평균 수면 시간 (파생변수)",
        "type": "continuous",
        "unit": "시간",
        "categories": {},
        "processing": "잠든 시각, 일어난 시각으로 계산",
        "notes": "주말 수면시간. 주중-주말 차이(사회적 시차) 분석 가능",
    },
    {
        "name": "sleep_sufficient",
        "label": "주관적 수면 충족도",
        "type": "categorical",
        "categories": {
            "1": "충분하다", "2": "약간 부족하다",
            "3": "매우 부족하다",
        },
        "processing": "충분(1) vs. 부족(2-3) 이분화",
        "notes": "주관적 수면의 질 지표",
    },
]

for v in sleep_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 수면건강 변수 {len(sleep_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 9. 손상 및 안전의식 (2문항)
# ─────────────────────────────────────────────────────────────────────────
safety_vars = [
    {
        "name": "seatbelt",
        "label": "안전벨트 착용 (승용차/택시 앞뒷좌석, 고속버스)",
        "type": "categorical",
        "categories": {
            "1": "항상 착용", "2": "대부분 착용",
            "3": "가끔 착용", "4": "거의 안 착용", "5": "탑승 안 함",
        },
        "processing": "항상/대부분(1-2) vs. 가끔/거의안함(3-4); 탑승안함(5) 제외",
        "notes": "안전벨트 착용률",
    },
    {
        "name": "school_injury",
        "label": "학교 손상으로 인한 병원 치료 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "학교 손상 경험률",
    },
]

for v in safety_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 손상/안전 변수 {len(safety_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 10. 구강건강 (9문항)
# ─────────────────────────────────────────────────────────────────────────
oral_vars = [
    {
        "name": "toothbrush_daily",
        "label": "하루 칫솔질 횟수",
        "type": "categorical",
        "categories": {
            "1": "0회", "2": "1회", "3": "2회", "4": "3회", "5": "4회 이상",
        },
        "processing": "하루 3회 이상(4-5) vs. 미만(1-3)",
        "notes": "구강위생 핵심 지표",
    },
    {
        "name": "toothbrush_lunch",
        "label": "학교 점심식사 후 칫솔질 실천",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "학교 구강위생 실천",
    },
    {
        "name": "sealant",
        "label": "치아홈메우기(실란트) 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "예방치과 처치 경험",
    },
    {
        "name": "toothbrush_night",
        "label": "취침 전 칫솔질 실천",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "취침 전 구강위생",
    },
    {
        "name": "dental_visit",
        "label": "치과 진료 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "치과 의료 이용",
    },
    {
        "name": "scaling",
        "label": "스케일링 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "예방치과 스케일링 이용",
    },
    {
        "name": "oral_health_perception",
        "label": "주관적 구강건강 인지",
        "type": "categorical",
        "categories": {
            "1": "매우 좋음", "2": "좋음", "3": "보통",
            "4": "나쁨", "5": "매우 나쁨",
        },
        "processing": "좋음(1-2) vs. 보통이하(3-5) 이분화",
        "notes": "자기보고 구강건강 수준",
    },
    {
        "name": "oral_symptom",
        "label": "구강증상 경험 (최근 12개월)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "치통, 잇몸 출혈 등 구강증상",
    },
    {
        "name": "oral_hygiene_product",
        "label": "구강위생용품 사용 여부",
        "type": "binary",
        "categories": {"1": "예", "2": "아니오"},
        "processing": "이분형 그대로",
        "notes": "치실, 구강세정제 등 사용",
    },
]

for v in oral_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 구강건강 변수 {len(oral_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 11. 개인위생, 성행태, 약물, 인터넷/스마트폰
# ─────────────────────────────────────────────────────────────────────────
other_vars = [
    {
        "name": "handwash",
        "label": "비누 이용 손씻기 실천 (학교/집 식사 전·화장실 후·귀가 후)",
        "type": "categorical",
        "categories": {
            "1": "항상", "2": "자주", "3": "가끔", "4": "전혀 안 함",
        },
        "processing": "항상/자주(1-2) vs. 가끔/안함(3-4)",
        "notes": "감염병 예방 핵심 지표",
    },
    {
        "name": "sex_experience",
        "label": "성관계 경험",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "성행태 분석 주의: 민감 변수",
    },
    {
        "name": "contraception",
        "label": "피임 경험 (성관계 경험자 중)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "성관계 경험자만 해당",
        "notes": "성행태 분석",
    },
    {
        "name": "drug_use",
        "label": "습관적 및 의도적 약물 사용 경험 (평생)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "이분형 그대로",
        "notes": "마약류, 흡입제, 수면제 등 불법/오남용",
    },
    {
        "name": "smartphone_weekday",
        "label": "주중 스마트폰 사용 시간 (하루 평균)",
        "type": "categorical",
        "categories": {
            "1": "사용 안 함", "2": "30분 미만", "3": "30분-1시간 미만",
            "4": "1-2시간 미만", "5": "2-3시간 미만",
            "6": "3-4시간 미만", "7": "4시간 이상",
        },
        "processing": "과사용(4시간 이상=7) vs. 적정 이분화",
        "notes": "스마트폰 과의존 지표",
    },
    {
        "name": "smartphone_weekend",
        "label": "주말 스마트폰 사용 시간 (하루 평균)",
        "type": "categorical",
        "categories": {
            "1": "사용 안 함", "2": "30분 미만", "3": "30분-1시간 미만",
            "4": "1-2시간 미만", "5": "2-3시간 미만",
            "6": "3-4시간 미만", "7": "4시간 이상",
        },
        "processing": "과사용(4시간 이상=7) vs. 적정 이분화",
        "notes": "주말 스마트폰 사용",
    },
    {
        "name": "health_perception",
        "label": "주관적 건강 인지",
        "type": "categorical",
        "categories": {
            "1": "매우 좋음", "2": "좋음", "3": "보통",
            "4": "나쁨", "5": "매우 나쁨",
        },
        "processing": "좋음(1-2) vs. 보통이하(3-5) 이분화",
        "notes": "전반적 건강 상태 지표 (기타 영역)",
    },
    {
        "name": "prevention_edu",
        "label": "학교 내 예방교육 경험 (흡연/음주/식생활/성/자살 등)",
        "type": "binary",
        "categories": {"1": "있음", "2": "없음"},
        "processing": "영역별로 별도 변수 존재 가능",
        "notes": "학교 보건교육 이행 지표",
    },
]

for v in other_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="결측 제외",
        notes=v.get("notes",""),
    )

print(f"  → 개인위생/성행태/약물/스마트폰 변수 {len(other_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 12. 가중치 및 층화 변수 (필수)
# ─────────────────────────────────────────────────────────────────────────
weight_vars = [
    {
        "name": "wt",
        "label": "표본 가중치",
        "type": "continuous",
        "unit": "",
        "categories": {},
        "processing": "모든 분석에 필수 적용. svydesign weights=~wt",
        "notes": "복합표본 분석 필수 — 미적용 시 결과 편향",
    },
    {
        "name": "strata_id",
        "label": "층 변수 (시도×학교급×학교유형)",
        "type": "categorical",
        "categories": {},
        "processing": "svydesign strata=~strata_id",
        "notes": "복합표본 설계 반영",
    },
    {
        "name": "cluster_id",
        "label": "집락 변수 (학교·학급 ID)",
        "type": "categorical",
        "categories": {},
        "processing": "svydesign id=~cluster_id",
        "notes": "집락 내 상관 보정",
    },
]

for v in weight_vars:
    lib.add_variable("KYRBS", v["name"],
        label=v["label"], type=v["type"],
        unit=v.get("unit",""),
        cutoffs=v.get("categories",{}),
        processing=v.get("processing",""),
        missing_strategy="제외 불가 (필수 변수)",
        notes=v.get("notes",""),
    )

print(f"  → 가중치/층화 변수 {len(weight_vars)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 공통 교란변수 등록
# ─────────────────────────────────────────────────────────────────────────
confounders = [
    "sex",
    "grade",
    "school_type",
    "region",
    "family_econ",
    "father_edu",
    "mother_edu",
    "academic_perf",
    "residence_type",
    "health_perception",
    "bmi_category",
    "stress",
    "depression",
    "sleep_weekday",
    "pa_60min",
]

for c in confounders:
    lib.add_confounder("KYRBS", c)

print(f"  → 공통 교란변수 {len(confounders)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 분석 주의사항 등록
# ─────────────────────────────────────────────────────────────────────────
analysis_notes = [
    "복합표본 설계 필수: svydesign(id=~cluster_id, strata=~strata_id, weights=~wt, nest=TRUE)로 설계 객체 생성 후 svyglm/svycoxph 사용",
    "BMI 분류는 반드시 2017 소아청소년 성장도표 성별·연령별 백분위 기준 사용 (성인 BMI 25/30 기준 미적용)",
    "자기보고 신장·체중 사용 시 measurement bias 명시 필요",
    "정신건강 변수(우울, 자살) 분석 시 IRB 승인 여부 및 보안 취급 주의",
    "성별(sex)은 모든 분석에서 층화 또는 통제 필수",
    "2025년 신규 항목: zero_drink_intake(제로음료), commute_pa_days/time(등하교 신체활동), ecig_start_period, iqos_start_period, mukbang_watch",
    "원시자료는 SPSS/SAS 형식 제공; R에서는 haven::read_sav()로 불러올 것",
    "다변수 분석 시 VIF >10 다중공선성 확인 필요 (특히 father_edu + mother_edu + family_econ 동시 투입 시)",
    "결측치는 일반적으로 listwise deletion; 단 가중치 보정 후 결측률 < 5% 확인",
    "추세 분석(연도별): 매년 조사이므로 반복 횡단 자료; 동일 개인 추적 불가",
    "학교 수준 집락 효과(ICC) 보고 권장: 개인 수준 변수가 학교 내 유사성 가짐",
]

for note in analysis_notes:
    lib.add_analysis_note("KYRBS", note)

print(f"  → 분석 주의사항 {len(analysis_notes)}개 등록")

# ─────────────────────────────────────────────────────────────────────────
# 결과 출력
# ─────────────────────────────────────────────────────────────────────────
ds = lib.get_dataset("KYRBS")
total_vars = len(ds["variables"]) if ds else 0
print(f"\n{'='*60}")
print(f"KYRBS 데이터셋 라이브러리 구축 완료")
print(f"{'='*60}")
print(f"  총 변수: {total_vars}개")
print(f"  저장 위치: data/libraries/dataset_kyrbs.json")
print()

# Claude 프롬프트용 컨텍스트 미리보기
ctx = lib.get_context("KYRBS")
print("=== Claude 컨텍스트 미리보기 (앞 2000자) ===")
print(ctx[:2000])
