"""Match log: point-by-point charting of hand-picked singles matches and the
shot statistics derived from it (2026-10-10).

The user logs a few matches they want analysed in depth — every rally as a
chain of shots (serve → stroke → stroke …, each with a landing spot on the
receiver's side) and how the point ended. Everything the coach later reads
is DERIVED here from those rows, never typed as prose:

- who won each point (the last hitter on a clean winner, the other player on
  an error) → set scores, serve/receive split, clutch points;
- my attacking strokes by landing spot: won / lost / missed;
- errors per stroke (unforced / forced) for both players, clean winners;
- how each serve (mine by repertoire row, the opponent's by attributes)
  performs, and how my receive of each stroke fares;
- rally-length split.
"""
from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.features.tactics import schemas
from app.features.tactics.models import TacticPoint, TacticServe, TacticSet
from app.features.tracker.models import Match

ATTACK_STROKES = {"fhloop", "bhloop", "fhdrive", "bhdrive", "smash", "flick"}
_SERVE_ATTRS = ("stance", "motion", "spin", "amount", "length")


# ------------------------------------------------------------- my repertoire
def list_serves(db: Session) -> list[TacticServe]:
    return db.query(TacticServe).order_by(TacticServe.sort_order, TacticServe.id).all()


def add_serve(db: Session, payload: schemas.ServeIn) -> TacticServe:
    last = db.query(func.max(TacticServe.sort_order)).scalar() or 0
    row = TacticServe(**payload.model_dump(), sort_order=last + 1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_serve(db: Session, serve_id: int, payload: schemas.ServeIn) -> TacticServe:
    row = db.get(TacticServe, serve_id)
    if row is None:
        raise LookupError("serve")
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_serve(db: Session, serve_id: int) -> None:
    """Points keep a copy of the serve's attributes (and the id for the
    label), so deleting a repertoire row never touches logged history."""
    row = db.get(TacticServe, serve_id)
    if row is not None:
        db.delete(row)
        db.commit()


# ----------------------------------------------------------------- the match
def _singles_match(db: Session, match_id: int) -> Match:
    m = db.get(Match, match_id)
    if m is None or m.is_nonplaying or m.discipline != "singles" or m.opponent_id is None:
        raise LookupError("match")
    return m


def _winner_of(server: str, shots: list[schemas.ShotIn], end_kind: str) -> str:
    last = shots[-1].h
    return last if end_kind == "winner" else ("opp" if last == "me" else "me")


def _validate_point(payload: schemas.PointIn) -> None:
    shots = payload.shots
    if not shots[0].serve or shots[0].h != payload.server:
        raise ValueError("The first shot must be the server's serve.")
    if shots[0].spin is None or shots[0].length is None:
        raise ValueError("A serve needs at least spin and length.")
    for i, sh in enumerate(shots):
        # A landing spot is required unless the shot missed (the last shot
        # of an error point).
        missed = i == len(shots) - 1 and payload.end_kind == "error"
        if sh.place is None and not missed:
            raise ValueError("Every shot that stayed in play needs a landing spot.")
    for i, sh in enumerate(shots):
        if i > 0:
            if sh.serve:
                raise ValueError("Only the first shot of a point is a serve.")
            if sh.stroke is None:
                raise ValueError("Every shot after the serve needs a stroke.")
            if sh.h == shots[i - 1].h:
                raise ValueError("Hitters must alternate.")


def _point_out(row: TacticPoint) -> schemas.PointOut:
    return schemas.PointOut(
        id=row.id,
        match_id=row.match_id,
        set_no=row.set_no,
        point_no=row.point_no,
        server=row.server,
        winner=row.winner,
        end_kind=row.end_kind,
        forced=bool(row.forced),
        note=row.note,
        shots=[schemas.ShotIn.model_validate(s) for s in json.loads(row.shots_json or "[]")],
    )


def _points_of(db: Session, match_id: int) -> list[TacticPoint]:
    return (
        db.query(TacticPoint)
        .filter(TacticPoint.match_id == match_id)
        .order_by(TacticPoint.set_no, TacticPoint.point_no, TacticPoint.id)
        .all()
    )


def _points_vs(db: Session, player_id: int) -> list[tuple[TacticPoint, Match]]:
    """Every charted point against this opponent (all matches), in play order."""
    return (
        db.query(TacticPoint, Match)
        .filter(
            TacticPoint.match_id == Match.id,
            Match.opponent_id == player_id,
            Match.discipline == "singles",
        )
        .order_by(Match.date, Match.order_index, Match.id, TacticPoint.set_no, TacticPoint.point_no)
        .all()
    )


def opp_serves_seen(points: list[TacticPoint]) -> list[schemas.OppServeSeen]:
    """Distinct serves the opponent has shown, most frequent first — the
    charter's one-tap chips for the opponent's serve."""
    seen: dict[tuple, schemas.OppServeSeen] = {}
    for p in points:
        if p.server != "opp":
            continue
        shots = json.loads(p.shots_json or "[]")
        if not shots:
            continue
        s = shots[0]
        key = tuple(s.get(a) for a in _SERVE_ATTRS)
        row = seen.get(key)
        if row is None:
            row = seen[key] = schemas.OppServeSeen(**{a: s.get(a) for a in _SERVE_ATTRS})
        row.count += 1
    return sorted(seen.values(), key=lambda r: -r.count)


def get_matchlog(db: Session, match_id: int) -> schemas.MatchLogOut:
    m = _singles_match(db, match_id)
    sets = (
        db.query(TacticSet)
        .filter(TacticSet.match_id == match_id)
        .order_by(TacticSet.set_no)
        .all()
    )
    points = _points_of(db, match_id)
    vs = [p for p, _m in _points_vs(db, m.opponent_id)]
    return schemas.MatchLogOut(
        match_id=match_id,
        sets=[schemas.SetOut.model_validate(s) for s in sets],
        points=[_point_out(p) for p in points],
        opp_serves_seen=opp_serves_seen(vs),
    )


def put_sets(db: Session, match_id: int, payload: schemas.SetsIn) -> list[schemas.SetOut]:
    """Replace the typed set scores of a match (one row per set_no)."""
    _singles_match(db, match_id)
    db.query(TacticSet).filter(TacticSet.match_id == match_id).delete()
    out: list[TacticSet] = []
    for s in payload.sets:
        row = TacticSet(match_id=match_id, **s.model_dump())
        db.add(row)
        out.append(row)
    db.commit()
    return [schemas.SetOut.model_validate(r) for r in out]


def add_point(db: Session, match_id: int, payload: schemas.PointIn) -> schemas.PointOut:
    _singles_match(db, match_id)
    _validate_point(payload)
    last = (
        db.query(func.max(TacticPoint.point_no))
        .filter(TacticPoint.match_id == match_id, TacticPoint.set_no == payload.set_no)
        .scalar()
        or 0
    )
    row = TacticPoint(
        match_id=match_id,
        set_no=payload.set_no,
        point_no=last + 1,
        server=payload.server,
        winner=_winner_of(payload.server, payload.shots, payload.end_kind),
        end_kind=payload.end_kind,
        forced=bool(payload.forced and payload.end_kind == "error"),
        note=(payload.note or "").strip() or None,
        shots_json=json.dumps(
            [s.model_dump(exclude_none=True) for s in payload.shots], ensure_ascii=False
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _point_out(row)


def update_point_note(db: Session, point_id: int, payload: schemas.PointNoteIn) -> schemas.PointOut:
    row = db.get(TacticPoint, point_id)
    if row is None:
        raise LookupError("point")
    row.note = (payload.note or "").strip() or None
    db.commit()
    db.refresh(row)
    return _point_out(row)


def delete_point(db: Session, point_id: int) -> None:
    """Delete one point and close the gap in its set's numbering."""
    row = db.get(TacticPoint, point_id)
    if row is None:
        return
    match_id, set_no, point_no = row.match_id, row.set_no, row.point_no
    db.delete(row)
    db.flush()
    later = (
        db.query(TacticPoint)
        .filter(
            TacticPoint.match_id == match_id,
            TacticPoint.set_no == set_no,
            TacticPoint.point_no > point_no,
        )
        .all()
    )
    for p in later:
        p.point_no -= 1
    db.commit()


def status_for_player(db: Session, player_id: int) -> list[schemas.MatchLogStatus]:
    """Per match vs this opponent: how many points are charted and how many
    set scores were typed — the match list's status chips."""
    pts = dict(
        db.query(TacticPoint.match_id, func.count(TacticPoint.id))
        .join(Match, Match.id == TacticPoint.match_id)
        .filter(Match.opponent_id == player_id)
        .group_by(TacticPoint.match_id)
        .all()
    )
    sets = dict(
        db.query(TacticSet.match_id, func.count(TacticSet.id))
        .join(Match, Match.id == TacticSet.match_id)
        .filter(
            Match.opponent_id == player_id,
            (TacticSet.my_points.isnot(None)) | (TacticSet.opp_points.isnot(None)),
        )
        .group_by(TacticSet.match_id)
        .all()
    )
    ids = sorted(set(pts) | set(sets))
    return [
        schemas.MatchLogStatus(match_id=i, points=pts.get(i, 0), sets_typed=sets.get(i, 0))
        for i in ids
    ]


# ------------------------------------------------------------------- stats
def compute_stats(rows: list[tuple[TacticPoint, Match | None]]) -> schemas.StatsOut:
    """Aggregate charted points into the StatsOut shape. `rows` is in play
    order so running set scores (clutch detection) can be rebuilt."""
    out = schemas.StatsOut()
    out.matches = len({p.match_id for p, _ in rows})
    out.points = len(rows)
    serves: dict[tuple, schemas.ServeStat] = {}
    running: dict[tuple[int, int], list[int]] = {}  # (match, set) → [me, opp]

    for p, m in rows:
        shots = json.loads(p.shots_json or "[]")
        if not shots:
            continue
        win_me = p.winner == "me"
        n = len(shots)
        key = (p.match_id, p.set_no)
        sc = running.setdefault(key, [0, 0])
        if sc[0] >= 8 and sc[1] >= 8:
            out.clutch[0 if win_me else 1] += 1
        if p.note:
            out.notes.append(
                schemas.PointNoteOut(
                    match_id=p.match_id,
                    date=m.date if m is not None else None,
                    set_no=p.set_no,
                    point_no=p.point_no,
                    score=f"{sc[0]}–{sc[1]}",
                    note=p.note,
                )
            )
        sc[0 if win_me else 1] += 1
        if win_me:
            out.points_me += 1
        else:
            out.points_opp += 1

        tgt = out.on_my_serve if p.server == "me" else out.on_opp_serve
        tgt[0] += 1
        if win_me:
            tgt[1] += 1

        bucket = "1-2" if n <= 2 else "3-4" if n <= 4 else "5+"
        out.rally_len.setdefault(bucket, [0, 0])[0 if win_me else 1] += 1

        for i, sh in enumerate(shots):
            is_last = i == n - 1
            hitter = sh.get("h")
            if i == 0:
                skey = (hitter, sh.get("serve_id")) + tuple(sh.get(a) for a in _SERVE_ATTRS) + (sh.get("place"),)
                st = serves.get(skey)
                if st is None:
                    st = serves[skey] = schemas.ServeStat(
                        side=hitter,
                        serve_id=sh.get("serve_id"),
                        place=sh.get("place"),
                        **{a: sh.get(a) for a in _SERVE_ATTRS},
                    )
                st.played += 1
                if p.winner == hitter:
                    st.won += 1
                continue
            stroke = sh.get("stroke")
            if stroke is None:
                continue
            place = sh.get("place") or "-"
            missed = is_last and p.end_kind == "error"
            if hitter == "me" and stroke in ATTACK_STROKES:
                cell = out.attacks.setdefault(stroke, {}).setdefault(place, [0, 0, 0])
                cell[2 if missed else (0 if win_me else 1)] += 1
            if i == 1:  # the receive of the serve
                tgt_r = out.receive_me if hitter == "me" else out.receive_opp
                won = p.winner == hitter
                tgt_r.setdefault(stroke, [0, 0, 0])[2 if missed else (0 if won else 1)] += 1
            if is_last:
                if p.end_kind == "error":
                    tgt_err = out.errors_me if hitter == "me" else out.errors_opp
                    tgt_err.setdefault(stroke, [0, 0])[1 if p.forced else 0] += 1
                else:
                    tgt_w = out.winners_me if hitter == "me" else out.winners_opp
                    tgt_w[stroke] = tgt_w.get(stroke, 0) + 1

    for b in ("1-2", "3-4", "5+"):
        out.rally_len.setdefault(b, [0, 0])
    out.serves = sorted(serves.values(), key=lambda s: (s.side != "me", -s.played))
    return out


def match_stats(db: Session, match_id: int) -> schemas.StatsOut:
    m = _singles_match(db, match_id)
    return compute_stats([(p, m) for p in _points_of(db, match_id)])


def player_stats(db: Session, player_id: int) -> schemas.StatsOut:
    """Every charted match against this opponent, folded together."""
    return compute_stats(_points_vs(db, player_id))


# ------------------------------------------------------- coach prompt block
# Vietnamese labels for the prompt (the GUI's vocab.ts is the other copy).
_STROKE_VI = {
    "fhloop": "giật phải", "bhloop": "giật trái", "fhdrive": "bạt phải",
    "bhdrive": "bạt trái", "fhpush": "gò phải", "bhpush": "gò trái",
    "flick": "hất", "block": "chặn", "smash": "đập", "chop": "thủ/lốp",
    "other": "đỡ/cú khác",
}
_PLACE_VI = {"R": "qua phải", "M": "vào giữa", "L": "qua trái", "-": "(hỏng, không rõ hướng)"}
_SPIN_VI = {"back": "xoáy xuống", "side": "xoáy ngang", "sideback": "ngang-xuống",
            "top": "xoáy lên", "none": "lỏng"}
_LEN_VI = {"short": "ngắn", "half": "nửa bàn", "long": "dài"}
_STANCE_VI = {"right": "đứng lệch phải", "center": "đứng giữa bàn", "left": "đứng lệch trái"}
_MOTION_VI = {"pend": "thuận tay", "rev": "ngược", "bh": "trái tay", "toma": "búa", "other": "khác"}
_AMT_VI = {"light": "nhẹ", "med": "vừa", "heavy": "nặng"}


def _serve_vi(s: schemas.ServeStat, serve_names: dict[int, str]) -> str:
    if s.serve_id is not None and s.serve_id in serve_names:
        base = serve_names[s.serve_id]
    else:
        base = " ".join(x for x in (
            _STANCE_VI.get(s.stance or "", ""), _MOTION_VI.get(s.motion or "", ""),
            _SPIN_VI.get(s.spin or "", ""), _AMT_VI.get(s.amount or "", ""),
            _LEN_VI.get(s.length or "", ""),
        ) if x) or "giao bóng"
    return f"{base} {_PLACE_VI.get(s.place or '-', '')}".strip()


def stats_block(stats: schemas.StatsOut, serve_names: dict[int, str], opp_name: str) -> str:
    """The match-log numbers as Vietnamese prompt lines (empty string when
    nothing is charted). Facts only — the coach prompt decides what to do
    with them (the user will tune that prompt themselves)."""
    if not stats.points:
        return ""
    me, opp = "Học trò", opp_name
    out = [
        f"Số trận đã ghi từng điểm: {stats.matches} — tổng {stats.points} điểm "
        f"({me} {stats.points_me} / {opp} {stats.points_opp}).",
        f"Điểm thắng khi học trò giao: {stats.on_my_serve[1]}/{stats.on_my_serve[0]}; "
        f"khi {opp} giao: {stats.on_opp_serve[1]}/{stats.on_opp_serve[0]}.",
        f"Điểm từ 8-8 trở đi: {me} {stats.clutch[0]} / {opp} {stats.clutch[1]}.",
        "Độ dài rally (điểm học trò/đối thủ): " + "; ".join(
            f"{k} cú {v[0]}/{v[1]}" for k, v in stats.rally_len.items()
        ) + ".",
    ]
    if stats.attacks:
        out.append("Cú tấn công của học trò (ăn/thua/hỏng theo hướng):")
        for stroke, by_place in stats.attacks.items():
            cells = ", ".join(
                f"{_PLACE_VI.get(pl, pl)} {v[0]}/{v[1]}/{v[2]}" for pl, v in by_place.items()
            )
            out.append(f"  - {_STROKE_VI.get(stroke, stroke)}: {cells}")
    for label, errs in (("học trò", stats.errors_me), (opp, stats.errors_opp)):
        if errs:
            out.append(f"Lỗi của {label} (tự hỏng/bị ép): " + ", ".join(
                f"{_STROKE_VI.get(k, k)} {v[0]}/{v[1]}" for k, v in errs.items()
            ) + ".")
    for label, wins in (("học trò", stats.winners_me), (opp, stats.winners_opp)):
        if wins:
            out.append(f"Cú ăn điểm trực tiếp của {label}: " + ", ".join(
                f"{_STROKE_VI.get(k, k)} {v}" for k, v in wins.items()
            ) + ".")
    for label, rec in (("học trò", stats.receive_me), (opp, stats.receive_opp)):
        if rec:
            out.append(f"Đỡ giao bóng của {label} (thắng/thua/đỡ hư): " + ", ".join(
                f"{_STROKE_VI.get(k, k)} {v[0]}/{v[1]}/{v[2]}" for k, v in rec.items()
            ) + ".")
    mine = [s for s in stats.serves if s.side == "me"]
    theirs = [s for s in stats.serves if s.side == "opp"]
    if mine:
        out.append("Giao bóng của học trò (điểm thắng/đã giao): " + "; ".join(
            f"{_serve_vi(s, serve_names)} {s.won}/{s.played}" for s in mine
        ) + ".")
    if theirs:
        out.append(f"Giao bóng của {opp} (điểm {opp} thắng/đã giao): " + "; ".join(
            f"{_serve_vi(s, serve_names)} {s.won}/{s.played}" for s in theirs
        ) + ".")
    if stats.notes:
        out.append("Ghi chú của học trò theo điểm:")
        for n in stats.notes[-20:]:
            out.append(f"  - [{n.date or '?'} set {n.set_no} tỉ số {n.score}] {n.note}")
    return "\n".join(out)


def stats_block_for(db: Session, player_id: int, opp_name: str) -> str:
    names = {s.id: s.name for s in list_serves(db)}
    return stats_block(player_stats(db, player_id), names, opp_name)
