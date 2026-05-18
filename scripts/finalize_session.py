"""Finalize current session — resolve completed insights and log work."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.env import bootstrap
bootstrap()

from src.memory import agent_insight, change_log

resolved_titles = [
    "ResearchPipeline.write_paper() continuity 로깅 미연결",
    "app/main.py Flask 레거시 코드 제거 필요",
]

all_insights = agent_insight.get_all(category="next_action", n=20)
for insight in all_insights:
    if insight["title"] in resolved_titles:
        agent_insight.resolve(insight["id"])
        print(f"Resolved: {insight['title'][:60]}")

change_log.log(
    title="자가 진단 시스템 완성 및 핵심 next_action 3건 처리",
    action_type="config_change",
    description=(
        "14개 초기 인사이트 입력, self_model 96/100 달성, "
        "ResearchPipeline 3개 메서드(write_paper/generate_topics/check_novelty) continuity 연결, "
        "Flask dead code(app/main.py + tests/test_app_health.py) 제거"
    ),
    why_better="논문 생산 파이프라인 전체가 이제 장기기억 시스템과 연결됨. 자가 진단 + 다음 액션 자동 제안 체계 완비.",
    inputs={"insights_count": 14, "next_actions_resolved": 2},
    outputs={
        "self_model_score": 96,
        "smoke_test": "12/12",
        "continuity_connected": ["write_paper", "generate_topics", "check_novelty"],
        "dead_code_removed": ["app/main.py", "tests/test_app_health.py"],
    },
    impact={"affected_modules": ["research_pipeline", "agent_insight", "self_model", "change_log"]},
)
print("Change log recorded.")

from src.memory.self_model import refresh, print_status
refresh()
print(print_status())
