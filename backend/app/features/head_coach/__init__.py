"""Head Coach feature — Tier-2 "HLV trưởng" (the brain).

A single, strict personal coach for one player (Nguyễn Bá Thảo). It does NOT
collect data itself: it reads the Tier-1 specialist reports (video analysis
skill ledger, training-center load, daily/match stats, the tactic playbook),
already distilled and machine-readable, and synthesises a holistic verdict +
a concrete, demanding plan via the local text model.

See HEAD_COACH_PLAN.md for the design contract.
"""
