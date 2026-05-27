"""Self-consistency / multi-sample ensemble — 같은 prompt를 n회 sample → 다수결/모순검출.

통계 해석, 인용 추천 같은 critical output에서 hallucination 확률 ↓.

호출:
    from src.llm.self_consistency import sample_consensus
    result = sample_consensus(prompt="...", system="...", n=3,
                                extractor=lambda r: r.lower())
    # → {"answer": "...", "n_agree": 3, "agreement": 1.0,
    #     "outliers": [], "all_responses": [...]}
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Dict, List, Optional


def sample_consensus(prompt: str, *, system: str = "", n: int = 3,
                      task: str = "qa",
                      extractor: Optional[Callable[[str], str]] = None,
                      llm_client=None,
                      max_tokens: int = 1024) -> Dict:
    """같은 prompt를 n회 호출해 다수결.

    Args:
        extractor: 응답 정규화 (소문자/숫자 추출 등). None이면 원문 strip.
        llm_client: 미주입 시 `get_llm_client(task)` 새로 생성.

    Returns:
        {"answer": str (가장 빈번), "n_agree": int, "agreement": float (0~1),
         "outliers": [str], "all_responses": [str]}
    """
    if llm_client is None:
        from src.llm import get_llm_client
        llm_client = get_llm_client(task=task)

    extractor = extractor or (lambda r: (r or "").strip())
    responses: List[str] = []
    for _ in range(max(1, n)):
        try:
            r = llm_client.generate(prompt, system_prompt=system, max_tokens=max_tokens)
        except Exception:
            r = ""
        responses.append(r)

    normalized = [extractor(r) for r in responses]
    cnt = Counter(normalized)
    if not cnt:
        return {"answer": "", "n_agree": 0, "agreement": 0.0,
                "outliers": [], "all_responses": responses}
    top, top_n = cnt.most_common(1)[0]
    outliers = [r for r, c in cnt.items() if r != top]
    return {"answer": top, "n_agree": top_n,
            "agreement": top_n / max(1, len(normalized)),
            "outliers": outliers, "all_responses": responses}
