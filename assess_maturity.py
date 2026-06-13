#!/usr/bin/env python
import json
from pathlib import Path

print("=" * 70)
print("DEVELOPMENT MATURITY ASSESSMENT — Medical-Agent")
print("=" * 70)

# 1. Codebase size
root = Path('.')
py_files = list(root.rglob('*.py'))
py_files = [f for f in py_files if 'venv' not in str(f) and '.venv' not in str(f) and '__pycache__' not in str(f)]
total_lines = sum(len(open(f, encoding='utf-8', errors='ignore').readlines()) for f in py_files)

print(f"\n[1] 코드베이스 규모")
print(f"  Python 파일: {len(py_files)} 개")
print(f"  총 라인수: {total_lines:,}")

# 2. Data assets
data_dir = Path('data')
def count_files_in(path):
    if not path.exists():
        return 0
    files = list(path.rglob('*'))
    return len([f for f in files if f.is_file()])

print(f"\n[2] 데이터 자산")
# FIX-0 (REVIEW_FIX_SPEC): reconcile_state.measure_truth 재사용 (중복 카운터 X, 규칙10)
try:
    from scripts.reconcile_state import measure_truth
    _truth = measure_truth()
    _p = _truth.get("papers", {})
    _ch = _truth.get("chromadb", {})
    _kg = _truth.get("knowledge_graph", {})
    print(f"  OA Papers: full-text {_p.get('full_text_files')}, "
          f">5KB {_p.get('full_text_above_5kb')} "
          f"({_p.get('full_text_completion_pct')}%), "
          f"meta_json {_p.get('meta_json_files')}")
    print(f"  ChromaDB: embeddings {_ch.get('embeddings')}, "
          f"queue {_ch.get('queue_pending')}")
    print(f"  Knowledge Graph: {_kg.get('nodes_total')} nodes / "
          f"{_kg.get('edges_total')} edges  "
          f"(types: {_kg.get('node_types', {})})")
    print(f"  Author Profiles: {count_files_in(data_dir / 'author_profiles')} files")
    print(f"  Style Profiles (per-user): "
          f"{_truth.get('style_profiles', {}).get('per_user_profiles', 0)}")
    print(f"  Ontology Concepts: {_truth.get('ontology', {}).get('concept_count')}")
except Exception as _e:
    # fallback: raw file count only (reconcile unavailable)
    print(f"  OA Papers: {count_files_in(data_dir / 'oa_papers')} files (reconcile fallback, reason: {_e})")
    print(f"  Knowledge Graph: {count_files_in(data_dir / 'knowledge_graph')} files")
    print(f"  Library/Components: {count_files_in(data_dir / 'library')} files")
    print(f"  Author Profiles: {count_files_in(data_dir / 'author_profiles')} files")

# 3. Documentation
docs_count = count_files_in(Path('docs'))
print(f"\n[3] 문서")
print(f"  docs/ 폴더: {docs_count} 파일")

# 4. Tests & scripts
test_count = len(list(Path('tests').rglob('test_*.py')))
scripts_count = len(list(Path('scripts').rglob('*.py')))
print(f"\n[4] 테스트 & 스크립트")
print(f"  Test 파일: {test_count} 개")
print(f"  Utility 스크립트: {scripts_count} 개")

# 5. Self model
print(f"\n[5] 시스템 건강도")
with open('data/agent_self/self_model.json', 'r', encoding='utf-8') as f:
    model = json.load(f)
    print(f"  Overall score: {model['overall_score']}/100")
    print(f"  Smoke test: {model['smoke_test_score']}")
    print(f"  Active insights: {model['active_insights']} 개")
    
    print(f"\n  주요 강점:")
    for i, strength in enumerate(model['known_strengths'][:3], 1):
        print(f"    {i}. {strength}")
    
    print(f"\n  주요 약점:")
    for i, weakness in enumerate(model['known_weaknesses'][:3], 1):
        print(f"    {i}. {weakness}")

with open('data/change_log/history.json', 'r', encoding='utf-8') as f:
    history = json.load(f)
    print(f"\n  Recorded sessions: {len(history)} 개")
    
    if history:
        print(f"\n  최근 작업:")
        for entry in history[:3]:
            print(f"    - {entry.get('title', 'N/A')}")

# 6. Modules
print(f"\n[6] 핵심 모듈 상태 (ARCHITECTURE 기준)")
arch_modules = {
    'data_loading': ['src/data/kyrbs_raw_loader.py', 'src/data/knhanes_loader.py'],
    'statistics': ['src/data/stat_bridge.py', 'src/statistics/medical_stats.py'],
    'research_pipeline': ['src/research/research_pipeline.py', 'src/research/paper_writer.py'],
    'llm_clients': ['src/llm/claude_client.py', 'src/llm/openai_client.py', 'src/llm/gemini_client.py'],
    'memory': ['src/memory/change_log.py', 'src/memory/self_model.py', 'src/memory/agent_insight.py'],
    'rag': ['src/rag/pipeline.py', 'src/vectordb/store.py'],
    'knowledge': ['src/knowledge/medical_graph.py', 'src/knowledge/code_graph.py'],
    'ui': ['app/streamlit_app.py', 'app/pages/', 'mcp_server.py'],
}

for category, files in arch_modules.items():
    existing = sum(1 for f in files if Path(f).exists() or len(list(Path(f).rglob('*.py'))) > 0)
    total = len(files)
    status = "✅" if existing == total else "⚠️" if existing > 0 else "❌"
    print(f"  {status} {category}: {existing}/{total}")

print("\n" + "=" * 70)
