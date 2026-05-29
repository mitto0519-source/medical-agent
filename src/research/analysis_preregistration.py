"""Analysis preregistration — 통계 분석 결정의 LLM 우회·잠금.

배경:
    StatBridge는 statsmodels로 deterministic하지만, "어떤 변수를 outcome으로 / 어떤 confounder
    를 포함할지"의 결정은 LLM이 생성하는 경우가 많다. 이 결정 단계에서 LLM이 매 호출마다
    조금씩 다른 spec을 만들면 같은 dataset에서도 결과가 흔들린다.

설계:
    1) LLM 또는 사람이 AnalysisPlan을 만든다 (outcome/exposure/confounders/model/seed).
    2) plan_hash = register(plan, dataset_path=...) → events.db에 immutable 기록.
    3) StatBridge.analyze(spec, plan_hash=...) — verify(plan_hash, spec) 통과해야 실행.
    4) 결과도 plan_hash와 연결 → 사후 재현 가능.

이로써 "LLM 변덕"을 차단하면서 LLM의 spec 제안은 그대로 활용 (proposal → register → execute).

API:
    plan = AnalysisPlan(outcome=..., exposure=..., confounders=[...], ...)
    plan_hash = register(plan, dataset_path=Path("data/raw/KYRBS_2025.sav"))
    # 실행 시점
    is_ok, msg = verify(plan_hash, current_spec=plan.to_spec())
    # 결과 연결
    record_result(plan_hash, summary_dict)

    lookup(plan_hash) -> AnalysisPlan
    recent(n=20) -> [plan_dicts]
    list_plans_for_dataset(label="KYRBS") -> [plans]
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events
from src.runtime import provenance as _prov

_log = get_logger(__name__)


VALID_MODELS = {
    "logistic", "linear", "poisson", "gee_logistic", "cox", "psm_logistic",
    "multilevel", "interrupted_time_series", "did",
}
VALID_DESIGNS = {
    "cross_sectional", "cohort", "case_control", "rct",
    "interrupted_time_series", "difference_in_differences", "meta_analysis",
}


@dataclass
class AnalysisPlan:
    """immutable한 통계 분석 계획. dataclass라 dict 변환 쉽고 해시 안정."""
    outcome: str
    exposure: str
    confounders: list[str] = field(default_factory=list)
    model_class: str = "logistic"
    design: str = "cross_sectional"
    dataset_label: str = ""
    dataset_md5: str = ""
    seed: int | None = None
    notes: str = ""
    # extras (자유 — 가중치, subgroup 등 추가 spec)
    extra: dict = field(default_factory=dict)

    def validate(self) -> tuple[bool, str]:
        if not self.outcome:
            return False, "outcome empty"
        if not self.exposure:
            return False, "exposure empty"
        if self.model_class not in VALID_MODELS:
            return False, f"unknown model_class={self.model_class}; valid={sorted(VALID_MODELS)}"
        if self.design not in VALID_DESIGNS:
            return False, f"unknown design={self.design}; valid={sorted(VALID_DESIGNS)}"
        return True, "ok"

    def to_spec(self) -> dict:
        """StatBridge가 받는 spec dict 양식."""
        d = {
            "outcome": self.outcome, "exposure": self.exposure,
            "confounders": list(self.confounders),
            "model": self.model_class, "design": self.design,
            "seed": self.seed,
        }
        if self.extra:
            d.update(self.extra)
        return d

    def canonical_hash(self) -> str:
        """결정론적 해시. 같은 plan → 같은 hash. confounders 순서도 정규화."""
        norm = {
            "outcome": self.outcome.strip().lower(),
            "exposure": self.exposure.strip().lower(),
            "confounders": sorted(c.strip().lower() for c in self.confounders),
            "model_class": self.model_class,
            "design": self.design,
            "dataset_label": self.dataset_label,
            "dataset_md5": self.dataset_md5,
            "seed": self.seed,
            "extra": _normalize(self.extra),
        }
        canonical = json.dumps(norm, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple, set)):
        return sorted([_normalize(x) for x in obj], key=lambda x: json.dumps(x, default=str, sort_keys=True))
    return obj


# ── Storage layer (events.db) ───────────────────────────────────────────────

_TYPE_REGISTERED = "analysis_plan_registered"
_TYPE_VERIFIED = "analysis_plan_verified"
_TYPE_VIOLATION = "analysis_plan_violation"
_TYPE_RESULT = "analysis_plan_result"


def register(plan: AnalysisPlan, *,
             dataset_path: str | Path | None = None,
             task_id: str | None = None,
             actor: str = "researcher") -> str:
    """plan을 검증하고 events.db에 immutable 기록. plan_hash 반환."""
    ok, msg = plan.validate()
    if not ok:
        raise ValueError(f"invalid AnalysisPlan: {msg}")
    # dataset md5 자동 채우기 (없으면)
    if dataset_path and not plan.dataset_md5:
        try:
            plan.dataset_md5 = _prov.file_md5(dataset_path)
        except Exception:
            pass
    # seed 자동 (없으면 결정론적)
    if plan.seed is None:
        plan.seed = _prov.seed_for("analysis_plan", plan.outcome + "|" + plan.exposure)

    plan_hash = plan.canonical_hash()
    payload = {**asdict(plan), "plan_hash": plan_hash}
    _events.append(type=_TYPE_REGISTERED, payload=payload,
                   task_id=task_id, actor=actor)
    # 별도 provenance fingerprint 함께
    fp = _prov.build_fingerprint(
        scope="analysis_plan", dataset_path=dataset_path,
        dataset_label=plan.dataset_label,
        seed=plan.seed,
        extra={"plan_hash": plan_hash, "model": plan.model_class},
    )
    _prov.record(fp, task_id=task_id, actor=actor)
    return plan_hash


def lookup(plan_hash: str) -> dict | None:
    """plan_hash로 registered plan dict 조회 (가장 최근)."""
    items = _events.find(type=_TYPE_REGISTERED, limit=400)
    for e in items:
        p = e.get("payload") or {}
        if p.get("plan_hash") == plan_hash:
            return p
    return None


def verify(plan_hash: str, current_spec: dict | None = None,
           *, task_id: str | None = None) -> tuple[bool, str]:
    """plan_hash 가 등록되어 있고 current_spec과 일치하는지 확인.

    Returns: (ok, message). ok=False면 violation 이벤트 기록.
    """
    plan = lookup(plan_hash)
    if plan is None:
        _events.append(type=_TYPE_VIOLATION,
                        payload={"plan_hash": plan_hash, "reason": "not_registered"},
                        task_id=task_id, actor="preregistration")
        return False, f"plan_hash {plan_hash} not registered"

    if current_spec is not None:
        # 같은 plan_hash 인데 spec이 변경됐다면 violation
        try:
            current = AnalysisPlan(
                outcome=current_spec.get("outcome", ""),
                exposure=current_spec.get("exposure", ""),
                confounders=current_spec.get("confounders", []) or [],
                model_class=current_spec.get("model", plan.get("model_class", "")),
                design=current_spec.get("design", plan.get("design", "")),
                dataset_label=plan.get("dataset_label", ""),
                dataset_md5=plan.get("dataset_md5", ""),
                seed=current_spec.get("seed", plan.get("seed")),
                extra=current_spec.get("extra", {}) or {},
            )
            current_hash = current.canonical_hash()
            if current_hash != plan_hash:
                _events.append(type=_TYPE_VIOLATION,
                                payload={"plan_hash": plan_hash,
                                          "got_hash": current_hash,
                                          "reason": "spec_mismatch"},
                                task_id=task_id, actor="preregistration")
                return False, f"spec_mismatch: registered={plan_hash} got={current_hash}"
        except Exception as e:
            return False, f"verify error: {type(e).__name__}: {e}"

    _events.append(type=_TYPE_VERIFIED,
                    payload={"plan_hash": plan_hash},
                    task_id=task_id, actor="preregistration")
    return True, "ok"


def record_result(plan_hash: str, summary: dict, *,
                  task_id: str | None = None, actor: str = "StatBridge") -> int:
    """분석 실행 결과를 plan_hash와 연결해 events에 적재."""
    payload = {"plan_hash": plan_hash, "summary": summary}
    return _events.append(type=_TYPE_RESULT, payload=payload,
                          task_id=task_id, actor=actor)


def recent(n: int = 20) -> list[dict]:
    items = _events.find(type=_TYPE_REGISTERED, limit=n)
    return [e.get("payload") or {} for e in items]


def list_plans_for_dataset(label: str, n: int = 20) -> list[dict]:
    items = _events.find(type=_TYPE_REGISTERED, limit=n * 4)
    label_l = label.lower()
    return [
        (e.get("payload") or {})
        for e in items
        if label_l in (e.get("payload") or {}).get("dataset_label", "").lower()
    ][:n]


def violations(n: int = 50) -> list[dict]:
    return [e.get("payload") or {} for e in _events.find(type=_TYPE_VIOLATION, limit=n)]


def run_locked(plan_hash: str, runner, *args, current_spec: dict | None = None,
               strict: bool = True, task_id: str | None = None, **kwargs):
    """preregister된 plan_hash로 잠긴 runner 실행.

    1) verify(plan_hash, current_spec) — 통과하지 못하면:
       - strict=True: RuntimeError raise (실행 거부)
       - strict=False: warning만 남기고 실행 (audit는 violation 기록됨)
    2) 통과 시 runner(*args, **kwargs) 실행 → 결과를 record_result로 events에 연결.

    Returns: runner의 반환값 그대로. strict=True에서 verify 실패 시 raise.
    """
    ok, msg = verify(plan_hash, current_spec=current_spec, task_id=task_id)
    if not ok:
        if strict:
            raise RuntimeError(f"preregistration violation: {msg}")
        _log.warning("preregistration violation (strict=False, 실행은 계속): %s", msg)

    result = runner(*args, **kwargs)
    try:
        # 결과 요약을 events에 적재 — 큰 결과는 키만
        if isinstance(result, dict):
            summary = {k: v for k, v in result.items()
                       if isinstance(v, (int, float, str, bool))}
            summary["_keys"] = sorted(result.keys())
        else:
            summary = {"type": type(result).__name__, "len": len(result) if hasattr(result, "__len__") else None}
        record_result(plan_hash, summary, task_id=task_id)
    except Exception:
        pass
    return result


__all__ = [
    "AnalysisPlan", "VALID_MODELS", "VALID_DESIGNS",
    "register", "verify", "lookup", "record_result", "run_locked",
    "recent", "list_plans_for_dataset", "violations",
]
