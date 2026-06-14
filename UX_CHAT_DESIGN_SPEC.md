# UX_CHAT_DESIGN_SPEC — 세련된 채팅 UX (디자인 시스템·구조화 출력·컴포저·스트리밍)

> 목표: Lovable/Claude급 세련됨. **가독성 + 사용성 + 엣지 있는 디자이너 감각.**
> 연계: 커뮤니케이션 규율=`prompts/chat_style.md` · 스트리밍=`FRONTEND_MIGRATION §5.5` · 컴포저=`FRONTEND_MIGRATION §6`.
> ★ 원칙: 커뮤니케이션 규율·디자인 토큰은 **지금(durable)**, 풀 컴포넌트·컴포저는 **Next.js**. Streamlit은 헤더 CSS만 최소.
> ★ 현재 문제 2개: (a) 채팅 말풍선에 h1/h2 제약 없어 문서급 거대 헤더, (b) 모델이 문서체로 출력(=chat_style.md로 해결).

---

## 1. 커뮤니케이션 규율 (배선)

`prompts/chat_style.md` 신설(완료). 배선:
- `src/agent/prompt_loader.py:TASK_PROMPTS`에 chat 계열 추가:
  ```
  "chat":        ["medical_core","safety_constraints","chat_style"],
  "qa":          ["medical_core","safety_constraints","chat_style"],
  "topic_explore":["medical_core","safety_constraints","chat_style"],
  ```
- **paper_write 계열엔 chat_style 미포함**(문서체 유지). 즉 *말풍선=chat_style, 프리뷰=yoosun_style* 분리.
- 효과: 결론 먼저·거대헤더 금지·짧은 문단 → 가독성의 80%.

---

## 2. 채팅 디자인 시스템 (디자인 토큰)

### 2.1 타입 스케일 (채팅 전용, 문서와 분리)
```
--chat-body:    15px / line-height 1.65      본문
--chat-h3:      0.95rem / 600                소제목(유일 허용 헤더)
--chat-small:   0.8rem                       메타/캡션
--chat-code:    0.86em mono
말풍선 max-width: 74ch   (긴 줄 = 가독성 저하)
```
> 현재 `.sg-manuscript`만 헤더 제약됨 → **채팅 말풍선(`.sg-msg-assistant`)에 동일 제약 추가**가 즉효(§6 CSS).

### 2.2 색·역할
```
user 말풍선:    진한 배경(우측 정렬), 텍스트 흰색
assistant:      투명/연한 면(좌측), 테두리 없음 → "AI는 캔버스, 사용자는 카드"
강조 컬러:      sapphire 1색만(--sg-accent). 무지개 금지
배지:           의미별 톤 — 경고=amber, 신뢰=emerald, 정보=slate
```

### 2.3 메시지 해부 (anatomy)
```
[아바타 32px] ─ 작성자/시간(0.8rem, muted)
              본문(15px, 문단 간 10px)
              [구조화 블록: 표/카드/배지 — §3]
              [출처 칩 · 액션(복사/프리뷰 삽입)]  ← hover 시 노출
```

---

## 3. 구조화 출력 컴포넌트 (★ "디자이너 엣지" — 텍스트 벽 → 컴포넌트)

모델 출력을 raw 마크다운으로 흘리지 말고 **타입별 컴포넌트로 렌더**. 파서가 패턴 인식 → 컴포넌트 매핑(Next.js MDX/remark 플러그인).

| 출력 타입 | 트리거 | 렌더 | 엣지 포인트 |
|---|---|---|---|
| **Answer-lead** | 응답 첫 문단 | 살짝 큰 본문 + 강조 1어 | 결론이 시각적으로 먼저 |
| **Callout/배지** | "확인 필요" "주의" "신뢰 0.87" | 좌측 컬러바 + 아이콘 박스 | 경고=amber, 신뢰=emerald |
| **비교 표** | 옵션·트레이드오프 | 라운드 헤더 zebra 표 | 모바일 카드로 reflow |
| **순위/단계** | "1위… 2위…" | 번호 칩 + 부제 | 진행감 |
| **인용 칩** | `[PMID:123]` | 클릭 가능한 칩(논문 미리보기 팝오버) | refs 패널 연동 |
| **통계 결과 카드** | kyrbs_stat 결과 | aOR(CI) 강조 카드 + "표로/프리뷰로" 버튼 | 숫자 한눈에 |
| **그림 카드** | figure 결과 | 썸네일 + 캡션 + 삽입 버튼 | |
| **코드/쿼리** | 코드블록 | 복사버튼 + 언어 라벨 | PubMed 검증쿼리 복사 |
| **접이식 디테일** | 긴 부연 | "자세히 ▾" 토글 | progressive disclosure |
| **활동 로그** | status/tool 이벤트 | 접히는 "작업 중…" 타임라인 | Lovable 빌드로그 느낌 |

원칙: **본문은 짧게, 무거운 정보는 컴포넌트로.** 표·카드가 산문 벽을 대체.

---

## 4. 컴포저 (Claude식 입력창 — 모델·첨부·레퍼런스)

```
┌──────────────────────────────────────────────────────────┐
│ [첨부 칩들: paper.pdf ✕  chart.png ✕]                      │  ← 첨부 미리보기
│ 메시지를 입력하세요…                                        │
│ [+ 첨부▾] [모델 ▾ Sonnet] [@ 레퍼런스] [/ 명령]      [↑ 전송]│
└──────────────────────────────────────────────────────────┘
```

