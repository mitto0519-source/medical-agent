"""Medical-Agent 전체 서비스 동시 기동 스크립트.

실행:
    python start.py

기동 서비스:
    - Streamlit 웹 UI  →  http://localhost:8501
    - MCP API 서버     →  http://localhost:8765/mcp
"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = sys.executable

STREAMLIT_PORT = int(os.environ.get("STREAMLIT_PORT", 8501))
MCP_PORT = int(os.environ.get("MCP_PORT", 8765))

procs = []


def _validate_env():
    """시작 시 환경변수 검증 — 필수 키 없으면 경고 출력."""
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    from src.config.env import bootstrap
    result = bootstrap(strict=False)

    print("=" * 60)
    print("  Medical-Agent 환경 점검")
    print("=" * 60)

    if result["ok"]:
        providers = result["providers"]
        print(f"  LLM: {'Anthropic Claude ✓' if providers['anthropic'] else ''}"
              f"{'  OpenAI ✓' if providers['openai'] else ''}")
        print(f"  Supabase: {'연결됨 ✓' if providers['supabase'] else '미설정 (로컬 모드)'}")
    else:
        print("  [경고] 필수 환경변수가 설정되지 않았습니다:")
        for m in result["missing"]:
            print(f"    ✗ {m}")
        print(f"\n  → {ROOT}/.env 파일을 확인하세요.")
        print(f"  → 예시: {ROOT}/.env.example")

    for w in result["warnings"]:
        print(f"  ⚠  {w}")
    print("=" * 60 + "\n")

    # 모델 정보 출력
    try:
        from src.config.models import list_available_models
        info = list_available_models()
        active = info.get("active", {})
        print(f"  활성 모델: {active.get('provider', '?')} / {active.get('model', '?')}")
        print(f"  임베딩:   {info.get('embedding', '?')}")
        print("=" * 60 + "\n")
    except Exception:
        pass

    return result["ok"]


def start_streamlit():
    print(f"[Streamlit] 기동 중 → http://localhost:{STREAMLIT_PORT}")
    return subprocess.Popen(
        [
            PYTHON, "-m", "streamlit", "run",
            str(ROOT / "app" / "streamlit_app.py"),
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=ROOT,
    )


def start_mcp():
    print(f"[MCP Server] 기동 중 → http://localhost:{MCP_PORT}/mcp")
    return subprocess.Popen(
        [PYTHON, str(ROOT / "mcp_server.py"), "--port", str(MCP_PORT)],
        cwd=ROOT,
    )


def shutdown(sig, frame):
    print("\n[Shutdown] 서비스 종료 중...")
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    env_ok = _validate_env()

    if not env_ok:
        ans = input("환경변수 문제가 있습니다. 그래도 계속 실행하시겠습니까? [y/N] ").strip().lower()
        if ans != "y":
            sys.exit(1)

    procs.append(start_streamlit())
    time.sleep(1)
    procs.append(start_mcp())

    print("\n" + "=" * 60)
    print("  Medical-Agent 실행 중")
    print("=" * 60)
    print(f"  웹 UI  (브라우저)    : http://localhost:{STREAMLIT_PORT}")
    print(f"  MCP API (에이전트)   : http://localhost:{MCP_PORT}/mcp")
    print("=" * 60)
    print("  종료: Ctrl+C")
    print("=" * 60 + "\n")

    for p in procs:
        p.wait()
