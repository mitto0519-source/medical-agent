# setup_autostart.ps1
# Medical-Agent 자동 동기화를 Windows 시작 프로그램으로 등록
# 관리자 권한 없이도 실행 가능 (현재 사용자 기준)

$TaskName = "MedicalAgent-AutoSync"
$ScriptPath = "$PSScriptRoot\..\scripts\auto_sync.py"
$ScriptPath = (Resolve-Path $ScriptPath).Path
$PythonPath = (Get-Command python).Source

Write-Host "=== Medical-Agent 자동 동기화 시작 프로그램 등록 ===" -ForegroundColor Cyan
Write-Host "  스크립트: $ScriptPath"
Write-Host "  Python: $PythonPath"

# 기존 작업 제거
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 작업 설정
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory (Split-Path $ScriptPath -Parent)

# 로그인 시 자동 시작
$Trigger = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Medical-Agent Git 자동 동기화 데몬" | Out-Null

Write-Host "`n✓ 등록 완료! 다음 로그인부터 자동 시작됩니다." -ForegroundColor Green
Write-Host "`n지금 바로 시작하려면:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow

# 지금 바로 시작 여부 묻기
$now = Read-Host "`n지금 바로 시작할까요? (Y/N)"
if ($now -eq "Y" -or $now -eq "y") {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "✓ 자동 동기화 시작됨." -ForegroundColor Green
    Write-Host "  로그 확인: $PSScriptRoot\sync.log"
}
