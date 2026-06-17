"""api/ — FastAPI 백엔드 (FRONTEND_MIGRATION_SPEC §5, FRONTEND_NEXTJS_SPEC §8).

★ 원칙: API는 얇게. 모든 로직은 src/service/*. (CLAUDE.md 규칙 10)
이 패키지는 service 함수를 HTTP/SSE로 노출하는 wrapper만.

Phase 2 출발: Phase 1 (service 추출) 위에 올림. Next.js Phase 3은 이 API 소비.
"""
__version__ = "0.1.0"
