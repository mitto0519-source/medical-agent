# web/ Vercel 배포 가이드 (mitto 결정 = 분리: HF=Streamlit, Vercel=Next.js)

> ★ 도메인 안내: 이 문서의 `{your-project-name}.vercel.app`은 placeholder입니다.
> mitto가 `vercel link` 한 뒤 본인 계정에서 자동 결정되는 도메인입니다 (예: cave87-medical-agent-web.vercel.app).
> `medical-agent.vercel.app`은 다른 사용자가 이미 차지한 별개 사이트 — 그 URL 사용 X.

## 0. 사전 (mitto 로컬)

```powershell
# Node.js PATH 영구 적용 (관리자 PowerShell)
[System.Environment]::SetEnvironmentVariable("PATH",
  $env:PATH + ";C:\Program Files\nodejs",
  "Machine")

# 새 PowerShell 열고
cd web
npm install
npm run dev    # http://localhost:3000 — FastAPI는 별도 (uvicorn api.main:app --port 8000)
```

## 1. Vercel 연결

```bash
# Vercel CLI (한 번만)
npm i -g vercel
cd web
vercel login
vercel link               # 프로젝트 연결 (cave87/medical-agent-web)
vercel env add NEXT_PUBLIC_API_BASE production
  # 입력: https://cave87-medical-agent.hf.space (HF의 FastAPI 라우트)
vercel env add NEXT_PUBLIC_SITE_URL production
  # 입력: https://{your-project-name}.vercel.app
```

## 2. 백엔드 = HF Space (FastAPI + Streamlit 공존)

현재 HF Space는 Streamlit (port 8501)만 띄움. FastAPI 22 라우트는 같은 컨테이너에서 별도 프로세스로 띄울 수 있도록 Dockerfile 보강 필요 (다음 사이클):

```dockerfile
# 컨테이너 시작 시 두 프로세스 동시
CMD bash -c "uvicorn api.main:app --host 0.0.0.0 --port 8000 & \
             streamlit run app/streamlit_app.py --server.port 8501 --server.address 0.0.0.0"
```

또는 별도 HF Space (cave87/medical-agent-api)를 만들어 FastAPI만 띄움.

## 3. 배포 (자동)

```bash
git push origin master  # → Vercel webhook이 자동 빌드/배포 (production)
```

GitHub 연결돼 있으면 master push → Vercel 자동 빌드.

## 4. 검증

```bash
# 공개 페이지
curl https://{your-project-name}.vercel.app/                  # 랜딩
curl https://{your-project-name}.vercel.app/llms.txt          # GEO
curl https://{your-project-name}.vercel.app/sitemap.xml       # 동적 sitemap
curl https://{your-project-name}.vercel.app/research/38542705 # 동적 paper
curl https://{your-project-name}.vercel.app/concept/C_adolescent

# 앱 (로그인 필요)
# https://{your-project-name}.vercel.app/app
```

## 5. 분리 구조 결과

```
huggingface.co/spaces/cave87/medical-agent  ← Streamlit (현 8501) + FastAPI (8000 후속)
  ↓ (SSE /chat)
{your-project-name}.vercel.app                     ← Next.js (web/) — 공개+앱 동시
  · / /research /concept /methods            (SEO/GEO, ISR)
  · /app (3-pane chat, JWT)                  (noindex)
  · llms.txt + JSON-LD + sitemap (10K+2K)
```
