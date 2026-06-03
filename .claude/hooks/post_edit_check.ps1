# Post-edit self-check hook — Edit/Write 직후 자동 실행
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = "SilentlyContinue"
Set-Location "C:\Users\mitto\OneDrive\Desktop\Medical-Agent"

$failed = $false
$failFlag = "0"

# 1. Streamlit 17 페이지 syntax
$syn = & python "scripts\check_streamlit_syntax.py" 2>&1
if ($LASTEXITCODE -ne 0) {
    $failed = $true
    $failFlag = "1"
    Write-Output "SYNTAX FAIL:"
    Write-Output $syn
}

# 2. 자가-loop 회로 강제 발화: events + self_model + memory.router
$pyCode = @"
import sys; sys.path.insert(0,'.')
ok = []
try:
    from src.runtime import events as _e
    _e.append(type='code_edit', payload={'failed': bool(int('$failFlag')), 'src':'post_edit_hook'})
    ok.append('events')
except Exception as ex: print(f'events FAIL: {ex}')
try:
    from src.memory import self_model as _sm
    _sm.refresh()
    ok.append('self_model')
except Exception as ex: print(f'self_model FAIL: {ex}')
try:
    from src.memory import router as _mr
    txt = 'post_edit syntax_failed=' + ('Y' if bool(int('$failFlag')) else 'N')
    _mr.write(txt, type='episodic', source='post_edit_hook')
    ok.append('memory.router')
except Exception as ex: print(f'memory.router FAIL: {ex}')
print('circuits OK:', ok)
"@
& python -c $pyCode

if ($failed) { exit 2 } else { exit 0 }
