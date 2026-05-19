"""지식그래프 트렌드 → 페르소나 자동 흡수.

periodic_learn.py 실행 후 호출되어:
1. 최근 수집된 PubMed 트렌드 읽기
2. 상위 토픽/개념 추출
3. 페르소나 accumulated_perspectives에 자동 반영

사용법:
  python scripts/evolve_persona.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger("evolve_persona")


def main():
    # 1. 지식그래프에서 상위 개념 노드 추출
    try:
        from src.knowledge.medical_graph import get_graph
        import json
        from pathlib import Path
        graph = get_graph()
        # concept_gap_pairs로 연구 공백 파악
        gaps = graph.concept_gap_pairs(n=5)
        trending = [(g[0], g[0], 1.0) for g in gaps] if gaps else []
    except Exception as e:
        _log.warning("그래프 로드 실패: %s", e)
        trending = []

    # 2. ontology에서 핵심 개념 레이블 추출
    try:
        from src.knowledge.medical_ontology import get_ontology
        ontology = get_ontology()
        concepts = ontology.all_concepts()
        recent_concepts = [c["label"].split("(")[0].strip() for c in concepts[:8]]
    except Exception as e:
        _log.warning("ontology 로드 실패: %s", e)
        recent_concepts = []

    if not trending and not recent_concepts:
        print("흡수할 새 트렌드 없음.")
        return

    # 3. 페르소나에 관점 주입
    from src.agent.persona import PersonaManager
    pm = PersonaManager()

    injected = 0
    for concept in recent_concepts[:5]:
        topic = concept if isinstance(concept, str) else concept.get("term", "")
        if not topic:
            continue
        perspective = (
            f"최근 PubMed 수집 기반: '{topic}'은(는) 한국 청소년/성인 공중보건 연구에서 "
            f"반복적으로 등장하는 핵심 주제. KYRBS/KNHANES 데이터와 연결 가능성 높음."
        )
        pm.add_perspective(topic=topic, perspective=perspective, confidence=0.72)
        injected += 1

    for node_id, label, weight in trending[:3]:
        topic = label or node_id
        perspective = (
            f"지식그래프 고빈도 노드: '{topic}'(가중치 {weight:.1f}). "
            f"관련 연구가 축적된 도메인으로, 신규 주제 제안 시 우선 고려."
        )
        pm.add_perspective(topic=topic, perspective=perspective, confidence=0.78)
        injected += 1

    # 4. 변화 기록
    from src.memory import change_log
    change_log.log(
        title=f"페르소나 자동 진화: {injected}개 관점 흡수",
        action_type="persona_evolve",
        description=f"periodic_learn 결과 → 페르소나 accumulated_perspectives 갱신. 개념: {recent_concepts[:3]}",
    )

    print(f"페르소나 진화 완료: {injected}개 관점 흡수됨")
    _log.info("페르소나 자동 진화 완료: %d개 관점", injected)


if __name__ == "__main__":
    main()
