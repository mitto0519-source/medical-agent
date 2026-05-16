"""자동 학습 루프 스탠드얼론 실행 스크립트.

Windows 작업 스케줄러 / cron 에서 정기 실행:
    python run_auto_learn.py

한 번 실행할 때마다:
  1. data/auto_learn_config.json 의 키워드를 모두 처리
  2. PubMed 검색 → 지식베이스(ChromaDB/Supabase) 인제스트
  3. NotebookLM 동기화 (온라인 시)
  4. last_run 타임스탬프 업데이트
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

LOOP_CFG = ROOT / "data" / "auto_learn_config.json"


def main():
    if not LOOP_CFG.exists():
        print("[AutoLearn] 설정 파일 없음. Streamlit UI에서 키워드를 먼저 등록하세요.")
        return

    cfg = json.loads(LOOP_CFG.read_text(encoding="utf-8"))
    jobs = cfg.get("jobs", [])
    if not jobs:
        print("[AutoLearn] 등록된 키워드 없음.")
        return

    from src.research.novelty_checker import NoveltyChecker
    from src.storage.manager import StorageManager

    checker = NoveltyChecker()
    sm = StorageManager()
    total = 0

    for job in jobs:
        kw = job["keyword"]
        topic = job["topic"]
        n = job.get("max", 20)
        print(f"[AutoLearn] 수집 중: {kw!r} (최대 {n}편)")
        try:
            papers = checker.search_papers(kw, max_results=n)
            if papers:
                result = sm.store_papers(papers, topic=topic)
                total += len(papers)
                print(f"  → {len(papers)}편 (NLM: {result['nlm']}, Local: {result['local']})")
            else:
                print(f"  → 결과 없음")
            job["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            print(f"  → 오류: {e}")

    LOOP_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[AutoLearn] 완료: 총 {total}편 학습")


if __name__ == "__main__":
    main()
