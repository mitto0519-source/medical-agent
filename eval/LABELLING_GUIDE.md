# eval/gold_set.json 라벨링 가이드 (mitto 전용)

> **★ SELF_EVOLUTION_SPEC §9 강제**: 시스템 자기 라벨 금지. mitto만 라벨.
> 이 가이드는 라벨 작업을 *돕는* 것이지 *대신하는* 것이 아닙니다.

---

## 0. 현재 상태 (2026-06-18 측정)

| 영역 | 항목 수 | 라벨 완료 | 우선순위 |
|---|---|---|---|
| `claim_evidence_pairs` | 3개 | 0/3 (TODO) | 🟡 2순위 |
| `survey_design_test_cases` | 1개 | 자동 검증 가능 (mitto 확인만) | ✅ 자동 |
| `queries` (retrieval@5) | 5개 | 1/5 (q_caffeine만 expected_pmids 박힘) | 🔴 **1순위** |
| `style_targets` | 1개 | 자동 계산 (yoosun_seed) | ✅ 자동 |
| `manuscript_targets` | 1개 | 자동 검증 (must_have_sections + no_overclaim) | ✅ 자동 |

`SELF_EVOLUTION anchor → overall=0.0, 골드셋 0/3` 사유: 라벨 미완 → 점수 NaN → 0 처리.

---

## 1. 라벨 순서 (정확성·기여도 순)

```
1. queries 4건 expected_pmids 채움          (15~30분 — RAG hit 검토)
2. claim_evidence_pairs 3건 label 결정       (30~60분 — 논문 1~2편 직접 읽기)
3. queries notes 보완 (선택)
```

### 1.1 queries.expected_pmids

각 query에 대해 "이 RAG가 회수해야 정답"인 PMID 2~3개를 박습니다.

**도구 사용**:
```bash
python scripts/suggest_gold_labels.py --query-id q_sleep_metabolic --top 8
```
→ 현재 RAG가 top-8 회수하는 PMID 후보 출력. mitto가 그 중 진짜 관련 있는 것 2~3개 선택해 직접 `expected_pmids`에 박음.

**기준**:
- 주제·인구·결과가 query와 정확히 매칭되는 것만.
- 단순 키워드 매칭 X — 실제 논문 abstract 읽고 결정.
- 2건이면 충분 (3건 이상은 over-fit).

### 1.2 claim_evidence_pairs.label

각 (claim, evidence_pmids) 쌍에 대해 **NLI 라벨**:
- `supports` — evidence가 claim을 직접 뒷받침
- `contradicts` — evidence가 claim과 반대 결과
- `neutral` — 관련 있지만 직접 입증 X

**작업 양식**:
1. `python scripts/suggest_gold_labels.py --pair-id ce_caffeine_dep --top 5` → 후보 PMID
2. PubMed에서 1~2편 직접 읽기
3. `evidence_pmids`에 PMID 2개 박고, `label`을 셋 중 하나로

**주의**:
- 한 claim에 supports + contradicts가 섞이면 → 별도 pair로 분리.
- PMID는 모두 ChromaDB·graph.json 안에 있는 것만 (검증 가능해야).

---

## 2. 자동 영역 (mitto 확인만)

### survey_design_test_cases
시스템이 `expected_engine = statsmodels.SurveyDesign + svy.logit` 자동 호출 → 결과 match 검증.
→ mitto 작업: spec 변경 시만 확인.

### style_targets (yoosun_seed)
mitto의 yoosun 논문 11편에서 자동 측정된 baseline (avg_sent_len / hedge / passive).
→ mitto 작업: `scripts/measure_yoosun_style.py` 한 번 실행해 값 갱신만.

### manuscript_targets
must_have_sections + no_overclaim_patterns 자동 grep. 라벨 불필요.

---

## 3. 라벨 후 검증

```bash
python -m src.evolution.anchor      # 6 axes 점수 재계산
# overall ≥ 0.6 이면 promotion 가능 신호
```

라벨이 완료된 axis만 점수 계산됩니다. NaN axis는 weighted geometric mean에서 자동 제외.

---

## 4. 절대 하지 말 것

- ❌ LLM에 "이 label 뭐일까?" 묻기 (자기 라벨 = §9 위반)
- ❌ 같은 PMID를 여러 queries.expected_pmids에 박기 (overlap → 자가검증 효과)
- ❌ 라벨 완료 전 promotion 실행 (NaN axis 다수 → false-positive 위험)
- ❌ scripts/suggest_gold_labels.py 결과를 그대로 paste (mitto 검토 필수)
