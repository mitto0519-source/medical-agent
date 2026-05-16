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

STREAMLIT_PORT = 8501
MCP_PORT = 8765

procs = []


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
        p.terminate()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

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
