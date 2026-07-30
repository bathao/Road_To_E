// One match per line — date, format tag, "with <partner> vs <opponents>",
// result + score, handicap, match kind, event, ±ELO chip. Shared by the
// Analysis drill-down modal and the Database tab's per-player modal so the
// two lists can never drift apart.
import { useMemo } from "react";
import { useLoad } from "../../../shared/useApi";
import { prettyDate } from "../../../shared/dates";
import { DISCIPLINE_SHORT } from "../../../shared/disciplines";
import { resultOf } from "../../../shared/types";
import { trackerApi } from "../api";
import type { Category, Match } from "../types";

// Match-kind wording used across the app (đánh chơi / đánh độ / đánh giải).
const KIND_LABEL: Record<string, string> = {
  practice_match: "casual",
  official_match: "light stakes",
  tournament_match: "tournament",
};

// "with <partner> vs <opponents>" — mirrors the MatchEditor list wording.
// Structurally typed so anything carrying the name slots can use it (Match
// rows here, RatingMover rows in the Match Stats ELO table).
export function matchupOf(m: {
  discipline: string;
  opponent_name?: string | null;
  opponent2_name?: string | null;
  partner_name?: string | null;
}): string {
  const opp1 = m.opponent_name ?? "?";
  const opps =
    m.discipline === "doubles" || m.discipline === "one_v_two"
      ? `${opp1} + ${m.opponent2_name ?? "?"}`
      : opp1;
  const partner =
    m.discipline === "doubles" || m.discipline === "two_v_one"
      ? m.partner_name ?? "?"
      : null;
  return partner ? `with ${partner} vs ${opps}` : `vs ${opps}`;
}

function hdcText(m: Match): string | null {
  if (!m.handicap) return null;
  const amount = m.handicap_pattern ?? String(Math.abs(m.handicap));
  return m.handicap > 0 ? `give ${amount}` : `receive ${amount}`;
}

export default function MatchRowList({ matches }: { matches: Match[] }) {
  const { data: categories } = useLoad<Category[]>(
    () => trackerApi.getCategories(),
    []
  );
  const kindOf = useMemo(() => {
    const byId = new Map<number, string>();
    (categories ?? []).forEach((c) =>
      byId.set(c.id, KIND_LABEL[c.key] ?? c.label)
    );
    return (id: number) => byId.get(id) ?? "";
  }, [categories]);

  return (
    <ul className="smm-list">
      {matches.map((m) => {
        const r = resultOf(m);
        const hdc = hdcText(m);
        return (
          <li key={m.id} className="smm-row">
            <span className="smm-date">{prettyDate(m.date)}</span>
            <span className="smm-tag">
              {DISCIPLINE_SHORT[m.discipline] ?? m.discipline}
            </span>
            <span className="smm-names">{matchupOf(m)}</span>
            <b className={r === "W" ? "win" : r === "L" ? "loss" : ""}>
              {r} {m.my_sets}–{m.opp_sets}
            </b>
            {hdc && <span className="smm-meta">{hdc}</span>}
            <span className="smm-meta">{kindOf(m.category_id)}</span>
            {m.event_name && <span className="smm-meta">{m.event_name}</span>}
            {m.elo_delta != null && (
              <span
                className={`elo-chip ${m.elo_delta >= 0 ? "elo-up" : "elo-down"}`}
                title="ELO change after this match"
              >
                {m.elo_delta > 0 ? "+" : ""}
                {m.elo_delta.toFixed(1)}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
