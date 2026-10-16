"""Match vocabularies: disciplines and tournament rounds (one place).

The ``Literal`` types validate API payloads (schemas); the tuples/dicts drive
cell rendering, the ELO replay, tournament placements and the tactics
prompts. Keep the ``Literal`` and ``get_args`` pairs together so adding a
value changes every consumer at once.
"""
from __future__ import annotations

from typing import Literal, get_args

# one_v_two = I play ALONE vs two opponents; two_v_one = me + partner vs one.
Discipline = Literal["singles", "doubles", "one_v_two", "two_v_one"]
DISCIPLINES: tuple[str, ...] = get_args(Discipline)

# Cell/export prefix per discipline (singles stays bare, Excel-style).
DISCIPLINE_PREFIX = {"doubles": "D: ", "one_v_two": "1v2: ", "two_v_one": "2v1: "}

Round = Literal["group", "r64", "r32", "r16", "r8", "qf", "sf", "f"]
ROUNDS: tuple[str, ...] = get_args(Round)

# Short round labels for tournament matches — group-stage matches stay bare
# (they're the bulk), knockout rounds each get their own prefixed cell line.
ROUND_SHORT = {
    "group": "",
    "r64": "1/64",
    "r32": "1/32",
    "r16": "1/16",
    "r8": "1/8",
    "qf": "QF",
    "sf": "SF",
    "f": "F",
}

# Long names for prompts and placement warnings (group stage has none).
ROUND_NAME = {
    "r64": "1/64", "r32": "1/32", "r16": "1/16", "r8": "1/8",
    "qf": "Quarter-final", "sf": "Semi-final", "f": "Final",
}

# Bracket depth (deeper = later) and the round that follows each knockout
# round — the tournament placement rules in rating.py walk these.
ROUND_DEPTH = {r: i for i, r in enumerate(ROUNDS)}
NEXT_ROUND = {"r64": "r32", "r32": "r16", "r16": "r8", "r8": "qf", "qf": "sf", "sf": "f"}
