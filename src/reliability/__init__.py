"""Reliability Layer — explainability, traceability, cost control.

Per MASTER_UPGRADE_ROADMAP §3 — most layers wire/extend existing primitives:
  cost_optimizer  (NEW, #3) — critical-path reviewer selection, wired BEFORE #2/#6
  provenance      (wire #2) — reuses src.runtime.provenance.build_fingerprint
  evidence_graph  (extend #1) — Claim node on src.knowledge.schema_v2 EDGE_CATALOG
  confidence      (aggregate #6) — composes schema_v2.edge_confidence + peer_reviewer rubric
  snapshot        (structure #4) — named checkpoint on src.runtime.events.db
  failure_kb      (structure #5) — procedural memory on src.memory.router
  journal_intel   (extend #7) — word_limit/ref_style on src.export.journal_targeting

Do not duplicate. Wire.
"""
__all__ = ["cost_optimizer", "evidence_graph", "confidence",
            "snapshot", "failure_kb", "journal_intel"]
