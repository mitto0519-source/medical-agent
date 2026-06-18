"""NOVA 4단계 식품 분류 — Monteiro 2019 + 한국 적용 (Sung 2020, Shim 2022).

NOVA 단계:
  1 = 천연·최소가공 (unprocessed/minimally processed)
  2 = 가공식품원재료 (processed culinary ingredients)
  3 = 가공식품 (processed foods)
  4 = ★ 초가공식품 (ultra-processed foods, UPF) — MASLD/대사이상 위험 증가

KNHANES 24시간 회상 식이조사 (영양조사):
  N_FN (식품명) / N_FCD (식품코드, 한국식품성분표 KOFRC) / N_INTK (섭취량 g)

본 모듈은 식품명 또는 코드 키워드 매핑으로 NOVA 4단계 자동 분류.
한국 NOVA 매핑 정밀화는 식품군 단위가 정확하나, 키워드 매핑은 80~90% 수준 작동.

usage:
    from src.data.nova_classification import classify_nova, upf_intake_share
    df["nova"] = classify_nova(df["N_FN"])
    upf_pct = upf_intake_share(df, intake_col="N_INTK", nova_col="nova")
"""
from __future__ import annotations

from typing import Iterable

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 키워드 매핑 (한국어 식품명 기준 + 영문 보조)
# 한국 영양섭취조사 실 식품명에서 자주 등장하는 양식 위주
# ─────────────────────────────────────────────────────────────────────────────

_NOVA_4_KEYWORDS = [
    # 가공음료
    "탄산음료", "콜라", "사이다", "환타", "스프라이트", "닥터페퍼",
    "에너지드링크", "핫식스", "레드불", "몬스터",
    "이온음료", "포카리", "게토레이", "파워에이드",
    "주스음료", "과채음료",
    "캔커피", "믹스커피", "맥심", "인스턴트커피",
    "초콜릿음료", "코코아",
    "두유음료", "가공우유", "초코우유", "딸기우유", "바나나우유",
    # 가공유제품
    "가공치즈", "체다", "슬라이스치즈",
    "마가린",
    "아이스크림", "빙수", "팥빙수",
    "요거트음료", "마시는요구르트",
    # 가공육
    "햄", "소시지", "베이컨", "스팸", "런천미트",
    "너겟", "치킨너겟", "치킨가스",
    "돈가스",
    "햄버거", "치즈버거",
    "프랑크", "비엔나",
    "어묵", "맛살", "게맛살",
    # 가공탄수
    "라면", "신라면", "짜파게티", "너구리", "팔도", "진라면",
    "컵라면", "사발면",
    "인스턴트면", "즉석면",
    "냉동만두", "냉동피자", "냉동돈까스",
    "피자", "도미노", "피자헛",
    "치킨", "후라이드", "양념치킨", "교촌", "BBQ",
    "팝콘", "감자칩", "포카칩", "프링글스", "꼬깔콘",
    "과자", "비스킷", "쿠키", "샌드",
    "초콜릿", "초콜렛", "킷캣", "스니커즈", "엠앤엠",
    "사탕", "캔디", "젤리", "마이쮸",
    "껌",
    "도넛", "케이크", "조각케이크", "롤케이크",
    "빵", "샌드위치", "토스트", "단팥빵", "크림빵", "소보로", "식빵",
    "시리얼", "콘플레이크", "첵스", "콘푸로스트",
    "에너지바", "그래놀라바",
    # 가공조미·간식
    "설탕시럽", "메이플시럽",
    "케첩", "마요네즈", "샐러드드레싱", "스리라차", "와사비마요",
    "라이트",
    "인스턴트수프", "분말스프", "큐브국물",
    "냉동식품", "냉동도시락", "즉석조리",
    "도시락", "삼각김밥", "편의점",
    "분말주스",
    # 영문 키워드
    "instant", "ultra-processed", "frozen meal", "ready-to-eat",
    "soda", "cola", "chips", "candy", "cookie", "cake",
    "ham", "sausage", "bacon", "nugget", "burger",
    "ramen", "noodle", "pizza", "ice cream",
]

_NOVA_3_KEYWORDS = [
    "통조림", "참치캔", "꽁치캔",
    "절임", "장아찌", "피클",
    "김치", "깍두기", "총각김치", "동치미",  # 전통 발효 — NOVA 3
    "된장", "고추장", "간장", "소금절임",
    "두부",  # 가공 두부 — NOVA 3
    "치즈",  # 일반 자연치즈 (가공 X)
    "베이커리빵", "베이커리",  # 빵집 빵 (대량생산 NOVA 4와 구분)
    "훈제연어", "훈제오리",
    "건어물", "마른오징어",
    "병조림",
    "통조림과일",
]

