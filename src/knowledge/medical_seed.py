"""Medical knowledge foundation — loads PubMed-derived seed data and injects
into LLM system prompts as a base knowledge layer.

Architecture:
  [Medical Foundation Preamble]  ← this module
  + [Yoosun Cho Style Prompt]   ← author_profile.py
  + [Task-specific Prompt]      ← caller

The preamble is auto-injected by ClaudeClient._build_system() when seed is present.
If seed is not yet built (scripts/seed_medical_knowledge.py not run), returns ""
so the system degrades gracefully with no error.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

_SEED_DIR = Path("data/medical_knowledge_seed")
_log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_seed() -> Dict:
    meta_path = _SEED_DIR / "seed_metadata.json"
    if not meta_path.exists():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        vocab: List[str] = []
        vocab_path = _SEED_DIR / "vocabulary.json"
        if vocab_path.exists():
            vocab = json.loads(vocab_path.read_text(encoding="utf-8"))

        methods: List[str] = []
        methods_path = _SEED_DIR / "methodology_terms.json"
        if methods_path.exists():
            methods = json.loads(methods_path.read_text(encoding="utf-8"))

        patterns: List[str] = []
        patterns_path = _SEED_DIR / "sentence_patterns.json"
        if patterns_path.exists():
            patterns = json.loads(patterns_path.read_text(encoding="utf-8"))

        topics: List[str] = []
        topics_path = _SEED_DIR / "topic_distribution.json"
        if topics_path.exists():
            topics = list(json.loads(topics_path.read_text(encoding="utf-8")).keys())

        return {
            "meta": meta,
            "vocabulary": vocab,
            "methodology_terms": methods,
            "sentence_patterns": patterns,
            "topics": topics,
        }
    except Exception as e:
        _log.warning(f"Medical seed load failed: {e}")
        return {}


def seed_available() -> bool:
    """True if seed has been built (seed_medical_knowledge.py was run)."""
    return bool(_load_seed().get("meta", {}).get("papers_count", 0))


def get_seed_stats() -> Dict:
    """Return metadata about the built seed (papers_count, vocab_size, etc.)."""
    return _load_seed().get("meta", {})


def get_medical_preamble(
    vocab_limit: int = 150,
    methods_limit: int = 60,
    patterns_limit: int = 8,
) -> str:
    """Return a compact system prompt preamble establishing medical knowledge.

    Returns "" if seed not built — caller degrades gracefully.
    """
    seed = _load_seed()
    meta = seed.get("meta", {})
    papers_count = meta.get("papers_count", 0)
    if papers_count == 0:
        return ""

    vocab = seed.get("vocabulary", [])[:vocab_limit]
    methods = seed.get("methodology_terms", [])[:methods_limit]
    patterns = seed.get("sentence_patterns", [])[:patterns_limit]
    topics = seed.get("topics", [])[:20]

    vocab_str = ", ".join(vocab) if vocab else ""
    methods_str = ", ".join(methods) if methods else ""
    patterns_block = "\n".join(f"  • {p}" for p in patterns) if patterns else ""
    topics_str = ", ".join(topics) if topics else ""

    preamble = (
        f"MEDICAL KNOWLEDGE FOUNDATION"
        f" [{papers_count:,} PubMed papers internalized]:\n"
        "\n"
        "You carry deep, internalized biomedical expertise spanning clinical medicine,\n"
        "epidemiology, biostatistics, and translational research. This knowledge shapes\n"
        "your vocabulary, reasoning structure, and methodological precision automatically.\n"
        "\n"
    )

    if topics_str:
        preamble += f"COVERED DOMAINS: {topics_str}\n\n"

    if vocab_str:
        preamble += f"CORE MEDICAL VOCABULARY (use naturally, not exhaustively):\n{vocab_str}\n\n"

    if methods_str:
        preamble += f"METHODOLOGY LITERACY:\n{methods_str}\n\n"

    if patterns_block:
        preamble += f"MEDICAL WRITING PATTERNS:\n{patterns_block}\n\n"

    preamble += (
        "Apply this foundation automatically — it is your default substrate, not a list\n"
        "to mechanically reproduce. Think and write as an expert medical researcher.\n"
        "─────────────────────────────────────────────────────────\n"
    )

    return preamble


def reload_seed() -> None:
    """Force-reload seed from disk (clears lru_cache). Call after re-seeding."""
    _load_seed.cache_clear()
