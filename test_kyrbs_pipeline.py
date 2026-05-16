"""KYRBS + ResearchPipeline 통합 테스트"""
import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from dotenv import load_dotenv
load_dotenv()

from src.library.dataset_library import DatasetLibrary
from src.library.methods_library import MethodsLibrary

# ── 라이브러리 로드 확인 ──────────────────────────────────────────────
lib = DatasetLibrary('data/libraries')
ctx = lib.get_context('KYRBS')
print("=== KYRBS 데이터셋 컨텍스트 (앞 1500자) ===")
print(ctx[:1500])
print("...\n")

# ── MethodsLibrary 확인 ──────────────────────────────────────────────
methods = MethodsLibrary('data/libraries')
recs = methods.recommend("binary")
print("=== 이진 결과변수 추천 통계 방법 ===")
for r in recs:
    print(f"  {r['name']}: {r.get('use_when', r.get('description',''))}")
print()

# ── ResearchPipeline 주제 생성 (1개) ──────────────────────────────────
print("=== ResearchPipeline 주제 생성 테스트 ===")
print("(ChromaDB + Claude API 호출 — 잠시 소요)")

from src.research.research_pipeline import ResearchPipeline

rp = ResearchPipeline(author_name="Yoosun Cho")
topics = rp.generate_topics(
    dataset_name="KYRBS",
    focus="스마트폰 사용과 수면 건강",
    n_topics=3,
)

print(f"\n총 {len(topics)}개 주제 생성됨:")
for i, t in enumerate(topics, 1):
    print(f"\n[{i}] {t.get('title','')}")
    print(f"    노출: {t.get('exposure','')}")
    print(f"    결과: {t.get('outcome','')}")
    print(f"    대상: {t.get('population','')}")
    print(f"    근거: {t.get('rationale','')[:100]}...")
