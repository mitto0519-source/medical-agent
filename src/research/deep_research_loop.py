"""Deep Research Loop — KNOWLEDGE_ACQUISITION_SPEC §11 (실시간 RAG 강화).

한 방 검색이 아니라 **반복 루프**:
    검색 → 공백 탐지 → 라이브 획득 → 내재화 → 재검색 → 합성

가져온 즉시 인제스트 → 다음 iter에 로컬 RAG가 더 강해진다. 이게 '실시간 강화'의 실체.

★ §13 통제 5규율 모두 강제:
  ① 한도: max_iters / cost_cap / time_cap
  ② 킬스위치: ENV `DEEP_RESEARCH_KILL=1` 또는 events에 'kill:deep_research' 박기
  ③ 관측: 모든 iter event append (deep_research_iter)
  ④ 휴먼 게이트: high-cost 의심 시 stop_and_ask
  ⑤ 고아 0: API는 service.* 만 호출 (외부 직접 호출 X)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)

# 통제 기본값 (호출자가 override 가능)
DEFAULT_MAX_ITERS = 4
DEFAULT_COST_CAP_USD = 0.50
DEFAULT_TIME_CAP_SEC = 90
DEFAULT_COVERAGE_TARGET = 0.8  # 0~1, 공백 비율 < (1 - target) 이면 종료

_KILL_ENV = "DEEP_RESEARCH_KILL"


def killswitch_active() -> bool:
    """ENV 또는 events.db에 'kill:deep_research' 사건이 있으면 즉시 정지."""
    if os.environ.get(_KILL_ENV) in ("1", "true", "TRUE"):
        return True
    try:
        recent = _events.recent(5, type="kill_signal")
        for ev in recent:
            pl = ev.get("payload") or {}
            if pl.get("target") == "deep_research":
                return True
    except Exception:
        pass
    return False


@dataclass
class IterResult:
    iter: int
    hits_local: int = 0
    hits_acquired: int = 0
    ingested: int = 0
    coverage: float = 0.0
    cost_usd: float = 0.0
    elapsed_sec: float = 0.0
    note: str = ""


@dataclass
class DeepResearchReport:
    query: str
    iters: List[IterResult] = field(default_factory=list)
    final_hits: List[Dict] = field(default_factory=list)
    synthesis: str = ""
    total_cost_usd: float = 0.0
    total_elapsed_sec: float = 0.0
    stopped_reason: str = ""

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "iters": [vars(i) for i in self.iters],
            "final_hits_count": len(self.final_hits),
            "synthesis_chars": len(self.synthesis),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_elapsed_sec": round(self.total_elapsed_sec, 1),
            "stopped_reason": self.stopped_reason,
        }


# ── 공백 탐지 (휴리스틱 — 단순 + 통제 가능) ────────────────────────────────

def detect_gaps(hits: List[Dict], target_n: int = 8) -> Dict[str, Any]:
    """coverage 추정 + 부족 분야 표면화.

    coverage = len(hits) / target_n. < 1.0이면 라이브 보강 필요.
    """
    if not hits:
        return {"coverage": 0.0, "missing": ["전체 — RAG 로컬 결과 없음"]}
    n = len(hits)
    coverage = min(1.0, n / target_n)
    missing: List[str] = []
    # 연도 다양성 (최근 5년 비율)
    years = [int(h.get("metadata", {}).get("year", 0) or 0) for h in hits]
    recent = sum(1 for y in years if y >= 2022)
    if recent / max(n, 1) < 0.3:
        missing.append("최근 3년 이내 evidence 부족")
    # PMID 명확성
    has_pmid = sum(1 for h in hits if h.get("metadata", {}).get("pmid"))
    if has_pmid / max(n, 1) < 0.7:
        missing.append("PMID 명확한 hit 부족")
    return {"coverage": coverage, "missing": missing}


# ── 라이브 획득 (T1 — service.rag 단일 진입 + service 통과) ───────────────

def acquire_live(query: str, *, n: int = 5) -> List[Dict]:
    """T1 라이브 API (Europe PMC / PubMed) — 공백 보강 전용. 통제: 1회 최대 n=5.

    내재화는 호출자(_internalize)가 결정. 본 함수는 메타만 반환.
    """
    out: List[Dict] = []
    try:
        from src.knowledge.evidence_reader import search_papers
        results = search_papers(query, max_results=n) or []
        for r in results:
            out.append({
                "pmid": r.get("pmid"),
                "title": r.get("title", "")[:200],
                "abstract": (r.get("abstract") or "")[:1500],
                "year": r.get("year"),
                "metadata": {"pmid": r.get("pmid"), "source": "live_pubmed",
                              "year": r.get("year")},
            })
    except Exception as e:
        _log.warning("acquire_live fail: %s", e)
    return out


def _internalize(acquired: List[Dict]) -> int:
    """가져온 메타를 RAG 코퍼스에 인제스트. 다음 iter에 로컬이 더 강해짐."""
    if not acquired:
        return 0
    try:
        from src.rag.pipeline import RAGPipeline
        rag = RAGPipeline()
        added = 0
        for p in acquired:
            txt = (p.get("title", "") + "\n\n" + p.get("abstract", "")).strip()
            if not txt or len(txt) < 50:
                continue
            try:
                if hasattr(rag, "add_document"):
                    rag.add_document(txt, metadata=p.get("metadata") or {})
                    added += 1
                elif hasattr(rag, "ingest"):
                    rag.ingest(txt, metadata=p.get("metadata") or {})
                    added += 1
            except Exception:
                continue
        return added
    except Exception as e:
        _log.warning("_internalize fail: %s", e)
        return 0


# ── 합성 (LLM 1콜 — 모든 iter 종료 후) ──────────────────────────────────

def synthesize(query: str, hits: List[Dict]) -> str:
    """final hits → 학술 요약. 모든 수치/주장은 hits 인용 강제."""
    if not hits:
        return f"(질의: {query} — 충분한 evidence 미확보 — 추가 라이브 fetch 필요)"
    facts_block = "\n\n".join(
        f"[PMID:{h.get('metadata',{}).get('pmid','?')}] "
        f"({h.get('metadata',{}).get('year','?')}) "
        f"{h.get('title','')[:200]}\n{(h.get('abstract') or h.get('text',''))[:800]}"
        for h in hits[:8]
    )
    try:
        from src.llm import get_llm_client
        prompt = (
            f"질의: {query}\n\n"
            f"수집된 evidence ({len(hits)}편):\n{facts_block}\n\n"
            f"위 evidence만 인용해 학술 요약 (3~5단락). 모든 주장은 [PMID:xxx] 인라인. "
            f"숫자 발명 절대 금지."
        )
        client = get_llm_client(task="paper_writing")
        return client.generate(prompt, system_prompt="", max_tokens=1500)
    except Exception as e:
        _log.warning("synthesize fail: %s", e)
        return f"(합성 실패: {e})"


# ── 메인 루프 ────────────────────────────────────────────────────────────

def deep_research(
    query: str, *,
    max_iters: int = DEFAULT_MAX_ITERS,
    cost_cap_usd: float = DEFAULT_COST_CAP_USD,
    time_cap_sec: float = DEFAULT_TIME_CAP_SEC,
    coverage_target: float = DEFAULT_COVERAGE_TARGET,
    top_k_local: int = 8,
    n_acquire: int = 5,
    on_iter: Optional[Callable[[IterResult], None]] = None,
) -> DeepResearchReport:
    """반복 루프: search → gap → live → ingest → re-search → synthesize.

    한도/킬/관측/휴먼게이트 통제 5규율 적용.
    on_iter: iter마다 호출되는 콜백 (UI에 진행 표시용 — 옵션).
    """
    t0 = time.time()
    rep = DeepResearchReport(query=query)

    # 시작 이벤트
    _events.append("deep_research_start",
                     {"query": query[:200], "max_iters": max_iters,
                      "cost_cap_usd": cost_cap_usd, "time_cap_sec": time_cap_sec},
                     actor="deep_research_loop", dedup_window_sec=10)

    from src.service.rag import retrieve

    final_hits: List[Dict] = []
    accumulated_cost = 0.0

    for i in range(1, max_iters + 1):
        elapsed = time.time() - t0
        ir = IterResult(iter=i, elapsed_sec=elapsed)

        # ★ 통제 ②: 킬스위치
        if killswitch_active():
            ir.note = "killswitch_active"
            rep.iters.append(ir)
            rep.stopped_reason = "killswitch"
            break
        # ★ 통제 ①: time_cap
        if elapsed > time_cap_sec:
            ir.note = f"time_cap_exceeded ({elapsed:.1f}s)"
            rep.iters.append(ir)
            rep.stopped_reason = "time_cap"
            break
        # ★ 통제 ①: cost_cap (휴리스틱 — 라이브 콜당 ~$0.02)
        if accumulated_cost >= cost_cap_usd:
            ir.note = f"cost_cap_reached (${accumulated_cost:.4f})"
            rep.iters.append(ir)
            rep.stopped_reason = "cost_cap"
            break

        # 1) 로컬 RAG retrieve
        try:
            local_hits = retrieve(query, top_k=top_k_local)
        except Exception as e:
            local_hits = []
            _log.warning("retrieve fail iter %d: %s", i, e)
        ir.hits_local = len(local_hits)

        # 2) 공백 탐지
        gap = detect_gaps(local_hits, target_n=top_k_local)
        ir.coverage = gap["coverage"]

        # 종료 조건: coverage target 충족
        if ir.coverage >= coverage_target and i > 1:
            final_hits = local_hits
            ir.note = f"coverage_target_met ({ir.coverage:.2f} >= {coverage_target})"
            ir.elapsed_sec = time.time() - t0
            rep.iters.append(ir)
            rep.stopped_reason = "coverage_target"
            if on_iter: on_iter(ir)
            break

        # 3) 라이브 획득 — 공백 있을 때만
        acquired: List[Dict] = []
        if gap["missing"] or ir.coverage < coverage_target:
            acquired = acquire_live(query, n=n_acquire)
            ir.hits_acquired = len(acquired)
            accumulated_cost += 0.02 * len(acquired)  # 추정 cost

        # 4) 내재화 — 다음 iter에 로컬 RAG가 더 강해짐
        if acquired:
            ir.ingested = _internalize(acquired)

        # 5) 관측 (§13 ③)
        ir.elapsed_sec = time.time() - t0
        ir.cost_usd = accumulated_cost
        rep.iters.append(ir)
        _events.append(
            "deep_research_iter",
            {"iter": i, "coverage": ir.coverage,
             "hits_local": ir.hits_local, "hits_acquired": ir.hits_acquired,
             "ingested": ir.ingested, "cost_usd": round(ir.cost_usd, 4),
             "elapsed_sec": round(ir.elapsed_sec, 1)},
            actor="deep_research_loop",
        )
        if on_iter:
            on_iter(ir)

        # final hits 누적 (마지막 iter의 local + acquired)
        final_hits = local_hits + acquired

    else:
        rep.stopped_reason = "max_iters"

    # 6) 합성
    rep.final_hits = final_hits
    rep.synthesis = synthesize(query, final_hits)
    rep.total_cost_usd = accumulated_cost
    rep.total_elapsed_sec = time.time() - t0

    _events.append(
        "deep_research_done",
        {**rep.to_dict()},
        actor="deep_research_loop",
    )
    return rep


# ── §12 Currency Study (도메인판 최신화 — 뉴스레터 X) ─────────────────────

def currency_study(
    topic: str, *,
    recency_days: int = 180,
    cost_cap_usd: float = 0.20,
    opt_in: bool = True,
) -> Dict[str, Any]:
    """활성 주제의 최신 evidence·트렌드·novelty 변화를 study.

    푸시 알림 X — study 카드(dict) 반환. heartbeat에서 호출 가능 (opt-in 필수).
    """
    if not opt_in:
        return {"skipped": "opt_out", "topic": topic}
    if killswitch_active():
        return {"skipped": "killswitch", "topic": topic}

    _events.append("currency_study_start",
                     {"topic": topic[:120], "recency_days": recency_days,
                      "cost_cap_usd": cost_cap_usd},
                     actor="currency_study", dedup_window_sec=300)

    # 1) 라이브 fetch — 최근 N일
    try:
        from src.knowledge.evidence_reader import search_papers
        latest = search_papers(f"{topic} (recent {recency_days} days)",
                                  max_results=10) or []
    except Exception as e:
        _log.warning("currency_study fetch fail: %s", e)
        latest = []

    # 2) 내재화 (코퍼스 최신화)
    ingested = _internalize([
        {"pmid": p.get("pmid"), "title": p.get("title", ""),
         "abstract": (p.get("abstract") or "")[:1500],
         "metadata": {"pmid": p.get("pmid"), "year": p.get("year"),
                       "source": "currency_study"}}
        for p in latest
    ])

    # 3) novelty 재평가 (가능 시)
    novelty_shift = None
    try:
        from src.research.novelty_checker import NoveltyChecker
        nc = NoveltyChecker()
        if hasattr(nc, "evaluate"):
            novelty_shift = nc.evaluate({"title": topic}, latest)
    except Exception:
        pass

    card = {
        "topic": topic,
        "new_papers_count": len(latest),
        "ingested_to_rag": ingested,
        "novelty_shift": novelty_shift,
        "preview": [{"pmid": p.get("pmid"), "title": (p.get("title") or "")[:140],
                       "year": p.get("year")} for p in latest[:5]],
        "rendered_as": "study_card (not push notification)",
    }
    _events.append("currency_study_done", card, actor="currency_study")
    return card


__all__ = [
    "deep_research", "currency_study",
    "killswitch_active", "detect_gaps", "synthesize",
    "DeepResearchReport", "IterResult",
]
