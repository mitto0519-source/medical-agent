import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_functional_rag_flow():
    from src.rag import pipeline as rag_pipeline

    class DummyVectorStore:
        def __init__(self):
            self._chunks = []
        def add_chunks(self, chunks):
            self._chunks.extend(chunks); return len(chunks)
        def search(self, query, n_results=5, where=None):
            hits=[]
            for c in self._chunks:
                if where and where.get('filename') and c.get('metadata',{}).get('filename')!=where.get('filename'):
                    continue
                hits.append({'text':c.get('text',''),'score':1.0,'metadata':c.get('metadata',{})})
                if len(hits)>=n_results: break
            return hits
        def count(self): return len(self._chunks)
        def list_sources(self): return list({c.get('metadata',{}).get('filename','unknown') for c in self._chunks})

    class DummyClaudeClient:
        def __init__(self, api_key=None): pass
        def answer_from_papers(self, question, context_chunks, **kwargs): return '[MOCK ANSWER]'
        def summarize_paper(self, text): return '[MOCK SUMMARY]'

    rag_pipeline.get_vector_store = lambda persist_dir=None: DummyVectorStore()
    rag_pipeline.ClaudeClient = DummyClaudeClient

    rag = rag_pipeline.RAGPipeline(persist_dir=':memory:', api_key='dummy')
    chunks=[{'text':'a','metadata':{'filename':'f.pdf'}}]
    added = rag._store.add_chunks(chunks)
    assert added == 1
    res = rag.ask('q', filename_filter='f.pdf')
    assert 'answer' in res
    summary = rag.summarize('f.pdf')
    assert isinstance(summary, str) and summary.startswith('[MOCK')
