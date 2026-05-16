"""Fetch all papers by Yoosun Cho (first/corresponding author) from PubMed
and ingest them into the Medical Agent vector store.
"""
import sys, os, json, time
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import requests
from dotenv import load_dotenv
load_dotenv()

from src.ingestion.web_reader import WebReader
from src.ingestion.chunker import TextChunker
from src.vectordb.store import VectorStore
from src.agent.memory import AgentMemory

# -------------------------------------------------------------------------
# 1. Search PubMed for Yoosun Cho papers
# -------------------------------------------------------------------------
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def search_pubmed(query: str, max_results: int = 200) -> list[str]:
    """Return list of PMIDs."""
    resp = requests.get(f"{BASE}/esearch.fcgi", params={
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }, timeout=30)
    resp.raise_for_status()
    ids = resp.json()["esearchresult"]["idlist"]
    return ids

def fetch_abstract(pmid: str) -> dict:
    """Fetch paper metadata + abstract via PubMed efetch."""
    resp = requests.get(f"{BASE}/efetch.fcgi", params={
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "xml",
    }, timeout=30)
    resp.raise_for_status()

    from xml.etree import ElementTree as ET
    root = ET.fromstring(resp.content)
    article = root.find(".//PubmedArticle")
    if article is None:
        return {}

    def text(path):
        el = article.find(path)
        return el.text.strip() if el is not None and el.text else ""

    # Title
    title = text(".//ArticleTitle")

    # Authors
    authors = []
    for a in article.findall(".//Author"):
        ln = text_of(a, "LastName")
        fn = text_of(a, "ForeName")
        aff = text_of(a, "AffiliationInfo/Affiliation")
        authors.append({"name": f"{ln} {fn}".strip(), "affiliation": aff})

    # Abstract
    abstract_parts = []
    for ab in article.findall(".//AbstractText"):
        label = ab.get("Label", "")
        txt = (ab.text or "").strip()
        if label:
            abstract_parts.append(f"{label}: {txt}")
        elif txt:
            abstract_parts.append(txt)
    abstract = "\n".join(abstract_parts)

    # Journal + year
    journal = text(".//Journal/Title")
    year = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")[:4]

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "journal": journal,
        "year": year,
    }

def text_of(element, path):
    el = element.find(path)
    return el.text.strip() if el is not None and el.text else ""

def is_first_or_corresponding(paper: dict, target_last="Cho", target_first="Yoosun") -> bool:
    """True if target is first author OR appears to be corresponding (last in list or marked)."""
    authors = paper.get("authors", [])
    if not authors:
        return False
    target = f"{target_last} {target_first}".lower()
    # First author
    if target in authors[0]["name"].lower():
        return True
    # Last author (often corresponding)
    if target in authors[-1]["name"].lower():
        return True
    return False

# -------------------------------------------------------------------------
# 2. Run search
# -------------------------------------------------------------------------
print("PubMed에서 Yoosun Cho 논문 검색 중...")
# Search with two queries to maximise recall
pmids_1 = search_pubmed('Cho Yoosun[Author]')
pmids_2 = search_pubmed('"Yoosun Cho"[Author]')
all_pmids = list(dict.fromkeys(pmids_1 + pmids_2))  # deduplicate, preserve order
print(f"  총 {len(all_pmids)}개 PMID 발견")

# -------------------------------------------------------------------------
# 3. Fetch metadata and filter first/corresponding author
# -------------------------------------------------------------------------
print("저자 위치 확인 중...")
target_papers = []
for pmid in all_pmids:
    try:
        meta = fetch_abstract(pmid)
        if meta and is_first_or_corresponding(meta):
            target_papers.append(meta)
            print(f"  [포함] PMID {pmid}: {meta['title'][:70]}")
        time.sleep(0.34)  # NCBI rate limit: max 3 req/sec
    except Exception as e:
        print(f"  [오류] PMID {pmid}: {e}")

print(f"\n제1저자/교신저자 논문: {len(target_papers)}개")

# -------------------------------------------------------------------------
# 4. Ingest into vector store
# -------------------------------------------------------------------------
chunker = TextChunker()
store = VectorStore()
memory = AgentMemory()

ingested = 0
for paper in target_papers:
    pmid = paper["pmid"]
    title = paper["title"]
    abstract = paper["abstract"]
    if not abstract:
        print(f"  [스킵] {title[:60]} — abstract 없음")
        continue

    full_text = f"Title: {title}\n\nJournal: {paper['journal']} ({paper['year']})\n\nAbstract:\n{abstract}"
    doc = {
        "path": f"pubmed:{pmid}",
        "filename": f"pubmed_{pmid}.txt",
        "title": title,
        "full_text": full_text,
        "page_count": 1,
        "file_type": "pubmed",
        "metadata": {
            "pmid": pmid,
            "journal": paper["journal"],
            "year": paper["year"],
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        },
    }

    chunks = chunker.chunk_document(doc)
    added = store.add_chunks(chunks)
    memory.log_ingest({
        "filename": doc["filename"],
        "title": title,
        "file_type": "pubmed",
        "page_count": 1,
        "chunks_total": len(chunks),
        "chunks_added": added,
    })
    ingested += 1
    print(f"  저장: {title[:65]}")

print(f"\n완료! {ingested}개 논문 학습됨. 총 저장 청크: {store.count()}개")

# Save summary
with open("data/yoosun_cho_papers.json", "w", encoding="utf-8") as f:
    json.dump(target_papers, f, ensure_ascii=False, indent=2)
print("논문 목록 저장: data/yoosun_cho_papers.json")
