---
name: style_polish
version: 1.0.0
applies_to: [paper_write, paper_polish]
extends: yoosun_style
last_updated: 2026-05-30
---

# Academic Style — 의미 단위 재창조 (단순 치환 아님)

본 가이드는 LLM이 의학 논문을 쓸 때 **단어 치환이 아닌, 단락의 의미·구성·강조점을 재해석**해서
독자에게 가치를 전달하는 학술 글로 만드는 트리거입니다.

---

## 1. 단락 구성 — 매 단락에 3개 자문

작성·재작성 직전에 다음 3개 질문에 답한 뒤 문장을 만드세요.

1. **Q1 핵심 발견(또는 주장)이 무엇인가?**
   → **첫 문장**에 그것을 둬라. "topic sentence first."
   → 약하게: "We observed an association..."
   → 강하게 (양식 — 본 프로젝트 변수로 치환): "Daily [exposure] was independently associated with [aOR]-fold higher odds of [outcome] (aOR [E]; 95% CI [Lo]–[Hi])."

2. **Q2 독자가 놀랄 만한 또는 행동을 바꿀 만한 숫자/대조가 있는가?**
   → **두 번째 문장 또는 그 직후**에 그 숫자/대조를 명시.
   → 양식: "We found a sex-specific effect (P for interaction < 0.001), with the association evident only in [subgroup]."

3. **Q3 기존 문헌과 다른 점, 또는 임상·정책 함의는 무엇인가?**
   → **단락 끝**에 그것으로 닫아라. 뻔한 "warrants further research"는 금지.
   → 양식: "Unlike [prior author] et al. ([year]), who [prior approach], our [current approach] suggests [mechanism/insight]."

---

## 2. 강조점(focus) 살리기

문장이 평면적이면 강조가 사라집니다. 다음 트리거로 강조점을 만드세요.

- **숫자의 비대칭**을 드러내라: "depressive symptoms were 27% more common" (단순 "higher" 금지)
- **방향성 동사** 사용: showed / declined / rose / persisted / attenuated / disappeared
- **subgroup 차이**가 있으면 그것을 main message로 끌어올려라. "Overall null, but stratified by sex..." 양식 자제 — 주요 발견이면 처음부터.
- **null finding도 의미가 있으면 강조**: "No association was observed even after adjustment for 11 confounders, suggesting the relationship is not mediated by lifestyle."

---

## 3. 회피해야 할 양식 — "AI 흔적"의 진짜 원인

각 항목은 **단어 치환이 아니라 사고 양식의 문제**입니다.

### 3.1 평면적 균형 (false balance)
- ❌ "On one hand X, on the other hand Y" — 의학 글에 어울리지 않음
- ❌ 3개 평행 구조 (tricolon) 남발: "robust, comprehensive, and nuanced"
- ✓ 비대칭 양식: "X was clear; Y, less so."

### 3.2 빈약한 일반화
- ❌ "Many studies have shown..." → 누가/언제/얼마나?
- ❌ "Significantly higher" without P-value
- ✓ "Three Korean cohorts (Cho 2024; Lee 2023; Park 2022) reported aORs of 1.2–1.4."

### 3.3 자조적 hedging (Yoosun 양식 hedging과 다름)
- Yoosun hedging: "**independently associated with**", "**may**" — 인과 회피
- ❌ AI hedging: "could potentially possibly maybe..." — 자신감 부족
- 정확한 hedging은 **인과 회피용**이지 **자신감 회피용이 아님**.

### 3.4 결론 stuffer
- ❌ "In conclusion / In summary / To summarize" — 의학 논문은 Discussion이 그 역할
- ✓ Discussion의 마지막 단락은 곧바로 **임상/정책 implication**으로.

### 3.5 Em-dash 과사용
- 한 단락에 1회 이하. 더 필요하면 그 단락은 too many ideas — 쪼개라.

### 3.6 Tonality 통일성
- AI는 모든 단락을 같은 톤·길이로 씀.
- ✓ Methods는 절차적·정확함. Discussion 첫 단락은 강한 단언. Limitation은 짧고 솔직함.

---

## 4. 단락 길이·문장 변동

- 한 단락 = 한 아이디어. 200–400 단어 권장.
- 문장 길이 **변동**: 한 단락 안에 짧은 문장(8–12 단어) ≥1개 + 긴 문장(25–35 단어) ≥1개.
- 매 문장이 15–20 단어로 균일하면 의심 — 다시 써라.

---

## 5. Yoosun(조유선) 양식 특이점 (yoosun_style.md와 정합)

- 전환어 다양화: Furthermore / Moreover / However / Compared with / Similar trends were observed / Across diverse populations / Notably / Of note / Conversely.
- 같은 전환어 한 단락 ≥2회 금지.
- "본 연구는" 양식은 Korean abstract 한 번만. 영문은 "Our study", "We" 적절 혼용.

---

## 6. 작성 직전 체크리스트 (LLM이 매 patch_preview 직전에 자문)

1. [ ] 이 단락은 **하나의 핵심 메시지**만 갖고 있나?
2. [ ] 그 메시지가 **첫 문장**에 있나?
3. [ ] 숫자/대조가 **두 번째 문장**에 명시됐나?
4. [ ] 마지막 문장이 **임상·정책 implication 또는 다음 단락의 다리**인가?
5. [ ] 문장 길이가 변동하나 (짧음·중간·긴 섞여)?
6. [ ] em-dash 1회 이하?
7. [ ] 평행 구조(3개 나열)·"It is important to note"·"In conclusion" 등 cliché 없나?
8. [ ] hedging이 **인과 회피용**(O)이지 **자신감 회피용**(X)이 아닌가?

체크리스트 한 항목이라도 No면, 그 단락은 **다시 써라** — 단어 치환이 아니라 구조부터.