_NOVA_2_KEYWORDS = [
    "식용유", "콩기름", "옥수수기름", "올리브유", "참기름", "들기름", "포도씨유",
    "설탕", "백설탕", "흑설탕", "황설탕",
    "소금", "꽃소금", "천일염",
    "꿀",
    "버터",  # 무가염
    "전분", "녹말",
    "식초",
]

_NOVA_1_KEYWORDS = [
    # 곡류 (생/도정)
    "쌀", "백미", "현미", "찹쌀", "보리", "콩", "팥", "수수", "조", "기장",
    # 채소
    "배추", "무", "당근", "양파", "감자", "고구마", "마늘", "생강",
    "오이", "토마토", "상추", "깻잎", "시금치", "쑥갓", "부추",
    "버섯", "표고", "팽이", "느타리", "양송이",
    # 과일 (생)
    "사과", "배", "복숭아", "포도", "감", "귤", "오렌지", "딸기",
    "수박", "참외", "키위", "바나나", "파인애플",
    # 신선 단백질
    "닭고기", "닭다리", "닭가슴살",
    "돼지고기", "삼겹살", "목살", "안심", "등심",
    "소고기", "한우", "등심", "안심", "갈비",
    "달걀", "계란",
    "고등어", "갈치", "삼치", "조기", "꽁치", "전어",
    "오징어", "낙지", "문어",
    "조개", "굴", "전복",
    "우유", "원유",  # 살균만
    "두유",  # 무첨가 (가공은 NOVA 4)
    "물", "생수", "약수",
]


def classify_nova(food_names: Iterable[str]) -> list[int]:
    """식품명 리스트 → NOVA 단계 (1~4) 리스트.

    매칭 우선순위: NOVA 4 (UPF) > 3 > 2 > 1. 미매칭은 NOVA 1 (보수적).
    """
    out = []
    for name in food_names:
        n = (str(name) if name is not None else "").strip().lower()
        if not n:
            out.append(1)
            continue
        # NOVA 4 우선 (UPF 우선 검출 — 분석 목적)
        if any(k.lower() in n for k in _NOVA_4_KEYWORDS):
            out.append(4)
        elif any(k.lower() in n for k in _NOVA_3_KEYWORDS):
            out.append(3)
        elif any(k.lower() in n for k in _NOVA_2_KEYWORDS):
            out.append(2)
        elif any(k.lower() in n for k in _NOVA_1_KEYWORDS):
            out.append(1)
        else:
            out.append(1)  # 보수적 default
    return out


def upf_intake_share(df, intake_col: str = "N_INTK", food_col: str = "N_FN",
                       nova_col: str | None = None) -> float:
    """일일 UPF (NOVA 4) 섭취량 / 총 섭취량 비율 (0~1).

    한 사람의 24h 회상 식이조사 (여러 식품 row) → 개인별 UPF 섭취 비율.
    Args:
        df: 식품 단위 row (한 사람 = 여러 row).
        intake_col: 섭취량 g 컬럼.
        food_col: 식품명 컬럼 (nova_col 없을 때 사용).
        nova_col: 미리 분류된 NOVA 컬럼명 (없으면 food_col로 즉시 분류).
    """
    if nova_col is None or nova_col not in df.columns:
        nova = classify_nova(df[food_col])
    else:
        nova = df[nova_col].tolist()
    intake = df[intake_col].astype(float).tolist()
    total = sum(intake)
    if total <= 0:
        return 0.0
    upf = sum(g for g, n in zip(intake, nova) if n == 4)
    return upf / total


def upf_share_by_person(df, person_col: str = "ID", intake_col: str = "N_INTK",
                          food_col: str = "N_FN"):
    """개인별 UPF 섭취 비율 계산 — DataFrame 반환.

    Args:
        person_col: 개인 식별 컬럼 (KNHANES ID).
    Returns:
        DataFrame [person_col, upf_share, total_kcal_proxy_g].
    """
    import pandas as pd
    df = df.copy()
    df["_nova"] = classify_nova(df[food_col])
    grp = df.groupby(person_col)
    rows = []
    for pid, g in grp:
        total = g[intake_col].astype(float).sum()
        upf = g[g["_nova"] == 4][intake_col].astype(float).sum()
        rows.append({person_col: pid,
                       "upf_share": (upf / total) if total > 0 else 0.0,
                       "total_intake_g": total})
    return pd.DataFrame(rows)


__all__ = [
    "classify_nova", "upf_intake_share", "upf_share_by_person",
]
