// The user's dynamic ELO — the big number, the "X to E" chip, the anchor
// edit and the ELO curve over a navigable timeline. Moved here from the
// Database tab (2026-07-27): the Database keeps other players' STATIC
// points; my own rating is a progress-tracking concern, so it lives on the
// Profile.
import { useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { pointsLabel } from "../../../shared/rank";
import { todayIso } from "../../../shared/dates";
import type { Mode, Period } from "../../../shared/period";
import { chartUnitFor, resolveRange, stepAnchor } from "../../../shared/period";
import LineChart from "../../../shared/ui/LineChart";
import PeriodControl from "../../../shared/ui/PeriodControl";
import { profileApi } from "../api";
import type { MyRating, RatingBreakdown } from "../types";

// The whole project's target band: E starts at 1201 BBTV points.
const RANK_E_FLOOR = 1201;

// The curve needs a span to draw a line, so "day" is left out; default Month.
const CURVE_MODES: Mode[] = ["week", "month", "year", "custom"];

// "2026-07-27" → "27/07" for chart labels.
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

// "2026-07-27" → "27/07/2026" for the anchor note.
function fmtAnchor(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

// ELO curve over the selected range, same semantics as the Daily Tracker's
// ELO block: full bucket axis (real time), pre-anchor buckets flat at the
// anchor value, future buckets blank. LineChart scales 0..max, which would
// flatten a curve hovering around ~950 — so values are re-based near the
// observed min and formatY maps gridline values back to real ratings.
function RatingChart({ bd }: { bd: RatingBreakdown }) {
  const today = todayIso();
  const anchorVal: number | null = bd.anchor_points ?? null;
  const valueOf = (b: (typeof bd.buckets)[number]): number | null =>
    b.date_from > today ? null : b.rating_end ?? anchorVal;
  const drawn = bd.buckets.map(valueOf).filter((v): v is number => v !== null);
  if (drawn.length < 2) {
    return (
      <p className="va-muted">
        Not enough data in this range to draw a line — matches count from the
        anchor ({shortDate(bd.anchor_date)}) onward.
      </p>
    );
  }
  const base = Math.min(...drawn) - 20;
  const sign = bd.total_delta > 0 ? "+" : "";
  return (
    <>
      {bd.rating_end !== null && (
        <p className="va-muted">
          net Δ {sign}
          {bd.total_delta.toFixed(1)} · {bd.counted} matches · period end{" "}
          <b>{bd.rating_end}</b>
        </p>
      )}
      <LineChart
        points={bd.buckets.map((b) => {
          const v = valueOf(b);
          return {
            label: shortDate(b.date_from),
            value: v === null ? null : v - base,
            display:
              b.rating_end === null
                ? `${anchorVal} · before anchor`
                : b.counted
                  ? `${b.rating_end} · Δ ${b.delta > 0 ? "+" : ""}${b.delta.toFixed(1)} (${b.counted} matches)`
                  : String(b.rating_end),
            tip:
              b.date_from === b.date_to
                ? b.date_from
                : `${b.date_from} → ${b.date_to}`,
          };
        })}
        formatY={(v) => String(Math.round(v + base))}
      />
    </>
  );
}

export default function MyRatingCard() {
  const { data: myRating, setData: setMyRating, error: loadError } =
    useLoad<MyRating>(() => profileApi.getMyRating(), []);
  // Same timeline model as the Daily Tracker, local to this card. Default:
  // the current month.
  const [period, setPeriod] = useState<Period>(() => ({
    mode: "month",
    anchor: new Date(),
    customFrom: todayIso(),
    customTo: todayIso(),
  }));
  const range = resolveRange(period);
  const unit = chartUnitFor(period.mode, "line", range.fromIso, range.toIso) ?? "day";
  const rangeValid = range.fromIso <= range.toIso;
  const { data: breakdown } = useLoad<RatingBreakdown | null>(
    () =>
      rangeValid
        ? profileApi.ratingBreakdown(range.fromIso, range.toIso, unit)
        : Promise.resolve(null),
    // Refetches when the range moves or the anchor changes (a manual save
    // changes myRating).
    [range.fromIso, range.toIso, unit, myRating?.points, myRating?.anchor_date]
  );
  const { run, error, busy } = useMutate();
  const [myDraft, setMyDraft] = useState<string | null>(null); // null = not editing

  // Saving the unchanged anchor is blocked: a new anchor restarts the ELO
  // replay from today, so an accidental re-save would drop every counted
  // match (the backend guards this too).
  const myDraftDirty =
    myDraft !== null &&
    myDraft.trim() !== "" &&
    Number(myDraft) !== myRating?.points;

  const saveMyRating = async () => {
    const n = Number(myDraft);
    if (!myDraftDirty || Number.isNaN(n) || n < 0 || n > 3000) return;
    const out = await run(() => profileApi.setMyRating(n));
    if (out !== undefined) {
      setMyRating(out);
      setMyDraft(null);
    }
  };

  return (
    <section className="va-card">
      <h3>🎯 My ELO</h3>
      <div className="db-me">
        {myDraft === null ? (
          <>
            <span className="db-me-points">{pointsLabel(myRating?.current)}</span>
            {myRating && myRating.current < RANK_E_FLOOR && (
              <span
                className="db-me-to-e"
                title={`Rank E starts at ${RANK_E_FLOOR} points`}
              >
                {RANK_E_FLOOR - myRating.current} to E
              </span>
            )}
            <button
              className="btn"
              title="Edit the anchor — ELO recalculates from today"
              onClick={() => setMyDraft(String(myRating?.points ?? ""))}
            >
              Edit
            </button>
          </>
        ) : (
          <>
            <input
              type="number"
              min={0}
              max={3000}
              value={myDraft}
              onChange={(e) => setMyDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveMyRating();
              }}
            />
            <button
              className="btn primary"
              disabled={busy || !myDraftDirty}
              title={
                myDraftDirty
                  ? "Set a new anchor from today — ELO recalculates from here"
                  : "Anchor points unchanged"
              }
              onClick={saveMyRating}
            >
              Save
            </button>
            <button className="btn" onClick={() => setMyDraft(null)}>
              Cancel
            </button>
          </>
        )}
        <span className="db-me-note">
          {myRating
            ? `Dynamic ELO · anchored ${myRating.points} since ${fmtAnchor(
                myRating.anchor_date
              )} · ${myRating.counted_matches} matches counted (singles + doubles + 1v2/2v1, handicaps converted)`
            : "the only dynamic rating (ELO)"}
        </span>
      </div>
      {(error || loadError) && <div className="pb-error">⚠ {error ?? loadError}</div>}
      <div className="db-chart">
        <div className="va-card-head">
          <h3>📈 ELO curve</h3>
          <PeriodControl
            mode={period.mode}
            label={range.label}
            customFrom={period.customFrom}
            customTo={period.customTo}
            modes={CURVE_MODES}
            onMode={(m) => setPeriod((p) => ({ ...p, mode: m }))}
            onStep={(dir) =>
              setPeriod((p) => ({
                ...p,
                anchor: stepAnchor(p.mode, p.anchor, dir),
              }))
            }
            onToday={() => setPeriod((p) => ({ ...p, anchor: new Date() }))}
            onCustomFrom={(iso) =>
              setPeriod((p) => ({ ...p, customFrom: iso }))
            }
            onCustomTo={(iso) => setPeriod((p) => ({ ...p, customTo: iso }))}
          />
        </div>
        {!rangeValid ? (
          <p className="va-muted">'From' date is after 'To' date.</p>
        ) : (
          breakdown && <RatingChart bd={breakdown} />
        )}
      </div>
    </section>
  );
}
