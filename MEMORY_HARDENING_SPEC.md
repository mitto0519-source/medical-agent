# MEMORY_HARDENING_SPEC — 외부 메모리 시스템(memorize/agentmemory/agentlas) 4기법 보강

> ★ 결정(2026-06-17): **외부 통째 통합 X.** `src/memory/`가 이미 그들의 ~80%다.
> events.db + router + 5-타입 + scorer + claim_evidence_nli + conversation_memory + change_log + SELF_EVOLUTION ledger.
> 통째 통합 = 메모리 사일로 자초 = 이 도구들이 해결한다고 주장하는 그 문제(드리프트) 재현.
>
> **★ 가져올 것: 기법 4개만. 기존 모듈에 보강.**
> ★ 가져오지 말 것: 별도 저장소·별도 진입점·별도 schema.

연계: [[RESEARCH_STATE_SPEC]] · [[SELF_EVOLUTION_SPEC]] · [[CLAUDE.md 규칙 12]].

---

## 0. 두 메모리 레이어 — 절대 섞지 마라

| 레이어 | 어디 | 어떤 도구가 맞나 |
|---|---|---|
| **제품 런타임 메모리** (Medical-Agent가 사용자 연구 기억) | `src/memory/`, `data/runtime/` | 이미 충분. **외부 통합 X.** 기법 4개만 보강. |
| **개발 워크플로 메모리** (mitto가 Opus↔GPT 갈아탈 때 작업기억 유지) | Claude Code / VS Code 별도 설치 | memorize / agentmemory가 진짜 맞음. **Medical-Agent 코드 안 건드림.** |

→ 본 스펙은 *전자만*. 후자는 별개로 처리 (이 코드베이스 변경 없음).

---

## 1. 빌려올 기법 4가지 (기존 모듈에 패턴 이식)

### 기법 ① 서버리스 내용기반 수렴 (memorize)
**약점**: 크로스머신은 Supabase 의존 → Supabase 다운 시 머신 간 메모리 수렴 멈춤.
**보강 위치**: [src/runtime/events.py](src/runtime/events.py) + [src/research/research_state.py](src/research/research_state.py)
**패턴**:
- append-only 로그의 entry id = `sha256(actor+type+payload_canonical)`.
- 두 머신이 같은 사건을 독립 기록해도 같은 hash → 자동 dedup.
- Supabase 없이 SQLite WAL append만으로 수렴 보장.
**적용**: events.append()에 `dedup_key` 자동 계산 (CAS) + 동일 key면 INSERT OR IGNORE.

### 기법 ② 워터마크 + 영속 후 전진 + 출처 dedup (memorize)
**약점**: memory.router가 통합 중 타임아웃/파싱 실패 시 부분 commit → 유실 견고성 미명세.
**보강 위치**: [src/memory/router.py](src/memory/router.py)
**패턴**:
- router.write()는 (스코어링→게이트→저장→인덱싱) 단계마다 **워터마크** 박음.
- "영속 후에만 전진" — fsync 완료 후 다음 단계 진입.
- 실패 시 마지막 워터마크부터 재개 (idempotent).
- 출처(`source_uri` + `content_hash`) 기반 dedup — 같은 PMID 두 번 들어와도 한 번만 저장.
**적용**: router.py에 `WriteState` 인라인 상태머신 + checkpoint 필드.

### 기법 ③ 티켓→Curator→Policy Gate 승격 (agentlas)
**약점**: raw 메모리 → typed 승격이 `memory_gate`로 있지만 governance가 prompt만큼 명시적이지 않음.
**보강 위치**: [src/memory/memory_gate.py](src/memory/memory_gate.py) + [src/evolution/ledger.py](src/evolution/ledger.py)
**패턴**:
- 새 메모리 후보 = `MemoryTicket` (raw observation + proposed type + evidence).
- Curator (자동 룰) — drop / accept / route-to-policy-gate.
- Policy Gate — semantic/procedural 승격은 (citation 또는 stat result 또는 휴먼 승인) 중 하나 충족.
- ledger에 ticket → decision → 승격 trail 기록 (감사 가능).
**적용**: memory_gate.py에 `MemoryTicket` dataclass + Curator policy 4규칙.

### 기법 ④ Bitemporal (memorize)
**약점**: `lifecycle.py`의 _archive는 단순 이동. "그땐 참, 지금 아님" 양식 부재 → 같은 사실 재발견 시 reopen 못함.
**보강 위치**: [src/memory/lifecycle.py](src/memory/lifecycle.py)
**패턴**:
- items 테이블에 `valid_to REAL NULL` 추가 (NULL = 현재 유효).
- close_validity(id, reason, at=now) — DELETE 안 함, valid_to만 박음.
- reopen(id) — valid_to=NULL 복원 (같은 사실 재확인 시).
- 조회 함수에 `active_only=True` 필터 (valid_to IS NULL).
- 기존 archive 테이블은 *영구 보관*용 (low_confidence/expired_ttl) 그대로 유지.
**적용**: ★ 이 스펙의 첫 구현. 본 commit에서 즉시 적용.

---

## 2. 구현 순서 (small → large)

| 순서 | 기법 | 파일 | scope |
|---|---|---|---|
| 1 | ④ bitemporal | `src/memory/lifecycle.py` | small (즉시 적용) |
| 2 | ① dedup_key | `src/runtime/events.py` | small |
| 3 | ② 워터마크 | `src/memory/router.py` | medium |
| 4 | ③ 티켓+Curator | `src/memory/memory_gate.py` + `src/evolution/ledger.py` | medium |

---

## 3. 검증 (각 기법별)

```bash
# ④ bitemporal
python -c "
from src.memory.lifecycle import register, close_validity, reopen, active_items
register('test:1', 'episodic', '카페인 가설 — 2024년 코호트', confidence=0.8)
print(active_items())                   # 1개
close_validity('test:1', reason='superseded by 2026 RCT')
print(active_items())                   # 0개 (닫힘)
reopen('test:1')
print(active_items())                   # 1개 (재발견 시 복원)
"

# 회귀
python scripts/test_rag_smoke.py
```

---

## 4. 절대 하지 않는 것

- ❌ memorize/agentmemory/agentlas의 SDK·라이브러리 통째 import.
- ❌ 새 SQLite DB 추가 (lifecycle.db + events.db + memory.db 그대로).
- ❌ `src/memory/*` 외부에 메모리 진입점 만들기.
- ❌ "외부와 동기" 데몬 (제품 메모리는 단일 정본 + Supabase 백업이면 충분).

---

## 5. 결론

> 메모리는 이미 80% 있다. 기법 4개만 빌려 자기 모듈에 박는다.
> 통째 통합 = 사일로 자초 = 이 도구들이 해결한다고 주장하는 그 문제의 재현.
> 본 스펙은 **자기 모듈 보강** — 외부 시스템 도입 0건.
