"""NLP module for research gap and novelty detection"""

import re
from typing import List, Dict, Tuple, Optional
from collections import Counter


def _get_st():
    """Lazy-load sentence_transformers — optional dependency."""
    try:
        from sentence_transformers import SentenceTransformer, util
        return SentenceTransformer("all-MiniLM-L6-v2"), util
    except ImportError:
        return None, None


class NoveltyDetector:
    """Detect research novelty and gaps using embeddings.

    Falls back to keyword-overlap similarity when sentence_transformers
    is not installed (e.g. environments without PyTorch).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._util = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer, util
                self._model = SentenceTransformer(self._model_name)
                self._util = util
            except ImportError:
                self._model = False  # mark as unavailable

    def _fallback_similarity(self, a: str, b: str) -> float:
        """Token-overlap cosine as fallback when no embedding model."""
        ta = set(re.findall(r"\b\w+\b", a.lower()))
        tb = set(re.findall(r"\b\w+\b", b.lower()))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / (len(ta | tb) ** 0.5)

    def find_similar_research(self, query: str, corpus: List[str],
                              threshold: float = 0.5) -> List[Dict]:
        self._load()
        results = []
        if self._model and self._model is not False:
            q_emb = self._model.encode(query, convert_to_tensor=True)
            c_emb = self._model.encode(corpus, convert_to_tensor=True)
            scores = self._util.pytorch_cos_sim(q_emb, c_emb)[0]
            for idx, score in enumerate(scores):
                if float(score) >= threshold:
                    results.append({"index": idx, "text": corpus[idx], "similarity": float(score)})
        else:
            for idx, text in enumerate(corpus):
                score = self._fallback_similarity(query, text)
                if score >= threshold:
                    results.append({"index": idx, "text": text, "similarity": score})
        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    def detect_research_gaps(self, existing_research: List[str],
                             new_research: str, threshold: float = 0.3) -> Dict:
        self._load()
        if self._model and self._model is not False:
            n_emb = self._model.encode(new_research, convert_to_tensor=True)
            e_emb = self._model.encode(existing_research, convert_to_tensor=True)
            similarities = self._util.pytorch_cos_sim(n_emb, e_emb)[0]
            max_similarity = float(max(similarities))
            similar_count = int((similarities >= (1 - threshold)).sum())
        else:
            sims = [self._fallback_similarity(new_research, e) for e in existing_research]
            max_similarity = max(sims) if sims else 0.0
            similar_count = sum(1 for s in sims if s >= (1 - threshold))

        gap_score = 1 - max_similarity
        return {
            "gap_score": gap_score,
            "is_novel": gap_score >= threshold,
            "max_similarity": max_similarity,
            "similar_count": similar_count,
        }


class KeywordExtractor:
    """Extract key concepts from medical texts."""

    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> List[Tuple[str, int]]:
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        stop_words = {"the", "and", "for", "with", "from", "are", "was", "is", "or", "an"}
        words = [w for w in words if w not in stop_words]
        return Counter(words).most_common(top_n)

    @staticmethod
    def extract_medical_terms(text: str) -> List[str]:
        patterns = [r"\b[a-z]*itis\b", r"\b[a-z]*oma\b", r"\b[a-z]*osis\b", r"\b[A-Z]{2,}\b"]
        terms = []
        for pattern in patterns:
            terms.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(terms))


class TextAnalyzer:
    """Analyze text characteristics and metrics."""

    @staticmethod
    def readability_metrics(text: str) -> Dict:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        words = text.split()
        characters = len(text)
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        avg_word_length = characters / len(words) if words else 0
        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "character_count": characters,
            "avg_sentence_length": avg_sentence_length,
            "avg_word_length": avg_word_length,
            "flesch_kincaid_grade": max(0, 0.39 * avg_sentence_length + 11.8 * avg_word_length - 15.59),
        }
