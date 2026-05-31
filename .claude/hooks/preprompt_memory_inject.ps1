# Medical-Agent — pre-prompt memory inject hook
# Outputs critical rules + data/ inventory to stdout for prepend.
# English-only to avoid cp949/UTF-8 round-trip mojibake.

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\mitto\OneDrive\Desktop\Medical-Agent"

Write-Output "## AUTO-RECALL (pre-prompt hook)"
Write-Output ""
Write-Output "RULE-1 ABSOLUTE: No lies, no laziness, no excuses. Do exactly what user asked, in order, completely."
Write-Output "RULE-2 DATA-INVENTORY: Before claiming 'X does not exist' or 'Y is missing', MUST grep MEMORY.md + ls data/ + grep ARCHITECTURE.md."
Write-Output "RULE-3 ORGANISM: New module needs 4 wires: upstream trigger / downstream output / events log / self-improvement loop."
Write-Output "RULE-4 WIRING: 'task done' means 'actually called and works', not 'file written'. Run audit_wiring.py."
Write-Output ""

# data/ inventory — surfaces forgotten assets
$dataDir = Join-Path $root "data"
if (Test-Path $dataDir) {
    Write-Output "## data/ INVENTORY (against 'missing' misjudgments)"
    $rows = @()
    $dirs = Get-ChildItem $dataDir -Directory -ErrorAction SilentlyContinue
    foreach ($d in $dirs) {
        $bytes = 0
        try {
            $files = Get-ChildItem $d.FullName -Recurse -File -ErrorAction SilentlyContinue
            foreach ($f in $files) { $bytes += $f.Length }
        } catch {}
        $mb = [Math]::Round($bytes / 1MB, 0)
        if ($mb -ge 1) {
            $rows += ("{0}={1}MB" -f $d.Name, $mb)
        }
    }
    Write-Output ($rows -join " ")
    Write-Output ""
}

# ARCHITECTURE.md section headers — module location enforcement
$arch = Join-Path $root "ARCHITECTURE.md"
if (Test-Path $arch) {
    Write-Output "## ARCHITECTURE.md sections (grep before creating new module)"
    $hdrs = @()
    $lines = Get-Content $arch -Encoding UTF8 -ErrorAction SilentlyContinue
    foreach ($ln in $lines) {
        if ($ln -match "^### \d+\.") {
            $hdrs += $ln.Substring(0, [Math]::Min(80, $ln.Length))
            if ($hdrs.Count -ge 16) { break }
        }
    }
    Write-Output ($hdrs -join " | ")
    Write-Output ""
}

# MEMORY.md index — first 6 entries (key rules user reminded recently)
$memIdx = "C:\Users\mitto\.claude\projects\c--Users-mitto-OneDrive-Desktop-Medical-Agent\memory\MEMORY.md"
if (Test-Path $memIdx) {
    Write-Output "## MEMORY.md top entries"
    $cnt = 0
    $lines = Get-Content $memIdx -Encoding UTF8 -ErrorAction SilentlyContinue
    foreach ($ln in $lines) {
        if ($ln.StartsWith("- [")) {
            $head = $ln
            if ($head.Length -gt 140) { $head = $head.Substring(0, 140) + "..." }
            Write-Output $head
            $cnt += 1
            if ($cnt -ge 6) { break }
        }
    }
    Write-Output ""
}

# CURRENT_STATE.json — authoritative runtime snapshot
$state = Join-Path $root "CURRENT_STATE.json"
if (Test-Path $state) {
    Write-Output "## CURRENT_STATE.json (authoritative runtime memory)"
    Get-Content $state -Encoding UTF8 -Raw
    Write-Output ""
}

# ARCHITECTURE_SHORT.md — module map summary
$archShort = Join-Path $root "ARCHITECTURE_SHORT.md"
if (Test-Path $archShort) {
    Write-Output "## ARCHITECTURE_SHORT.md"
    Get-Content $archShort -Encoding UTF8 -Raw
    Write-Output ""
}

# FAILURE_PATTERNS.md — common failures and prevention
$failPat = Join-Path $root "FAILURE_PATTERNS.md"
if (Test-Path $failPat) {
    Write-Output "## FAILURE_PATTERNS.md (prevent repeat)"
    Get-Content $failPat -Encoding UTF8 -Raw
    Write-Output ""
}

Write-Output "## END pre-prompt — Read above before answering. Never claim 'missing' without grep."
