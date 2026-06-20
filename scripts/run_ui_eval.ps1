# scripts/run_ui_eval.ps1 — ui_eval 실 실행 (★ 온라인 우선)
#
# 외부 LLM 통찰(2026-06-20): "이 프로젝트 실행·검증 기본값이 전부 '로컬 우선'으로
# 깔려 있는데, 현실은 '온라인 우선'. ui_eval BASE를 env로 빼서 HF 직접도메인 기본값으로,
# 라이브에서 돌려라."
#
# Playwright + 인터넷이면 동작. docker/streamlit/localhost 전부 불필요.
#
# 사용:
#   .\scripts\run_ui_eval.ps1                            # 라이브 HF 가이드 출력
#   .\scripts\run_ui_eval.ps1 -Run                       # 라이브 HF에 실 실행 (기본)
#   .\scripts\run_ui_eval.ps1 -Run -Local                # 로컬 docker (옛 양식)
param(
    [switch]$Run,
    [switch]$Local,
    [string]$Base = "https://cave87-medical-agent.hf.space"
)

Write-Host "=== ui_eval 실행 가이드 (★ 온라인 우선) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "이 프로젝트는 온라인 우선:" -ForegroundColor Yellow
Write-Host "  검사 대상 = 인터넷의 라이브 HF Space"
Write-Host "  도구 = Playwright (네 머신에서 브라우저 자동화)"
Write-Host "  로컬 앱(docker/streamlit) 불필요"
Write-Host ""
Write-Host "1. Playwright (한 번만):" -ForegroundColor Yellow
Write-Host "   pip install playwright"
Write-Host "   playwright install chromium"
Write-Host ""
Write-Host "2. BASE URL (★ 직접도메인 — iframe 래퍼 X):" -ForegroundColor Yellow
Write-Host "   기본: https://cave87-medical-agent.hf.space"
Write-Host "   X    : https://huggingface.co/spaces/cave87/medical-agent  ← iframe, Playwright가 내부 못 봄"
Write-Host ""
Write-Host "3. HF Space RUNNING 확인 (슬립이면 콜드스타트 대기):" -ForegroundColor Yellow
Write-Host "   start https://cave87-medical-agent.hf.space"
Write-Host "   → 로그인 화면 뜨면 정상. 빌드 중이면 옛 화면 = 푸시 sha 일치 확인 필요."
Write-Host ""
Write-Host "4. ui_eval 실행 (기본 = 라이브 HF):" -ForegroundColor Yellow
Write-Host "   python scripts/ui_eval.py"
Write-Host "   # 또는 env 명시:"
Write-Host "   `$env:UI_EVAL_BASE = '$Base'"
Write-Host "   python scripts/ui_eval.py"
Write-Host ""
Write-Host "현재 assertion (J1~J7):" -ForegroundColor Green
Write-Host "  J1-J3 : 로그인 / 페이지 렌더 / 채팅→Introduction"
Write-Host "  J4    : KYRBS survey-weighted logistic (★ J4 PASS = 통계 엔진 살아있음)"
Write-Host "  J5    : 주제 잠금 (Decision Lock — ZCB 회귀 X)"
Write-Host "  J6    : 데이터셋 인지 (DATASETS 블록)"
Write-Host "  J7 ★  : KNHANES UPF × MASLD (RESEARCH_STATE §1.5 + 도메인 함수 실작동)"
Write-Host ""

if ($Run) {
    Write-Host "=== 실 실행 ===" -ForegroundColor Cyan
    if ($Local) {
        $env:UI_EVAL_BASE = "http://localhost:8501"
        Write-Host "★ 로컬 모드: localhost:8501 (docker compose up -d 먼저)" -ForegroundColor Yellow
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -TimeoutSec 5 -ErrorAction Stop
            Write-Host "  ✓ Streamlit 헬스체크 OK" -ForegroundColor Green
        } catch {
            Write-Host "  ✗ Streamlit 안 떠있음 — docker compose up -d 먼저" -ForegroundColor Red
            exit 1
        }
    } else {
        $env:UI_EVAL_BASE = $Base
        Write-Host "★ 라이브 HF 모드: $Base" -ForegroundColor Yellow
        try {
            $r = Invoke-WebRequest -Uri $Base -TimeoutSec 15 -ErrorAction Stop
            Write-Host "  ✓ HF Space 응답 OK (status=$($r.StatusCode))" -ForegroundColor Green
        } catch {
            Write-Host "  ✗ HF Space 응답 없음 — 빌드 중이거나 슬립일 수 있음" -ForegroundColor Yellow
            Write-Host "    잠시 대기 후 재시도 권장" -ForegroundColor Yellow
        }
    }
    Write-Host "ui_eval 실행..."
    python scripts/ui_eval.py
    Write-Host ""
    Write-Host "결과: scripts/ui_eval_outputs/report.md" -ForegroundColor Green
}
