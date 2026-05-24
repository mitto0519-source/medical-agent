"""Periodic Trend Learner — PubMed 주기적 수집 + 그래프 갱신 + 자가학습.

이 모듈이 '자가발전 지식 베이스'의 핵심 엔진이다.

실행 흐름:
  1. PubMed에서 최근 N일 논문 수집 (KYRBS/KNHANES 특화 쿼리)
  2. 온톨로지로 개념 추출 → 그래프 업데이트
  3. 벡터 DB(ChromaDB/Supabase)에 신규 논문 인제스트
  4. self_model.refresh() 자가 진단 실행
  5. auto_learn.reflect_and_record()로 발견 사항 인사이트 기록

호출 방법:
  - 직접: python scripts/periodic_learn.py
  - MCP 서버 시작 시 asyncio 백그라운드 태스크로 자동 실행 (24h 주기)
  - 수동: from src.knowledge.trend_learner import run_trend_learn; run_trend_learn()
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL  = "mitto0519@gmail.com"
_STATE_FILE = Path("data/knowledge_graph/trend_state.json")


# ── PubMed 유틸 ──────────────────────────────────────────────────────────────

def _pubmed_get(url: str, params: Dict, retries: int = 3) -> Optional[str]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full_url, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            _log.warning("[pubmed] attempt %d failed: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def _search_pmids(query: str, days: int = 60, max_results: int = 50) -> List[str]:
    """PubMed 검색으로 PMID 목록 반환."""
    mindate = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    xml = _pubmed_get(f"{EUTILS}/esearch.fcgi", {
        "db": "pubmed", "term": query, "retmax": max_results,
        "mindate": mindate, "datetype": "pdat",
        "retmode": "xml", "email": EMAIL,
    })
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
        return [el.text for el in root.findall(".//Id") if el.text]
    except Exception:
        return []


def _fetch_papers(pmids: List[str]) -> List[Dict]:
    """PMID 목록으로 논문 메타데이터 수집."""
    if not pmids:
        return []
    xml = _pubmed_get(f"{EUTILS}/efetch.fcgi", {
        "db": "pubmed", "id": ",".join(pmids[:100]),
        "rettype": "xml", "retmode": "xml", "email": EMAIL,
    })
    if not xml:
        return []
    papers = []
    try:
        root = ET.fromstring(xml)
        for article in root.findall(".//PubmedArticle"):
            try:
                pmid = article.findtext(".//PMID", "")
                title = article.findtext(".//ArticleTitle", "").strip()
                abstract_parts = [el.text or "" for el in article.findall(".//AbstractText")]
                abstract = " ".join(abstract_parts).strip()
                year_text = article.findtext(".//PubDate/Year", "")
                year = int(year_text) if year_text.isdigit() else None
                journal = article.findtext(".//Journal/Title", "")
                papers.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract[:1500],
                    "year": year,
                    "journal": journal,
                })
            except Exception:
                continue
    except Exception as e:
        _log.warning("[pubmed] parse error: %s", e)
    return papers


# ── 상태 관리 ─────────────────────────────────────────────────────────────────

def _load_state() -> Dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_run": None, "ingested_pmids": [], "run_count": 0}


def _save_state(state: Dict):
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_already_ingested(pmid: str, state: Dict) -> bool:
    return pmid in state.get("ingested_pmids", [])


# ── 핵심 파이프라인 ───────────────────────────────────────────────────────────

def run_trend_learn(days: int = 60, max_per_query: int = 30) -> Dict[str, Any]:
    """주기적 학습 파이프라인 전체 실행.

    Returns:
        실행 요약 딕셔너리 (new_papers, concepts_extracted, graph_nodes, ...)
    """
    _log.info("[trend_learn] ===== 주기적 학습 시작 =====")
    state = _load_state()
    summary: Dict[str, Any] = {
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "new_papers": 0,
        "skipped_papers": 0,
        "concepts_extracted": 0,
        "graph_nodes_before": 0,
        "graph_nodes_after": 0,
        "errors": [],
    }

    # ── 1. 온톨로지 + 그래프 로드 ────────────────────────────────────────────
    from src.knowledge.medical_ontology import get_ontology
    from src.knowledge.medical_graph import get_graph
    ontology = get_ontology()
    graph    = get_graph()
    stats_before = graph.stats()
    summary["graph_nodes_before"] = stats_before.get("total_nodes", 0)

    # ── 2. PubMed 쿼리 구성 ───────────────────────────────────────────────────
    queries = []
    queries += ontology.pubmed_queries_for_dataset("KYRBS")
    queries += ontology.pubmed_queries_for_dataset("KNHANES")
    # 확장된 공중보건 특화 쿼리 (KYRBS/KNHANES 논문 생산 커버리지 극대화)
    extra_topics = [
        # KYRBS 청소년 건강 핵심 주제
        '"adolescent obesity" AND Korea[Title/Abstract]',
        '"sleep duration" AND Korean[Title/Abstract]',
        '"mental health" AND KYRBS[Title/Abstract]',
        '"physical activity" AND Korean adolescent[Title/Abstract]',
        '"screen time" AND Korean youth[Title/Abstract]',
        '"adolescent depression" AND Korea[Title/Abstract]',
        '"suicidal ideation" AND Korean adolescent[Title/Abstract]',
        '"smoking" AND Korean youth[Title/Abstract]',
        '"alcohol use" AND Korean adolescent[Title/Abstract]',
        '"breakfast skipping" AND Korean adolescent[Title/Abstract]',
        '"academic stress" AND Korean student[Title/Abstract]',
        '"smartphone" AND Korean adolescent health[Title/Abstract]',
        '"sedentary behavior" AND Korean youth[Title/Abstract]',
        # KNHANES 성인 만성질환 주제
        '"metabolic syndrome" AND KNHANES[Title/Abstract]',
        '"type 2 diabetes" AND Korean adults[Title/Abstract]',
        '"hypertension" AND KNHANES[Title/Abstract]',
        '"dyslipidemia" AND Korean population[Title/Abstract]',
        '"cardiovascular disease" AND Korean adults[Title/Abstract]',
        '"obesity" AND KNHANES[Title/Abstract]',
        '"sarcopenia" AND Korean[Title/Abstract]',
        '"dietary pattern" AND Korean adults[Title/Abstract]',
        # 방법론 논문
        '"complex survey analysis" AND health[Title/Abstract]',
        '"logistic regression" AND cross-sectional AND Korean[Title/Abstract]',
        '"propensity score" AND Korean health[Title/Abstract]',
        # 고급 분석 주제
        '"sleep quality" AND cardiometabolic AND Korea[Title/Abstract]',
        '"gut microbiome" AND Korean population[Title/Abstract]',
        '"air pollution" AND Korea health[Title/Abstract]',
        '"socioeconomic status" AND health inequality AND Korea[Title/Abstract]',
    ]
    queries += extra_topics

    # ── 3. 수집 + 중복 제거 ───────────────────────────────────────────────────
    all_papers: Dict[str, Dict] = {}
    for q in queries:
        _log.info("[trend_learn] 검색: %s", q[:80])
        pmids = _search_pmids(q, days=days, max_results=max_per_query)
        if not pmids:
            continue
        new_pmids = [p for p in pmids if not _is_already_ingested(p, state)]
        if not new_pmids:
            _log.debug("[trend_learn] 모두 기수집 (%d)", len(pmids))
            summary["skipped_papers"] += len(pmids)
            continue
        papers = _fetch_papers(new_pmids)
        for p in papers:
            all_papers[p["pmid"]] = p
        time.sleep(0.4)  # NCBI rate limit

    _log.info("[trend_learn] 신규 논문: %d편", len(all_papers))

    # ── 4. 온톨로지 개념 추출 + 그래프 구축 ──────────────────────────────────
    enriched_papers = []
    for pmid, paper in all_papers.items():
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        concepts = ontology.extract_concepts(text)

        # 데이터셋 감지
        datasets = []
        if any(kw in text.lower() for kw in ["kyrbs", "korea youth risk behavior", "청소년건강행태"]):
            datasets.append("KYRBS")
        if any(kw in text.lower() for kw in ["knhanes", "korea national health and nutrition", "국민건강영양조사"]):
            datasets.append("KNHANES")

        enriched = {
            **paper,
            "datasets": datasets,
            "concepts": [
                {
                    "concept_id": c["concept_id"],
                    "label": c["label"],
                    "domain_label": c["domain_label"],
                    "weight": 1.0,
                }
                for c in concepts
            ],
        }
        enriched_papers.append(enriched)
        graph.ingest_paper(enriched)
        summary["concepts_extracted"] += len(concepts)

    # ── 5. 도메인 내 형제 개념 자동 연결 (온톨로지 RELATED_TO 엣지) ───────────
    from src.knowledge.medical_ontology import ONTOLOGY
    for domain in ONTOLOGY.values():
        sibling_ids = list(domain["children"].keys())
        for i, c1 in enumerate(sibling_ids):
            for c2 in sibling_ids[i+1:]:
                n1 = f"concept:{c1}"
                n2 = f"concept:{c2}"
                if graph._G is not None and graph._G.has_node(n1) and graph._G.has_node(n2):
                    graph.link_concepts(n1, n2, weight=0.3)

    graph.save()
    stats_after = graph.stats()
    summary["graph_nodes_after"] = stats_after.get("total_nodes", 0)
    summary["new_papers"] = len(enriched_papers)

    # ── 6. 벡터 DB 인제스트 ───────────────────────────────────────────────────
    rag_ok = _ingest_to_rag(enriched_papers)
    summary["rag_ingested"] = rag_ok

    # ── 7. 상태 저장 ──────────────────────────────────────────────────────────
    state["last_run"] = summary["started_at"]
    state["run_count"] = state.get("run_count", 0) + 1
    existing_pmids = set(state.get("ingested_pmids", []))
    existing_pmids.update(all_papers.keys())
    state["ingested_pmids"] = list(existing_pmids)[-2000:]  # 최대 2000개 유지
    _save_state(state)

    # ── 8. self_model 자가 진단 갱신 ─────────────────────────────────────────
    try:
        from src.memory.self_model import refresh as sm_refresh
        sm_refresh()
        _log.info("[trend_learn] self_model 갱신 완료")
    except Exception as e:
        _log.warning("[trend_learn] self_model 갱신 실패: %s", e)

    # ── 9. 자가 학습 인사이트 기록 ────────────────────────────────────────────
    _record_insight(summary, enriched_papers)

    # ── 10. change_log 기록 ───────────────────────────────────────────────────
    try:
        from src.memory import change_log
        change_log.log(
            title=f"주기적 학습 완료 — 신규 {summary['new_papers']}편 수집",
            action_type="auto_learn",
            description=(
                f"PubMed 수집: {summary['new_papers']}편 신규 / "
                f"{summary['skipped_papers']}편 중복 스킵. "
                f"그래프 노드: {summary['graph_nodes_before']} → {summary['graph_nodes_after']}. "
                f"개념 추출: {summary['concepts_extracted']}건."
            ),
            why_better="지식 베이스 자동 갱신으로 최신 연구 트렌드 반영",
            impact={"affected_modules": ["data/knowledge_graph", "ChromaDB/RAG"]},
        )
    except Exception as e:
        _log.warning("[trend_learn] change_log 기록 실패: %s", e)

    _log.info("[trend_learn] ===== 완료: %s =====", json.dumps(summary, ensure_ascii=False))
    return summary


def _ingest_to_rag(papers: List[Dict]) -> int:
    """신규 논문을 RAG 벡터 DB에 인제스트. 성공한 논문 수 반환."""
    if not papers:
        return 0
    try:
        from src.vectordb.store import get_vector_store
        from src.ingestion.hierarchical_chunker import chunk_paper
        store = get_vector_store()
        total_chunks = 0
        count = 0
        for p in papers:
            title = p.get("title", "")
            abstract = p.get("abstract", "")
            text = abstract if abstract else title
            if len(text.strip()) < 30:
                continue
            meta = {
                "filename": title[:80],
                "source": f"pubmed:{p.get('pmid', '')}",
                "pmid": p.get("pmid", ""),
                "year": str(p.get("year", "")),
                "journal": p.get("journal", ""),
                "topic": "periodic_learn",
                "tier": "auto",  # 자동수집 = 미검증 표식 (메모리 위생)
                "datasets": ",".join(p.get("datasets", [])),
                "concepts": ",".join(c["concept_id"] for c in p.get("concepts", [])),
            }
            # 계층 청킹: 구조화 초록을 섹션/role/citation/stat 메타로 분해 (조언 #1 RAG 재설계)
            chunks = chunk_paper(text, base_meta=meta)
            added = store.add_chunks(chunks)
            total_chunks += added
            count += 1
        _log.info("[trend_learn] RAG 인제스트: %d편 / %d청크", count, total_chunks)
        return count
    except Exception as e:
        _log.warning("[trend_learn] RAG 인제스트 실패: %s", e)
        return 0


def _record_insight(summary: Dict, papers: List[Dict]):
    """트렌드 학습 결과를 자가 학습 인사이트로 기록."""
    if not papers:
        return
    try:
        # 가장 많이 등장한 개념 집계
        concept_freq: Dict[str, int] = {}
        for p in papers:
            for c in p.get("concepts", []):
                cid = c["concept_id"]
                concept_freq[cid] = concept_freq.get(cid, 0) + 1

        if not concept_freq:
            return

        top3 = sorted(concept_freq.items(), key=lambda x: -x[1])[:3]
        top3_str = ", ".join(f"{cid}({cnt}편)" for cid, cnt in top3)

        from src.memory.agent_insight import record
        record(
            title=f"PubMed 트렌드 [{datetime.now().strftime('%Y-%m')}]: {top3[0][0]} 최다",
            insight=(
                f"최근 {summary.get('new_papers', 0)}편 수집. "
                f"상위 개념: {top3_str}. "
                f"그래프: {summary['graph_nodes_after']}노드."
            ),
            category="pattern",
            why_matters="최신 연구 트렌드 반영 — 주제 생성 시 우선 참조",
            how_to_apply=f"주제 생성 시 {top3[0][0]} 관련 주제 우선 검토",
            confidence=0.75,
            tags=["pubmed", "trend", "auto_learn"],
            source="periodic_learning",
        )
    except Exception as e:
        _log.debug("[trend_learn] insight 기록 실패 (무시): %s", e)


def get_last_run_info() -> Dict:
    """마지막 실행 정보 반환."""
    state = _load_state()
    return {
        "last_run": state.get("last_run", "미실행"),
        "run_count": state.get("run_count", 0),
        "ingested_count": len(state.get("ingested_pmids", [])),
    }
