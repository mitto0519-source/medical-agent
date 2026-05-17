#!/usr/bin/env python3
"""Functional smoke: ingest->vector->query with in-memory mocks

This script monkeypatches the RAG pipeline to use an in-memory vector
store and a dummy LLM so we can validate the end-to-end control flow
without external services.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rag import pipeline as rag_pipeline


class DummyVectorStore:
    def __init__(self):
        self._chunks = []

    def add_chunks(self, chunks):
        self._chunks.extend(chunks)
        return len(chunks)

    def search(self, query, n_results=5, where=None):
        hits = []
        for c in self._chunks:
            if where and where.get("filename") and c.get("metadata", {}).get("filename") != where.get("filename"):
                continue
            hits.append({"text": c.get("text", ""), "score": 1.0, "metadata": c.get("metadata", {})})
            if len(hits) >= n_results:
                break
        return hits

    def count(self):
        return len(self._chunks)

    def list_sources(self):
        return list({c.get("metadata", {}).get("filename", "unknown") for c in self._chunks})


class DummyClaudeClient:
    def __init__(self, api_key=None):
        pass

    def answer_from_papers(self, question, context_chunks):
        return "[MOCK ANSWER] " + (context_chunks[0][:200] if context_chunks else "no context")

    def summarize_paper(self, text):
        return "[MOCK SUMMARY] " + (text[:300] if text else "")


def main():
    # Monkeypatch factory and client
    rag_pipeline.get_vector_store = lambda persist_dir=None: DummyVectorStore()
    import src.llm.claude_client as cc
    cc.ClaudeClient = DummyClaudeClient

    # Instantiate pipeline (uses our dummy store & client)
    rag = rag_pipeline.RAGPipeline(persist_dir=":memory:", api_key="dummy")

    # Add a fake document as chunks
    chunks = [
        {"text": "This is a mock paper. The main finding: exposure X increases risk by 2x.", "metadata": {"filename": "mock_paper.pdf"}},
        {"text": "Methods: cohort study with N=10000, logistic regression adjusted for age.", "metadata": {"filename": "mock_paper.pdf"}},
    ]
    added = rag._store.add_chunks(chunks)
    print(f"Chunks added: {added}")

    # Query
    res = rag.ask("What is the main finding of the paper?", filename_filter="mock_paper.pdf")
    print("Answer:", res.get("answer"))
    print("Sources:", res.get("sources"))

    # Summarize
    summary = rag.summarize("mock_paper.pdf")
    print("Summary:", summary)


if __name__ == "__main__":
    main()
