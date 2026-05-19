"""Signal 3: Anthropic Fine-tuning 관리자.

고점수 논문(peer_score >= 75)을 학습 데이터로 fine-tuning 제출.
완료된 fine-tuned 모델 ID를 추적하고 MetaLearner에 신호 전달.
fine-tuning API 미지원 시 graceful fallback.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_STATE = Path("data/agent_self/finetune_state.json")
_TRAINING_DIR = Path("data/finetune")
_MIN_SCORE = 75      # fine-tuning 대상 최소 peer score
_MIN_SAMPLES = 10    # fine-tuning 최소 샘플 수


def get_insights() -> Dict:
    """현재 fine-tuning 상태에서 신호 추출."""
    state = _load_state()

    insights = []
    confidence = 0.1
    data_volume = state.get("total_samples", 0)

    active_model = state.get("active_model_id")
    if active_model:
        insights.append(
            f"Fine-tuned 모델 활성: {active_model}. "
            f"한국 공중보건 도메인 특화 학습 완료 "
            f"(학습 샘플 {state.get('total_samples', 0)}개)."
        )
        confidence = 0.8

    pending = state.get("pending_job_id")
    if pending:
        status = _check_job_status(pending)
        if status == "succeeded":
            model_id = _get_fine_tuned_model(pending)
            if model_id:
                state["active_model_id"] = model_id
                state["pending_job_id"] = None
                _save_state(state)
                insights.append(f"Fine-tuning 완료: {model_id} 활성화.")
                confidence = 0.8
        elif status in ("failed", "cancelled"):
            _log.warning("[finetune] 작업 실패: %s", pending)
            state["pending_job_id"] = None
            _save_state(state)
        else:
            insights.append(f"Fine-tuning 진행 중 (job: {pending[:16]}...).")
            confidence = 0.3

    high_score_papers = _collect_high_score_papers()
    state["total_samples"] = len(high_score_papers)

    if not active_model and not pending and len(high_score_papers) >= _MIN_SAMPLES:
        job_id = _submit_finetune_job(high_score_papers)
        if job_id:
            state["pending_job_id"] = job_id
            state["submitted_at"] = datetime.now().isoformat()
            _save_state(state)
            insights.append(
                f"Fine-tuning 제출: {len(high_score_papers)}개 고품질 논문 "
                f"(peer_score≥{_MIN_SCORE}). job_id={job_id[:16]}..."
            )
            confidence = 0.3
    elif len(high_score_papers) < _MIN_SAMPLES:
        insights.append(
            f"Fine-tuning 대기 중: 고품질 논문 {len(high_score_papers)}/{_MIN_SAMPLES}개 "
            f"(peer_score≥{_MIN_SCORE} 필요). 논문 파이프라인 실행으로 데이터 축적."
        )

    _save_state(state)

    return {
        "source": "finetune_manager",
        "insights": insights,
        "confidence": confidence,
        "data_volume": data_volume,
        "active_model": active_model,
    }


def _collect_high_score_papers() -> List[Dict]:
    """history.json에서 peer_score >= MIN_SCORE 논문 수집."""
    history_path = Path("data/change_log/history.json")
    if not history_path.exists():
        return []
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    # peer_review + paper_write 쌍 매칭
    reviews = {
        h["inputs"].get("topic", ""): h["outputs"]
        for h in history
        if h.get("action_type") == "peer_review"
    }
    papers = []
    for h in history:
        if h.get("action_type") != "paper_write":
            continue
        topic = h.get("inputs", {}).get("topic_title", "")
        review = reviews.get(topic, {})
        score = review.get("score", 0)
        if score >= _MIN_SCORE:
            draft_path = Path(h.get("outputs", {}).get("output_path", ""))
            if draft_path.exists():
                papers.append({
                    "topic": topic,
                    "score": score,
                    "path": str(draft_path),
                })
    return papers


def _submit_finetune_job(papers: List[Dict]) -> Optional[str]:
    """Anthropic fine-tuning API에 job 제출."""
    try:
        import anthropic
        from src.config.env import bootstrap
        bootstrap()
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

        # JSONL 학습 데이터 생성
        _TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        jsonl_path = _TRAINING_DIR / "training_data.jsonl"
        lines = []
        for paper in papers:
            try:
                content = Path(paper["path"]).read_text(encoding="utf-8")[:3000]
                lines.append(json.dumps({
                    "messages": [
                        {"role": "user", "content": f"Write a Korean public health paper on: {paper['topic']}"},
                        {"role": "assistant", "content": content}
                    ]
                }, ensure_ascii=False))
            except Exception:
                continue

        if not lines:
            return None

        jsonl_path.write_text("\n".join(lines), encoding="utf-8")

        # 파일 업로드
        with open(jsonl_path, "rb") as f:
            file_obj = client.beta.files.upload(
                file=(jsonl_path.name, f, "application/jsonl")
            )

        # Fine-tuning job 제출
        job = client.beta.fine_tuning.jobs.create(
            model="claude-haiku-4-5-20251001",
            training_file=file_obj.id,
            hyperparameters={"n_epochs": 3},
        )
        _log.info("[finetune] job 제출 성공: %s", job.id)
        return job.id

    except Exception as e:
        _log.warning("[finetune] API 미지원 또는 오류 (graceful fallback): %s", str(e)[:100])
        return None


def _check_job_status(job_id: str) -> str:
    try:
        import anthropic
        from src.config.env import bootstrap
        bootstrap()
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        job = client.beta.fine_tuning.jobs.retrieve(job_id)
        return job.status
    except Exception as e:
        _log.warning("[finetune] 상태 확인 실패: %s", e)
        return "unknown"


def _get_fine_tuned_model(job_id: str) -> Optional[str]:
    try:
        import anthropic
        from src.config.env import bootstrap
        bootstrap()
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        job = client.beta.fine_tuning.jobs.retrieve(job_id)
        return getattr(job, "fine_tuned_model", None)
    except Exception:
        return None


def _load_state() -> Dict:
    if _STATE.exists():
        try:
            return json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: Dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
