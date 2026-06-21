# Medical-Agent — HF Space 단일 컨테이너 (Next.js + FastAPI).
# ★ 2026-06-21 v7: 풀이관 양식 (사용자 '매번 켜기 싫다 → HF 정식 호스팅').
#   - port 3000 (Next.js, 외부 노출)
#   - port 8000 (FastAPI, 내부 — Next.js rewrites /fastapi/* → localhost:8000/*)
#   - supervisord로 두 process 동시 관리
# 이전 v6 (9f3d4b0)이 실패한 모든 원인 해결됨:
#   ✓ postcss.config.mjs 추가 (Tailwind 정합)
#   ✓ /login Suspense boundary
#   ✓ (public)/page.tsx → (public)/landing/page.tsx (route group 충돌)
#   ✓ RecentSidebar + PreviewPane + Composer 실 컴포넌트
#   ✓ middleware 화이트리스트 (/ 인증 게이트)
#   ✓ verify_user 이메일만 (Streamlit 동일)
#   ✓ layout h-screen overflow-hidden (Composer viewport 안)
# 기존 Streamlit Dockerfile = Dockerfile.streamlit 백업 (roll-back 안전).

# ── Stage 1: Next.js deps ───────────────────────────────────────────────
FROM node:20-alpine AS web-deps
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --prefer-offline || npm install --no-audit

# ── Stage 2: Next.js build (standalone) ─────────────────────────────────
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY --from=web-deps /web/node_modules ./node_modules
COPY web/ .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_BASE=/fastapi
RUN npm run build

# ── Stage 3: Runtime (python + node + supervisord) ─────────────────────
FROM python:3.12-slim

# 시스템 deps + Node.js 20 + supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libgomp1 \
        fonts-nanum \
        fonts-noto-cjk \
        curl \
        gnupg \
        ca-certificates \
        supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/data/.hf_cache \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE=/fastapi

WORKDIR /app

# Python deps 먼저 (변경 적음 → 캐시 hit)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Python source
COPY . .

# Next.js standalone build 결과 복사
COPY --from=web-builder /web/.next/standalone /app/web-runtime/
COPY --from=web-builder /web/.next/static /app/web-runtime/.next/static
COPY --from=web-builder /web/public /app/web-runtime/public

# Supervisor config (Next.js + FastAPI 동시 관리)
COPY supervisord.conf /etc/supervisor/conf.d/medical-agent.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 CMD curl -fsS http://localhost:3000/ >/dev/null || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/medical-agent.conf"]
