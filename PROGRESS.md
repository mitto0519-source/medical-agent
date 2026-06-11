# PROGRESS.md — 현재 진행 + 다음 TODO + 차단

> Harness Engineering State Layer. 매 세션 끝에 갱신. AGENTS.md(Instructions)와 짝.
> 자동: events.db / change_log.json / self_model.json. 이 파일은 사람·에이전트 둘 다 읽는 단일 요약.

## 현재 작업 (2026-06-11)

**활성 작업:** LLM 인프라 복구 + Harness Engineering 패턴 적용

### 완료된 항목 (최근 7일)
- ✅ ez_home 채팅 스트리밍 (`generate_streamed`) + 600px 고정 높이 컨테이너
- ✅ chat(좌)+preview(우) 고정 2-split 단일 페이지 양식 (`_render_chat_page`)
- ✅ 우측 RECENT 그리드 제거 (사이드바 RECENT만 유지)
- ✅ Preview empty state 로고 + tagline
- ✅ 단일 코어 wiring 6개 (persona / versioned prompts / conversation_memory / events / memory.router / change_log) — VS Code MCP와 동일 backend
- ✅ OpenRouter client 추가 (`src/llm/openrouter_client.py`) — 무료 4개 모델 순환 (Gemma 4B / Nemotron 9B / Mistral 7B / Llama 70B)
- ✅ Factory `_resolve_provider_order`에 openrouter 등록 + priority rank 2위
- ✅ Cooldown 600s → 60s (충전 후 즉시 재시도)
- ✅ Audit 결과: persona/medical_seed/recall_relevant/medical_graph 모두 실제 주입 확인 (5101자 system prompt)
- ✅ Harness Engineering 패턴 첫 적용: AGENTS.md (기존) + PROGRESS.md + feature_list.json + .harness/

### 진행 중
- ⏳ Go wide / Go deep 트리거를 ez_home 채팅에 wiring (parallel exploration)
- ⏳ figurelabs-style PublicationFigureGenerator를 chat에서 자연어 호출

### 차단 (사용자 액션 필요)
- 🚫 **Anthropic credit 0** (`"Your credit balance is too low"`) → console.anthropic.com/billing
- 🚫 **OpenAI quota 0** → platform.openai.com/usage
- 🚫 **Google free 5 RPM 한계** → 즉시 폴백 사용 못 함
- 🟡 권장 fix: **OpenRouter 무료 키 추가** (https://openrouter.ai/keys — 카드 불필요)
  → `.env`에 `OPENROUTER_API_KEY=sk-or-v1-...` 추가하면 즉시 활성화

## 다음 (우선순위 순)

1. **(P0) 사용자 LLM 키 fix** — 상기 3 옵션 중 하나
2. **(P1) Figma·Fable5·Harness 패턴**:
   - Go wide / Go deep 트리거 ez_home에 wiring (parallel prompting)
   - "이 방향 깊게" / "3가지로 펼쳐줘" 자연어 인식
3. **(P1) PublicationFigureGenerator 채팅 hookup** — "Forest plot 그려줘" → SVG/PNG preview에 표시
4. **(P2) RULE-8 #2/#5**: 12,500편 PICO/GRADE/limitation 구조화 추출 + paper_writer few-shot
5. **(P2) HF Datasets oa_papers 백그라운드 업로드 완료 확인**
6. **(P2) HF Space build + secrets + 외부 URL 접속 검증**
7. **(P3) Harness Engineering 추가**: norms.md / guardrails.md / hooks 양식 자동 학습 회로 (사용자가 "하지마" "왜 자꾸" 입력 시 자동 규칙 학습)

## 알려진 기술 부채

- `MedicalGraph.number_of_nodes()` 호출 시 attribute 없음 (Python: `g._graph.number_of_nodes()` 또는 facade 양식 양식)
- ez_home `_llm_reply` 비활성 (스트리밍으로 대체). 정리 필요.
- HF Datasets oa_papers 업로드 백그라운드 — 마지막 확인 시점에서 retry 중 (704MB, 25,251 files)

## 세션 핸드오프

이 PROGRESS.md를 다음 세션 시작 시 가장 먼저 읽는다. 그 다음 순서:
1. AGENTS.md — 에이전트 책임 맵
2. CLAUDE.md — 12개 작업 표준 규칙
3. ARCHITECTURE.md — 모듈 정의 레지스트리
4. feature_list.json — 기능 + 상태
5. `git log --oneline -10`
