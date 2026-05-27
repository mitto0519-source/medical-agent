# Medical-Agent

> **바이브 논문**(vibe paper) 코파일럿 — 사람이 의학 논문을 써내려가는 흐름을 AI가 실시간으로 거든다.
> KYRBS/KNHANES 공중보건 데이터 → StatBridge 통계 → Figure → Word/EndNote 풀셋.

[![Tests](https://img.shields.io/badge/smoke-13%2F13-brightgreen)](scripts/test_rag_smoke.py)
[![UI Eval](https://img.shields.io/badge/Playwright-49%2F49-brightgreen)](scripts/ui_eval.py)
[![Function E2E](https://img.shields.io/badge/E2E-10%2F10-brightgreen)](scripts/e2e_functions.py)

---

## 🚀 빠른 시작 (Docker · 권장)

```bash
docker compose up -d --build
# 브라우저: http://localhost:8501
# 로그: docker compose logs -f
```

API 키는 `.env`에 (admin 전역 키로 모든 사용자에 적용):
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIzaSy...   # Gemini (무료 폴백)
```

3중 자동 폴백 (Claude → OpenAI → Gemini), 예산 80% 도달 시 Gemini로 강제 다운그레이드.

---

## 🏗️ 아키텍처 (한눈에)

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer        app/streamlit_app.py                       │
│                  ↳ 논문 작업실 · 통계 코드 · 인용/레퍼런스   │
├─────────────────────────────────────────────────────────────┤
│  Tool Registry   src/tools/__init__.py                      │
│                  ↳ TOOLS dict + render_result(st.dialog)    │
├─────────────────────────────────────────────────────────────┤
│  Domain Logic    src/data/      ↳ KYRBS/KNHANES loader      │
│                  src/research/  ↳ paper_writer, peer review │
│                  src/export/    ↳ figure/table/citation     │
│                  src/llm/       ↳ failover client + budget  │
├─────────────────────────────────────────────────────────────┤
│  Runtime Layer   src/runtime/   ↳ events/tasks/idempotency/ │
│                                   heartbeat (SQLite WAL)    │
│                  src/memory/    ↳ router/scorer/lifecycle/  │
│                                   gate/conversation         │
├─────────────────────────────────────────────────────────────┤
│  Persistence     data/raw/      ↳ KYRBS 2005~2025 .sav      │
│                  data/runtime/  ↳ events.db/tasks.db/...    │
│                  data/exports/  ↳ Figure*.png/.docx/.xml    │
│                  data/chromadb/ ↳ 10k+ paper chunks (RAG)   │
├─────────────────────────────────────────────────────────────┤
│  MCP Server      mcp_server.py — Claude Desktop·외부 agent  │
│                  공통 backend (memory/task/events/budget)   │
└─────────────────────────────────────────────────────────────┘
```

자세한 모듈 레지스트리 → [ARCHITECTURE.md](ARCHITECTURE.md)
디자인 토큰 (색·폰트·spacing) → [DESIGN.md](DESIGN.md)

---

## 📐 핵심 원칙 (CLAUDE.md 규칙)

1. **사람이 주인공** — AI 자동 생성은 보조, 메인은 직접 쓰는 흐름
2. **장기 메모리 자가 진화** — `src/memory/router.py`가 단일 진입점, lifecycle decay/충돌해결 자동
3. **모델 하드코딩 금지** — `src/config/models.py` 경유
4. **LLM 호출은 failover 경유** — `get_llm_client()` 만 사용, 직접 client 생성 금지
5. **로컬 + 클라우드** — 항상 로컬 먼저, Supabase는 선택
6. **데이터 무결성 잠금** — 환각 차단 (`memory_gate.assess`), 숫자/통계 토큰 보존

전체 11 규칙 → [CLAUDE.md](CLAUDE.md)

---

## 🧪 검증 (다층)

| 레이어 | 명령 | 무엇 |
|---|---|---|
| ① 임포트 + RAG | `python scripts/test_rag_smoke.py` | 모든 모듈 import + ChromaDB 절대기준 |
| ② 코드 무결성 | `python scripts/e2e_diagnose.py` | LLM 무관 정적 분석 + code_graph |
| ③ 함수 E2E | `python scripts/e2e_functions.py` | 10/10 핵심 함수 실데이터 검증 |
| ④ 통계 회귀 | `python scripts/prove_stata_e2e.py` | 실 KYRBS → StatBridge → ZCB aOR 재현 |
| ⑤ UI 회귀 | `python scripts/ui_eval.py` | Playwright 49 assertion · 실 브라우저 |
| ⑥ 인용 워크플로 | `python scripts/e2e_citation.py` | 9/9 PubMed + EndNote 풀셋 |

---

## 📊 ZCB ↔ 우울 논문 재현 (대표 사례)

```bash
# 1. 실 KYRBS 2025 → 모든 분석 데이터 계산
docker compose exec learner python scripts/compute_all_figure_data.py

# 2. 4 figure 생성 (Stata v2.4 캐노니컬 매칭)
docker compose exec learner python scripts/build_paper_figures.py

# 3. EndNote CWYW 필드 임베드 Word docx
docker compose exec learner python scripts/build_endnote_docx.py \
    data/exports/ZCB_paper_v2.4_FINAL.md ZCB_paper_endnote
```

산출 → `data/exports/`:
- `Figure{1,2,3}_*.{png,pdf}` — 13단계 sample flow / 성별 예측확률 / forest plot
- `ZCB_paper_v2.4_FINAL.md` — 논문 본문 (paired with `ZCB_v2.4_canonical.do`)
- `ZCB_paper_v2.4_yoosun_deep_endnote.docx` — EN.CITE 필드 28개 임베드

---

## 🤖 외부 agent 연동 (MCP)

`mcp_server.py`로 Claude Desktop / Cursor / 다른 AI agent가 같은 backend 사용:

```bash
python mcp_server.py --port 8765
```

Claude Desktop 설정 (`~/.config/claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "medical-agent": {
      "url": "http://localhost:8765/mcp",
      "headers": { "Authorization": "Bearer ma-YOUR_API_KEY" }
    }
  }
}
```

노출 도구 (15+):
- 분석: `search_papers`, `check_novelty`, `generate_research_topics`
- 메모리: `memory_write`, `memory_recall`, `memory_lifecycle_tick`
- 작업: `task_list_unfinished`, `task_status`
- 감사: `events_recent`, `events_replay`
- 예산: `budget_status`, `budget_set_caps`

---

## 🛡️ 안전 + 품질 레이어 (12번 섹션 of ARCHITECTURE.md)

모든 LLM 출력은 다음을 자동 통과:

| 단계 | 모듈 | 차단/검증 |
|---|---|---|
| Prompt 합성 | `prompts/*.md` + `prompt_loader` + `build_base_system` | medical_core/safety/yoosun v1.0.0 자동 주입 |
| Truth 분류 | `safety/truth_hierarchy` + `memory/router` | PROJECT_FACT 이상만 LLM 컨텍스트 주입 가능 |
| 환각 차단 | `memory/memory_gate.assess` | quarantine 자동 + audit_trail 기록 |
| 임상 키워드 | `safety/physician_review` | 처방/진단/복용량 → 검토 큐 자동 격리 |
| 인용 grounding | `safety/citation_grounding` | DOI CrossRef 검증 + orphan ref 감지 |
| 본문 일관성 | `safety/consistency_checker` | n/OR-CI/p값/연도 모순 정규식 검출 |
| Figure 검증 | `safety/figure_validator` | Claude Vision으로 axis/CI/legend 재확인 |
| Reporting | `research/reporting_checklist` | STROBE 22항목 자동 체크 → peer_reviewer 흡수 |
| Tool-use loop | `llm/claude_client.generate_with_tools` | function calling agentic loop (events 기록) |
| Multi-stage RAG | `rag/pipeline.search_multistage` | dense + Jaccard rerank + recency_boost |
| Citation graph | `knowledge/citation_graph` | PubMed eLink co-citation/bridging/missing seminal |
| Self-consistency | `llm/self_consistency` | n-sample 다수결 (critical output에서) |
| Cost/latency | `llm/budget.latency_summary` | p50/p95 provider별 + events 기반 |
| Prompt A/B | `diagnostics/prompt_ab` | epsilon-greedy variant 선택 + eval 점수 누적 |
| Eval→Prompt | `eval_benchmark` + `capability_bench.get_improvement_context` | 5축 점수의 fail 항목이 다음 LLM에 자동 주입 |
| Replay | `scripts/replay_task.py` | events.db 사후 시간순 재구성 |
| Wiring audit | `scripts/audit_wiring.py` | 새 심볼 호출부 검증 — dead code 차단 |

---

## 📄 Word 표준 양식 (zcb_dep_v5)

모든 논문 docx는 동일 양식으로 출력 — `data/templates/manuscript_template.json` 단일 진실원본.

```python
from src.export.word_exporter import WordExporter
WordExporter().export(
    topic={"title": "...", "authors": [...], "affiliations": [...]},
    sections={"Abstract": {"Background": "...", "Methods": "...", ...},
              "Introduction": "...", "Methods": {...subsection...}, ...},
    keywords=["zero-calorie beverage", "depression", ...],
    figures=[{"bytes": ..., "caption": "...", "n": 1}, ...],
    tables=[{"type": "baseline", "data": [...], "caption": "...", "n": 1}],
    references=[{"authors": "...", "title": "...", "journal": "...",
                 "year": "2025", "volume": "385", "pages": "445-449"}],
    back_matter={"Ethics approval": "...", "Funding": "...", ...},
)
```

자동 적용: Times New Roman / double-spaced / Abstract inline label /
**Vancouver [1]** 인라인 / *italic P* / 학술지 세 줄 표 (NEJM 양식).

---

## 🔄 자동 동기화 (선택)

```bash
python scripts/auto_sync.py
# 또는 Windows hidden: wscript scripts/run_sync_hidden.vbs
```

v3 commit-first 패턴 — stash 0 의존, 60초 디바운스, 분 단위 polling.

---

## 📁 디렉토리

```
.
├── app/                    Streamlit UI (단일 진입점)
├── src/
│   ├── data/               KYRBS/KNHANES loader, StatBridge
│   ├── research/           paper_writer, peer_reviewer, pipeline
│   ├── export/             figure_builder, citation_workflow, table_builder
│   ├── llm/                failover client (Claude/OpenAI/Gemini), budget
│   ├── memory/             router, scorer, lifecycle, gate, conversation
│   ├── runtime/            events, tasks, idempotency, heartbeat
│   ├── tools/              TOOLS registry + render_result
│   ├── agent/              persona, MedicalAgent
│   ├── knowledge/          medical_seed, trend_learner, research_wiki
│   ├── rag/                ChromaDB pipeline
│   └── config/             models, env, logging
├── scripts/
│   ├── test_rag_smoke.py   ① 임포트 + RAG
│   ├── e2e_diagnose.py     ② 코드 무결성
│   ├── e2e_functions.py    ③ 함수 E2E
│   ├── prove_stata_e2e.py  ④ 통계 회귀
│   ├── ui_eval.py          ⑤ Playwright
│   ├── compute_all_figure_data.py  KYRBS → 모든 figure 수치
│   ├── build_paper_figures.py      → PNG/PDF
│   └── auto_sync.py        v3 commit-first 데몬
├── data/
│   ├── raw/                KYRBS/KNHANES .sav (gitignore)
│   ├── runtime/            SQLite (events/tasks/idempotency/lifecycle)
│   ├── exports/            논문 산출물
│   ├── chromadb/           RAG 벡터 인덱스
│   ├── agent_self/         persona, insights, change_log
│   └── author_profiles/    yoosun_cho.json 등
├── mcp_server.py           MCP backend (공통)
├── docker-compose.yml      medical-agent + learner 서비스
├── ARCHITECTURE.md         모듈 레지스트리 (★새 모듈 만들기 전 필독)
├── DESIGN.md               디자인 토큰 (★figure/UI 색·폰트 변경 전 필독)
└── CLAUDE.md               작업 표준 11 규칙
```

---

## 🛠️ 기술 스택

- **UI**: Streamlit 1.30+
- **LLM**: Anthropic Claude · OpenAI GPT · Google Gemini (3중 failover)
- **통계**: statsmodels, pingouin, lifelines, pyreadstat (KYRBS .sav)
- **시각화**: matplotlib, seaborn, plotly (논문 figure는 matplotlib)
- **RAG**: sentence-transformers + ChromaDB (or Supabase pgvector)
- **문서**: python-docx, mammoth (DOCX), reportlab (PDF), python-pptx
- **인프라**: Docker, SQLite WAL, FastMCP

---

## 📚 자세한 문서

- [CLAUDE.md](CLAUDE.md) — 작업 표준 11 규칙
- [ARCHITECTURE.md](ARCHITECTURE.md) — 모듈 레지스트리 (11 섹션)
- [DESIGN.md](DESIGN.md) — 디자인 토큰 (YAML + body)
- `memory/` — 세션 간 영속 컨텍스트
- `data/change_log/history.json` — 모든 의미있는 변경 이력

---

## 라이선스 / 사용자

연구용 · 환자 진료 결정에 직접 사용 금지 (의료 안전 레이어는 별도 검토 필요).
