# 외부 공개 배포 가이드

> **사용자 시나리오 (2026-05-30)**: 외부 사람이 Streamlit 주소를 치면 GitHub 로그인을 요구당함.
> 의도: 누구나 로그인 화면을 볼 수 있고, **가입·초대된 사람만 들어올 수 있게** 하고 싶음.

## 진단

우리 앱은 이미 `_login_gate()`(`app/streamlit_app.py`)로 자체 로그인을 갖춤. 이메일 기반 + `src/auth/users.py` 가 등록된 사용자만 통과시킴. 따라서 코드 레벨에서는 "가입·초대된 사람만 로그인" 구조가 이미 완성.

**문제는 배포 계층**:

| 배포 위치 | 외부에서 접근 시 | 우리 `_login_gate` 도달 여부 |
|---|---|---|
| 로컬 docker (현재) | 외부 인터넷에서 접근 불가 (localhost 한정) | ❌ 외부 접근 불가 |
| Streamlit Community Cloud (private) | **GitHub OAuth 화면** 먼저 통과해야 함 | ❌ 우리 화면 못 봄 |
| Streamlit Community Cloud (public) | 우리 sapphire 로그인 화면 바로 표시 | ✅ |
| Railway / Render | 공개 URL → 우리 로그인 화면 바로 | ✅ |
| Cloudflare Tunnel | 공개 URL → 우리 로그인 화면 바로 | ✅ |

따라서 해결은 "**배포 계층을 공개(public)로 바꾸면**" 끝납니다. 아래 3가지 옵션.

---

## 옵션 A — Streamlit Community Cloud의 앱을 public으로 (가장 빠름, 5분)

이미 share.streamlit.io에 deploy된 상태라면:

1. https://share.streamlit.io 에 GitHub로 로그인
2. 본인 앱 카드 → 우측 점 3개 메뉴 → **Settings**
3. **Sharing** 탭 → **"Anyone with the link can view"** 선택
4. Save

이 후로는 외부 사람이 URL을 치면 GitHub 로그인 없이 **우리 sapphire 로그인 화면**(이메일 입력)이 바로 떠요. 등록 안 된 이메일은 `_login_gate`에서 "등록되지 않은 이메일입니다." 차단.

**주의**: Streamlit Cloud의 무료 플랜은 동시 사용자/CPU 제한 있음. 본격 운영은 옵션 B/C 권장.

---

## 옵션 B — Railway 배포 (`railway.toml` 이미 준비됨)

`railway.toml`이 이미 있어 푸시 한 번이면 끝납니다.

```bash
# 1) Railway 계정 만들기 + GitHub 연결
#    https://railway.app → New Project → Deploy from GitHub repo

# 2) 환경변수 등록 (Railway 콘솔 → Variables)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_DB_URL=...

# 3) Deploy 자동 — push to main triggers build
git push origin master

# 4) Public domain 발급 — Railway → Settings → Networking → "Generate Domain"
```

배포되면 `your-app.up.railway.app` URL로 외부 누구나 접근 → 우리 `_login_gate` 화면 표시 → 등록된 이메일만 통과.

---

## 옵션 C — 로컬 docker + Cloudflare Tunnel (서버 운영비 0원)

PC를 안 끄는 경우 가장 저렴.

```bash
# 1) cloudflared 설치 (Windows)
winget install --id=Cloudflare.cloudflared -e

# 2) 무료 tunnel 생성 + 우리 docker 8501 노출
cloudflared tunnel --url http://localhost:8501
# → 출력에 https://<random>.trycloudflare.com 양식 URL이 나옴
```

그 URL을 사용자에게 보내면 외부에서 바로 접근. 우리 로그인 화면 → 등록 이메일만 통과.

**한계**: PC 꺼지면 끊김. 영구 URL이 필요하면 무료 Cloudflare 계정 + 도메인 연결.

---

## 로컬 docker ↔ 클라우드 프로젝트 공유 (2026-05-30 신규)

KYRBS .sav 원시자료(약 1.7GB)는 GitHub에 못 올리는데, **이미 작성한 논문 프로젝트**는 어디서든 보고
첨삭 가능해야 합니다. 두 가지 자동화:

### A. Supabase 자동 동기 (권장)

로컬 docker에서 작업한 프로젝트는 `_save_project` 호출 시 자동으로 Supabase의 `ma_working_papers`
테이블에 동기됩니다. 클라우드에서 **같은 user_email로 로그인하면 ez_home에 ☁ Cloud 배지와 함께
자동 표시**되고, 클릭하면 작업실에서 chat 첨삭 가능 (KYRBS 통계 도구만 graceful fail, LLM 본문
재작성·STROBE·consistency는 정상).

Streamlit Cloud Secrets 또는 Railway 환경변수에 동일 키 설정:
```
SUPABASE_DB_URL=postgresql://postgres.xxx:pwd@aws-x.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
```

### B. .json 파일 직접 import (Supabase 없을 때)

로컬 docker 토픽바의 🔗 Share 버튼으로 프로젝트 JSON을 다운로드해서, 클라우드의 ez_home 입력바
아래 📎 파일 첨부로 그 .json을 올리면 자동으로 작업실에 import됩니다.

---

## 사용자 등록(초대) 방법

배포 위치와 무관하게, 신규 사용자를 추가하려면:

### 방법 1 — admin 페이지 (Streamlit UI)

`super_admin` 권한(`mitto0519@gmail.com`, `misslonghorn46@gmail.com`)으로 로그인 후 사이드바
"사용자 관리"에서 이메일 추가.

### 방법 2 — CLI (직접)

```bash
docker exec medical-agent python -c "
from src.auth.users import add_user
add_user(email='new.colleague@example.com', name='홍길동', role='viewer')
"
```

### 방법 3 — Supabase 콘솔

`ma_users` 테이블에 직접 INSERT — `cloud_available() == True`인 환경.

---

## 권장 (실제 운영)

1. **즉시 외부 공개가 필요하면** → 옵션 A (Streamlit Cloud public, 5분)
2. **장기 운영 (1년+) + 데이터 영속** → 옵션 B (Railway, 월 $5)
3. **연구실 내부 시연만** → 옵션 C (Cloudflare Tunnel, 무료)

## 확인 체크리스트

배포 후 다음 3개가 외부 브라우저에서 정상 작동하면 끝:

- [ ] URL 접속 시 sapphire 보라 배경 + 🔬 Medical-Agent 카드가 보임 (chrome 노출 X)
- [ ] 등록 안 된 이메일 입력 시 "등록되지 않은 이메일입니다." 차단
- [ ] 등록된 이메일 입력 → ez_home(/ez_home) 자동 이동 + Build로 5섹션 논문 생성
