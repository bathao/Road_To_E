"""Tournament scheduling + the derived played-tournament record.

Deliberately NOT a results store — match results keep flowing into the
Daily Tracker as usual. A tournament here is a scheduling commitment ("on
day X I play singles + doubles with P") that the GUI counts down to and
the Head Coach plans training toward. Once results are entered (matches
linked via tournament_entry_id) the tournament counts as played: it leaves
the upcoming views and GET /record derives its history — placement / round
reached, W-L, per-match detail — with nothing stored.
"""
