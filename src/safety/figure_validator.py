"""Vision으로 figure 자체 검증 — 출력한 figure를 Claude Vision으로 다시 읽어
axis label/CI bar/legend/숫자 일관성 자동 검출.

기존 `src/ingestion/document_reader.py`의 `_image_ocr()`이 이미 Claude Vision wrapper.
본 모듈은 그 vision client를 그대로 재사용해 **figure-specific 프롬프트**로 호출.

호출:
    from src.safety.figure_validator import validate_figure
    report = validate_figure("data/exports/Figure3_forest_subgroups.png",
                              expected={"n_rows": 21, "ref_line": 1.0,
                                        "x_label": "Adjusted Odds Ratio"})
    # report.ok: bool / report.issues: [str]

audit_trail 자동 기록 (ok=False시).
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class FigureValidationReport:
    ok: bool = True
    image_path: str = ""
    raw_vision_response: str = ""
    issues: List[str] = field(default_factory=list)
    detected: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_PROMPT = """이 의학 논문 figure를 출판 품질 기준으로 검증하세요. 다음 JSON으로 답해주세요:

{{
  "axis_labels_visible": true|false,
  "axis_labels_text": "...",
  "legend_present": true|false,
  "ci_bars_complete": true|false,    // forest plot일 때 모든 추정값에 CI bar 짝
  "ref_line_visible": true|false,    // OR=1 등 기준선
  "numeric_labels_readable": true|false,
  "font_consistent": true|false,
  "low_contrast_warnings": ["..."],  // 가독성 문제 텍스트
  "missing_elements": ["..."],
  "n_data_points_estimated": <int>,
  "overall_quality": "publication_ready" | "minor_issues" | "major_issues",
  "specific_issues": ["..."]
}}

검증 기준 (있으면 이 값과 비교):
{expected_block}
"""


def _encode_image(path: Path) -> tuple[str, str]:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = path.suffix.lower().lstrip(".")
    media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    return b64, media_type


def validate_figure(image_path: str | Path,
                     expected: Optional[Dict] = None,
                     timeout: int = 30) -> FigureValidationReport:
    """Vision으로 figure 검증. 실패해도 raise 안 함 — report.ok=False 반환."""
    p = Path(image_path)
    rep = FigureValidationReport(image_path=str(p))
    if not p.exists():
        rep.ok = False
        rep.issues.append(f"이미지 파일 없음: {p}")
        _emit_audit(rep, "missing_image")
        return rep

    try:
        from src.config.models import get_vision_model
        import anthropic
        _, model_id = get_vision_model()
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            rep.ok = False
            rep.issues.append("ANTHROPIC_API_KEY 미설정 — vision 검증 스킵")
            return rep
        client = anthropic.Anthropic(api_key=key)
        b64, mt = _encode_image(p)
        exp_block = "(기준값 없음 — 일반 품질만 평가)" if not expected else str(expected)
        prompt = _PROMPT.format(expected_block=exp_block)

        resp = client.messages.create(
            model=model_id, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        rep.raw_vision_response = raw

        # JSON 추출
        import json, re
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                detected = json.loads(m.group(0))
                rep.detected = detected
                if not detected.get("axis_labels_visible", True):
                    rep.issues.append("axis label 누락 또는 보이지 않음")
                if not detected.get("ci_bars_complete", True):
                    rep.issues.append("CI bar 짝 안 맞음")
                if not detected.get("numeric_labels_readable", True):
                    rep.issues.append("수치 라벨 가독성 낮음")
                for it in detected.get("specific_issues", []):
                    rep.issues.append(it)
                quality = detected.get("overall_quality", "minor_issues")
                if quality == "major_issues":
                    rep.ok = False
                elif rep.issues:
                    rep.ok = (quality == "publication_ready")
            except Exception as e:
                rep.issues.append(f"vision JSON 파싱 실패: {e}")
        else:
            rep.issues.append("vision 응답에서 JSON 미발견")
    except Exception as e:
        rep.ok = False
        rep.issues.append(f"vision 호출 실패: {e}")
        _log.warning("validate_figure: %s", e)

    if not rep.ok:
        _emit_audit(rep, "figure_validation_fail")
    return rep


def _emit_audit(rep: FigureValidationReport, subtype: str):
    try:
        from src.safety.audit_trail import record_safety_event
        record_safety_event(subtype, {"image": rep.image_path,
                                       "n_issues": len(rep.issues),
                                       "first": rep.issues[0] if rep.issues else ""})
    except Exception:
        pass
