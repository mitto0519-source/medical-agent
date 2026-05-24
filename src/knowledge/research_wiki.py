"""Research Wiki — OpenKB/Karpathy식 '누적 LLM 위키'.

RAG는 매 쿼리마다 지식을 재발견하지만, 이 위키는 지식이 **누적**된다. 사용자가
논문을 쓰고 자료를 읽을수록 연구 도메인의 '개념 페이지'가 쌓이고 교차링크되며,
그 축적분을 다음 글쓰기에 주입한다("쓸수록 더 잘 쓰는" 바이브 논문의 핵심).

기존 자산과의 분담 (중복 금지, 규칙 10):
  - medical_graph(NetworkX)  : 엔티티-관계 그래프
  - conversation_memory      : 대화 verbatim + 의미검색
  - research_wiki(이 모듈)   : 사람이 읽는 '개념 위키'(Obsidian 호환 markdown) 누적

저장: data/wiki/{owner}/  (concepts/*.md, summaries/*.md, index.md, log.md)
의미검색: ChromaDB 'research_wiki' 컬렉션 재사용.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_BASE = Path("data/wiki")


def _slug(title: str) -> str:
    s = re.sub(r"[^\w가-힣 -]", "", (title or "").strip()).strip().replace(" ", "-")
    return (s[:60] or "untitled").lower()


def _safe_owner(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", (email or "shared").lower())


class ResearchWiki:
    """누적 개념 위키."""

    def __init__(self, base_dir: str | Path = _BASE, owner_email: str = ""):
        self._dir = Path(base_dir) / _safe_owner(owner_email)
        self._concepts = self._dir / "concepts"
        self._summaries = self._dir / "summaries"
        self._concepts.mkdir(parents=True, exist_ok=True)
        self._summaries.mkdir(parents=True, exist_ok=True)
        self._owner = owner_email
        self._vs = None
        self._vs_tried = False

    # ── 의미검색 인덱스 (lazy, graceful) ─────────────────────────────────
    def _vstore(self):
        if self._vs is not None or self._vs_tried:
            return self._vs
        self._vs_tried = True
        try:
            from src.vectordb.store import VectorStore
            self._vs = VectorStore(collection_name="research_wiki")
        except Exception as e:
            _log.warning("위키 의미검색 비활성(ChromaDB 없음): %s", str(e)[:80])
            self._vs = None
        return self._vs

    # ── 소스 추가 → 개념 페이지 누적 ─────────────────────────────────────
    def add_source(self, text: str, title: str = "", source_type: str = "note") -> Dict:
        """자료 1건을 위키에 흡수: 요약 페이지 + 개념 페이지 누적(생성/추가) + 색인."""
        text = (text or "").strip()
        if not text:
            return {"error": "빈 텍스트"}
        title = title or text[:40]
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 1) 요약 페이지 (원문 보존 계층)
        sslug = _slug(title) + "-" + datetime.now().strftime("%m%d%H%M")
        (self._summaries / f"{sslug}.md").write_text(
            f"---\ntitle: {title}\ntype: summary\nsource_type: {source_type}\n"
            f"created: {ts}\n---\n\n# {title}\n\n{text[:4000]}\n", encoding="utf-8")

        # 2) LLM으로 핵심 개념 추출 + 기존 개념과 연결 (실패해도 graceful)
        existing = [p.stem for p in self._concepts.glob("*.md")]
        concepts = self._extract_concepts(text, title, existing)

        updated = []
        for c in concepts:
            ctitle = (c.get("concept") or "").strip()
            ccontent = (c.get("content") or "").strip()
            if not ctitle or not ccontent:
                continue
            related = [r for r in (c.get("related") or []) if r]
            updated.append(self._upsert_concept(ctitle, ccontent, related, title, ts))

        # 3) 인덱스/로그 갱신
        self._update_index()
        self._append_log(f"[{ts}] +source '{title}' → 개념 {len(updated)}개 갱신: {', '.join(updated)}")
        return {"title": title, "concepts_updated": updated, "summary": sslug}

    def _extract_concepts(self, text: str, title: str, existing: List[str]) -> List[Dict]:
        """LLM: 새 텍스트에서 핵심 개념 2~4개 추출 + 기존 개념과 연결. 실패 시 폴백."""
        try:
            from src.llm import get_llm_client
            llm = get_llm_client(task="fast")
            prompt = (
                "의학 연구 지식 위키를 누적 편집한다. 아래 새 자료에서 핵심 '개념' 2~4개를 뽑아, "
                "각 개념마다 재사용 가능한 한국어 지식 노트(3~6문장)를 작성하라. "
                "기존 개념 목록과 의미가 같으면 그 제목을 그대로 써서 누적되게 하라.\n"
                f"기존 개념들: {existing[:40]}\n"
                f"새 자료 제목: {title}\n새 자료:\n{text[:3000]}\n\n"
                'JSON만 출력: {"concepts":[{"concept":"개념명","content":"지식 노트",'
                '"related":["연결할 기존/신규 개념명"]}]}'
            )
            raw = llm.generate(prompt, task="fast", max_tokens=1200)
            data = self._parse_json(raw)
            if data and isinstance(data.get("concepts"), list):
                return data["concepts"][:4]
        except Exception as e:
            _log.warning("위키 개념추출 LLM 실패(요약만 저장됨): %s", str(e)[:100])
        # 폴백: 제목을 단일 개념으로
        return [{"concept": title[:40], "content": text[:400], "related": []}]

    def _upsert_concept(self, ctitle: str, ccontent: str, related: List[str],
                        source_title: str, ts: str) -> str:
        """개념 페이지 생성 또는 누적(append). [[링크]]로 교차참조. 반환: slug."""
        slug = _slug(ctitle)
        path = self._concepts / f"{slug}.md"
        links = " ".join(f"[[{_slug(r)}]]" for r in related if _slug(r) != slug)
        if path.exists():
            # 누적: 날짜 섹션으로 새 지식 추가 (덮어쓰기 아님 — 지식 보존)
            prev = path.read_text(encoding="utf-8")
            prev = re.sub(r"updated:.*", f"updated: {ts}", prev, count=1)
            block = f"\n\n### + {ts} (from: {source_title})\n{ccontent}\n"
            if links:
                block += f"\n관련: {links}\n"
            path.write_text(prev + block, encoding="utf-8")
        else:
            path.write_text(
                f"---\ntitle: {ctitle}\ntype: concept\ncreated: {ts}\nupdated: {ts}\n---\n\n"
                f"# {ctitle}\n\n{ccontent}\n" + (f"\n관련: {links}\n" if links else ""),
                encoding="utf-8")
        # 의미검색 색인
        vs = self._vstore()
        if vs is not None:
            try:
                vs.add_chunks([{"text": f"{ctitle}\n{ccontent}",
                                "metadata": {"slug": slug, "title": ctitle,
                                             "owner_email": self._owner, "updated": ts}}])
            except Exception:
                pass
        return slug

    # ── 회수 (글쓰기에 주입) ─────────────────────────────────────────────
    def build_context(self, query: str, n: int = 3, max_chars: int = 1500) -> str:
        """질문/주제와 관련된 누적 개념을 LLM 주입용 텍스트로. 글쓰기 품질↑."""
        vs = self._vstore()
        if vs is None or not (query or "").strip():
            return ""
        try:
            hits = vs.search(query, n_results=n, where={"owner_email": self._owner} if self._owner else None)
        except Exception:
            return ""
        hits = [h for h in hits if h.get("score", 0) >= 0.2]
        if not hits:
            return ""
        out = ["[누적 연구 지식 — 일관성 위해 활용]"]
        for h in hits:
            out.append(f"• {h['text'][:400]}")
        return "\n".join(out)[:max_chars]

    # ── 조회/관리 ────────────────────────────────────────────────────────
    def list_pages(self) -> List[Dict]:
        out = []
        for p in sorted(self._concepts.glob("*.md")):
            txt = p.read_text(encoding="utf-8")
            m = re.search(r"updated:\s*(.+)", txt)
            out.append({"slug": p.stem, "title": _first_title(txt) or p.stem,
                        "updated": (m.group(1).strip() if m else ""),
                        "inlinks": 0})
        # inlink 계산 (orphan 탐지용)
        allnames = {p["slug"] for p in out}
        link_count = {s: 0 for s in allnames}
        for p in self._concepts.glob("*.md"):
            for tgt in re.findall(r"\[\[([^\]]+)\]\]", p.read_text(encoding="utf-8")):
                if tgt in link_count:
                    link_count[tgt] += 1
        for o in out:
            o["inlinks"] = link_count.get(o["slug"], 0)
        return out

    def get_page(self, slug: str) -> str:
        p = self._concepts / f"{slug}.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def lint(self) -> Dict:
        """건강 검사: 고립(orphan) 페이지, 오래된(stale) 페이지, 개수."""
        pages = self.list_pages()
        now = time.time()
        orphans = [p["slug"] for p in pages if p["inlinks"] == 0]
        stale = []
        for p in pages:
            try:
                t = time.mktime(time.strptime(p["updated"][:10], "%Y-%m-%d"))
                if now - t > 60 * 86400:
                    stale.append(p["slug"])
            except Exception:
                pass
        return {"n_concepts": len(pages), "n_summaries": len(list(self._summaries.glob("*.md"))),
                "orphans": orphans, "stale": stale}

    def _update_index(self):
        pages = self.list_pages()
        lines = [f"---\ntitle: Research Wiki Index\nupdated: {datetime.now():%Y-%m-%d %H:%M}\n---\n",
                 f"# 연구 지식 위키 ({len(pages)} 개념)\n"]
        for p in sorted(pages, key=lambda x: x.get("updated", ""), reverse=True):
            lines.append(f"- [[{p['slug']}]] {p['title']}  · 갱신 {p['updated'][:10]} · 피링크 {p['inlinks']}")
        (self._dir / "index.md").write_text("\n".join(lines), encoding="utf-8")

    def _append_log(self, line: str):
        with (self._dir / "log.md").open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    @staticmethod
    def _parse_json(raw: str):
        raw = (raw or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lstrip().lower().startswith("json"):
                raw = raw.lstrip()[4:]
        try:
            return json.loads(raw.strip().rstrip("`").strip())
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return None
        return None


def _first_title(md: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else ""
