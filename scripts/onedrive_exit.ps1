# scripts/onedrive_exit.ps1 — OneDrive 탈출 마무리 (이번 세션 종료 후 실행).
#
# 사용자 plan Phase 0 마무리. 현재 세션이 OneDrive에서 진행 중이므로 세션 종료 후 실행.
#
# 실행 양식:
#   1) 이번 Claude 세션 완전 종료 (창 닫기 양식)
#   2) 새 PowerShell 열기 (시작메뉴 → 'powershell')
#   3) cd 명령으로 이 폴더 양식 이동: cd "$env:OneDrive\Desktop\Medical-Agent"
#   4) .\scripts\onedrive_exit.ps1 양식 실행
#
# 양식:
#   · 마지막 변경 OneDrive → C:\dev sync (이번 세션 양식 변경 반영)
#   · 바탕화면 단축경로 양식 양식 생성 (Medical-Agent.lnk → C:\dev\Medical-Agent)
#   · OneDrive 폴더 양식 이름 변경 (_Medical-Agent_OLD_YYYY-MM-DD)
#   · 2-3일 안전 양식 확인 후 사용자 본인 양식 통째 삭제

$ErrorActionPreference = "Stop"

Write-Host "=== OneDrive 탈출 마무리 ===" -ForegroundColor Cyan
Write-Host ""

# 1) 안전 양식 확인
$src = "$env:OneDrive\Desktop\Medical-Agent"
$dst = "C:\dev\Medical-Agent"

if (-not (Test-Path $src)) {
    Write-Host "✗ OneDrive 폴더 양식 X: $src" -ForegroundColor Red
    Write-Host "  이미 OneDrive 탈출 양식 완료 — 종료" -ForegroundColor Yellow
    exit 0
}
if (-not (Test-Path $dst)) {
    Write-Host "✗ C:\dev 양식 X: $dst" -ForegroundColor Red
    Write-Host "  이전 세션 양식 robocopy mirror 양식 누락 — 양식 실행 양식 양식 X" -ForegroundColor Red
    exit 1
}

# 2) 마지막 sync (이번 세션 변경 양식 반영)
Write-Host "★ Step 1/4: 마지막 sync (OneDrive → C:\dev)" -ForegroundColor Yellow
robocopy $src $dst /MIR `
    /XD ".venv" "data\.hf_cache" "node_modules" ".next" "data\.chroma" "__pycache__" `
    /XF "*.db-wal" "*.db-shm" `
    /NP /NDL /NJH /R:1 /W:1 /MT:8 | Select-Object -Last 5
$rc = $LASTEXITCODE
if ($rc -ge 8) {
    Write-Host "  ✗ robocopy 실패 (exit $rc)" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ sync 완료 (robocopy exit $rc — 0-7 정상)" -ForegroundColor Green
Write-Host ""

# 3) 바탕화면 단축경로
Write-Host "★ Step 2/4: 바탕화면 단축경로 양식 (Medical-Agent.lnk)" -ForegroundColor Yellow
$lnk = "$env:USERPROFILE\Desktop\Medical-Agent.lnk"
if (Test-Path $lnk) { Remove-Item $lnk -Force }
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($lnk)
$Shortcut.TargetPath = "C:\dev\Medical-Agent"
$Shortcut.IconLocation = "C:\Windows\System32\imageres.dll,3"
$Shortcut.Save()
if (Test-Path $lnk) {
    Write-Host "  ✓ 단축경로 양식 생성: $lnk → $dst" -ForegroundColor Green
}
Write-Host ""

# 4) OneDrive 폴더 양식 이름 변경 (즉시 삭제 X — 안전 양식)
Write-Host "★ Step 3/4: OneDrive 폴더 양식 이름 변경 (백업 양식)" -ForegroundColor Yellow
$date = Get-Date -Format "yyyy-MM-dd"
$oldName = "_Medical-Agent_OLD_$date"
$newPath = "$env:OneDrive\Desktop\$oldName"
if (Test-Path $newPath) {
    Write-Host "  ⚠ 백업 폴더 양식 이미 존재 — 양식 skip" -ForegroundColor Yellow
} else {
    Rename-Item $src $oldName -Force
    Write-Host "  ✓ 이름 변경: Medical-Agent → $oldName" -ForegroundColor Green
}
Write-Host ""

# 5) C:\dev에서 .venv 양식 검증
Write-Host "★ Step 4/4: C:\dev\Medical-Agent .venv + git 양식 검증" -ForegroundColor Yellow
Set-Location $dst
if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" -c "import sys; print(f'  ✓ python: {sys.executable}')"
} else {
    Write-Host "  ⚠ .venv 양식 X — python -m venv .venv 양식 양식" -ForegroundColor Yellow
}
$remote = git remote -v 2>&1 | Select-Object -First 1
Write-Host "  ✓ git remote: $remote" -ForegroundColor Green
$branch = git branch --show-current 2>&1
Write-Host "  ✓ branch: $branch" -ForegroundColor Green
Write-Host ""

# 6) 정리
Write-Host "=== 완료 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "이제 부터 작업 양식:" -ForegroundColor Green
Write-Host "  · 바탕화면 'Medical-Agent' 단축경로 양식 더블클릭 → C:\dev\Medical-Agent로 이동" -ForegroundColor White
Write-Host "  · 새 PowerShell: cd C:\dev\Medical-Agent" -ForegroundColor White
Write-Host "  · .venv 활성화: .venv\Scripts\activate" -ForegroundColor White
Write-Host ""
Write-Host "2-3일 안전 양식 확인 후 OneDrive 백업 양식 삭제:" -ForegroundColor Yellow
Write-Host "  Remove-Item '$newPath' -Recurse -Force" -ForegroundColor Gray
Write-Host ""
Write-Host "OneDrive 탈출 — 사고 영구 종료." -ForegroundColor Green
