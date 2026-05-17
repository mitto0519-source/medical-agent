"""Agent self-model — 프로젝트 건강도 자동 분석 및 다음 우선순위 산출.

이 모듈은 Claude가 스스로 프로젝트 상태를 파악하고,
무엇을 다음으로 해야 할지 선제적으로 계산한다.

매 세션 시작 시 또는 주요 작업 완료 후 refresh()를 호출하면
현재 상태 + 우선순위 액션 목록이 갱신된다.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger
from src.memory import agent_insight

_log = get_logger(__name__)
_MODEL_FILE = Path("data/agent_self/self_model.json")


@dataclass
class ProjectHealthModel:
    updated_at: str = ""
    overall_score: int = 0          # 0-100
    smoke_test_status: str = "unknown"   # passing | failing | unknown
    smoke_test_score: str = "?"          # "12/12" 형식
    known_strengths: List[str] = field(default_factory=list)
    known_weaknesses: List[str] = field(default_factory=list)
    top_next_actions: List[Dict] = field(default_factory=list)  # [{title, reason, priority}]
    active_insights: int = 0
    recent_changes: List[str] = field(default_factory=list)
    git_summary: str = ""


def _run(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).parent.parent.parent,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _load_model() -> Dict:
    if not _MODEL_FILE.exists():
        return {}
    try:
        return json.loads(_MODEL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_model(model: ProjectHealthModel) -> None:
    _MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MODEL_FILE.write_text(
        json.dumps(asdict(model), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def refresh() -> ProjectHealthModel:
    """프로젝트 현재 상태를 분석하고 self_model을 갱신한다."""
    model = ProjectHealthModel(updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # ── Git 상태 ──────────────────────────────────────────────────────
    git_log = _run("git log --oneline -8")
    git_status = _run("git status --short")
    model.git_summary = f"최근 커밋:\n{git_log}\n변경사항: {git_status or '없음'}"
    model.recent_changes = [
        line.split(" ", 1)[-1] for line in git_log.splitlines()
    ][:5]

    # ── 모듈 임포트 상태 분석 ────────────────────────────────────────
    module_checks = [
        ("src.config.models", "list_available_models"),
        ("src.config.env", "bootstrap"),
        ("src.memory.change_log", "log"),
        ("src.memory.agent_insight", "record"),
        ("src.agent.medical_agent", "MedicalAgent"),
        ("src.research.research_pipeline", "ResearchPipeline"),
        ("src.rag.pipeline", "RAGPipeline"),
    ]
    passing, failing = [], []
    for mod, attr in module_checks:
        try:
            m = __import__(mod, fromlist=[attr])
            getattr(m, attr)
            passing.append(mod.split(".")[-1])
        except Exception as e:
            failing.append(f"{mod.split('.')[-1]}: {str(e)[:60]}")

    if failing:
        model.known_weaknesses.extend([f"모듈 임포트 실패: {f}" for f in failing])
    model.smoke_test_status = "passing" if not failing else "failing"
    model.smoke_test_score = f"{len(passing)}/{len(module_checks)}"

    # ── 핵심 파일 존재 확인 ──────────────────────────────────────────
    critical_files = {
        "CLAUDE.md": "작업 표준 규칙 자동 로드",
        "src/memory/change_log.py": "장기기억 시스템",
        "src/memory/agent_insight.py": "자가 학습 DB",
        "src/config/models.py": "중앙 모델 레지스트리",
        "data/change_log/history.json": "작업 이력",
    }
    for fpath, desc in critical_files.items():
        if Path(fpath).exists():
            model.known_strengths.append(f"{desc} ({fpath})")
        else:
            model.known_weaknesses.append(f"누락: {fpath} — {desc}")

    # ── 클라우드 상태 ────────────────────────────────────────────────
    try:
        from src.cloud.db import cloud_available
        if cloud_available():
            model.known_strengths.append("Supabase 클라우드 연결 활성")
        else:
            model.known_weaknesses.append("Supabase 미연결 (SUPABASE_DB_URL 미설정 — 로컬 전용 모드)")
    except Exception:
        pass

    # ── 인사이트 DB 상태 ────────────────────────────────────────────
    all_insights = agent_insight.get_all(n=200)
    model.active_insights = len(all_insights)
    next_actions = agent_insight.get_next_actions(n=5)
    model.top_next_actions = [
        {
            "title": a.get("title", ""),
            "reason": a.get("why_matters", ""),
            "confidence": a.get("confidence", 0.8),
        }
        for a in next_actions
    ]

    # ── 종합 점수 계산 ───────────────────────────────────────────────
    score = 50
    score += len(passing) * 4               # 모듈당 4점
    score += len(model.known_strengths) * 3 # 강점당 3점
    score -= len(model.known_weaknesses) * 5 # 약점당 -5점
    model.overall_score = max(0, min(100, score))

    _save_model(model)
    _log.info("Self-model refreshed: score=%d, smoke=%s", model.overall_score, model.smoke_test_score)
    return model


def get_model() -> ProjectHealthModel:
    """저장된 self_model 반환. 없으면 refresh() 실행."""
    data = _load_model()
    if not data:
        return refresh()
    m = ProjectHealthModel()
    for k, v in data.items():
        if hasattr(m, k):
            setattr(m, k, v)
    return m


def surface_next_action() -> Optional[str]:
    """가장 우선순위 높은 다음 액션을 텍스트로 반환. 없으면 None."""
    model = get_model()
    if model.top_next_actions:
        top = model.top_next_actions[0]
        return f"[자동 제안] {top['title']} (근거: {top['reason'][:80]})"
    return None


def print_status() -> str:
    """현재 프로젝트 상태 요약 출력용 텍스트 생성."""
    model = get_model()
    lines = [
        f"=== Medical-Agent 프로젝트 자가 진단 ({model.updated_at}) ===",
        f"종합 점수: {model.overall_score}/100",
        f"Smoke Test: {model.smoke_test_score} ({model.smoke_test_status})",
        "",
        f"강점 ({len(model.known_strengths)}개):",
        *[f"  + {s}" for s in model.known_strengths[:5]],
        "",
        f"약점 ({len(model.known_weaknesses)}개):",
        *[f"  - {w}" for w in model.known_weaknesses[:5]],
        "",
        f"다음 우선 작업:",
        *[f"  [{int(a['confidence']*100)}%] {a['title']}" for a in model.top_next_actions[:3]],
        "",
        f"활성 인사이트: {model.active_insights}개",
    ]
    if model.git_summary:
        lines += ["", "Git 상태:", *[f"  {l}" for l in model.git_summary.splitlines()[:5]]]
    return "\n".join(lines)
