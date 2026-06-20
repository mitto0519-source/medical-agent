# Medical-Agent — HF Space 단일 컨테이너 (Next.js + FastAPI 동시).
# ★ 2026-06-20 v6: Streamlit → Next.js 이사 (사용자 약속 이행).
#   - port 3000 (Next.js 외부 노출, HF Space app_port와 일치)
#   - port 8000 (FastAPI 내부, Next.js rewrite로 /fastapi/* → localhost:8000/*)
#   - supervisord로 두 process 동시 관리
# 기존 Streamlit 양식은 Dockerfile.streamlit으로 보존 (roll-back 안전).

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

# Next.js standalone build 결과 복사 (web-runtime 별도 디렉토리)
COPY --from=web-builder /web/.next/standalone /app/web-runtime/
COPY --from=web-builder /web/.next/static /app/web-runtime/.next/static
COPY --from=web-builder /web/public /app/web-runtime/public

# Supervisor config (Next.js + FastAPI 동시 관리)
COPY supervisord.conf /etc/supervisor/conf.d/medical-agent.conf

# HF Space는 app_port 1개만 노출 = 3000 (Next.js).
# 8000은 컨테이너 내부 전용 (Next.js rewrites가 proxy).
EXPOSE 3000

# HF Space 헬스체크 (Next.js port) — 한 줄로 (linter \ continuation 오인 회피)
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 CMD curl -fsS http://localhost:3000/ >/dev/null || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/medical-agent.conf"]
