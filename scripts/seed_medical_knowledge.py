"""Seed the medical knowledge foundation from ~2000 random PubMed abstracts.

Usage:
    python scripts/seed_medical_knowledge.py            # fetch + extract
    python scripts/seed_medical_knowledge.py --resume   # skip already-fetched topics
    python scripts/seed_medical_knowledge.py --stats    # show current seed stats

What it does:
  1. Fetches ~100 papers per medical topic (20 topics = ~2000 papers) via NCBI eutils
  2. Extracts: medical vocabulary, methodology terms, sentence patterns, topic distribution
  3. Saves to data/medical_knowledge_seed/ (JSON files)
  4. src/knowledge/medical_seed.py then injects this as system prompt preamble

NCBI eutils: free, no API key required (max 3 req/s without key, 10/s with key).
If you have an NCBI API key, set NCBI_API_KEY in .env to increase throughput.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "mitto0519@gmail.com"  # NCBI requires email for API access
SEED_DIR = Path("data/medical_knowledge_seed")
RAW_DIR = SEED_DIR / "raw"
PAPERS_PER_TOPIC = 100

# 22 medical domains → target ~2200 papers
TOPICS = [
    ("obesity",           "obesity[MeSH] AND (cohort OR epidemiology) AND hasabstract[text]"),
    ("diabetes",          "diabetes mellitus[MeSH] AND (randomized OR clinical trial) AND hasabstract[text]"),
    ("cardiovascular",    "cardiovascular diseases[MeSH] AND (risk factors OR cohort) AND hasabstract[text]"),
    ("cancer_biomarker",  "neoplasms[MeSH] AND biomarkers AND (prognosis OR survival) AND hasabstract[text]"),
    ("hypertension",      "hypertension[MeSH] AND (treatment OR management) AND hasabstract[text]"),
    ("nutrition",         "nutrition[MeSH] AND (dietary intake OR diet) AND epidemiology AND hasabstract[text]"),
    ("sleep_health",      "sleep disorders[MeSH] AND (cardiovascular OR metabolic) AND hasabstract[text]"),
    ("inflammation",      "inflammation[MeSH] AND (biomarker OR cytokine) AND clinical AND hasabstract[text]"),
    ("metabolic_syndrome","metabolic syndrome[MeSH] AND (prevalence OR risk) AND hasabstract[text]"),
    ("physical_activity", "exercise[MeSH] AND (mortality OR cardiovascular) AND hasabstract[text]"),
    ("pediatric_obesity", "pediatric obesity[MeSH] AND (prevention OR intervention) AND hasabstract[text]"),
    ("geriatrics",        "aged[MeSH] AND (frailty OR cognitive decline OR dementia) AND hasabstract[text]"),
    ("lung_cancer",       "lung neoplasms[MeSH] AND (survival OR prognosis OR treatment) AND hasabstract[text]"),
    ("kidney_disease",    "renal insufficiency chronic[MeSH] AND (progression OR outcome) AND hasabstract[text]"),
    ("liver_disease",     "liver diseases[MeSH] AND (epidemiology OR incidence) AND hasabstract[text]"),
    ("mental_health",     "depression[MeSH] AND (risk factors OR comorbidity OR treatment) AND hasabstract[text]"),
    ("smoking_cancer",    "smoking[MeSH] AND (lung neoplasms OR cancer risk) AND hasabstract[text]"),
    ("diet_mortality",    "diet[MeSH] AND (all cause mortality OR cardiovascular mortality) AND hasabstract[text]"),
    ("stroke",            "stroke[MeSH] AND (risk factors OR prevention OR outcome) AND hasabstract[text]"),
    ("breast_cancer",     "breast neoplasms[MeSH] AND (hormone OR treatment OR survival) AND hasabstract[text]"),
    ("thyroid",           "thyroid diseases[MeSH] AND (epidemiology OR outcome OR treatment) AND hasabstract[text]"),
    ("NAFLD",             "non-alcoholic fatty liver disease[MeSH] AND (prevalence OR risk) AND hasabstract[text]"),
]

# Statistical / methodology terms to detect
_STAT_PATTERNS = re.compile(
    r"\b("
    r"hazard ratio|odds ratio|risk ratio|relative risk|incidence rate ratio"
    r"|confidence interval|p[\s-]?value|statistical(?:ly)? significant"
    r"|multivariate|multivariable|logistic regression|linear regression"
    r"|cox proportional hazard|kaplan.meier|log.rank"
    r"|propensity score|inverse probability|matching"
    r"|meta.analysis|systematic review|pooled analysis"
    r"|randomized controlled trial|RCT|double.blind|placebo"
    r"|cohort study|cross.sectional|case.control|prospective|retrospective"
    r"|sensitivity analysis|subgroup analysis|interaction term"
    r"|area under the curve|AUC|ROC|receiver operating characteristic"
    r"|spearman|pearson|kendall|correlation coefficient"
    r"|bonferroni|FDR|false discovery rate|multiple comparisons"
    r"|mediation analysis|moderation|effect modification"
    r"|GWAS|genome.wide|single nucleotide polymorphism|SNP"
    r"|weighted kappa|intraclass correlation|ICC"
    r"|survival analysis|time.to.event|censoring"
    r"|adjusted|unadjusted|crude|standardized"
    r")\b",
    re.IGNORECASE,
)

# Medical sentence openers to capture as patterns
_OPENER_PATTERNS = re.compile(
    r"^(We|This study|This analysis|These findings|Our results?|Among|After|In this|"
    r"The present|Compared with|A total of|We found|The risk|Higher|Lower|"
    r"Participants|Subjects|Patients|Adults|Children|Women|Men|Individuals)\b",
    re.IGNORECASE,
)

# Medical vocabulary: multi-word capitalized terms and key single terms
_VOCAB_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+|"  # Multi-word capitalized
    r"body mass index|BMI|glycated hemoglobin|HbA1c|"
    r"C-reactive protein|CRP|interleukin|tumor necrosis factor|TNF|"
    r"low.density lipoprotein|LDL|high.density lipoprotein|HDL|"
    r"systolic blood pressure|diastolic blood pressure|"
    r"waist circumference|waist-to-hip ratio|"
    r"insulin resistance|insulin sensitivity|HOMA-IR|"
    r"glomerular filtration rate|GFR|creatinine|albuminuria|"
    r"atherosclerosis|atherogenic|cardiovascular event|"
    r"all-cause mortality|cause-specific mortality|"
    r"non-alcoholic fatty liver|hepatic steatosis|"
    r"adipose tissue|visceral fat|subcutaneous fat|"
    r"inflammatory marker|inflammatory cytokine|"
    r"endothelial dysfunction|arterial stiffness|"
    r"sleep duration|sleep quality|obstructive sleep apnea|"
    r"physical inactivity|sedentary behavior|"
    r"dietary pattern|Mediterranean diet|DASH diet|"
    r"comorbidity|multimorbidity|polypharmacy|"
    r"socioeconomic status|health disparity|"
    r"survival benefit|disease-free survival|overall survival|"
    r"hazard ratio|odds ratio|relative risk)\b",
    re.IGNORECASE,
)

# ── Utilities ────────────────────────────────────────────────────────────────

def _ncbi_get(url: str, retries: int = 3) -> bytes:
    api_key = os.environ.get("NCBI_API_KEY", "")
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}email={EMAIL}" + (f"&api_key={api_key}" if api_key else "")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=30) as r:
                return r.read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return b""


def search_pubmed(query: str, retmax: int = 100) -> list[str]:
    """Return up to retmax PMID strings matching query."""
    params = urllib.parse.urlencode({"db": "pubmed", "term": query, "retmax": retmax,
                                     "retmode": "json", "usehistory": "n"})
    data = json.loads(_ncbi_get(f"{EUTILS}/esearch.fcgi?{params}"))
    return data["esearchresult"]["idlist"]


def fetch_abstracts_xml(pmids: list[str]) -> bytes:
    """Fetch abstracts for a list of PMIDs (batch), return raw XML bytes."""
    ids = ",".join(pmids)
    params = urllib.parse.urlencode({"db": "pubmed", "id": ids,
                                     "rettype": "abstract", "retmode": "xml"})
    return _ncbi_get(f"{EUTILS}/efetch.fcgi?{params}")


def parse_xml(xml_bytes: bytes) -> list[dict]:
    """Parse PubMed XML → list of paper dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return papers

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_parts = []
        for ab in article.findall(".//AbstractText"):
            label = ab.get("Label", "")
            text = "".join(ab.itertext())
            abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        year_el = (article.find(".//PubDate/Year")
                   or article.find(".//ArticleDate/Year"))
        year = year_el.text if year_el is not None else ""

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        mesh_terms = [
            m.text for m in article.findall(".//MeshHeading/DescriptorName")
            if m.text
        ]

        if abstract:
            papers.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "journal": journal,
                "mesh_terms": mesh_terms,
            })
    return papers


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_features(papers: list[dict]) -> dict:
    """Extract vocabulary, methodology terms, sentence patterns from papers."""
    vocab_counter: Counter = Counter()
    method_counter: Counter = Counter()
    pattern_counter: Counter = Counter()
    year_counter: Counter = Counter()
    journal_counter: Counter = Counter()

    for paper in papers:
        full_text = f"{paper['title']} {paper['abstract']}"

        # Vocabulary
        for match in _VOCAB_PATTERN.finditer(full_text):
            term = match.group(0).strip()
            if 3 < len(term) < 60:
                vocab_counter[term.lower()] += 1

        # Methodology
        for match in _STAT_PATTERNS.finditer(full_text):
            method_counter[match.group(0).lower()] += 1

        # Sentence patterns (from abstract only)
        for sent in re.split(r"(?<=[.!?])\s+", paper["abstract"]):
            sent = sent.strip()
            m = _OPENER_PATTERNS.match(sent)
            if m and 30 < len(sent) < 200:
                # Generalise: keep first ~12 words
                words = sent.split()[:12]
                pattern = " ".join(words) + "…"
                pattern_counter[pattern] += 1

        if paper.get("year"):
            year_counter[paper["year"]] += 1
        if paper.get("journal"):
            journal_counter[paper["journal"]] += 1

    return {
        "vocabulary": [w for w, _ in vocab_counter.most_common(500)],
        "methodology_terms": [t for t, _ in method_counter.most_common(100)],
        "sentence_patterns": [p for p, _ in pattern_counter.most_common(50)],
        "year_distribution": dict(year_counter.most_common(20)),
        "top_journals": dict(journal_counter.most_common(30)),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def load_env():
    try:
        from pathlib import Path as _P
        env_path = _P(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"\''))
    except Exception:
        pass


def show_stats():
    meta_path = SEED_DIR / "seed_metadata.json"
    if not meta_path.exists():
        print("Seed not built yet. Run: python scripts/seed_medical_knowledge.py")
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    print(f"Seed built: {meta.get('built_at', '?')}")
    print(f"Papers:     {meta.get('papers_count', 0):,}")
    print(f"Vocabulary: {meta.get('vocab_size', 0):,} terms")
    print(f"Methodology:{meta.get('methodology_count', 0)} terms")
    print(f"Patterns:   {meta.get('pattern_count', 0)}")
    print(f"Topics:     {meta.get('topic_count', 0)}")
    topic_dist = SEED_DIR / "topic_distribution.json"
    if topic_dist.exists():
        dist = json.loads(topic_dist.read_text(encoding="utf-8"))
        for t, n in dist.items():
            print(f"  {t:<30} {n} papers")


def run(resume: bool = False):
    load_env()
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Delay between requests — respect NCBI rate limit
    api_key = os.environ.get("NCBI_API_KEY", "")
    delay = 0.11 if api_key else 0.4  # 9/s with key, 2.5/s without

    all_papers: list[dict] = []
    topic_dist: dict = {}

    for topic_name, query in TOPICS:
        raw_file = RAW_DIR / f"{topic_name}.json"
        if resume and raw_file.exists():
            cached = json.loads(raw_file.read_text(encoding="utf-8"))
            all_papers.extend(cached)
            topic_dist[topic_name] = len(cached)
            print(f"  [cached] {topic_name:<30} {len(cached)} papers")
            continue

        print(f"  [fetch]  {topic_name:<30} ", end="", flush=True)
        try:
            pmids = search_pubmed(query, retmax=PAPERS_PER_TOPIC)
            time.sleep(delay)

            if not pmids:
                print("0 hits")
                topic_dist[topic_name] = 0
                continue

            # Fetch in batches of 50
            papers = []
            for i in range(0, len(pmids), 50):
                batch = pmids[i:i + 50]
                xml_bytes = fetch_abstracts_xml(batch)
                papers.extend(parse_xml(xml_bytes))
                time.sleep(delay)

            raw_file.write_text(
                json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            all_papers.extend(papers)
            topic_dist[topic_name] = len(papers)
            print(f"{len(papers)} papers")

        except Exception as e:
            print(f"ERROR: {e}")
            topic_dist[topic_name] = 0

    print(f"\nTotal papers: {len(all_papers)}")
    print("Extracting features…", flush=True)

    features = extract_features(all_papers)

    # Save structured seed files
    (SEED_DIR / "vocabulary.json").write_text(
        json.dumps(features["vocabulary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (SEED_DIR / "methodology_terms.json").write_text(
        json.dumps(features["methodology_terms"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (SEED_DIR / "sentence_patterns.json").write_text(
        json.dumps(features["sentence_patterns"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (SEED_DIR / "topic_distribution.json").write_text(
        json.dumps(topic_dist, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from datetime import datetime
    meta = {
        "built_at": datetime.utcnow().isoformat() + "Z",
        "papers_count": len(all_papers),
        "topics": list(topic_dist.keys()),
        "topic_count": len(topic_dist),
        "vocab_size": len(features["vocabulary"]),
        "methodology_count": len(features["methodology_terms"]),
        "pattern_count": len(features["sentence_patterns"]),
        "ncbi_email": EMAIL,
        "papers_per_topic": PAPERS_PER_TOPIC,
    }
    (SEED_DIR / "seed_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Vocabulary:    {len(features['vocabulary'])} terms")
    print(f"Methodology:   {len(features['methodology_terms'])} terms")
    print(f"Patterns:      {len(features['sentence_patterns'])}")
    print(f"\nSeed saved to {SEED_DIR}/")
    print("Run your app — medical knowledge preamble will be auto-injected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build medical knowledge seed from PubMed")
    parser.add_argument("--resume", action="store_true", help="Skip already-fetched topics")
    parser.add_argument("--stats", action="store_true", help="Show current seed stats")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run(resume=args.resume)
