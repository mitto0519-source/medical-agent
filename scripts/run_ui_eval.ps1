# scripts/run_ui_eval.ps1 — ui_eval 실 실행 PowerShell 가이드 (mitto 환경)
#
# 외부 LLM 통찰(2026-06-19): "앱 먼저 띄우고 → 브라우저 확인 → 그다음 ui_eval".
# 순서 어기면 항상 connection hang. ui_eval은 호스트(저장소 루트)에서, docker는 앱만.
#
# 사용:
#   .\scripts\run_ui_eval.ps1            # 가이드 출력
#   .\scripts\run_ui_eval.ps1 -Run        # 실 실행
param([switch]$Run)

Write-Host "=== ui_eval 실행 가이드 (저장소 루트에서) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. 저장소 루트 확인:" -ForegroundColor Yellow
Write-Host "   cd C:\Users\mitto\OneDrive\Desktop\Medical-Agent"
Write-Host ""
Write-Host "2. ★ Streamlit 앱 띄우기 (docker 또는 직접):" -ForegroundColor Yellow
Write-Host "   docker compose up -d"
Write-Host "   # 또는 docker 없으면:"
Write-Host "   #   .venv\Scripts\Activate.ps1"
Write-Host "   #   streamlit run app/streamlit_app.py --server.port 8501"
Write-Host ""
Write-Host "3. ★ 브라우저 확인 (이 단계 건너뛰면 connection hang):" -ForegroundColor Yellow
Write-Host "   start http://localhost:8501"
Write-Host "   # 로그인 화면 뜨면 정상. 안 뜨면 docker logs 또는 venv 확인."
Write-Host ""
Write-Host "4. Playwright 의존성 (한 번만):" -ForegroundColor Yellow
Write-Host "   pip install playwright"
Write-Host "   playwright install chromium"
Write-Host ""
Write-Host "5. ★ ui_eval 실행:" -ForegroundColor Yellow
Write-Host "   python scripts/ui_eval.py"
Write-Host "   # → scripts/ui_eval_outputs/report.md + .png 스크린샷"
Write-Host ""
Write-Host "현재 assertion (J1~J7):" -ForegroundColor Green
Write-Host "  J1-J3 : 로그인 / 페이지 렌더 / 채팅→Introduction 채워짐"
Write-Host "  J4    : KYRBS survey-weighted logistic"
Write-Host "  J5    : 주제 잠금 (Decision Lock — 흡연→무관 입력→ZCB 회귀 X)"
Write-Host "  J6    : 데이터셋 인지 (DATASETS 블록 — '어디' 묻지 않음)"
Write-Host "  J7 ★  : KNHANES UPF × MASLD (RESEARCH_STATE §1.5 + 도메인 함수 실작동)"
Write-Host ""

if ($Run) {
    Write-Host "=== 실 실행 ===" -ForegroundColor Cyan
    # 1. 앱 떠있는지 확인
    Write-Host "1. localhost:8501 응답 확인..."
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" `
                                  -TimeoutSec 5 -ErrorAction Stop
        Write-Host "   ✓ Streamlit 헬스체크 OK (status=$($r.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host "   ✗ Streamlit 안 떠있음 — docker compose up -d 먼저!" -ForegroundColor Red
        Write-Host "   [중단] hang 방지" -ForegroundColor Red
        exit 1
    }
    # 2. ui_eval 실행
    Write-Host "2. ui_eval 실행..."
    python scripts/ui_eval.py
    Write-Host ""
    Write-Host "결과: scripts/ui_eval_outputs/report.md" -ForegroundColor Green
}
