"""Research Pipeline — 조유선 스타일 논문 생산 마스터 파이프라인

흐름:
  1. 데이터셋 + 방법론 라이브러리 참조
  2. 주제 생성
  3. 신규성 확인 (PubMed)
  4. 타당성 간이 검증
  5. 통계 수행 (외부 데이터 필요)
  6. 조유선 스타일 논문 작성
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import anthropic

from src.profile.author_profile import AuthorProfile
from src.library.dataset_library import DatasetLibrary
from src.library.methods_library import MethodsLibrary
from src.research.novelty_checker import NoveltyChecker
from src.research.paper_writer import PaperWriter
from src.rag.pipeline import RAGPipeline
from src.ingestion.evidence_reader import EvidenceReader


class ResearchPipeline:
    """조유선 스타일 논문 생산 마스터 파이프라인.

    사용 예:
        rp = ResearchPipeline()
        rp.setup_author("Yoosun Cho")

        # 데이터셋 등록
        rp.register_dataset("KYBRS", variables=[...])

        # 주제 생성
        topics = rp.generate_topics("KYBRS", focus="breast density")

        # 신규성 확인
        novelty = rp.check_novelty(topics[0])

        # 논문 초안 작성
        draft = rp.write_paper(topics[0], study_info={...}, results={...})
    """

    def __init__(
        self,
        author_name: str = "Yoosun Cho",
        persist_dir: str = "data/chromadb",
        profile_dir: str = "data/author_profiles",
        library_dir: str = "data/libraries",
        api_key: Optional[str] = None,
    ):
        # Load .env explicitly if needed
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
        if not self._api_key:
            try:
                from dotenv import load_dotenv
                _root = Path(__file__).parent.parent.parent
                load_dotenv(dotenv_path=_root / ".env", override=True)
                self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            except Exception:
                pass
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일 또는 환경변수를 확인하세요.")
        self._client = anthropic.Anthropic(api_key=self._api_key)

        self.author = AuthorProfile(author_name, profile_dir, self._api_key)
        self.datasets = DatasetLibrary(library_dir)
        self.methods = MethodsLibrary(library_dir)
        self.novelty = NoveltyChecker(self._api_key)
        self.rag = RAGPipeline(persist_dir=persist_dir, api_key=self._api_key)
        self.writer = PaperWriter(
            self.author, self.methods, self.datasets, self.rag, self._api_key
        )
        self.evidence = EvidenceReader()

        self._output_dir = Path("data/drafts")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1 — 저자 스타일 시드 구축
    # ------------------------------------------------------------------

    def build_author_profile(self, paper_texts: List[Dict]) -> str:
        """논문 텍스트 목록으로 저자 스타일 시드 구축.

        paper_texts: [{"title": "...", "text": "..."}, ...]
        """
        print(f"[Pipeline] {self.author.author_name} 스타일 시드 구축 중...")
        for paper in paper_texts:
            title = paper.get("title", "")
            text = paper.get("text", "")
            if len(text) < 200:
                continue
            result = self.author.analyse_paper(text, title)
            print(f"  {'[완료]' if result['status'] == 'analysed' else '[스킵]'} {title[:60]}")

        return self.author.summary()

    # ------------------------------------------------------------------
    # Step 2 — 데이터셋 라이브러리화
    # ------------------------------------------------------------------

    def register_dataset(
        self,
        name: str,
        full_name: str = "",
        description: str = "",
        variables: Optional[List[Dict]] = None,
        confounders: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
    ):
        """데이터셋과 변수를 라이브러리에 등록.

        variables: [{"name": "BMI", "label": "...", "type": "continuous", ...}]
        """
        self.datasets.add_dataset(name, full_name, description)
        for v in (variables or []):
            vname = v.pop("name", None)
            if vname:
                self.datasets.add_variable(name, vname, **v)
        for c in (confounders or []):
            self.datasets.add_confounder(name, c)
        for n in (notes or []):
            self.datasets.add_analysis_note(name, n)
        print(f"[Pipeline] 데이터셋 '{name}' 라이브러리 등록 완료.")

    # ------------------------------------------------------------------
    # Step 3 — 주제 생성
    # ------------------------------------------------------------------

    def generate_topics(
        self,
        dataset_name: str,
        focus: str = "",
        n_topics: int = 5,
        reference_query: Optional[str] = None,
    ) -> List[Dict]:
        """데이터셋 + RAG 컨텍스트 기반 연구 주제 생성.

        Returns list of topic dicts:
        {"title", "exposure", "outcome", "population", "rationale"}
        """
        dataset_ctx = self.datasets.get_context(dataset_name)

        # RAG (로컬 인덱스) + Open Evidence 통합 검색
        rag_ctx = ""
        if reference_query or focus:
            # 로컬 RAG
            hits = self.rag.ask(reference_query or focus)
            rag_ctx = "\n".join(h["text"] for h in hits.get("sources", [])[:3])
            # 오픈 에비던스 (PubMed + Semantic Scholar)
            ev_summary = self.evidence.search_and_summarise(reference_query or focus, n=5)
            rag_ctx = ev_summary + "\n\n--- LOCAL INDEX ---\n" + rag_ctx

        prompt = f"""You are a medical research strategist.
Given this dataset and research context, generate {n_topics} original, publishable research topics.

DATASET CONTEXT:
{dataset_ctx}

RESEARCH FOCUS: {focus}

EXISTING LITERATURE CONTEXT:
{rag_ctx[:2000] if rag_ctx else 'Not provided'}

