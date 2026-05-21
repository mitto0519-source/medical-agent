"""Phase A — 자율 연구 루프 (Google Deep Research 수준 근접)

흐름:
  seed_topic → [질문 생성 → PubMed 검색 → 증거 합성 → 가설 수정]×N
  → novelty_score >= threshold 달성 or max_rounds → 최종 주제 + 증거 반환

Google 대비 격차 해소:
- 단방향 PubMed 검색 → 반복적 탐색+가설 수정 루프
- 5라운드, 라운드마다 새 질문 생성 (이전 발견 기반)
- 신규성 점수가 threshold 달성 시 조기 종료
"""
from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger
from src.llm import get_llm_client
from src.research.novelty_checker import NoveltyChecker

_log = get_logger(__name__)

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pubmed_search(query: str, max_results: int = 15) -> List[Dict]:
    """PubMed에서 논문 검색 후 title+abstract 반환."""
    import requests
    import xml.etree.ElementTree as ET

    try:
        r = requests.get(
            f"{_BASE_URL}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            timeout=20,
        )
        r.raise_for_status()
        pmids = r.json()["esearchresult"]["idlist"]
    except Exception as e:
        _log.warning("PubMed esearch 실패: %s", e)
        return []

    if not pmids:
        return []

    try:
        time.sleep(0.5)
        r2 = requests.get(
            f"{_BASE_URL}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "rettype": "xml", "retmode": "xml"},
            timeout=30,
        )
        r2.raise_for_status()
        root = ET.fromstring(r2.text)
    except Exception as e:
        _log.warning("PubMed efetch 실패: %s", e)
        return []

    papers = []
    for article in root.findall(".//PubmedArticle"):
        try:
            title_el = article.find(".//ArticleTitle")
            title = (title_el.text or "").strip() if title_el is not None else ""
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join((el.text or "") for el in abstract_parts if el.text)
            year_el = article.find(".//PubDate/Year")
            year = year_el.text if year_el is not None else ""
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            if title or abstract:
                papers.append({"pmid": pmid, "title": title, "abstract": abstract[:800], "year": year})
        except Exception:
            continue
    return papers


