# Medical-Agent — pre-prompt memory inject hook
#
# Claude Code의 user-prompt-submit 양식 hook으로 호출되어, 매 사용자 입력 직전에
# 핵심 메모리/룰 + data/ 인벤토리를 stdout으로 prepend한다.
# Background polling은 불가능 — Claude는 stateless. 이게 가장 가까운 양식.

# UTF-8 강제 (한국어 mojibake 차단)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\mitto\OneDrive\Desktop\Medical-Agent"

# ── 1. 핵심 룰 (압축 — 토큰 절약) ──────────────────────────────
Write-Output "## AUTO-RECALL (pre-prompt)"
Write-Output ""
Write-Output "ABSOLUTE: 대충/거짓말/일안함/뻥치기 금지. 길더라도 시킨대로 무조건 다."
Write-Output "DATA INVENTORY: 'X 없다' 진단 전 MEMORY.md grep + ls data/ + ARCHITECTURE grep 의무."
Write-Output "ORGANISM: 새 모듈은 선행 trigger / 후행 output / events 기록 / 자가발전 회로 4가지 확보."
Write-Output "WIRING: 작업 완료 = '파일 작성'이 아니라 '실제 호출되어 동작'. audit_wiring 실행."
Write-Output ""

# ── 2. data/ 인벤토리 (한 줄로) — 자주 까먹는 자산 위치 ─────────
$dataDir = Join-Path $root "data"
if (Test-Path $dataDir) {
    Write-Output "## data/ INVENTORY (부재 단정 차단용)"
    $items = Get-ChildItem $dataDir -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $size = 0
            try {
                $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                         Measure-Object -Sum Length).Sum / 1MB
            } catch {}
            if ($size -ge 1) {
                "{0}({1:N0}M)" -f $_.Name, $size
            }
        }
    Write-Output ($items -join " ")
    Write-Output ""
}

# ── 3. ARCHITECTURE.md 섹션 헤더 (모듈 위치 강제 인지) ──────────
$arch = Join-Path $root "ARCHITECTURE.md"
if (Test-Path $arch) {
    Write-Output "## ARCHITECTURE.md sections"
    $lines = Get-Content $arch -Encoding UTF8 -ErrorAction SilentlyContinue |
        Select-String -Pattern "^### \d+\." |
        Select-Object -First 16 -ExpandProperty Line
    Write-Output ($lines -join " | ")
    Write-Output ""
}

# ── 4. 최근 change_log 1줄 (마지막 작업이 뭐였는지) ─────────────
$changeLog = Join-Path $root "data/change_log/history.json"
if (Test-Path $changeLog) {
    try {
        $j = Get-Content $changeLog -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($j -is [Array] -and $j.Count -gt 0) {
            $last = $j[-1]
            Write-Output "## LAST change_log"
            Write-Output ("{0}: {1}" -f $last.title, ($last.description -replace "`n", " ").Substring(0, [Math]::Min(120, ($last.description).Length)))
            Write-Output ""
        }
    } catch {}
}

Write-Output "## END pre-prompt"
