"""Loop Engineering layer (LOOP_ENGINEERING_SPEC).

기존 자동화·sub-agent·상태 인프라를 LoopDefinition으로 표면화만 — 새 인프라 0.

모듈:
  registry   — LoopDefinition + list_loops + run_loop
  triage     — backlog/events/change_log → 4분류 inbox
  state_view — ResearchProject + CURRENT_STATE + self_model → today_view
  commands   — /loop /goal /triage /state /checkpoint /branch slash dispatch
"""
__all__ = ["registry", "triage", "state_view", "commands"]
