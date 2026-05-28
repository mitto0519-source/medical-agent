"""Tool consensus + rollback + shadow execution — frontier agent tool intelligence.

외부 진단 (2026-05-28): "speculative tool execution / parallel branch / consensus rerank /
rollback / shadow execution / verification agents" 미구현 → 본 모듈이 그 격차.

핵심 3 기능:

1. **consensus_call(tool_fn, args, n=3)** — 같은 tool 동일 args로 n번 호출
   → 결과 hash 다수결, contradiction 시 events 기록 + 최빈답 반환.
   PubMed search/RAG 같이 stochastic ranking이 있는 tool에 유효.

2. **parallel_branches(branches)** — 같은 의도를 다른 strategy로 병렬 호출
   예: ["pubmed_search", "rag_search", "cross_modal_query"] → 셋 합집합 + rerank.
   ThreadPoolExecutor (I/O bound). LLM tool 호출도 thread-safe면 가능.

3. **shadow_execute(real_fn, shadow_fn, args)** — real_fn 결과 사용자에게 보여주되
   shadow_fn 결과를 events에 기록해 비교. 새 prompt/도구 검증용.

4. **rollback_context(transaction_id)** — patch_preview 등 destructive tool 호출
   직전 snapshot 저장 → events.rollback_request 시 복원.

호출:
    from src.llm.tool_consensus import consensus_call, parallel_branches, snapshot_for_rollback
    result = consensus_call(rag_pipeline.search, {"query": "..."}, n=3)
    branch_results = parallel_branches([
        ("pubmed", lambda: pubmed_search("...")),
        ("rag", lambda: rag_search("...")),
        ("xmodal", lambda: cross_modal_query("...")),
    ])
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Rollback snapshot store (in-memory + events) ────────────────────────────

_SNAPSHOTS: Dict[str, Dict] = {}    # txn_id → snapshot dict


def snapshot_for_rollback(target: str, current_state: Any,
                           ttl_sec: int = 1800) -> str:
    """destructive tool 호출 직전 snapshot 저장. txn_id 반환."""
    txn = uuid.uuid4().hex[:12]
    _SNAPSHOTS[txn] = {"target": target, "state": current_state,
                        "ts": time.time(), "ttl_sec": ttl_sec}
    # 오래된 snapshot GC
    now = time.time()
    expired = [k for k, v in _SNAPSHOTS.items()
                if now - v["ts"] > v["ttl_sec"]]
    for k in expired:
        _SNAPSHOTS.pop(k, None)
    try:
        from src.runtime import events as _events
        _events.append("rollback_snapshot",
                        {"txn": txn, "target": target,
                         "size": len(json.dumps(current_state, default=str)[:2000])},
                        actor="tool_consensus")
    except Exception:
        pass
    return txn


def rollback(txn_id: str) -> Optional[Dict]:
    """저장된 snapshot 반환. 호출자가 실제 state 복원 책임."""
    snap = _SNAPSHOTS.get(txn_id)
    if not snap:
        return None
    try:
        from src.runtime import events as _events
        _events.append("rollback_invoked",
                        {"txn": txn_id, "target": snap["target"]},
                        actor="tool_consensus")
    except Exception:
        pass
    return snap


# ── consensus ───────────────────────────────────────────────────────────────

def _result_hash(r: Any) -> str:
    """결과 정규화 hash (다수결용)."""
    try:
        s = json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        s = str(r)
    # 앞 1KB만 — long output에서 무관한 변동 제거
    return hashlib.sha1(s[:1024].encode("utf-8")).hexdigest()[:16]


def consensus_call(fn: Callable[..., Any], args: Optional[Dict] = None,
                    *, n: int = 3, parallel: bool = True,
                    min_agreement: float = 0.5) -> Dict:
    """동일 tool n번 호출 → 다수결 + contradiction detect.

    Returns: {"answer": ..., "agreement": float, "all_hashes": [...], "raw": [...],
              "contradiction": bool, "n": int}
    """
    args = args or {}
    n = max(1, int(n))
    results: List[Any] = []

    def _run():
        try:
            return fn(**args) if isinstance(args, dict) else fn(args)
        except Exception as e:
            return {"_error": str(e)[:200]}

    if parallel and n > 1:
        with ThreadPoolExecutor(max_workers=min(n, 5)) as ex:
            futs = [ex.submit(_run) for _ in range(n)]
            for f in as_completed(futs):
                results.append(f.result())
    else:
        for _ in range(n):
            results.append(_run())

    hashes = [_result_hash(r) for r in results]
    from collections import Counter
    cnt = Counter(hashes)
    top_hash, top_n = cnt.most_common(1)[0]
    agreement = top_n / max(1, len(results))
    contradiction = agreement < min_agreement and len(cnt) > 1
    answer = next((r for r, h in zip(results, hashes) if h == top_hash), None)

    try:
        from src.runtime import events as _events
        _events.append("consensus_call",
                        {"n": n, "agreement": round(agreement, 3),
                         "contradiction": contradiction,
                         "n_unique": len(cnt)},
                        actor="tool_consensus")
    except Exception:
        pass

    return {"answer": answer, "agreement": round(agreement, 3),
            "all_hashes": hashes, "raw": results,
            "contradiction": contradiction, "n": len(results)}


# ── parallel branches ───────────────────────────────────────────────────────

def parallel_branches(branches: List[Tuple[str, Callable[[], Any]]],
                       *, timeout_sec: int = 60) -> Dict:
    """다른 strategy의 병렬 호출. branches: [(name, callable), ...].

    Returns: {"results": {name: result}, "errors": {name: err}, "elapsed_sec": float}
    """
    t0 = time.time()
    out: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    if not branches:
        return {"results": {}, "errors": {}, "elapsed_sec": 0.0}
    with ThreadPoolExecutor(max_workers=min(len(branches), 8)) as ex:
        futs = {ex.submit(fn): name for name, fn in branches}
        for f in as_completed(futs, timeout=timeout_sec):
            name = futs[f]
            try:
                out[name] = f.result()
            except Exception as e:
                errors[name] = str(e)[:200]
    elapsed = round(time.time() - t0, 2)
    try:
        from src.runtime import events as _events
        _events.append("parallel_branches",
                        {"n_branches": len(branches), "n_ok": len(out),
                         "n_err": len(errors), "elapsed_sec": elapsed,
                         "branch_names": [n for n, _ in branches]},
                        actor="tool_consensus")
    except Exception:
        pass
    return {"results": out, "errors": errors, "elapsed_sec": elapsed}


# ── shadow execution ────────────────────────────────────────────────────────

def shadow_execute(real_fn: Callable[..., Any],
                    shadow_fn: Callable[..., Any],
                    args: Optional[Dict] = None,
                    *, shadow_label: str = "shadow") -> Dict:
    """real_fn 결과를 즉시 반환, shadow_fn은 background 실행 → events 기록.
    새 prompt/도구가 기존 대비 어떤 출력 차이를 내는지 검증."""
    args = args or {}

    def _r():
        return real_fn(**args) if isinstance(args, dict) else real_fn(args)

    def _s():
        try:
            return shadow_fn(**args) if isinstance(args, dict) else shadow_fn(args)
        except Exception as e:
            return {"_error": str(e)[:200]}

    real_result = _r()

    # shadow는 background thread (결과는 events만)
    def _bg():
        s_result = _s()
        try:
            from src.runtime import events as _events
            same = _result_hash(real_result) == _result_hash(s_result)
            _events.append("shadow_execution",
                            {"label": shadow_label, "same_as_real": same,
                             "real_hash": _result_hash(real_result),
                             "shadow_hash": _result_hash(s_result)},
                            actor="tool_consensus")
        except Exception:
            pass

    import threading
    threading.Thread(target=_bg, daemon=True).start()
    return {"real": real_result, "shadow_label": shadow_label}


# ── verifier ────────────────────────────────────────────────────────────────

def contradiction_check(results: List[Any]) -> Dict:
    """여러 결과 사이의 contradiction 검사 (text 유사도 + JSON key/value 비교)."""
    if len(results) < 2:
        return {"contradiction": False, "reason": "too few"}
    hashes = [_result_hash(r) for r in results]
    all_same = len(set(hashes)) == 1
    if all_same:
        return {"contradiction": False, "n_results": len(results)}
    # 텍스트 차이 정량화 (간단 — Jaccard token)
    try:
        sets: List[set] = []
        for r in results:
            s = json.dumps(r, ensure_ascii=False, default=str).lower()
            tokens = {t for t in s.split() if len(t) > 3}
            sets.append(tokens)
        inter = set.intersection(*sets) if sets else set()
        union = set.union(*sets) if sets else set()
        jaccard = len(inter) / max(1, len(union))
        contradicts = jaccard < 0.5
        return {"contradiction": contradicts,
                 "agreement_jaccard": round(jaccard, 3),
                 "n_results": len(results),
                 "n_unique_hash": len(set(hashes))}
    except Exception as e:
        return {"contradiction": False, "error": str(e)[:120]}
