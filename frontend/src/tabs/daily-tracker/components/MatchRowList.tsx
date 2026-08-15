// One match per line — date, format tag, "with <partner> vs <opponents>",
// result + score, handicap, match kind, event, ±ELO chip. Sole consumer is
// the Database tab's per-player modal (its other user, the Analysis
// drill-down modal, was removed 2026-08-02 with the win-rate cards).
import { useMemo } from "react";
import { useLoad } from "../../../shared/useApi";
import { prettyDate } from "../../../shared/dates";
import { DISCIPLINE_SHORT } from "../../../shared/disciplines";
import EloDeltaChip from "../../../shared/ui/EloDeltaChip";
import { hdcLabel, matchupOf, ROUND_SHORT } from "../../../shared/matches";
import { resultOf } from "../../../shared/types";
import { trackerApi } from "../api";
import type { Category, Match } from "../types";

// Match-kind wording used across the app (đánh chơi / đánh độ / đánh giải).
const KIND_LABEL: Record<string, string> = {
  practice_match: "casual",
  official_match: "light stakes",
  tournament_match: "tournament",
};

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
        const hdc = hdcLabel(m.handicap, m.handicap_pattern);
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
            {m.round && ROUND_SHORT[m.round] && (
              <span className="smm-tag smm-round">{ROUND_SHORT[m.round]}</span>
            )}
            <span className="smm-meta">{kindOf(m.category_id)}</span>
            {m.event_name && <span className="smm-meta">{m.event_name}</span>}
            {m.elo_delta != null && (
              <EloDeltaChip
                delta={m.elo_delta}
                title="ELO change after this match"
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
