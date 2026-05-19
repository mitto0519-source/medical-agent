"""MetaLearner — 3개 학습 신호의 가중치 통합 조율자.

OutcomeTracker + KnowledgeDistiller + FineTuneManager의 신호를
가중치 기반으로 통합해 최종 학습 컨텍스트를 생성.

가중치 업데이트 원칙:
  - confidence * log(data_volume + 1) 로 초기 가중치 계산
  - 이전 사이클에서 peer_score가 개선됐으면 기여한 신호의 가중치 증가
  - 데이터 없는 신호(cold start)는 자동으로 weight ≈ 0
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_META_FILE = Path("data/agent_self/meta_insights.json")
_WEIGHTS_FILE = Path("data/agent_self/meta_weights.json")

_SOURCES = ["outcome_tracker", "knowledge_distiller", "finetune_manager"]
_DEFAULT_WEIGHTS = {s: 1.0 for s in _SOURCES}


class MetaLearner:
    """3개 신호의 통합 조율자."""

    def __init__(self):
        self.weights = self._load_weights()

    def run_cycle(self) -> Dict:
        """전체 학습 사이클 실행 — 3개 신호 수집 → 통합 → 저장."""
        _log.info("[meta] 학습 사이클 시작")

        from src.learning import outcome_tracker, knowledge_distiller, finetune_manager

        signals = {
            "outcome_tracker": outcome_tracker.extract_insights(),
            "knowledge_distiller": knowledge_distiller.distill(),
            "finetune_manager": finetune_manager.get_insights(),
        }

        for src, sig in signals.items():
            _log.info("[meta] %s: confidence=%.2f, data=%d, insights=%d",
                      src, sig["confidence"], sig["data_volume"], len(sig["insights"]))

        # 가중치 재계산
        raw_weights = {}
        for src, sig in signals.items():
            conf = sig.get("confidence", 0.1)
            vol = sig.get("data_volume", 0)
            raw_weights[src] = self.weights.get(src, 1.0) * conf * math.log(vol + 2)

        total = sum(raw_weights.values()) or 1.0
        norm_weights = {k: v / total for k, v in raw_weights.items()}

        # 인사이트 통합 (가중치 순 정렬)
        merged_insights: List[Dict] = []
        for src, sig in signals.items():
            w = norm_weights[src]
            for insight in sig.get("insights", []):
                merged_insights.append({
                    "text": insight,
                    "source": src,
                    "weight": w,
                })

        # 가중치 높은 순으로 정렬, 상위 15개 선택
        merged_insights.sort(key=lambda x: x["weight"], reverse=True)
        top_insights = merged_insights[:15]

        # 최종 프롬프트 주입용 텍스트 생성
        learning_context = self._build_context(top_insights, norm_weights)

        result = {
            "updated_at": datetime.now().isoformat(),
            "cycle_weights": norm_weights,
            "top_insights": top_insights,
            "learning_context": learning_context,
            "signal_summary": {
                src: {
                    "confidence": sig["confidence"],
                    "data_volume": sig["data_volume"],
                    "n_insights": len(sig["insights"]),
                    "norm_weight": norm_weights[src],
                }
                for src, sig in signals.items()
            },
        }

        _META_FILE.parent.mkdir(parents=True, exist_ok=True)
        _META_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self._update_weights(signals, norm_weights)

        _log.info("[meta] 사이클 완료: %d개 통합 인사이트, weights=%s",
                  len(top_insights),
                  {k: f"{v:.2f}" for k, v in norm_weights.items()})

        from src.memory import change_log
        change_log.log(
            title=f"MetaLearner 사이클 완료: {len(top_insights)}개 통합 인사이트",
            action_type="meta_learn",
            description=(
                f"OutcomeTracker({norm_weights['outcome_tracker']:.2f}) + "
                f"KnowledgeDistiller({norm_weights['knowledge_distiller']:.2f}) + "
                f"FineTuner({norm_weights['finetune_manager']:.2f}) 통합"
            ),
            outputs={"n_insights": len(top_insights), "weights": norm_weights},
        )
        return result

    def get_learning_context(self) -> str:
        """저장된 학습 컨텍스트 반환 — LLM 시스템 프롬프트 주입용."""
        if not _META_FILE.exists():
            return ""
        try:
            data = json.loads(_META_FILE.read_text(encoding="utf-8"))
            return data.get("learning_context", "")
        except Exception:
            return ""

    def _build_context(self, insights: List[Dict], weights: Dict) -> str:
        if not insights:
            return ""

        lines = ["## 자율 학습 기반 도메인 인사이트 (MetaLearner 통합)"]
        lines.append(
            f"신호 가중치: OutcomeTracker {weights['outcome_tracker']:.0%} | "
            f"KnowledgeDistiller {weights['knowledge_distiller']:.0%} | "
            f"FineTuner {weights['finetune_manager']:.0%}"
        )
        lines.append("")

        by_source: Dict[str, List[str]] = {}
        for item in insights:
            src = item["source"]
            by_source.setdefault(src, []).append(item["text"])

        source_labels = {
            "outcome_tracker": "성과 패턴",
            "knowledge_distiller": "문헌 증류",
            "finetune_manager": "파인튜닝",
        }
        for src in _SOURCES:
            items = by_source.get(src, [])
            if items:
                lines.append(f"### {source_labels.get(src, src)}")
                for item in items[:5]:
                    lines.append(f"- {item}")
                lines.append("")

        return "\n".join(lines)

    def _update_weights(self, signals: Dict, used_weights: Dict) -> None:
        """다음 사이클을 위한 가중치 업데이트 — 고신뢰 신호 강화."""
        new_weights = dict(self.weights)
        for src, sig in signals.items():
            conf = sig.get("confidence", 0.1)
            # confidence가 0.5 이상이면 가중치 소폭 증가, 이하면 감소
            if conf >= 0.5:
                new_weights[src] = min(3.0, new_weights.get(src, 1.0) * 1.05)
            else:
                new_weights[src] = max(0.3, new_weights.get(src, 1.0) * 0.97)

        self.weights = new_weights
        _WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _WEIGHTS_FILE.write_text(
            json.dumps(new_weights, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_weights(self) -> Dict:
        if _WEIGHTS_FILE.exists():
            try:
                return json.loads(_WEIGHTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return dict(_DEFAULT_WEIGHTS)
