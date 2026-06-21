# scripts/onedrive_exit.ps1 - OneDrive exit final (run after this session ends).
#
# v2 (2026-06-21): KFM redirect handling + ASCII output (PS encoding fix).
#
# Usage:
#   1) Close Claude session
#   2) Open new PowerShell
#   3) cd to project (either OneDrive path or C:\dev)
#   4) .\scripts\onedrive_exit.ps1

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== OneDrive exit final ===" -ForegroundColor Cyan
Write-Host ""

# Resolve real Desktop path (KFM-aware) - .NET API returns true location
$realDesktop = [Environment]::GetFolderPath('Desktop')
Write-Host "Real Desktop (KFM-resolved): $realDesktop" -ForegroundColor Gray

# Source: OneDrive Medical-Agent (current location)
$src = "$env:OneDrive\Desktop\Medical-Agent"
$dst = "C:\dev\Medical-Agent"

if (-not (Test-Path $src)) {
    Write-Host "OK - OneDrive folder already removed: $src" -ForegroundColor Green
    Write-Host "  Migration already done. Exit." -ForegroundColor Yellow
    exit 0
}
if (-not (Test-Path $dst)) {
    Write-Host "FAIL - C:\dev folder missing: $dst" -ForegroundColor Red
    Write-Host "  Run robocopy mirror first." -ForegroundColor Red
    exit 1
}

# 1) Last sync (this session changes -> C:\dev)
Write-Host ""
Write-Host "Step 1/4: Last sync (OneDrive -> C:\dev)" -ForegroundColor Yellow
robocopy $src $dst /MIR `
    /XD ".venv" "data\.hf_cache" "node_modules" ".next" "data\.chroma" "__pycache__" `
    /XF "*.db-wal" "*.db-shm" `
    /NP /NDL /NJH /R:1 /W:1 /MT:8 | Select-Object -Last 3
$rc = $LASTEXITCODE
if ($rc -ge 8) {
    Write-Host "  FAIL robocopy (exit $rc)" -ForegroundColor Red
    exit 1
}
Write-Host "  OK sync done (robocopy exit $rc - 0-7 is success)" -ForegroundColor Green

# 2) Desktop shortcut (use real Desktop path - KFM aware)
Write-Host ""
Write-Host "Step 2/4: Desktop shortcut" -ForegroundColor Yellow
$lnk = Join-Path $realDesktop "Medical-Agent.lnk"
Write-Host "  Target: $lnk" -ForegroundColor Gray
if (Test-Path $lnk) { Remove-Item $lnk -Force }
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($lnk)
$Shortcut.TargetPath = "C:\dev\Medical-Agent"
$Shortcut.IconLocation = "C:\Windows\System32\imageres.dll,3"
$Shortcut.Save()
if (Test-Path $lnk) {
    Write-Host "  OK shortcut created" -ForegroundColor Green
} else {
    Write-Host "  WARN shortcut save failed - skip" -ForegroundColor Yellow
}

# 3) Rename OneDrive folder (backup - don't delete yet)
Write-Host ""
Write-Host "Step 3/4: Rename OneDrive folder (backup safe)" -ForegroundColor Yellow
$date = Get-Date -Format "yyyy-MM-dd"
$oldName = "_Medical-Agent_OLD_$date"
$newPath = "$env:OneDrive\Desktop\$oldName"
if (Test-Path $newPath) {
    Write-Host "  WARN backup folder already exists - skip" -ForegroundColor Yellow
} else {
    try {
        Rename-Item $src $oldName -Force -ErrorAction Stop
        Write-Host "  OK renamed: Medical-Agent -> $oldName" -ForegroundColor Green
    } catch {
        Write-Host "  WARN rename failed (file in use?): $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  Try manually after closing all apps using this folder" -ForegroundColor Yellow
    }
}

# 4) Verify C:\dev\Medical-Agent
Write-Host ""
Write-Host "Step 4/4: Verify C:\dev\Medical-Agent" -ForegroundColor Yellow
Set-Location $dst
if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" -c "import sys; print(f'  python: {sys.executable}')"
} else {
    Write-Host "  WARN .venv missing - run: python -m venv .venv" -ForegroundColor Yellow
}
$remote = (git remote -v 2>&1 | Select-Object -First 1)
Write-Host "  git remote: $remote" -ForegroundColor Gray
$branch = (git branch --show-current 2>&1)
Write-Host "  branch: $branch" -ForegroundColor Gray

# Summary
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "From now on:" -ForegroundColor Green
Write-Host "  - Desktop shortcut 'Medical-Agent' -> C:\dev\Medical-Agent" -ForegroundColor White
Write-Host "  - PowerShell: cd C:\dev\Medical-Agent" -ForegroundColor White
Write-Host "  - Activate venv: .venv\Scripts\activate" -ForegroundColor White
Write-Host ""
Write-Host "After 2-3 days of safe verification, delete OneDrive backup:" -ForegroundColor Yellow
Write-Host "  Remove-Item '$newPath' -Recurse -Force" -ForegroundColor Gray
Write-Host ""
Write-Host "OneDrive exit complete." -ForegroundColor Green
