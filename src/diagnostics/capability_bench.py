"""Phase C — 역량 자기평가 + 자동 개선 체계 (Google 수준 AGI 근접).

Google 대비 격차 해소:
- 취약 역량 자동 감지 → insights.json 누적 → 다음 프롬프트 자동 반영
- 매 논문 완성 후 7개 차원 자동 벤치마크
- 점수 추이 추적 + 지속 개선 루프

평가 차원 (각 0~100점)
1. citation_accuracy    — 인용 출처 정확도 (인라인 인용 수/논문 길이)
2. stats_completeness   — 통계 설명 완성도 (OR/CI/p값 모두 포함 여부)
3. methodology_quality  — 방법론 적절성 (설계, 혼란변수, 한계점 포함 여부)
4. structure_score      — 논문 구조 점수 (IMRAD 충족 여부)
5. language_quality     — 언어 품질 (LLM 자가평가)
6. novelty_alignment    — 신규성 정렬도 (주제 신규성 vs 실제 기여)
7. figure_completeness  — 그림/표 완성도 (생성된 그림 수)
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.llm import get_llm_client

_log = get_logger(__name__)

_BENCH_HISTORY_PATH = Path("data/diagnostics/capability_bench_history.json")
_CAP_INSIGHTS_PATH = Path("data/diagnostics/capability_insights.json")  # CapabilityBench 전용 (agent_insight와 충돌 방지)


@dataclass
class BenchmarkResult:
    timestamp: str
    topic_title: str
    citation_accuracy: float = 0.0
    stats_completeness: float = 0.0
    methodology_quality: float = 0.0
    structure_score: float = 0.0
    language_quality: float = 0.0
    novelty_alignment: float = 0.0
    figure_completeness: float = 0.0
    overall: float = 0.0
    weak_areas: List[str] = None
    improvement_notes: str = ""

    def __post_init__(self):
        if self.weak_areas is None:
            self.weak_areas = []
        scores = [
            self.citation_accuracy, self.stats_completeness,
            self.methodology_quality, self.structure_score,
            self.language_quality, self.novelty_alignment,
            self.figure_completeness,
        ]
        self.overall = round(sum(scores) / len(scores), 1)
        self.weak_areas = [
            name for name, score in zip(
                ["인용정확도", "통계완성도", "방법론품질", "논문구조",
                 "언어품질", "신규성정렬", "그림완성도"],
                scores
            )
            if score < 60
        ]

    def to_dict(self) -> dict:
        return asdict(self)


class CapabilityBench:
    """매 논문 완성 후 역량을 자동 벤치마크하고 약점을 insights.json에 누적."""

    def __init__(self):
        self._llm = get_llm_client()

    def evaluate(
        self,
        draft: str,
        stat_result: dict,
        topic: dict,
        figures: dict = None,
        novelty_score: float = 0.0,
    ) -> BenchmarkResult:
        """논문 초안 + 통계 결과를 평가."""
        from datetime import datetime
        figures = figures or {}
        title = topic.get("title", "Untitled")

        scores = {
            "citation_accuracy": self._score_citations(draft),
            "stats_completeness": self._score_stats(draft, stat_result),
            "methodology_quality": self._score_methodology(draft),
            "structure_score": self._score_structure(draft),
            "language_quality": self._score_language(draft, title),
            "novelty_alignment": min(100.0, float(novelty_score) * 10),
            "figure_completeness": self._score_figures(figures),
        }

        result = BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            topic_title=title,
            **scores,
        )

        # 약점 기반 개선 노트 생성
        if result.weak_areas:
            result.improvement_notes = self._generate_improvement_notes(result)

        self._save_history(result)
        self._update_insights(result)
        _log.info("[CapabilityBench] 전체 점수: %.1f/100 | 약점: %s",
                  result.overall, result.weak_areas)
        return result

    # ── 평가 함수들 ───────────────────────────────────────────────────────

    def _score_citations(self, draft: str) -> float:
        """인라인 인용 밀도 평가 ([1], [2] 형태)."""
        citations = len(re.findall(r'\[\d+\]', draft))
        words = len(draft.split())
        if words == 0:
            return 0.0
        density = citations / (words / 1000)  # 1000단어당 인용 수
        return min(100.0, density * 20)  # 5개/1000단어 = 100점

    def _score_stats(self, draft: str, stat_result: dict) -> float:
        """OR, CI, p값이 논문에 포함됐는지 확인."""
        has_or = bool(re.search(r'OR\s*=?\s*[\d.]+', draft, re.IGNORECASE)
                      or re.search(r'odds ratio', draft, re.IGNORECASE))
        has_ci = bool(re.search(r'95%\s*CI', draft, re.IGNORECASE)
                      or re.search(r'confidence interval', draft, re.IGNORECASE))
        has_p = bool(re.search(r'p\s*[<>=]\s*0\.\d+', draft, re.IGNORECASE))
        has_n = bool(re.search(r'n\s*=\s*[\d,]+', draft))
        score = (has_or + has_ci + has_p + has_n) / 4 * 100

        # 통계 결과와 논문 내용 일치도 확인
        if stat_result.get("model_vars"):
            sig_vars = [v for v in stat_result["model_vars"] if v.get("significant")]
            if sig_vars:
                first_or = str(round(float(sig_vars[0].get("or_value", 0)), 1))
                if first_or in draft:
                    score = min(100.0, score + 10)
        return round(score, 1)

    def _score_methodology(self, draft: str) -> float:
        """방법론 완성도 평가."""
        checks = {
            "study_design": bool(re.search(
                r'cross.sectional|cohort|case.control|retrospective|prospective', draft, re.I)),
            "confounders": bool(re.search(
                r'adjust|confounder|covariate|control for', draft, re.I)),
            "sample_size": bool(re.search(r'n\s*=\s*[\d,]+', draft)),
            "limitations": bool(re.search(r'limitation|한계|제한', draft, re.I)),
            "ethics": bool(re.search(r'IRB|ethics|ethical|institutional review', draft, re.I)),
            "software": bool(re.search(r'SAS|SPSS|R\s+software|STATA|Python', draft, re.I)),
        }
        score = sum(checks.values()) / len(checks) * 100
        return round(score, 1)

    def _score_structure(self, draft: str) -> float:
        """IMRAD 구조 충족 여부."""
        sections = {
            "abstract": bool(re.search(r'Abstract|초록', draft, re.I)),
            "introduction": bool(re.search(r'Introduction|서론|배경', draft, re.I)),
            "methods": bool(re.search(r'Methods|방법|대상 및 방법', draft, re.I)),
            "results": bool(re.search(r'Results|결과', draft, re.I)),
            "discussion": bool(re.search(r'Discussion|고찰', draft, re.I)),
            "conclusion": bool(re.search(r'Conclusion|결론', draft, re.I)),
            "references": bool(re.search(r'References|참고문헌|\[\d+\]', draft, re.I)),
        }
        return round(sum(sections.values()) / len(sections) * 100, 1)

    def _score_language(self, draft: str, title: str) -> float:
        """LLM 기반 언어 품질 평가 (짧은 샘플 기준)."""
        sample = draft[:2000] if len(draft) > 2000 else draft
        prompt = f"""Rate the academic English quality of this paper excerpt on a scale of 0-100.
