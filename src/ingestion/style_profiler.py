"""StyleProfiler — 사용자 본인 논문에서 문체 지표를 추출해 per-user 프로파일 생성.

"AI같지 않게 = 사용자 본인 문체"의 진짜 엔진. 기존 yoosun_style.md(단일 저자 시드)는
fallback으로 유지하고, 사용자가 본인 논문(.docx/.pdf/.txt)을 1편 이상 업로드하면
이 모듈이 다음 5개 차원을 추출해 `data/profiles/{owner_hash}/style_profile.json`에 저장:

  1. sentence_length_stats   문장 길이 분포 (mean, std, median, p25, p75, p95)
  2. hedge_frequency         헤지 표현 비율 (may/might/suggest/appear/likely/potential 등)
  3. passive_voice_ratio     수동태 비율 (was/were + V-ed pattern)
  4. clause_depth            평균 종속절 깊이 (콤마/세미콜론 분포로 근사)
  5. lexical_signature       TF-IDF top-K 관용 어휘 (기본 의학영어 코퍼스 대비 ratio)

호출:
    profile = StyleProfiler().extract_from_files(["my_paper1.docx", "my_paper2.pdf"])
    StyleProfiler.save(owner_email="user@x.com", profile=profile)
    loaded = StyleProfiler.load(owner_email="user@x.com")  # fallback to None

persona.get_system_prompt(task, owner_email)가 이 프로파일을 읽어 prompts/user_style_template.md의
변수 슬롯({{avg_sent_len}}, {{hedge_top5}}, {{vocab_top10}})을 채워 system prompt에 주입.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PROFILES_DIR = Path("data/profiles")

# 의학 영어 표준 헤지 표현 (Hyland 2008 hedging taxonomy 기반 축약)
_HEDGE_TERMS = [
    "may", "might", "could", "would", "should",
    "suggest", "suggests", "suggested", "suggesting",
    "appear", "appears", "appeared", "seemed",
    "likely", "possibly", "probably", "potentially",
    "potential", "possible", "probable", "tentative",
    "indicate", "indicates", "indicated", "imply", "implies",
    "approximately", "about", "around", "roughly",
    "tend", "tends", "tended",
    "estimate", "estimates", "estimated",
    "assume", "assumed", "presumably",
]

# 의학 영어 기본 어휘 (기본 코퍼스 — 사용자 lexical_signature 빼낼 기준)
_BASE_MEDICAL_VOCAB = {
    "study", "patient", "patients", "result", "results", "method", "methods",
    "analysis", "data", "outcome", "outcomes", "association", "associated",
    "risk", "odds", "ratio", "confidence", "interval", "significant",
    "significantly", "prevalence", "incidence", "mean", "standard", "deviation",
    "regression", "logistic", "model", "models", "variable", "variables",
    "subjects", "subgroup", "subgroups", "table", "figure", "discussion",
    "conclusion", "background", "objective", "introduction",
}


@dataclass
class StyleProfile:
    """추출된 사용자 문체 프로파일."""
    owner_email: str
    sample_size_papers: int = 0
    sample_size_sentences: int = 0
    sample_size_words: int = 0

    # Sentence length
    avg_sent_len: float = 0.0
    std_sent_len: float = 0.0
    median_sent_len: float = 0.0
    p25_sent_len: float = 0.0
    p75_sent_len: float = 0.0
    p95_sent_len: float = 0.0

    # Hedging
    hedge_ratio: float = 0.0       # hedge tokens / total tokens
    hedge_top5: List[str] = field(default_factory=list)

    # Passive voice
    passive_ratio: float = 0.0     # passive sentences / total sentences

    # Clause depth (comma + semicolon density 근사)
    clause_density: float = 0.0    # mean (commas + semicolons) per sentence

    # Lexical signature (사용자만의 관용어 top-K)
    vocab_top10: List[str] = field(default_factory=list)
    vocab_full: Dict[str, float] = field(default_factory=dict)  # TF-IDF score

    extracted_at: str = ""


class StyleProfiler:
    """사용자 논문 corpus → 문체 프로파일 추출."""

    _SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\'(\[])")
    _WORD_TOK = re.compile(r"\b[A-Za-z]{2,}\b")
    _PASSIVE_PAT = re.compile(
        r"\b(?:was|were|is|are|be|been|being|been)\s+\w+(?:ed|en)\b",
        re.IGNORECASE,
    )

    def __init__(self):
        self._base_vocab = _BASE_MEDICAL_VOCAB

    @staticmethod
    def _owner_hash(owner_email: str) -> str:
        norm = (owner_email or "anonymous").strip().lower()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _profile_path(owner_email: str) -> Path:
        h = StyleProfiler._owner_hash(owner_email)
        d = _PROFILES_DIR / h
        d.mkdir(parents=True, exist_ok=True)
        return d / "style_profile.json"

    def _read_file(self, fp: Path) -> str:
        """확장자에 따라 텍스트 추출. 실패 시 빈 문자열."""
        ext = fp.suffix.lower()
        try:
            if ext == ".txt":
                return fp.read_text(encoding="utf-8", errors="ignore")
            if ext == ".docx":
                try:
                    from docx import Document
                    doc = Document(str(fp))
                    return "\n".join(p.text for p in doc.paragraphs)
                except Exception as e:
                    _log.warning("docx read fail %s: %s", fp.name, e)
                    return ""
            if ext == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(fp))
                    return "\n".join((p.extract_text() or "") for p in reader.pages)
                except Exception:
                    try:
                        from pypdf2 import PdfReader
                        reader = PdfReader(str(fp))
                        return "\n".join((p.extract_text() or "") for p in reader.pages)
                    except Exception as e:
                        _log.warning("pdf read fail %s: %s", fp.name, e)
                        return ""
        except Exception as e:
            _log.warning("file read fail %s: %s", fp.name, e)
        return ""

    def extract_from_text(self, text: str, owner_email: str = "anonymous",
                            n_papers: int = 1) -> StyleProfile:
        """단일 텍스트 corpus에서 5축 추출."""
        import statistics
        from datetime import datetime

        if not text or len(text.strip()) < 200:
            _log.warning("text too short for style profiling (%d chars)", len(text))
            return StyleProfile(owner_email=owner_email,
                                  extracted_at=datetime.now().isoformat())

        # 1) sentence split
        sentences = [s.strip() for s in self._SENT_SPLIT.split(text) if len(s.strip()) > 10]
        if not sentences:
            return StyleProfile(owner_email=owner_email,
                                  extracted_at=datetime.now().isoformat())

        # 2) sentence length distribution (words per sentence)
        word_counts = [len(self._WORD_TOK.findall(s)) for s in sentences]
        word_counts = [w for w in word_counts if w > 0]
        sorted_wc = sorted(word_counts)

        def _percentile(arr: List[int], p: float) -> float:
            if not arr:
                return 0.0
            k = int(round((p / 100.0) * (len(arr) - 1)))
            return float(arr[max(0, min(len(arr) - 1, k))])

        # 3) Hedging
        all_words = [w.lower() for s in sentences for w in self._WORD_TOK.findall(s)]
        total_words = len(all_words) or 1
        hedge_counts = Counter(w for w in all_words if w in _HEDGE_TERMS)
        hedge_total = sum(hedge_counts.values())
        hedge_top5 = [w for w, _ in hedge_counts.most_common(5)]

        # 4) Passive voice
        passive_sents = sum(1 for s in sentences if self._PASSIVE_PAT.search(s))

        # 5) Clause density (commas + semicolons per sentence)
        clause_marks = sum(s.count(",") + s.count(";") for s in sentences)

        # 6) Lexical signature — TF-IDF approx (사용자 vocab − 기본 의학 vocab)
        word_freq = Counter(all_words)
        user_specific = {w: c for w, c in word_freq.items()
                          if w not in self._base_vocab and len(w) > 3 and c >= 2}
        # 간단한 TF-IDF: tf * log(N/df) — df는 base_vocab 가짓수 양식 양식, 양식 양식 양식
        # 양식 양식 양식 양식 양식 양식 양식 양식 양식 양식
        import math
        N = len(word_freq) or 1
        tfidf = {w: (c / total_words) * math.log(N / 1) for w, c in user_specific.items()}
        vocab_top10 = [w for w, _ in sorted(tfidf.items(), key=lambda x: -x[1])[:10]]

        from datetime import datetime
        profile = StyleProfile(
            owner_email=owner_email,
            sample_size_papers=n_papers,
            sample_size_sentences=len(sentences),
            sample_size_words=total_words,
            avg_sent_len=round(statistics.mean(word_counts), 2),
            std_sent_len=round(statistics.stdev(word_counts), 2) if len(word_counts) > 1 else 0.0,
            median_sent_len=round(statistics.median(word_counts), 2),
            p25_sent_len=_percentile(sorted_wc, 25),
            p75_sent_len=_percentile(sorted_wc, 75),
            p95_sent_len=_percentile(sorted_wc, 95),
            hedge_ratio=round(hedge_total / total_words, 4),
            hedge_top5=hedge_top5,
            passive_ratio=round(passive_sents / len(sentences), 4),
            clause_density=round(clause_marks / len(sentences), 2),
            vocab_top10=vocab_top10,
            vocab_full={k: round(v, 6) for k, v in
                          sorted(tfidf.items(), key=lambda x: -x[1])[:50]},
            extracted_at=datetime.now().isoformat(),
        )
        _log.info("style profile extracted: %d sentences, %d words, hedge=%.2f%%, passive=%.2f%%",
                   len(sentences), total_words, profile.hedge_ratio * 100,
                   profile.passive_ratio * 100)
        return profile

    def extract_from_files(self, files: List[str], owner_email: str = "anonymous") -> StyleProfile:
        """여러 파일에서 코퍼스 합쳐 추출."""
        texts = []
        for f in files:
            fp = Path(f)
            if not fp.exists():
                continue
            t = self._read_file(fp)
            if t:
                texts.append(t)
        merged = "\n\n".join(texts)
        return self.extract_from_text(merged, owner_email=owner_email,
                                        n_papers=len(texts))

    @classmethod
    def save(cls, profile: StyleProfile) -> Path:
        path = cls._profile_path(profile.owner_email)
        path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2),
                         encoding="utf-8")
        _log.info("style profile saved: %s", path)
        return path

    @classmethod
    def load(cls, owner_email: str) -> Optional[StyleProfile]:
        path = cls._profile_path(owner_email)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return StyleProfile(**data)
        except Exception as e:
            _log.warning("style profile load fail: %s", e)
            return None

    @classmethod
    def to_prompt_block(cls, profile: Optional[StyleProfile]) -> str:
        """프로파일을 system prompt에 inject할 짧은 텍스트로 변환."""
        if not profile or profile.sample_size_sentences == 0:
            return ""
        return (
            f"\n\n--- USER STYLE PROFILE (extracted from {profile.sample_size_papers} of your papers) ---\n"
            f"- Average sentence length: {profile.avg_sent_len} words "
            f"(p25={profile.p25_sent_len}, p75={profile.p75_sent_len}, p95={profile.p95_sent_len})\n"
            f"- Hedging rate: {profile.hedge_ratio * 100:.2f}% — favorite hedges: "
            f"{', '.join(profile.hedge_top5) or '(none)'}\n"
            f"- Passive voice ratio: {profile.passive_ratio * 100:.1f}% per sentence\n"
            f"- Clause density: {profile.clause_density} marks (',;') per sentence\n"
            f"- User-distinctive vocabulary (top 10): {', '.join(profile.vocab_top10) or '(generic)'}\n"
            f"\nWrite manuscript drafts that mimic this profile: match sentence length distribution, "
            f"keep hedging similar, prefer the user's lexical choices.\n"
        )


def extract_and_save_for_user(files: List[str], owner_email: str) -> StyleProfile:
    """convenience: 추출 + 저장 + 반환."""
    profiler = StyleProfiler()
    profile = profiler.extract_from_files(files, owner_email=owner_email)
    StyleProfiler.save(profile)
    return profile
