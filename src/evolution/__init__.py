"""Self-evolution closed-loop layer (SELF_EVOLUTION_SPEC).

Modules:
  ledger  — versioned change ledger (candidate → gate result → promote/rollback)
  gate    — baseline vs candidate gate runner on gold_set
  anchor  — gold_set held-out scorer (composes existing quality_harness axes)

Invariants (do NOT violate):
  - External anchor only — gold_set is the single source of truth for "is it better".
  - Held-out — never inject gold_set into prompts/training.
  - Versioned — every persona/prompt/retrieval-cfg change is a candidate.
  - Gated — candidate must beat baseline on gold_set to promote; otherwise rollback.
  - Provenance — every promote/rollback decision recorded with fingerprint.
"""
__all__ = ["ledger", "gate", "anchor"]
