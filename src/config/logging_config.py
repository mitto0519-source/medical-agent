"""표준 로깅 설정 — 전체 프로젝트 공통 규칙.

규칙:
  1. 모든 모듈은 get_logger(__name__)으로 로거를 얻는다.
  2. 최초 1회 setup_logging()이 호출되면 이후 중복 설정은 무시된다.
  3. 콘솔 + 파일(data/logs/app.log) 동시 출력.
  4. 포맷: [시간] LEVEL [모듈명] 메시지

Usage:
    from src.config.logging_config import get_logger
    _log = get_logger(__name__)
    _log.info("작업 시작")
    _log.warning("경고 메시지")
    _log.error("오류 발생: %s", err)
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

_configured = False
_LOG_DIR = Path("data/logs")
_LOG_FILE = _LOG_DIR / "app.log"
_FMT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """루트 로거 설정. 앱 시작 시 1회만 호출."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    if root.handlers:
        _configured = True
        return

    root.setLevel(level)
    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # 콘솔 핸들러
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level)
    root.addHandler(console)

    # 파일 핸들러 (로테이션: 5MB × 3개)
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_h = logging.handlers.RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_h.setFormatter(formatter)
        file_h.setLevel(level)
        root.addHandler(file_h)
    except Exception:
        pass  # 로그 파일 쓰기 권한 없을 때 콘솔만 유지

    # 외부 라이브러리 노이즈 억제
    for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """모듈 로거 반환. 미설정 시 자동으로 setup_logging() 호출."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)
