"""Results 섹션 자동 생성 — 통계 분석 결과 → 학술 논문 텍스트."""
from __future__ import annotations

from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.config.models import get_model

_log = get_logger(__name__)


class ResultsWriter:
    """통계 결과 딕셔너리를 학술 논문 Results 섹션 텍스트로 변환."""

    def write(
        self,
        analysis_result: Dict,
        topic: Dict,
        dataset_name: str = "KYRBS",
        n_total: Optional[int] = None,
    ) -> str:
        """
        Args:
            analysis_result: AutoAnalyzer.analyze() 반환값
            topic: {"title": str, "exposure": str, "outcome": str, "population": str}
            dataset_name: "KYRBS" | "KNHANES"
            n_total: 전체 대상자 수

        Returns:
            Results 섹션 텍스트 (학술 논문 스타일)
        """
        test = analysis_result.get("test_used", "")
        p = analysis_result.get("p_value")
        effect = analysis_result.get("effect_size")
        ci = analysis_result.get("ci", [])
        summary = analysis_result.get("summary", "")
        table_data = analysis_result.get("table", [])

        exposure = topic.get("exposure", "노출변수")
        outcome = topic.get("outcome", "결과변수")
        population = topic.get("population", "대상자")

        # LLM으로 자연스러운 Results 텍스트 생성
        try:
            return self._llm_write(analysis_result, topic, dataset_name, n_total)
        except Exception as e:
            _log.warning(f"LLM Results 작성 실패, 템플릿 사용: {e}")
            return self._template_write(analysis_result, topic, dataset_name, n_total)

    def _llm_write(self, result: Dict, topic: Dict, dataset: str, n_total: Optional[int]) -> str:
        from src.llm.claude_client import ClaudeClient

        client = ClaudeClient()
        prompt = f"""다음 통계 분석 결과를 학술 논문 Results 섹션 텍스트로 작성하세요.
Vancouver 스타일, 한국어, 3~5 문단.

연구 정보:
- 제목: {topic.get('title', '')}
- 노출변수: {topic.get('exposure', '')}
- 결과변수: {topic.get('outcome', '')}
- 대상: {topic.get('population', '')}
- 데이터: {dataset}{f', N={n_total:,}' if n_total else ''}

통계 결과:
{result.get('summary', '')}
검정: {result.get('test_used', '')}
p값: {result.get('p_value', '')}
효과크기: {result.get('effect_size', '')}
95% CI: {result.get('ci', [])}

요구사항:
- "본 연구에서는..."으로 시작
- 수치는 모두 포함 (OR, CI, p값)
- 통계적 유의성 명확히 기술
- 테이블/그림은 "Table 1", "Figure 1" 형식으로 참조
"""
        return client.complete(prompt, max_tokens=1500)

    def _template_write(self, result: Dict, topic: Dict, dataset: str, n_total: Optional[int]) -> str:
        test = result.get("test_used", "통계 분석")
        p = result.get("p_value")
        effect = result.get("effect_size")
        ci = result.get("ci", [])
        exposure = topic.get("exposure", "노출변수")
        outcome = topic.get("outcome", "결과변수")
        population = topic.get("population", "대상자")
        p_str = "<0.001" if p and p < 0.001 else f"{p:.3f}" if p is not None else "N/A"
        ci_str = f"{ci[0]:.2f}–{ci[1]:.2f}" if len(ci) == 2 else "N/A"

        n_str = f"{n_total:,}명의 " if n_total else ""
        text = (
            f"본 연구에서는 {dataset} 자료를 이용하여 {n_str}{population}을 대상으로 "
            f"{exposure}과 {outcome}의 관련성을 분석하였다.\n\n"
            f"{test}을 시행한 결과, {exposure}은 {outcome}과 통계적으로 "
            f"{'유의한' if p and p < 0.05 else '유의하지 않은'} 관련성을 보였다 "
            f"(효과크기={effect:.3f}, 95% CI {ci_str}, p={p_str}). "
            f"자세한 결과는 Table 1 및 Figure 1에 제시하였다.\n\n"
            f"{result.get('summary', '')}"
        )
        return text
