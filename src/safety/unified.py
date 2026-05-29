"""Safety unified gate — 모든 safety 게이트의 단일 진입점.

배경:
    7개 게이트(citation_grounding, consistency, causal, physician_review, truth_hierarchy,
    figure_validator, audit_trail)가 각각 산재해 어떤 진입점에서 호출되는지 추적이 어렵다.
    호출자가 잊거나 부분 호출하면 보호가 깨진다.

설계:
    `check_all(text, *, sections=None, design=None, references=None, fig_paths=None)`
    한 줄로 모든 게이트를 호출하고 통합 SafetyReport 반환 + audit_trail 자동 적재.

    severity 통합 규칙:
        - 한 게이트라도 'fail' → overall 'fail'
        - 한 게이트라도 'warn' (그리고 fail 없음) → overall 'warn'
        - 모두 ok → 'ok'

호출 위치 (정석):
    - paper_writer._generate() 출력 직후
    - run_full() 각 섹션 완료 직후
    - agentic_loop의 assistant 최종 텍스트 직후
    - tools/export_citations 게이팅 직전
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger

_log = get_logger(__name__)


SEVERITY_ORDER = {"ok": 0, "info": 0, "warn": 1, "fail": 2, "error": 2}


def _max_sev(*severs: str) -> str:
    s = max(severs, key=lambda x: SEVERITY_ORDER.get(x, 0))
    return s if s in SEVERITY_ORDER else "ok"


@dataclass
class GateOutcome:
    name: str
    severity: str = "ok"      # ok | warn | fail | error
    summary: str = ""
    detail: dict = field(default_factory=dict)
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class SafetyReport:
    scope: str = ""
    overall: str = "ok"
    gates: list[GateOutcome] = field(default_factory=list)
    ts: float = 0.0

    @property
    def failed_gates(self) -> list[str]:
        return [g.name for g in self.gates if g.severity == "fail"]

    @property
    def warning_gates(self) -> list[str]:
        return [g.name for g in self.gates if g.severity == "warn"]

    def to_dict(self) -> dict:
        return {
            "scope": self.scope, "overall": self.overall, "ts": self.ts,
            "failed_gates": self.failed_gates,
            "warning_gates": self.warning_gates,
            "gates": [asdict(g) for g in self.gates],
        }


def _gate_citation(text: str, references: Any | None) -> GateOutcome:
    out = GateOutcome(name="citation_grounding")
    if references is None:
        out.skipped = True
        out.skip_reason = "references not provided"
        return out
    t0 = time.time()
    try:
        from src.safety.citation_grounding import verify_citation_integrity
        rep = verify_citation_integrity(text, refs=references)
        out.detail = rep if isinstance(rep, dict) else {"raw": str(rep)[:200]}
        # heuristic severity — orphan markers or missing DOIs → warn/fail
        orphans = out.detail.get("orphan_markers") or []
        missing = out.detail.get("missing_dois") or []
        if len(orphans) >= 3 or len(missing) >= 3:
            out.severity = "fail"
        elif orphans or missing:
            out.severity = "warn"
        out.summary = f"orphans={len(orphans)} missing_dois={len(missing)}"
    except Exception as e:
        out.severity = "error"
        out.summary = f"{type(e).__name__}: {str(e)[:120]}"
    out.duration_ms = int((time.time() - t0) * 1000)
    return out


def _gate_consistency(sections: dict | None) -> GateOutcome:
    out = GateOutcome(name="consistency")
    if not sections:
        out.skipped = True; out.skip_reason = "sections not provided"
        return out
    t0 = time.time()
    try:
        from src.safety.consistency_checker import check_consistency
        rep = check_consistency(sections)
        out.severity = rep.severity  # ok|warn|fail
        out.detail = rep.to_dict()
        out.summary = f"{len(rep.issues)} issues"
    except Exception as e:
        out.severity = "error"
        out.summary = f"{type(e).__name__}: {str(e)[:120]}"
    out.duration_ms = int((time.time() - t0) * 1000)
    return out


def _gate_causal(text: str, design: str | None) -> GateOutcome:
    out = GateOutcome(name="causal_claims")
    if not text:
        out.skipped = True; out.skip_reason = "empty text"
        return out
    t0 = time.time()
    try:
        from src.safety.causal_checker import check_causal_claims
        rep = check_causal_claims(text, study_design=design or "cross_sectional")
        d = rep.to_dict() if hasattr(rep, "to_dict") else (rep if isinstance(rep, dict) else {})
        out.detail = d
        # heuristic severity
        n_inappropriate = sum(1 for c in d.get("claims", []) if not c.get("appropriate", True))
        if n_inappropriate >= 3:
            out.severity = "fail"
        elif n_inappropriate >= 1:
            out.severity = "warn"
        out.summary = f"inappropriate_claims={n_inappropriate} design={design}"
    except Exception as e:
        out.severity = "error"
        out.summary = f"{type(e).__name__}: {str(e)[:120]}"
    out.duration_ms = int((time.time() - t0) * 1000)
    return out


def _gate_physician(text: str) -> GateOutcome:
    out = GateOutcome(name="physician_review")
    t0 = time.time()
    try:
        from src.safety.physician_review import review_required
        needed, triggers = review_required(text)
        out.detail = {"required": needed, "triggers": triggers}
        out.severity = "warn" if needed else "ok"
        out.summary = f"required={needed} triggers={len(triggers)}"
    except Exception as e:
        out.severity = "error"
        out.summary = f"{type(e).__name__}: {str(e)[:120]}"
    out.duration_ms = int((time.time() - t0) * 1000)
    return out


def _gate_figures(paths: list | None) -> GateOutcome:
    out = GateOutcome(name="figure_validator")
    if not paths:
        out.skipped = True; out.skip_reason = "no figures provided"
        return out
    t0 = time.time()
    try:
        from src.safety.figure_validator import validate_figure
        fails, warns = 0, 0
        details = []
        for p in paths:
            try:
                rep = validate_figure(p)
                d = rep if isinstance(rep, dict) else (rep.to_dict() if hasattr(rep, "to_dict") else {})
                details.append({"path": str(p), **d})
                if d.get("severity") == "fail":
                    fails += 1
                elif d.get("severity") == "warn":
                    warns += 1
            except Exception as e:
                details.append({"path": str(p), "error": str(e)[:120]})
        out.detail = {"results": details, "fail_count": fails, "warn_count": warns}
        out.severity = "fail" if fails else ("warn" if warns else "ok")
        out.summary = f"fails={fails} warns={warns} total={len(paths)}"
    except Exception as e:
        out.severity = "error"
        out.summary = f"{type(e).__name__}: {str(e)[:120]}"
    out.duration_ms = int((time.time() - t0) * 1000)
    return out


def check_all(
    text: str,
    *,
    sections: dict | None = None,
    design: str | None = None,
    references: Any | None = None,
    fig_paths: list | None = None,
    scope: str = "paper_write",
    record_audit: bool = True,
) -> SafetyReport:
    """모든 safety 게이트를 호출하고 통합 보고.

    audit_trail에 자동으로 fail/warn 이벤트를 적재 (record_audit=True 기본).
    호출자는 보고서를 받아 결정만 하면 됨.
    """
    t0 = time.time()
    gates = [
        _gate_citation(text, references),
        _gate_consistency(sections),
        _gate_causal(text, design),
        _gate_physician(text),
        _gate_figures(fig_paths),
    ]
    overall = _max_sev(*[g.severity for g in gates if not g.skipped]) or "ok"
    report = SafetyReport(scope=scope, overall=overall, gates=gates, ts=t0)

    # ── audit_trail 자동 적재 ──
    if record_audit:
        try:
            from src.safety.audit_trail import record_safety_event
            for g in gates:
                if g.skipped or g.severity in ("ok", "info"):
                    continue
                record_safety_event(
                    type=f"safety.{g.name}.{g.severity}",
                    payload={"scope": scope, "summary": g.summary,
                              "detail_keys": sorted(g.detail.keys())},
                )
            if overall in ("warn", "fail"):
                record_safety_event(
                    type=f"safety.check_all.{overall}",
                    payload={"scope": scope,
                              "failed": report.failed_gates,
                              "warning": report.warning_gates},
                )
        except Exception:
            pass

    # ── tracing — 호출자가 span 안이면 자동 부모 child ──
    try:
        from src.runtime.tracing import current_span
        sp = current_span()
        if sp is not None:
            sp.set("safety_overall", overall)
            sp.set("safety_failed", report.failed_gates)
    except Exception:
        pass

    return report


__all__ = [
    "SEVERITY_ORDER", "GateOutcome", "SafetyReport", "check_all",
]
