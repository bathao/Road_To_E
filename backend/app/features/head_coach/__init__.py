"""Head Coach feature — Tier-2 "HLV trưởng" (the brain).

A single, strict personal coach for one player. It does NOT collect data
itself: it reads hard facts from the database — Daily Tracker volume + every
match (score, opponent level, pips, practice/official, head-to-head), racket
time, Training Center load and the player's day notes — and synthesises a
holistic verdict + a concrete, demanding plan via the local text model.
No AI-derived technique ratings: the retired technique-analysis pipeline was
model guesswork, so the coach reasons only over recorded results.

Surfaces: the on-demand verdict (+ live directive progress), rolling 7/30-day
recaps (button-only), grounded chat with an auto-written notebook.
"""
