"""RAG + 전체 스택 smoke test."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger("rag_smoke")

def test_chromadb():
    try:
        from src.vectordb.store import VectorStore
        vs = VectorStore(persist_dir="data/chromadb_test", collection_name="test_smoke")

        chunks = [
            {"text": "Adolescent obesity is associated with sleep deprivation in Korean youth.",
             "metadata": {"filename": "test_paper.pdf", "source": "test"}},
            {"text": "Physical activity reduces the risk of metabolic syndrome in teenagers.",
             "metadata": {"filename": "test_paper.pdf", "source": "test"}},
            {"text": "Screen time negatively correlates with sleep quality among adolescents.",
             "metadata": {"filename": "test_paper2.pdf", "source": "test"}},
        ]

        added = vs.add_chunks(chunks)
        _log.info("ChromaDB: %d chunks added", added)

        hits = vs.search("obesity sleep adolescents", n_results=2)
        _log.info("RAG search: %d results", len(hits))
        for h in hits:
            _log.info("  score=%.3f: %s", h["score"], h["text"][:70])

        sources = vs.list_sources()
        _log.info("Indexed docs: %s", sources)

        vs.delete_source("test_paper.pdf")
        vs.delete_source("test_paper2.pdf")
        print("[PASS] ChromaDB RAG 정상 작동")
        return True

    except ImportError as e:
        print(f"[SKIP] ChromaDB 미설치 — pip install chromadb : {e}")
        return False
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FAIL] ChromaDB 오류: {e}")
        return False


def test_imports():
    results = {}
    modules = [
        ("config.models",        "src.config.models",         "list_available_models"),
        ("config.env",           "src.config.env",            "bootstrap"),
        ("config.logging",       "src.config.logging_config", "get_logger"),
        ("agent.memory",         "src.agent.memory",          "AgentMemory"),
        ("llm.factory",          "src.llm.factory",           "get_llm_client"),
        ("vectordb.store",       "src.vectordb.store",        "get_vector_store"),
        ("ingestion.doc_reader", "src.ingestion.document_reader", "DocumentReader"),
        ("storage.manager",      "src.storage.manager",       "StorageManager"),
        ("research.pipeline",    "src.research.research_pipeline", "ResearchPipeline"),
        ("research.novelty",     "src.research.novelty_checker", "NoveltyChecker"),
        ("research.writer",      "src.research.paper_writer", "PaperWriter"),
        ("rag.pipeline",         "src.rag.pipeline",          "RAGPipeline"),
    ]
    for name, module, attr in modules:
        try:
            m = __import__(module, fromlist=[attr])
            getattr(m, attr)
            results[name] = "PASS"
        except Exception as e:
            results[name] = f"FAIL: {e}"

    for name, result in results.items():
        icon = "[PASS]" if result == "PASS" else "[FAIL]"
        print(f"  {icon} {name}: {result if result != 'PASS' else 'OK'}")

    return all(v == "PASS" for v in results.values())


if __name__ == "__main__":
    print("\n=== Medical-Agent Smoke Test ===\n")

    print("[1] 모듈 임포트 테스트:")
    imports_ok = test_imports()

    print("\n[2] ChromaDB RAG 테스트:")
    rag_ok = test_chromadb()

    print("\n=== 결과 ===")
    print(f"  임포트: {'PASS' if imports_ok else 'FAIL (일부 실패)'}")
    print(f"  ChromaDB RAG: {'PASS' if rag_ok else 'SKIP/FAIL'}")
