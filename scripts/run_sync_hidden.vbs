' run_sync_hidden.vbs — 창 없이 Python 자동 동기화 실행
Dim WShell
Set WShell = CreateObject("WScript.Shell")

Dim base
base = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
base = CreateObject("Scripting.FileSystemObject").GetParentFolderName(base)

Dim cmd
cmd = "python """ & base & "\scripts\auto_sync.py"""

' 0 = 창 숨김
WShell.Run cmd, 0, False
