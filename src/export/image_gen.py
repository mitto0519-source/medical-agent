"""Multi-modal image generation — 의학 다이어그램·flow chart 자동 생성.

배경 (2026-05-30):
    publication_figure_generator는 statsmodels 결과로 forest/ROC/Kaplan-Meier 만들지만,
    PRISMA flow chart, study design 다이어그램, conceptual model 같은 '설명용 그림'은 못함.
    이 모듈은 두 경로 제공:

    1) Mermaid (text → SVG/PNG): 정확한 medical flow (PRISMA, study design)
       - LLM이 mermaid syntax 생성 → mermaid CLI 또는 mermaid.ink 양식 렌더
       - 환각 위험 낮음 (text-based)

    2) DALL-E / Stable Diffusion (text → image): conceptual illustration
       - 의학 그림은 부정확할 수 있어 limitation 명시
       - 사용자가 명시적으로 요청한 경우만

API:
    gen_mermaid_chart(description, *, kind="prisma"|"study_design"|"flowchart") -> bytes
        → PNG bytes
    gen_dalle_image(prompt, *, size="1024x1024") -> bytes (optional, requires OPENAI_API_KEY)

호출:
    workspace Figures 탭의 "+ Mermaid 다이어그램" 버튼.
    chat에서 "PRISMA flow chart 그려줘" 요청 시 자동.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)


# ── Mermaid: LLM → syntax → SVG/PNG via mermaid.ink (외부 의존 없음) ─────────

def _llm_to_mermaid_syntax(description: str, kind: str = "flowchart") -> str:
    """LLM에 mermaid syntax 생성시킴. kind에 따라 양식 제시."""
    from src.llm import get_llm_client
    client = get_llm_client(task="fast")

    sys_p = (
        "You generate ONLY Mermaid diagram syntax (no prose, no markdown fence). "
        "Output starts directly with 'graph TD' or 'flowchart TD' or similar.\n"
        "For PRISMA: use flowchart TD with Identification → Screening → Eligibility → Included.\n"
        "For study_design: use flowchart LR with Population → Exposure → Outcome → Analysis.\n"
        "Use Korean text in [labels] if the description is Korean.\n"
        "Keep node count under 15."
    )
    usr = f"Kind: {kind}\nDescription: {description}\n\nReturn mermaid syntax only."
    out = client.generate(usr, system_prompt=sys_p, max_tokens=600, task="fast")
    # ```mermaid ... ``` fence 제거
    text = (out or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def gen_mermaid_chart(description: str, *,
                       kind: str = "flowchart",
                       out_dir: str = "data/exports") -> bytes:
    """description → mermaid syntax → PNG bytes (via mermaid.ink HTTP API).

    mermaid.ink는 무료 공개 서비스. 인터넷 없으면 syntax만 반환.
    """
    import urllib.request

    syntax = _llm_to_mermaid_syntax(description, kind)
    if not syntax:
        raise RuntimeError("Mermaid syntax 생성 실패 (LLM 응답 비어있음)")

    # mermaid.ink: base64 인코딩한 syntax를 URL path로
    try:
        b64 = base64.urlsafe_b64encode(syntax.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{b64}?type=png"
        with urllib.request.urlopen(url, timeout=15) as resp:
            png_bytes = resp.read()
    except Exception as e:
        # 인터넷 없으면 syntax를 SVG처럼 텍스트로 wrap
        _log.warning("mermaid.ink 렌더 실패 (syntax만 반환): %s", e)
        svg = (f'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
               f'width="600" height="400"><foreignObject width="100%" height="100%">'
               f'<pre xmlns="http://www.w3.org/1999/xhtml">{syntax}</pre>'
               f'</foreignObject></svg>')
        png_bytes = svg.encode("utf-8")

    # 저장
    try:
        out_path = Path(out_dir) / f"mermaid_{kind}_{abs(hash(syntax)) % 100000}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png_bytes)
        _events.append("mermaid_generated",
                        {"kind": kind, "syntax_chars": len(syntax),
                         "png_bytes": len(png_bytes), "path": str(out_path)},
                        actor="image_gen")
    except Exception:
        pass

    return png_bytes


# ── DALL-E (optional, OPENAI_API_KEY 있을 때만) ─────────────────────────────

def gen_dalle_image(prompt: str, *, size: str = "1024x1024",
                     out_dir: str = "data/exports") -> Optional[bytes]:
    """DALL-E 3로 이미지 생성. medical conceptual illustration용.
    OPENAI_API_KEY 없으면 None 반환 (graceful).
    """
    if not os.environ.get("OPENAI_API_KEY"):
        _log.warning("OPENAI_API_KEY 없음 → DALL-E 호출 스킵")
        return None
    try:
        from openai import OpenAI
        client = OpenAI()
        # 의학 도메인 안전성 — prompt에 medical illustration 양식 명시
        enhanced = (
            f"Medical research illustration: {prompt}. "
            f"Style: professional, journal-quality, monochrome with accent color, "
            f"clinical clarity. No text labels (will be added separately)."
        )
        result = client.images.generate(
            model="dall-e-3", prompt=enhanced, size=size,
            quality="standard", n=1, response_format="b64_json",
        )
        b64 = result.data[0].b64_json
        png_bytes = base64.b64decode(b64)

        out_path = Path(out_dir) / f"dalle_{abs(hash(prompt)) % 100000}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png_bytes)
        _events.append("dalle_generated",
                        {"prompt_chars": len(prompt), "size": size,
                         "png_bytes": len(png_bytes), "path": str(out_path)},
                        actor="image_gen")
        return png_bytes
    except Exception as e:
        _log.warning("DALL-E 호출 실패: %s", e)
        return None


__all__ = ["gen_mermaid_chart", "gen_dalle_image"]
