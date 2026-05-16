"""
조유선 스타일 시드 구축 스크립트
================================
1. PubMed에서 Yoosun Cho 제1/교신저자 논문 수집
2. 각 논문 초록으로 스타일 분석 → AuthorProfile 저장
3. BRCT 워드 파일로 추가 분석
4. 완성된 스타일 시드 출력
"""

import sys, os, json, time
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from dotenv import load_dotenv
load_dotenv()

import requests
from xml.etree import ElementTree as ET
from src.profile.author_profile import AuthorProfile
from src.ingestion.document_reader import DocumentReader
from src.vectordb.store import VectorStore
from src.ingestion.chunker import TextChunker
from src.agent.memory import AgentMemory

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ── 1. PubMed 검색 ──────────────────────────────────────────────────────

def search_pubmed(query, max_results=200):
    resp = requests.get(f"{BASE}/esearch.fcgi", params={
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]

def fetch_paper_xml(pmid):
    resp = requests.get(f"{BASE}/efetch.fcgi", params={
        "db": "pubmed", "id": pmid,
        "rettype": "abstract", "retmode": "xml",
    }, timeout=30)
    resp.raise_for_status()
    return resp.content

def parse_paper(xml_bytes):
    root = ET.fromstring(xml_bytes)
    article = root.find(".//PubmedArticle")
    if article is None:
        return None

    def text(path):
        el = article.find(path)
        return (el.text or "").strip() if el is not None else ""

    def text_of(el, path):
        e = el.find(path)
        return (e.text or "").strip() if e is not None else ""

    title = text(".//ArticleTitle")

    authors = []
    for a in article.findall(".//Author"):
        ln = text_of(a, "LastName")
        fn = text_of(a, "ForeName")
        name = f"{ln} {fn}".strip()
        aff = text_of(a, "AffiliationInfo/Affiliation")
        authors.append({"name": name, "affiliation": aff})

    abstract_parts = []
    for ab in article.findall(".//AbstractText"):
        label = ab.get("Label", "")
        txt = (ab.text or "").strip()
        if label:
            abstract_parts.append(f"{label}: {txt}")
        elif txt:
            abstract_parts.append(txt)
    abstract = "\n".join(abstract_parts)

    journal = text(".//Journal/Title")
    year = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")[:4]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "journal": journal,
        "year": year,
    }

def is_first_or_corresponding(paper):
    authors = paper.get("authors", [])
    if not authors:
        return False
    target = "cho yoosun"
    if target in authors[0]["name"].lower():
        return True
    if target in authors[-1]["name"].lower():
        return True
    return False

# ── 2. 논문 수집 ──────────────────────────────────────────────────────

print("=" * 60)
print("조유선 스타일 시드 구축 시작")
print("=" * 60)

print("\n[1/4] PubMed 검색 중...")
pmids_a = search_pubmed('Cho Yoosun[Author]')
pmids_b = search_pubmed('"Yoosun Cho"[Author]')
all_pmids = list(dict.fromkeys(pmids_a + pmids_b))
print(f"  총 {len(all_pmids)}개 PMID 발견")

papers = []
for pmid in all_pmids:
    try:
        xml = fetch_paper_xml(pmid)
        paper = parse_paper(xml)
        if paper and is_first_or_corresponding(paper) and paper["abstract"]:
            paper["pmid"] = pmid
            papers.append(paper)
            print(f"  [포함] {paper['title'][:65]}")
        time.sleep(0.35)
    except Exception as e:
        print(f"  [오류] PMID {pmid}: {e}")

print(f"\n  제1/교신저자 논문 (초록 있음): {len(papers)}개")

# 저장
os.makedirs("data", exist_ok=True)
with open("data/yoosun_cho_papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)
print("  논문 목록 저장: data/yoosun_cho_papers.json")

# ── 3. 벡터스토어에 저장 ──────────────────────────────────────────────

print("\n[2/4] 논문 ChromaDB 인덱싱 중...")
store = VectorStore()
chunker = TextChunker()
memory = AgentMemory()

ingested = 0
for p in papers:
    full_text = (
        f"Title: {p['title']}\n"
        f"Journal: {p['journal']} ({p['year']})\n"
        f"Authors: {', '.join(a['name'] for a in p['authors'][:5])}\n\n"
        f"Abstract:\n{p['abstract']}"
    )
    doc = {
        "path": f"pubmed:{p['pmid']}",
        "filename": f"pubmed_{p['pmid']}.txt",
        "title": p["title"],
        "full_text": full_text,
        "page_count": 1,
        "file_type": "pubmed",
        "metadata": {
            "pmid": p["pmid"],
            "journal": p["journal"],
            "year": p["year"],
            "author": "Yoosun Cho",
        },
    }
    chunks = chunker.chunk_document(doc)
    added = store.add_chunks(chunks)
    memory.log_ingest({
        "filename": doc["filename"],
        "title": p["title"],
        "file_type": "pubmed",
        "page_count": 1,
        "chunks_total": len(chunks),
        "chunks_added": added,
    })
    ingested += 1

print(f"  {ingested}개 논문 저장. 총 청크: {store.count()}개")

# ── 4. BRCT 워드 파일 인덱싱 ─────────────────────────────────────────

print("\n[3/4] BRCT 워드 파일 인덱싱 중...")
reader = DocumentReader()
brct_dir = "data/papers/BRCT"
if os.path.exists(brct_dir):
    docs = reader.read_directory(brct_dir)
    for doc in docs:
        chunks = chunker.chunk_document(doc)
        added = store.add_chunks(chunks)
        memory.log_ingest({
            "filename": doc["filename"],
            "title": doc["title"],
            "file_type": doc["file_type"],
            "page_count": doc["page_count"],
            "chunks_total": len(chunks),
            "chunks_added": added,
        })
        print(f"  {doc['filename']} → {added}개 신규 저장")
else:
    print("  BRCT 디렉토리 없음, 스킵")

# ── 5. 스타일 시드 구축 ──────────────────────────────────────────────

print("\n[4/4] 조유선 스타일 시드 분석 중...")
profile = AuthorProfile("Yoosun Cho")

# BRCT 논문 전문 먼저 (가장 풍부한 텍스트)
brct_main = "data/papers/BRCT/BRCT_LIBRA_AI_text_v2_clean.docx"
if os.path.exists(brct_main):
    doc = reader.read(brct_main)
    result = profile.analyse_paper(doc["full_text"], doc["title"])
    print(f"  BRCT 논문 분석: {result['status']}")

# PubMed 논문 초록으로 추가 분석 (최대 10편)
for p in papers[:10]:
    full_text = f"Title: {p['title']}\n\nAbstract:\n{p['abstract']}"
    result = profile.analyse_paper(full_text, p["title"])
    print(f"  {'[완료]' if result['status'] == 'analysed' else '[스킵]'} {p['title'][:55]}")

# ── 결과 출력 ────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("조유선 스타일 시드 구축 완료")
print("=" * 60)
print(profile.summary())
print(f"\n저장 위치: data/author_profiles/yoosun_cho.json")
print(f"인덱스 총 청크: {store.count()}개")
print(f"인덱싱된 파일: {store.list_sources()}")
