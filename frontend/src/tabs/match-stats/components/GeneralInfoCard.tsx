// Profile header: avatar + name + the CURRENT dynamic ELO with the "X to E"
// chip. Rangeless — always "now"; the ranged curve lives in the ELO card
// below. The anchor is FIXED (user decision 2026-07-30): the rating only
// moves through played matches, so there is no edit UI — a new anchor would
// need a deliberate API call (PUT /tracker/my-rating still exists).
import { useLoad } from "../../../shared/useApi";
import { pointsLabel } from "../../../shared/rank";
import { dmyDate } from "../../../shared/dates";
import { matchStatsApi } from "../api";
import type { MyRating } from "../types";

// The whole project's target band: E starts at 1201 BBTV points.
const RANK_E_FLOOR = 1201;

export default function GeneralInfoCard() {
  const { data: myRating, error } = useLoad<MyRating>(
    () => matchStatsApi.getMyRating(),
    []
  );
  const { data: lastDate } = useLoad(() => matchStatsApi.lastDate(), []);

  return (
    <section className="stats-card prof-header">
      <img className="prof-avatar" src="/avatar.jpg" alt="Nguyễn Bá Thảo" />
      <div className="prof-header-main">
        <h2 className="prof-name">Nguyễn Bá Thảo</h2>
        <div className="db-me">
          <span className="db-me-points">{pointsLabel(myRating?.current)}</span>
          {myRating && myRating.current < RANK_E_FLOOR && (
            <span
              className="db-me-to-e"
              title={`Rank E starts at ${RANK_E_FLOOR} points`}
            >
              {RANK_E_FLOOR - myRating.current} to E
            </span>
          )}
        </div>
        <span className="db-me-note">
          {myRating
            ? `Dynamic ELO · anchored ${myRating.points} since ${dmyDate(
                myRating.anchor_date
              )} · ${myRating.counted_matches} matches counted (singles + doubles + 1v2/2v1, handicaps converted)`
            : "the only dynamic rating (ELO)"}
        </span>
        {lastDate?.date && (
          <p className="va-muted prof-asof">Data as of {lastDate.date}</p>
        )}
        {error && <div className="pb-error">⚠ {error}</div>}
      </div>
    </section>
  );
}
