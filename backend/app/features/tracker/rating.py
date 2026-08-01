"""The user's dynamic ELO rating — the only dynamic rating in the system.

Everything rating-related lives here: the settled constants, the my-points
anchor storage, at-match-time point snapshots, the handicap ladder and the
replay engine. Decision history: PROGRESS.md, 2026-07-26.

Architecture: REPLAY, not stored deltas. The anchor (date, points) lives in
tracker_setting; the current rating = anchor + every eligible match since,
recomputed on read. Editing/deleting/backfilling matches self-corrects; a
manual points edit = a new anchor from that day.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.features.tracker import schemas
from app.features.tracker.models import Category, Match, Player, Setting

# ------------------------------------------------------------- constants
#   dR = K_BASE × t(kind) × d(discipline) × m(margin) × (S − E)
#   E  = 1 / (1 + 10^((R_theirs − R_mine)/400)),  S = 1 win / 0 loss
#   with R_receiver += handicap_bonus(...) when the match has a chấp
#
# Doubles compare TEAM AVERAGES on the same /400 curve (a sum would silently
# double the sensitivity). d = 1.0 by USER DECISION 2026-07-26 ("tác động
# của tôi trong trận đánh đôi vẫn phải tốt nếu thắng"): a doubles result
# moves the rating exactly like a singles one, both ways — a partner's bad
# day costs full points too. (0.5 = half attribution was the alternative.)
#
# 1v2 / 2v1 (one player vs a pair) — USER RULE 2026-07-27: the solo side's
# ELO counts ×2 "để so sánh với bên kia THÔI" — i.e. the solo player stands
# in as BOTH members of their team ("coi như 2 người tôi đánh với 2 người
# bên kia"). On the team-average scale that is simply: solo side average =
# their own rating. The win/loss delta stays the NORMAL magnitude — the ×2
# never multiplies the gain/loss. Assumes solo-at-R vs pair-averaging-R is
# an even kèo; if the format itself proves lopsided, revisit with data.
#
# K sized for ~20 matches/week and a 3-4 MONTH skill timescale — luck noise
# stays ~±20/week.
ELO_K_BASE = 12.0
ELO_DOUBLES_MULT = 1.0  # full weight — user decision (see above)
ELO_KIND_MULT = {
    "practice_match": 0.5,  # đánh chơi
    "official_match": 1.0,  # đánh độ nhẹ
    "tournament_match": 1.5,  # đánh giải (placeholder until real data exists)
}
ELO_SWEEP_MULT = 1.25  # 3-0 / 2-0 / 4-0: a sweep moves the rating more
ELO_DECIDER_MULT = 0.75  # 3-2 / 2-1 / 4-3: a deciding set moves it less

# The BBTV band the whole project aims at ("Road To E"): E starts at 1201.
RANK_E_FLOOR = 1201

# Tournament placement bonus (user table 2026-07-31): a FLAT add-on applied
# at the end of the deciding match's day, after that day's matches — no K,
# no expected score. "third" = lost the SF (all bronze is shared, there is
# no 3rd-place match); "quarterfinal" = lost the QF, a singles-only tier.
# Replay architecture applies here too: the bonus is a step in the timeline,
# so editing/deleting the deciding match self-corrects on the next read.
TOURNAMENT_BONUS: dict[str, dict[str, int]] = {
    "singles": {"champion": 70, "runner_up": 50, "third": 35, "quarterfinal": 10},
    "doubles": {"champion": 35, "runner_up": 25, "third": 10},
    "team": {"champion": 30, "runner_up": 20, "third": 10},
}

PLACEMENT_LABEL = {
    "champion": "Champion",
    "runner_up": "Runner-up",
    "third": "3rd (lost SF)",
    "quarterfinal": "Quarter-final",
}


def placement_bonus(discipline: str, placement: str | None) -> int:
    """Bonus points a placement earns; 0 = none (unknown key included)."""
    if placement is None:
        return 0
    return TOURNAMENT_BONUS.get(discipline, {}).get(placement, 0)


# The placement is NEVER input — it is derived from the matches entered in
# the grid (user decision 2026-07-31: "dựa vào data tôi nhập của giải trong
# sheet"). Reading the deepest round entered per entry:
#   final won → champion · final lost → runner-up · SF lost → third ·
#   QF lost → quarterfinal · anything shallower → no placement.
# Tournaments are entered AFTER they finish (user 2026-07-31), so winning
# the deepest entered knockout round with no later round = MISSING DATA,
# not an ongoing event → no placement + a derive_warnings() entry.
_ROUND_DEPTH = {"group": 0, "r64": 1, "r32": 2, "r16": 3, "r8": 4, "qf": 5, "sf": 6, "f": 7}
_NEXT_ROUND = {"r64": "r32", "r32": "r16", "r16": "r8", "r8": "qf", "qf": "sf", "sf": "f"}
_ROUND_NAME = {
    "r64": "1/64", "r32": "1/32", "r16": "1/16", "r8": "1/8",
    "qf": "Quarter-final", "sf": "Semi-final", "f": "Final",
}


def _deepest_decided(db: Session) -> dict[int, Match]:
    """entry_id → last DECIDED match (has a result) of the deepest entered
    round, for every entry with linked matches."""
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_entry_id.isnot(None),
            Match.is_nonplaying == False,  # noqa: E712
            Match.my_sets != Match.opp_sets,  # a result exists
        )
        .order_by(Match.date, Match.order_index, Match.id)
        .all()
    )
    by_entry: dict[int, list[Match]] = {}
    for m in matches:
        by_entry.setdefault(m.tournament_entry_id, []).append(m)
    out: dict[int, Match] = {}
    for entry_id, ms in by_entry.items():
        deepest = max(_ROUND_DEPTH.get(m.round or "group", 0) for m in ms)
        out[entry_id] = [
            m for m in ms if _ROUND_DEPTH.get(m.round or "group", 0) == deepest
        ][-1]
    return out


def derive_placements(db: Session) -> dict[int, tuple[str, dt.date]]:
    """entry_id → (placement, date of the deciding match) for every linked
    entry whose entered matches already decide a placement."""
    out: dict[int, tuple[str, dt.date]] = {}
    for entry_id, last in _deepest_decided(db).items():
        deepest = _ROUND_DEPTH.get(last.round or "group", 0)
        won = last.my_sets > last.opp_sets
        if deepest == _ROUND_DEPTH["f"]:
            placement = "champion" if won else "runner_up"
        elif deepest == _ROUND_DEPTH["sf"] and not won:
            placement = "third"
        elif deepest == _ROUND_DEPTH["qf"] and not won:
            placement = "quarterfinal"
        else:
            continue
        out[entry_id] = (placement, last.date)
    return out


def derive_round_reached(db: Session) -> dict[int, tuple[str, bool]]:
    """entry_id → (deepest DECIDED round key, won that match?) for every
    entry with linked matches — the "how far did I get" fact behind the
    Tournament Record section (Profile tab). Matches saved without a round
    count as group stage, same fallback as the placement derivation."""
    return {
        entry_id: (last.round or "group", last.my_sets > last.opp_sets)
        for entry_id, last in _deepest_decided(db).items()
    }


def derive_warnings(db: Session) -> dict[int, str]:
    """entry_id → data-gap warning: the deepest entered knockout round was
    WON but the next round has no decided match. Tournaments are entered
    after the fact, so a won round with nothing after it means the user
    forgot matches — surface it instead of silently paying no bonus."""
    out: dict[int, str] = {}
    for entry_id, last in _deepest_decided(db).items():
        rnd = last.round or "group"
        nxt = _NEXT_ROUND.get(rnd)
        if nxt and last.my_sets > last.opp_sets:
            out[entry_id] = (
                f"Won the {_ROUND_NAME[rnd]} but no {_ROUND_NAME[nxt]} match"
                " entered — matches missing?"
            )
    return out

# The user's own points/anchor — stored in the key-value settings table.
_MY_POINTS_KEY = "my_points"
_MY_POINTS_DEFAULT = 950  # rank G, set 2026-07-25
# User decision 2026-07-26: rating counts from 2026-07-27; older matches never.
_MY_ANCHOR_DATE_KEY = "my_points_date"
_MY_ANCHOR_DATE_DEFAULT = dt.date(2026, 7, 27)

# Handicap → Elo bonus (user ladder 2026-07-26): the RECEIVER's effective
# rating gains the bonus before the normal comparison. The ladder (0-2-0 →
# +50, 2-0-2 → +100, 2-2-2 → +150, 2-3-2 → +200, … 5-5-5 → +600, the
# maximum) reduces to a formula over s = handicap points normalized to a
# 3-set sum: 25×s up to s=6, then 50×s − 150 — so uniform ints (1-1-1 → 75)
# and free-digit patterns ("4-2-0-2-4" → 210) get consistent values too.
HANDICAP_BONUS_MAX_S3 = 15.0  # 5-5-5 is the maximum handicap ratio
# Global calibration knob on the ladder. 0.5 was chosen by the user on
# 2026-07-27 after a production-engine backtest of the 23 pre-anchor
# handicapped matches: results tracked the RAW rating gap (scale 0 fit best,
# log-loss 0.227 vs 0.548 at 1.0), most plausibly a kèo-selection effect —
# people offer chấp exactly when the true gap exceeds the anchors. 0.5 is
# the agreed midpoint between the social ladder and the data; re-run
# scratchpad scale_backtest.py after months of post-anchor data.
HANDICAP_SCALE = 0.5

# Why a match does not move the rating (MatchOut.elo_status; counted = it does).
STATUS_COUNTED = "counted"
SKIP_NONPLAYING = "nonplaying"
SKIP_BEFORE_ANCHOR = "before_anchor"
SKIP_NO_OPPONENT = "no_opponent"
SKIP_NO_RESULT = "no_result"
SKIP_UNRATED = "unrated"


# ------------------------------------------------------------- anchor store


def get_my_points(db: Session) -> int:
    row = db.get(Setting, _MY_POINTS_KEY)
    return int(row.value) if row is not None else _MY_POINTS_DEFAULT


def set_my_points(db: Session, points: int) -> int:
    """Manual edit of "Điểm của tôi" = a NEW ANCHOR from today: the replay
    restarts at (today, points). Matches dated today still count (the anchor
    date is inclusive).

    Saving the UNCHANGED value is a no-op: an accidental re-save must not
    silently move the anchor to today and drop every replayed match."""
    if points == get_my_points(db):
        return points
    row = db.get(Setting, _MY_POINTS_KEY)
    if row is None:
        db.add(Setting(key=_MY_POINTS_KEY, value=str(points)))
    else:
        row.value = str(points)
    date_row = db.get(Setting, _MY_ANCHOR_DATE_KEY)
    today = dt.date.today().isoformat()
    if date_row is None:
        db.add(Setting(key=_MY_ANCHOR_DATE_KEY, value=today))
    else:
        date_row.value = today
    db.commit()
    return points


def get_my_anchor_date(db: Session) -> dt.date:
    row = db.get(Setting, _MY_ANCHOR_DATE_KEY)
    return dt.date.fromisoformat(row.value) if row is not None else _MY_ANCHOR_DATE_DEFAULT


# ------------------------------------------------------------- snapshots


def _current_points(db: Session, player_id: int | None) -> int | None:
    if player_id is None:
        return None
    player = db.get(Player, player_id)
    return player.points if player is not None else None


def snapshot_match_points(
    db: Session,
    match: Match,
    prev_ids: tuple[int | None, int | None, int | None] | None = None,
) -> None:
    """Freeze the involved players' CURRENT points onto the match row.

    User decision 2026-07-26: the rating replay must use the points that were
    in effect when the match was played — raising a player's static points
    later only applies from that moment on. On update pass ``prev_ids`` =
    (opponent_id, opponent2_id, partner_id) as they were BEFORE the edit:
    only a slot whose player changed is re-snapshotted, so editing a score or
    a date never silently refreshes an old snapshot.
    """
    slots = (
        ("opponent_id", "opp_points_snap"),
        ("opponent2_id", "opp2_points_snap"),
        ("partner_id", "partner_points_snap"),
    )
    for i, (id_attr, snap_attr) in enumerate(slots):
        player_id = getattr(match, id_attr)
        if prev_ids is not None and prev_ids[i] == player_id:
            continue  # same player as before — keep the original snapshot
        setattr(match, snap_attr, _current_points(db, player_id))


def _snap_or_current(snap: int | None, player: Player | None) -> int | None:
    """At-match-time snapshot first; current points only as a fallback for
    legacy rows written before snapshots existed."""
    if snap is not None:
        return snap
    return player.points if player is not None else None


# ------------------------------------------------------------- pieces


def _margin_mult(m: Match) -> float:
    if min(m.my_sets, m.opp_sets) == 0:
        return ELO_SWEEP_MULT
    if m.my_sets + m.opp_sets == m.best_of:
        return ELO_DECIDER_MULT
    return 1.0


def handicap_bonus(handicap: int, pattern: str | None) -> float:
    """Elo equivalent of a per-set handicap (always ≥ 0; caller picks the side
    via the sign of `handicap`)."""
    if handicap == 0 and not pattern:
        return 0.0
    if pattern:
        digits = [int(d) for d in pattern.split("-")]
        s3 = 3.0 * sum(digits) / len(digits) if digits else 0.0
    else:
        s3 = 3.0 * abs(handicap)
    s3 = min(s3, HANDICAP_BONUS_MAX_S3)
    base = 25.0 * s3 if s3 <= 6.0 else 50.0 * s3 - 150.0
    return base * HANDICAP_SCALE


def skip_reason(m: Match, anchor_date: dt.date) -> str | None:
    """Why this match does NOT move the rating; None = it counts.

    Single source of truth: the replay uses it to filter, the week view uses
    it to tag matches ("không tính") so the user sees which entries the
    rating ignored (and can fix the actionable ones — name the opponent,
    rate the players)."""
    if m.is_nonplaying:
        return SKIP_NONPLAYING
    if m.date < anchor_date:
        return SKIP_BEFORE_ANCHOR
    if m.opponent_id is None:
        return SKIP_NO_OPPONENT
    if m.my_sets == m.opp_sets:
        return SKIP_NO_RESULT
    if _snap_or_current(m.opp_points_snap, m.opponent) is None:
        return SKIP_UNRATED
    # A missing team member reads as unrated too (same treatment as doubles):
    # doubles needs partner + both opponents, 1v2 both opponents, 2v1 the partner.
    if m.discipline in ("doubles", "two_v_one"):
        if _snap_or_current(m.partner_points_snap, m.partner) is None:
            return SKIP_UNRATED
    if m.discipline in ("doubles", "one_v_two"):
        if _snap_or_current(m.opp2_points_snap, m.opponent2) is None:
            return SKIP_UNRATED
    return None


# ------------------------------------------------------------- replay engine


@dataclass
class ReplayStep:
    # None = a tournament placement bonus, not a match (see `bonus_label`).
    match_id: int | None
    date: dt.date
    delta: float
    rating_after: float
    bonus_label: str | None = None  # "Giải X — Champion" on bonus steps
    bonus_discipline: str | None = None  # entry discipline on bonus steps


# (final rating, one step per counted match or placement bonus) — what
# replay() returns. Callers that need several ELO-dependent builds replay
# once and pass this around.
ReplayResult = tuple[float, list[ReplayStep]]


@dataclass
class _BonusEvent:
    date: dt.date  # deciding match's day — the bonus lands after its matches
    points: int
    label: str
    discipline: str


def _bonus_events(db: Session, anchor_date: dt.date) -> list[_BonusEvent]:
    """Derived placement bonuses since the anchor, oldest first."""
    placements = derive_placements(db)
    if not placements:
        return []
    # Local import: tournament ← tracker at module scope would be a cycle.
    from app.features.tournament.models import Tournament, TournamentEntry

    rows = (
        db.query(TournamentEntry, Tournament)
        .join(Tournament, TournamentEntry.tournament_id == Tournament.id)
        .filter(TournamentEntry.id.in_(placements))
        .order_by(TournamentEntry.id)
        .all()
    )
    events: list[_BonusEvent] = []
    for entry, tour in rows:
        placement, date = placements[entry.id]
        points = placement_bonus(entry.discipline, placement)
        if points == 0 or date < anchor_date:
            continue
        label = f"{tour.name} — {PLACEMENT_LABEL[placement]}"
        events.append(_BonusEvent(date, points, label, entry.discipline))
    events.sort(key=lambda e: e.date)
    return events


def replay(db: Session) -> ReplayResult:
    """Replay every eligible match since the anchor, in play order, plus one
    flat bonus step per tournament placement (at the end of the tournament's
    last day, after that day's matches).

    Returns (final rating, one step per counted match/bonus). Nothing is
    stored — this is the single engine behind the current rating, the
    per-match ±Δ annotations and the daily history curve."""
    rating = float(get_my_points(db))
    anchor_date = get_my_anchor_date(db)
    kind_mult_by_cat = {
        c.id: ELO_KIND_MULT[c.key]
        for c in db.query(Category).filter(Category.key.in_(list(ELO_KIND_MULT))).all()
    }
    matches = (
        db.query(Match)
        .options(
            selectinload(Match.opponent),
            selectinload(Match.opponent2),
            selectinload(Match.partner),
        )
        .filter(
            Match.date >= anchor_date,
            Match.is_nonplaying == False,  # noqa: E712
            Match.discipline.in_(("singles", "doubles", "one_v_two", "two_v_one")),
            Match.opponent_id.isnot(None),
            Match.category_id.in_(list(kind_mult_by_cat)),
        )
        .order_by(Match.date, Match.order_index, Match.id)
        .all()
    )
    bonuses = _bonus_events(db, anchor_date)
    steps: list[ReplayStep] = []

    def flush_bonuses(before: dt.date | None) -> None:
        """Apply pending bonuses dated before `before` (None = all): each
        lands at the END of its own day, i.e. before any later-dated match."""
        nonlocal rating
        while bonuses and (before is None or bonuses[0].date < before):
            b = bonuses.pop(0)
            rating += b.points
            steps.append(
                ReplayStep(
                    None,
                    b.date,
                    float(b.points),
                    rating,
                    bonus_label=b.label,
                    bonus_discipline=b.discipline,
                )
            )

    for m in matches:
        flush_bonuses(before=m.date)
        if skip_reason(m, anchor_date) is not None:
            continue
        opp_points = _snap_or_current(m.opp_points_snap, m.opponent)
        if m.discipline == "doubles":
            partner_points = _snap_or_current(m.partner_points_snap, m.partner)
            opp2_points = _snap_or_current(m.opp2_points_snap, m.opponent2)
            mine = (rating + partner_points) / 2.0
            theirs = (opp_points + opp2_points) / 2.0
            attribution = ELO_DOUBLES_MULT
        elif m.discipline == "one_v_two":
            # I play ALONE vs a pair (user rule 2026-07-27): I stand in as
            # both members of my side, so on the team-average scale my side
            # = my own rating vs the pair's average. The ×2 is comparison
            # only — the delta magnitude stays normal.
            opp2_points = _snap_or_current(m.opp2_points_snap, m.opponent2)
            mine = rating
            theirs = (opp_points + opp2_points) / 2.0
            attribution = 1.0
        elif m.discipline == "two_v_one":
            # Me + partner vs one player who stands in for both opponents
            # (mirror of 1v2). A partner is involved → doubles attribution.
            partner_points = _snap_or_current(m.partner_points_snap, m.partner)
            mine = (rating + partner_points) / 2.0
            theirs = float(opp_points)
            attribution = ELO_DOUBLES_MULT
        else:
            mine, theirs = rating, float(opp_points)
            attribution = 1.0
        # Handicap: the receiving side plays "up" by the FULL ladder bonus —
        # even past the opponent's rating (user decision 2026-07-26: a big
        # chấp CAN make the receiver the favourite; losing from there
        # deserves the big deduction, winning from there earns little).
        # Sign of the stored handicap: +N = I (my team) give, −N = I receive.
        bonus = handicap_bonus(m.handicap, m.handicap_pattern)
        if m.discipline == "doubles":
            # User rule 2026-07-26: in doubles the chấp ELO belongs to ONE
            # member, not both — on the team-AVERAGE scale that is half the
            # ladder value (avoids inflating the receiving pair abnormally).
            bonus /= 2.0
        # 1v2 / 2v1 keep the FULL ladder value ("có điểm chấp thì cũng như
        # công thức bình thường", user 2026-07-27) — the same absolute /400
        # shift as a singles chấp.
        if m.handicap > 0:
            theirs += bonus
        elif m.handicap < 0:
            mine += bonus
        expected = 1.0 / (1.0 + 10 ** ((theirs - mine) / 400.0))
        score = 1.0 if m.my_sets > m.opp_sets else 0.0
        delta = (
            ELO_K_BASE
            * kind_mult_by_cat[m.category_id]
            * attribution
            * _margin_mult(m)
            * (score - expected)
        )
        rating += delta
        steps.append(ReplayStep(m.id, m.date, delta, rating))
    flush_bonuses(before=None)
    return rating, steps


def compute_my_rating(
    db: Session, replay_result: ReplayResult | None = None
) -> schemas.MyRatingOut:
    """Current dynamic rating = anchor points + replay of every eligible match
    since the anchor date. Nothing is stored per match, so editing, deleting
    or backfilling old matches self-corrects on the next read."""
    final, steps = replay_result or replay(db)
    return schemas.MyRatingOut(
        points=get_my_points(db),
        current=round(final),
        anchor_date=get_my_anchor_date(db).isoformat(),
        # Matches only — placement bonus steps are not matches.
        counted_matches=sum(1 for s in steps if s.match_id is not None),
    )
