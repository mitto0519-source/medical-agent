@echo off
:: Medical-Agent 자동 동기화 시작
:: 더블클릭하면 백그라운드에서 실행됩니다

set BASE=%~dp0..
set LOGFILE=%BASE%\scripts\sync.log

echo [%date% %time%] 자동 동기화 시작 >> "%LOGFILE%"

:: 이미 실행 중인지 확인
tasklist /fi "imagename eq python.exe" /fo csv | findstr /i "auto_sync" >nul 2>&1
if %errorlevel% == 0 (
    echo 자동 동기화가 이미 실행 중입니다.
    timeout /t 2 >nul
    exit /b 0
)

:: 백그라운드로 실행 (창 숨김)
start "" /min python "%BASE%\scripts\auto_sync.py"

echo ✓ Medical-Agent 자동 동기화가 시작되었습니다.
echo   로그: %LOGFILE%
timeout /t 3 >nul