Generate {n_topics} research topics as JSON array:
[
  {{
    "title": "concise study title",
    "exposure": "main exposure variable",
    "outcome": "primary outcome",
    "population": "target population",
    "rationale": "why this is important and feasible with this dataset",
    "suggested_design": "cross-sectional / cohort / etc.",
    "suggested_methods": ["logistic_regression", ...]
  }},
  ...
]
Return JSON only."""

        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[-1].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        try:
            topics = json.loads(raw)
        except Exception:
            topics = [{"title": raw, "exposure": "", "outcome": "", "population": ""}]

        print(f"[Pipeline] 주제 {len(topics)}개 생성 완료.")
        return topics

    # ------------------------------------------------------------------
    # Step 4 — 신규성 확인
    # ------------------------------------------------------------------

    def check_novelty(self, topic: Dict) -> Dict:
        """주제 신규성 PubMed 검증."""
        print(f"[Pipeline] 신규성 확인: {topic.get('title', '')[:60]}")
        return self.novelty.check(
            topic=topic.get("title", ""),
            exposure=topic.get("exposure", ""),
            outcome=topic.get("outcome", ""),
            population=topic.get("population", ""),
        )

    # ------------------------------------------------------------------
    # Step 5 — 타당성 간이 검증
    # ------------------------------------------------------------------

    def validate_feasibility(self, topic: Dict, dataset_name: str) -> Dict:
        """데이터셋 변수 기반 연구 타당성 빠른 검증."""
        dataset_ctx = self.datasets.get_context(dataset_name)
        prompt = f"""Evaluate the feasibility of this research topic given the available dataset.

TOPIC: {json.dumps(topic, ensure_ascii=False)}

AVAILABLE DATASET:
{dataset_ctx}

Return JSON:
{{
  "is_feasible": true/false,
  "confidence": "high/medium/low",
  "available_variables": ["list of needed variables that ARE in dataset"],
  "missing_variables": ["list of needed variables NOT in dataset"],
  "sample_size_concern": true/false,
  "confounding_concern": "description of main confounders to adjust",
  "verdict": "one sentence go/no-go recommendation",
  "modifications_needed": ["list of adjustments to make it feasible"]
}}
Return JSON only."""

        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[-1].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw, "is_feasible": None}

    # ------------------------------------------------------------------
    # Step 6 — 논문 작성
    # ------------------------------------------------------------------

    def write_paper(
        self,
        topic: Dict,
        study_info: Dict,
        results: Dict,
        use_rag_references: bool = True,
    ) -> str:
        """조유선 스타일로 논문 초안 생성 및 파일 저장."""

        reference_context = None
        if use_rag_references:
            query = f"{topic.get('exposure', '')} {topic.get('outcome', '')} {topic.get('population', '')}"
            hits = self.rag.ask(query)
            if hits.get("sources"):
                reference_context = "\n\n".join(h["text"] for h in hits["sources"][:5])

        print(f"[Pipeline] 논문 작성 시작: {topic.get('title', '')[:60]}")
        draft = self.writer.write_full_paper(
            topic=topic.get("title", "Untitled"),
            study_info=study_info,
            results=results,
            reference_context=reference_context,
        )

        # 로컬 저장
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic.get("title", "draft"))[:60]
        out_path = self._output_dir / f"{safe_title}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"[Pipeline] 논문 저장: {out_path}")

        # 클라우드 저장 (SUPABASE_DB_URL 설정 시)
        try:
            from src.cloud.db import cloud_available, get_engine
            if cloud_available():
                from sqlalchemy import text
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ma_drafts (safe_title, topic_title, content)
                        VALUES (:safe_title, :topic_title, :content)
                    """), {
                        "safe_title": safe_title,
                        "topic_title": topic.get("title", ""),
                        "content": draft,
                    })
                print(f"[Pipeline] 클라우드 저장 완료: ma_drafts/{safe_title}")
        except Exception as e:
            print(f"[Pipeline] 클라우드 저장 실패 (로컬만 저장됨): {e}")

        return draft

    # ------------------------------------------------------------------
    # Full automated run
    # ------------------------------------------------------------------

    def run(
        self,
        dataset_name: str,
        focus: str,
        study_info_template: Optional[Dict] = None,
        auto_select_topic: bool = True,
    ) -> Dict:
        """데이터셋 이름과 주제만 주면 주제 생성 → 신규성 → 타당성 → 출력까지 자동 실행.

        Returns: {topics, novelty_results, feasibility_results, recommendation}
        """
        print(f"\n{'='*60}")
        print(f"Research Pipeline 시작: {focus} / {dataset_name}")
        print(f"{'='*60}\n")

        topics = self.generate_topics(dataset_name, focus=focus)

        results = []
        for t in topics:
            novelty = self.check_novelty(t)
            feasibility = self.validate_feasibility(t, dataset_name)
            score = (novelty.get("novelty_score", 0) or 0)
            viable = feasibility.get("is_feasible", False)
            results.append({
                "topic": t,
                "novelty": novelty,
                "feasibility": feasibility,
                "combined_score": score * (1.5 if viable else 0.5),
            })

        results.sort(key=lambda x: x["combined_score"], reverse=True)
        best = results[0]

        print(f"\n[Pipeline] 최우선 주제: {best['topic']['title']}")
        print(f"  신규성: {best['novelty'].get('novelty_score', '?')}/10")
        print(f"  타당성: {best['feasibility'].get('verdict', '?')}")
        print(f"  권고: {best['novelty'].get('recommendation', '?')}")

        return {
            "all_topics": results,
            "recommended": best,
        }
