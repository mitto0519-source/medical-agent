import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from src.ingestion.document_reader import DocumentReader
from src.ingestion.chunker import TextChunker
from src.vectordb.store import VectorStore

reader = DocumentReader()
chunker = TextChunker()
store = VectorStore()

brct_dir = "data/papers/BRCT"
docs = reader.read_directory(brct_dir)
print(f"읽은 파일 수: {len(docs)}개")

for doc in docs:
    chunks = chunker.chunk_document(doc)
    added = store.add_chunks(chunks)
    print(f"  {doc['filename']} ({doc['file_type']}) -> {len(chunks)}청크, {added}개 신규 저장")

print(f"\n총 저장된 청크: {store.count()}개")
print("인덱싱된 파일:", store.list_sources())