class AutonomousResearchLoop:
    """Google Deep Research 스타일의 자율 반복 연구 루프.

    Parameters
    ----------
    max_rounds:     최대 탐색 라운드 수 (기본 5)
    novelty_threshold: 이 점수 이상이면 조기 종료 (기본 7.0/10)
    questions_per_round: 라운드당 생성하는 서브 질문 수
    """

    def __init__(
        self,
        max_rounds: int = 5,
        novelty_threshold: float = 7.0,
        questions_per_round: int = 3,
    ):
        self.max_rounds = max_rounds
        self.novelty_threshold = novelty_threshold
        self.questions_per_round = questions_per_round
        self._llm = get_llm_client()
        self._novelty = NoveltyChecker()

    # ── 공개 API ──────────────────────────────────────────────────────────

    def run(self, seed_topic: Dict) -> Tuple[Dict, List[Dict], float]:
        """자율 연구 루프 실행.

        Returns
        -------
        (refined_topic, evidence_list, final_novelty_score)
        """
        topic = dict(seed_topic)
        all_evidence: List[Dict] = []
        novelty_score = 0.0

        _log.info("[AutonomousLoop] 시작: %s", topic.get("title", "")[:60])

        for round_idx in range(1, self.max_rounds + 1):
            _log.info("[AutonomousLoop] 라운드 %d/%d", round_idx, self.max_rounds)

            # 1. 현재 주제 기반 서브 질문 생성
            questions = self._generate_sub_questions(topic, all_evidence)
            _log.info("[AutonomousLoop] 질문 %d개: %s", len(questions), questions[:2])

            # 2. 각 질문으로 PubMed 검색
            round_evidence: List[Dict] = []
            for q in questions:
                papers = _pubmed_search(q, max_results=8)
                for p in papers:
                    p["search_query"] = q
                round_evidence.extend(papers)

            all_evidence.extend(round_evidence)
            _log.info("[AutonomousLoop] 라운드 %d 증거 %d개 수집", round_idx, len(round_evidence))

            if not round_evidence:
                _log.warning("[AutonomousLoop] 증거 없음 — 라운드 종료")
                break

            # 3. 증거 합성 + 주제 개선
            topic = self._refine_topic(topic, round_evidence, all_evidence)

            # 4. 신규성 재평가
            try:
                novelty_result = self._novelty.check(
                    topic=topic.get("title", ""),
                    exposure=topic.get("exposure", ""),
                    outcome=topic.get("outcome", ""),
                    population=topic.get("population", ""),
                )
                novelty_score = float(novelty_result.get("novelty_score", 0))
                _log.info("[AutonomousLoop] 신규성 점수: %.1f/10", novelty_score)
            except Exception as e:
                _log.warning("[AutonomousLoop] 신규성 평가 실패: %s", e)

            if novelty_score >= self.novelty_threshold:
                _log.info("[AutonomousLoop] 목표 신규성 달성 (%.1f >= %.1f) — 조기 종료",
                          novelty_score, self.novelty_threshold)
                break

        topic["loop_rounds"] = round_idx
        topic["evidence_count"] = len(all_evidence)
        topic["final_novelty_score"] = novelty_score

        _log.info("[AutonomousLoop] 완료: %d라운드, 증거 %d개, 신규성 %.1f",
                  round_idx, len(all_evidence), novelty_score)
        return topic, all_evidence, novelty_score

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────

    def _generate_sub_questions(self, topic: Dict, prior_evidence: List[Dict]) -> List[str]:
        """현재 주제와 기존 발견 기반으로 새 탐색 질문 생성."""
        evidence_summary = ""
        if prior_evidence:
            sample = prior_evidence[-min(5, len(prior_evidence)):]
            evidence_summary = "\n".join(
                f"- {p.get('title', '')} ({p.get('year', '')}): {p.get('abstract', '')[:200]}"
                for p in sample
            )

        prompt = f"""You are a systematic review expert. Generate {self.questions_per_round} targeted PubMed search queries.

CURRENT TOPIC:
{json.dumps(topic, ensure_ascii=False, indent=2)}

RECENT EVIDENCE FOUND:
{evidence_summary or "(none yet — first round)"}

Task: Generate {self.questions_per_round} new search queries that:
1. Explore angles NOT yet covered by existing evidence
2. Target gaps, contradictions, or under-studied populations
3. Are optimized for PubMed (use MeSH terms if appropriate)

Return JSON array of strings only:
["query1", "query2", "query3"]"""

        try:
            raw = self._llm.generate(prompt, task="research")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            questions = json.loads(raw)
            if isinstance(questions, list):
                return [str(q) for q in questions[:self.questions_per_round]]
        except Exception as e:
            _log.warning("[AutonomousLoop] 질문 생성 실패: %s", e)

        # 폴백: 기본 쿼리
        exposure = topic.get("exposure", "")
        outcome = topic.get("outcome", "")
        population = topic.get("population", "")
        return [
            f"{exposure} {outcome} {population}",
            f"{exposure} {outcome} Korea adolescent",
            f"{outcome} risk factor Korean youth",
        ]

    def _refine_topic(
        self, topic: Dict, new_evidence: List[Dict], all_evidence: List[Dict]
    ) -> Dict:
        """새 증거를 바탕으로 연구 주제 정제."""
        evidence_text = "\n".join(
            f"- [{p.get('year', '')}] {p.get('title', '')}: {p.get('abstract', '')[:300]}"
            for p in new_evidence[:10]
        )

        prompt = f"""You are a research methodology expert. Refine this research topic based on new evidence.

CURRENT TOPIC:
{json.dumps(topic, ensure_ascii=False, indent=2)}

NEW EVIDENCE ({len(new_evidence)} papers):
{evidence_text}

Task: Refine the topic to:
1. Address gaps revealed by the evidence
2. Make the hypothesis more specific and testable
3. Identify novel angles not well-covered in existing literature
4. Sharpen the exposure-outcome relationship

Return JSON with the same keys as CURRENT TOPIC, updated:
{{
  "title": "refined Korean title",
  "exposure": "refined exposure",
  "outcome": "refined outcome",
  "population": "refined population",
  "suggested_design": "study design",
  "hypothesis": "specific testable hypothesis",
  "novelty_rationale": "why this is novel given the evidence"
}}
Return JSON only."""

        try:
            raw = self._llm.generate(prompt, task="research")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            refined = json.loads(raw)
            if isinstance(refined, dict) and "title" in refined:
                refined.setdefault("loop_evidence", len(all_evidence))
                return refined
        except Exception as e:
            _log.warning("[AutonomousLoop] 주제 정제 실패: %s", e)

        return topic


def run_autonomous_research(
    seed_topic: Dict,
    max_rounds: int = 5,
    novelty_threshold: float = 7.0,
) -> Tuple[Dict, List[Dict], float]:
    """자율 연구 루프 편의 함수."""
    return AutonomousResearchLoop(
        max_rounds=max_rounds,
        novelty_threshold=novelty_threshold,
    ).run(seed_topic)
