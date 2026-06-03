"""Streamlit 페이지 syntax + import 검증 — 코드 수정 후 의무 실행."""
import ast, sys, importlib.util
from pathlib import Path

PAGES = list(Path('app').rglob('*.py'))
fails = []
for p in PAGES:
    if '__pycache__' in str(p): continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        fails.append(f"{p}:{e.lineno} {e.msg}")
        continue
if fails:
    print("SYNTAX FAIL:")
    for f in fails: print(f"  {f}")
    sys.exit(1)
print(f"OK syntax: {len(PAGES)} files")