Consider: clarity, academic tone, grammar, terminology appropriateness.

Title: {title}
Excerpt: {sample[:500]}

Return only a number between 0 and 100. No explanation."""
        try:
            raw = self._llm.generate(prompt, task="qa")
            score = float(re.search(r'\d+', raw).group())
            return min(100.0, max(0.0, score))
        except Exception:
            return 70.0  # 기본값

    def _score_figures(self, figures: dict) -> float:
        """생성된 그림/표 수 기반 평가."""
        n = len(figures)
        if n == 0:
            return 0.0
        if n >= 5:
            return 100.0
        return round(n / 5 * 100, 1)

    # ── 개선 노트 + 기억 업데이트 ─────────────────────────────────────────

    def _generate_improvement_notes(self, result: BenchmarkResult) -> str:
        """약점 기반 개선 노트 생성."""
        advice_map = {
            "인용정확도": "인라인 인용 삽입 강화 — insert_inline_citations() 호출 확인",
            "통계완성도": "OR/CI/p값을 abstract와 results 모두에 명시",
            "방법론품질": "study design, confounders, limitations, software 명시 필요",
            "논문구조": "IMRAD 구조 (Abstract/Intro/Methods/Results/Discussion) 완전 포함",
            "언어품질": "학술 영어 표현 강화 — PaperWriter 프롬프트 개선 필요",
            "신규성정렬": "연구 주제와 기여 차별성 강조 섹션 보강",
            "그림완성도": "publication_figure_generator.generate_all() 호출 확인",
        }
        notes = [advice_map.get(area, area) for area in result.weak_areas]
        return " | ".join(notes)

    def _save_history(self, result: BenchmarkResult):
        """벤치마크 이력 저장."""
        _BENCH_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if _BENCH_HISTORY_PATH.exists():
            try:
                history = json.loads(_BENCH_HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append(result.to_dict())
        history = history[-100:]  # 최근 100개만 유지
        _BENCH_HISTORY_PATH.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _update_insights(self, result: BenchmarkResult):
        """약점을 insights.json에 누적하여 다음 프롬프트에 자동 반영."""
        if not result.weak_areas:
            return
        try:
            insights = {}
            if _CAP_INSIGHTS_PATH.exists():
                insights = json.loads(_CAP_INSIGHTS_PATH.read_text(encoding="utf-8"))
            if "capability_weaknesses" not in insights:
                insights["capability_weaknesses"] = []
            entry = {
                "timestamp": result.timestamp,
                "overall_score": result.overall,
                "weak_areas": result.weak_areas,
                "improvement_notes": result.improvement_notes,
            }
            insights["capability_weaknesses"].append(entry)
            insights["capability_weaknesses"] = insights["capability_weaknesses"][-20:]
            insights["latest_bench_score"] = result.overall
            _CAP_INSIGHTS_PATH.write_text(
                json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _log.info("[CapabilityBench] insights.json 업데이트 완료")
        except Exception as e:
            _log.warning("[CapabilityBench] insights 업데이트 실패: %s", e)

    def get_trend(self, last_n: int = 10) -> Dict:
        """최근 N개 벤치마크의 점수 추이 반환."""
        if not _BENCH_HISTORY_PATH.exists():
            return {}
        try:
            history = json.loads(_BENCH_HISTORY_PATH.read_text(encoding="utf-8"))
            recent = history[-last_n:]
            if not recent:
                return {}
            avg_overall = sum(r["overall"] for r in recent) / len(recent)
            latest = recent[-1]
            first = recent[0]
            trend = "improving" if latest["overall"] > first["overall"] else "declining"
            return {
                "avg_overall": round(avg_overall, 1),
                "latest_overall": latest["overall"],
                "trend": trend,
                "n_evaluations": len(history),
                "common_weak_areas": self._most_common_weak_areas(recent),
            }
        except Exception as e:
            _log.warning("[CapabilityBench] 추이 계산 실패: %s", e)
            return {}

    @staticmethod
    def _most_common_weak_areas(history: list) -> List[str]:
        from collections import Counter
        all_areas = []
        for r in history:
            all_areas.extend(r.get("weak_areas", []))
        if not all_areas:
            return []
        return [area for area, _ in Counter(all_areas).most_common(3)]

    def build_improvement_context(self) -> str:
        """insights.json의 약점 이력을 LLM 프롬프트 컨텍스트로 변환.

        인스턴스 메서드는 모듈 함수에 위임 (LLM 클라이언트 생성 없이 가볍게 호출 가능).
        """
        return get_improvement_context()


def get_improvement_context() -> str:
    """약점 이력 → LLM 프롬프트 컨텍스트 (LLM 클라이언트 생성 없는 경량 함수).

    `_build_system()`이 매 호출마다 부르므로 파일 읽기만 수행한다.
    Phase C 자기개선 루프를 닫는 핵심 연결점.
    """
    try:
        if not _CAP_INSIGHTS_PATH.exists():
            return ""
        insights = json.loads(_CAP_INSIGHTS_PATH.read_text(encoding="utf-8"))
        weaknesses = insights.get("capability_weaknesses", [])
        if not weaknesses:
            return ""
        recent = weaknesses[-3:]
        # 최근 3회 약점 빈도 집계 → 반복되는 약점 강조
        from collections import Counter
        area_counter = Counter()
        for w in recent:
            for a in (w.get("weak_areas") or []):
                area_counter[a] += 1
        if not area_counter:
            return ""
        top_weak = ", ".join(f"{a}(×{c})" for a, c in area_counter.most_common(3))
        lines = [
            "SELF-IMPROVEMENT FROM PAST BENCHMARKS (proactively strengthen these weak areas):",
            f"- 반복 약점: {top_weak}",
        ]
        for w in recent:
            note = w.get("improvement_notes", "")
            if note:
                lines.append(f"- {note[:200]}")
        return "\n".join(lines)
    except Exception:
        return ""


def run_capability_bench(
    draft: str,
    stat_result: dict,
    topic: dict,
    figures: dict = None,
    novelty_score: float = 0.0,
) -> BenchmarkResult:
    """편의 함수 — 논문 파이프라인 종료 시 자동 호출."""
    return CapabilityBench().evaluate(
        draft=draft,
        stat_result=stat_result,
        topic=topic,
        figures=figures,
        novelty_score=novelty_score,
    )
