"""Medical-Agent 운영 런타임 레이어.

- events: 모든 시스템 동작의 append-only 이벤트 소스 (replay/감사용)
- tasks: 장기 작업의 durable state machine (크래시 복구·idempotency)
- idempotency, budget: 별도 모듈

설계 원칙: 무겁지 않게 — SQLite + WAL, 외부 의존(Redis/Temporal) 없음.
"""
