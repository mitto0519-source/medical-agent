# Medical-Agent — pre-prompt memory inject hook (PowerShell)
#
# 매 사용자 입력 직전에 호출되어, 자주 까먹는 핵심 메모리/룰을
# Claude 컨텍스트에 prepend한다. Background polling이 아니라
# user-turn 단위 자동 reload.
#
# 출력 = stdout. Claude Code가 이를 user prompt 앞에 prepend.

$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\mitto\OneDrive\Desktop\Medical-Agent"
$memDir = "C:\Users\mitto\.claude\projects\c--Users-mitto-OneDrive-Desktop-Medical-Agent\memory"

Write-Output "=== AUTO-MEMORY RECALL (pre-prompt hook, 매 입력시 자동) ==="
Write-Output ""

# 1. 절대 규칙 — no-excuses
$abs = Join-Path $memDir "feedback_no_excuses_absolute_rule.md"
if (Test-Path $abs) {
    Write-Output "[ABSOLUTE RULE — feedback_no_excuses_absolute_rule.md]"
    $body = Get-Content $abs -Raw
    # frontmatter 제외하고 본문만
    $stripped = $body -replace "(?s)^---.*?---\s*", ""
    Write-Output ($stripped.Substring(0, [Math]::Min(700, $stripped.Length)))
    Write-Output ""
}

# 2. Data inventory protocol — 부재 진단 전 grep 의무
$di = Join-Path $memDir "feedback_data_inventory_protocol.md"
if (Test-Path $di) {
    Write-Output "[DATA INVENTORY PROTOCOL — 부재 진단 전 grep 의무]"
    $body = Get-Content $di -Raw
    $stripped = $body -replace "(?s)^---.*?---\s*", ""
    Write-Output ($stripped.Substring(0, [Math]::Min(600, $stripped.Length)))
    Write-Output ""
}

# 3. Organism flow
$org = Join-Path $memDir "feedback_organism_flow.md"
if (Test-Path $org) {
    Write-Output "[ORGANISM FLOW — 선후행 연결 필수]"
    $body = Get-Content $org -Raw
    $stripped = $body -replace "(?s)^---.*?---\s*", ""
    Write-Output ($stripped.Substring(0, [Math]::Min(400, $stripped.Length)))
    Write-Output ""
}

# 4. data/ 인벤토리 (자주 까먹는 자산 위치)
$dataDir = Join-Path $root "data"
if (Test-Path $dataDir) {
    Write-Output "[CURRENT data/ INVENTORY — '없다' 진단 전 확인]"
    Get-ChildItem $dataDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $size = 0
        try {
            $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                     Measure-Object -Sum Length).Sum / 1MB
        } catch {}
        Write-Output ("  data/{0}  {1:N1} MB" -f $_.Name, $size)
    }
    Write-Output ""
}

# 5. ARCHITECTURE.md 섹션 인덱스 (해당 모듈 찾기 강제)
$arch = Join-Path $root "ARCHITECTURE.md"
if (Test-Path $arch) {
    Write-Output "[ARCHITECTURE.md section index — 새 모듈 만들기 전 확인]"
    Select-String -Path $arch -Pattern "^### \d+\." -ErrorAction SilentlyContinue |
        Select-Object -First 20 | ForEach-Object { Write-Output $_.Line }
    Write-Output ""
}

Write-Output "=== END AUTO-MEMORY RECALL ==="
Write-Output ""
