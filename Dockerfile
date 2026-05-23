# Medical-Agent — 재현 가능한 컨테이너 이미지
# 목적: OneDrive 동기화로 인한 패키지 증발/소스 되돌림 문제를 컨테이너 격리로 근본 차단.
#   - 의존성 + 소스를 이미지에 고정 (code-in-image)
#   - 2.8GB data/ 는 런타임 볼륨 마운트 (이미지에 굽지 않음)
FROM python:3.12-slim

# 시스템 의존성: 일부 패키지 소스 빌드(build-essential) + OpenMP 런타임(libgomp1)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/data/.hf_cache

WORKDIR /app

# 1) 의존성 먼저 설치 — 소스만 바뀌면 이 레이어는 캐시 재사용 (재빌드 빠름)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 2) 소스 코드 이미지에 포함 (.dockerignore가 data/·.venv·.env 등 제외)
COPY . .

EXPOSE 8501

# Streamlit 헬스체크 (컨테이너 정상 기동 확인)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