### 4.1 첨부 (+▾) — 파일/사진/폴더
- 드래그drop + 클릭. 타입: **pdf/docx/txt(논문·문서) · png/jpg(그림·표 캡처) · csv · .sav/.dta(데이터) · 폴더(다중)**.
- 칩으로 미리보기(파일명·크기·썸네일), ✕로 제거.
- 라우팅: 논문→StyleProfiler/RAG 인제스트, .sav→데이터셋 등록(register_dataset), 이미지→비전 분석.
- **현존**: ez_home `_enqueue_uploaded_files`(pdf/docx/txt/sav) → 이미지·폴더·드래그drop **확장 필요**.

### 4.2 모델 선택 (▾)
- 칩: **Haiku(빠름) / Sonnet(균형·기본) / Opus(최고품질)** — §5.5 라우팅과 동일.
- 턴별 override 또는 task 자동(대화=Haiku, 작성=Sonnet). 비용/속도 힌트 툴팁.
- **현존**: `models.py` 라우팅 有 → UI picker만 추가(override는 `LLM_MODEL_OVERRIDE` 경유).

### 4.3 레퍼런스 삽입 (@)
- `@` 입력 → pubmed/rag 실시간 검색(네이티브 tool-use) → 결과 칩 선택 → 본문/프리뷰에 인용 삽입.
- References 패널과 양방향(삽입/제거 시 인용번호 재계산).
- **현존**: references 서비스 + pubmed_search 툴 有 → tool-use 연결 시 작동(J6).

### 4.4 슬래시 명령 (/)
- `/논문쓰기 /통계 /신규성 /그림 /제출` 등 → agentic_loop 툴·여정 단축. `slash_commands` 모듈 재사용.

### 4.5 상태
- 전송 중: 입력 비활성 + 스트리밍 표시. 빈 입력·첨부만=전송 가능. 에러=인라인 토스트.

---

## 5. 스트리밍·활동 렌더 (§5.5 이벤트 → UI)

`ChatEvent`(FRONTEND §5.5) 매핑:
- `status`/`plan` → 상단 접히는 **활동 타임라인**("KYRBS 불러오는 중 · novelty 검색 중") — Lovable 빌드로그.
- `tool_start/result` → 활동 칩 + 해당 패널(stat/figure/refs) 채움.
- `token` → 우측 프리뷰 섹션 append(채팅엔 요약만).
- `warning/badge` → 응답 하단 배지(신뢰 0.87 · survey-weight 경고).
첫 `status` <300ms로 **빈 스피너 0** → 체감속도.

---

## 6. 지금(Streamlit 최소) vs Next.js(풀) 분리

### 6.1 지금 적용 — `sapphire_glass.py`에 헤더 CSS만 (과투자 금지)
```css
.sg-msg-assistant h1,.sg-msg-assistant h2{font-size:1.05rem;font-weight:700;margin:14px 0 6px;line-height:1.3}
.sg-msg-assistant h3{font-size:.95rem;margin:12px 0 4px}
.sg-msg-assistant p{margin:0 0 10px;line-height:1.65}
.sg-msg-assistant ul,.sg-msg-assistant ol{margin:6px 0 10px;padding-left:18px}
.sg-msg-assistant table{font-size:.88rem;border-collapse:collapse}
.sg-msg-assistant{max-width:74ch}
```
+ chat_style.md 배선(§1). → 이 둘이 *현재 화면* 가독성 즉시 개선.

### 6.2 Next.js — 풀 디자인 시스템 + 컴포넌트 + 컴포저
- 타입 토큰(§2) Tailwind theme로, sapphire 팔레트 이식(디자인 연속성).
- §3 구조화 컴포넌트 = MDX/remark 플러그인(인용칩·통계카드·callout·접이식).
- §4 컴포저 = React 컴포넌트(드래그drop·모델칩·@레퍼런스·/슬래시).
- §5 활동 타임라인 = EventSource reducer.

> Streamlit에 컴포저·컴포넌트 풀구현 금지 — 버려진다. **헤더 CSS + chat_style만 지금.**

---

## 7. 기존 코드 매핑 / 배선

| 요소 | 현존 | 변경 |
|---|---|---|
| 커뮤니케이션 | prompts/* (paper만) | `chat_style.md`(완료) + prompt_loader TASK_PROMPTS 배선 |
| 채팅 헤더 거대 | `.sg-msg-assistant` 제약 없음 | §6.1 CSS 추가 |
| 첨부 | `_enqueue_uploaded_files`(pdf/docx/txt/sav) | 이미지·폴더·드래그drop(Next.js) |
| 모델 picker | `models.py` 라우팅 | UI picker + override |
| 레퍼런스 | references 서비스·pubmed_search | tool-use 연결(J6) |
| 슬래시 | `slash_commands` | 컴포저 `/` 메뉴 |
| 구조화 출력 | raw 마크다운 | remark 컴포넌트(Next.js) |
| 활동 로그 | (없음) | §5.5 이벤트 타임라인 |

---

## 8. 수용 기준
- 채팅에 거대 헤더 0(h1/h2 ≤1.05rem), 결론 첫 문단, 문단 벽 없음.
- 비교는 표·통계는 카드·인용은 칩으로 렌더(텍스트 벽 아님).
- 컴포저: 파일/이미지/폴더 첨부·모델 선택·@레퍼런스·/명령 동작(Next.js).
- 첫 status <300ms, 활동 타임라인 노출.
- "디자이너가 설계한 느낌" 체크: 1 강조색·일관 타입스케일·여백·컴포넌트화.

> 요약: **세련됨 = (a) chat_style 규율 + (b) 헤더 CSS(지금) + (c) 구조화 출력 컴포넌트·컴포저(Next.js).**
> 지금 둘만 해도 화면이 확 읽히고, 풀 엣지는 React에서 완성된다.
