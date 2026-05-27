"""ComponentLibrary — 논문에서 추출한 reusable microcomponent 자산화.

사용자 진단 (2026-05-28): "단순 chunk가 아니라 잘게 분해된 reusable 에셋,
조합의 다양성이 키, 표준화된 요소로 자산화".

논문 chunk(~380 word)는 너무 큼. 본 모듈은 chunk → **microcomponent** 추출:
  - hedging, stat_report, transition, topic_sentence, methods_boilerplate,
    mechanism_phrase, limitation, figure_caption_pattern, subgroup_sentence,
    citation_cluster_pattern

저장: SQLite `data/library/components.db` (FTS5 검색 지원).
조합: WritingOrchestrator.gather_components(kind, intent, n)로 호출.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DB = Path("data/library/components.db")


# ── Component Kinds ─────────────────────────────────────────────────────────

COMPONENT_KINDS = (
    "hedging",                   # remains underexplored, may, is consistent with
    "stat_report",               # aOR 1.27; 95% CI 1.03-1.56; P = 0.026
    "transition",                # However, In line with, Compared with
    "topic_sentence",            # Adolescents are increasingly consuming...
    "methods_boilerplate",       # Survey-weighted logistic regression estimated...
    "mechanism_phrase",          # potentially mediated through gut-microbiome...
    "limitation",                # As a cross-sectional study, reverse causation...
    "figure_caption_pattern",    # Figure N. Adjusted predicted probabilities by sex
    "table_caption_pattern",     # Table N. Baseline characteristics by ...
    "subgroup_sentence",         # A significant interaction was observed (P = 0.008)
    "citation_cluster_pattern",  # [1-3], [12, 14, 15]
)

# 2-layer pipeline (사용자 요구 2026-05-28):
# ① Content layer — 내용/전문성. OA 5만편에서 차용.
# ② Style layer  — 저자 양식(hedging/transition/topic). yoosun_cho 등 author_style별.
CONTENT_KINDS = (
    "stat_report", "methods_boilerplate", "mechanism_phrase", "limitation",
    "figure_caption_pattern", "table_caption_pattern", "subgroup_sentence",
    "citation_cluster_pattern",
)
STYLE_KINDS = (
    "hedging", "transition", "topic_sentence",
)


def kind_layer(kind: str) -> str:
    """주어진 kind가 'content' 인지 'style' 인지 반환. 'unknown'일 수도 있음."""
    if kind in CONTENT_KINDS:
        return "content"
    if kind in STYLE_KINDS:
        return "style"
    return "unknown"


@dataclass
class PaperComponent:
    """단일 reusable component."""
    id: str                          # sha1(kind + text[:80])
    kind: str
    text: str
    source_pmid: str = ""
    source_section: str = ""         # introduction|methods|results|discussion
    author_style: str = ""           # 'yoosun_cho' | 'generic' | author surname
    n_words: int = 0
    n_uses: int = 0
    created_at: float = field(default_factory=time.time)
    last_used_at: float = 0.0
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


def _hash(kind: str, text: str) -> str:
    return hashlib.sha1(f"{kind}|{text[:80]}".lower().encode("utf-8")).hexdigest()[:16]


def make_component(kind: str, text: str, *, source_pmid: str = "",
                    source_section: str = "", author_style: str = "",
                    extra: Optional[Dict] = None) -> PaperComponent:
    text = (text or "").strip()
    return PaperComponent(
        id=_hash(kind, text), kind=kind, text=text,
        source_pmid=source_pmid, source_section=source_section,
        author_style=author_style, n_words=len(text.split()),
        extra=extra or {},
    )


# ── ComponentLibrary (SQLite) ───────────────────────────────────────────────

class ComponentLibrary:
    """Reusable component 저장소. SQLite + FTS5 검색."""

    _instance: Optional["ComponentLibrary"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        _DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(_DB), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        c = self._conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS components(
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                source_pmid TEXT,
                source_section TEXT,
                author_style TEXT,
                n_words INTEGER,
                n_uses INTEGER DEFAULT 0,
                created_at REAL,
                last_used_at REAL DEFAULT 0,
                extra_json TEXT
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_kind ON components(kind)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_author ON components(author_style)")
        # FTS5 (있으면)
        try:
            c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS components_fts
                          USING fts5(text, kind, content='components', content_rowid='rowid')""")
            c.execute("""CREATE TRIGGER IF NOT EXISTS components_ai AFTER INSERT ON components
                          BEGIN INSERT INTO components_fts(rowid, text, kind)
                          VALUES (new.rowid, new.text, new.kind); END""")
        except Exception as e:
            _log.debug("FTS5 unavailable: %s", e)
        self._conn.commit()

    # ── add / get ───────────────────────────────────────────────────────────

    def add(self, comp: PaperComponent) -> bool:
        """중복 id는 skip. 추가 시 True."""
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO components"
                "(id, kind, text, source_pmid, source_section, author_style,"
                " n_words, n_uses, created_at, last_used_at, extra_json)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (comp.id, comp.kind, comp.text, comp.source_pmid,
                 comp.source_section, comp.author_style, comp.n_words,
                 comp.n_uses, comp.created_at, comp.last_used_at,
                 json.dumps(comp.extra, ensure_ascii=False)),
            )
            self._conn.commit()
            cur = self._conn.execute("SELECT changes()").fetchone()
            return cur[0] > 0
        except Exception as e:
            _log.warning("component add fail: %s", e)
            return False

    def add_many(self, comps: List[PaperComponent]) -> int:
        n = 0
        for c in comps:
            if self.add(c):
                n += 1
        return n

    def get(self, comp_id: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT id, kind, text, source_pmid, source_section, author_style,"
            " n_words, n_uses, created_at, last_used_at, extra_json"
            " FROM components WHERE id=?", (comp_id,)).fetchone()
        return _row_to_dict(row) if row else None

    # ── search / sample ─────────────────────────────────────────────────────

    def search(self, *, kind: Optional[str] = None,
                author_style: Optional[str] = None,
                contains: Optional[str] = None,
                fts_query: Optional[str] = None,
                limit: int = 10) -> List[Dict]:
        """필터 + 검색. fts_query는 FTS5 사용 (있으면)."""
        if fts_query:
            try:
                rows = self._conn.execute(
                    "SELECT c.id, c.kind, c.text, c.source_pmid, c.source_section,"
                    " c.author_style, c.n_words, c.n_uses, c.created_at,"
                    " c.last_used_at, c.extra_json"
                    " FROM components_fts f JOIN components c ON c.rowid = f.rowid"
                    " WHERE components_fts MATCH ? "
                    + (" AND c.kind=?" if kind else "")
                    + " ORDER BY rank LIMIT ?",
                    tuple([fts_query] + ([kind] if kind else []) + [limit])).fetchall()
                return [_row_to_dict(r) for r in rows]
            except Exception as e:
                _log.debug("FTS search fail: %s", e)

        sql = ("SELECT id, kind, text, source_pmid, source_section, author_style,"
                " n_words, n_uses, created_at, last_used_at, extra_json"
                " FROM components WHERE 1=1")
        params: list = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if author_style:
            sql += " AND author_style=?"
            params.append(author_style)
        if contains:
            sql += " AND text LIKE ?"
            params.append(f"%{contains}%")
        sql += " ORDER BY n_uses DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def sample(self, kind: str, n: int = 5,
                author_style: Optional[str] = None) -> List[Dict]:
        """특정 kind에서 무작위 N개 (n_uses 낮은 것 우선 = diverse 보장)."""
        sql = ("SELECT id, kind, text, source_pmid, source_section, author_style,"
                " n_words, n_uses, created_at, last_used_at, extra_json"
                " FROM components WHERE kind=?")
        params: list = [kind]
        if author_style:
            sql += " AND author_style=?"
            params.append(author_style)
        sql += " ORDER BY n_uses ASC, RANDOM() LIMIT ?"
        params.append(n)
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def mark_used(self, comp_id: str):
        self._conn.execute(
            "UPDATE components SET n_uses=n_uses+1, last_used_at=? WHERE id=?",
            (time.time(), comp_id))
        self._conn.commit()

    # ── stats ───────────────────────────────────────────────────────────────

    def stats(self) -> Dict:
        total = self._conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        by_kind = dict(self._conn.execute(
            "SELECT kind, COUNT(*) FROM components GROUP BY kind ORDER BY 2 DESC"
        ).fetchall())
        by_author = dict(self._conn.execute(
            "SELECT author_style, COUNT(*) FROM components "
            "WHERE author_style != '' GROUP BY author_style ORDER BY 2 DESC LIMIT 10"
        ).fetchall())
        most_used = self._conn.execute(
            "SELECT id, kind, text, n_uses FROM components "
            "WHERE n_uses > 0 ORDER BY n_uses DESC LIMIT 5"
        ).fetchall()
        return {
            "total": total, "by_kind": by_kind, "by_author": by_author,
            "most_used": [{"id": r[0], "kind": r[1], "text": r[2][:120],
                            "n_uses": r[3]} for r in most_used],
        }


def _row_to_dict(row) -> Dict:
    extra = {}
    try:
        extra = json.loads(row[10]) if row[10] else {}
    except Exception:
        extra = {}
    return {
        "id": row[0], "kind": row[1], "text": row[2],
        "source_pmid": row[3], "source_section": row[4],
        "author_style": row[5], "n_words": row[6], "n_uses": row[7],
        "created_at": row[8], "last_used_at": row[9],
        "extra": extra,
    }


def get_library() -> ComponentLibrary:
    return ComponentLibrary()
