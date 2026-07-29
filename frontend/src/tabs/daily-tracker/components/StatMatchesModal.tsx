// Drill-down behind one Analysis stat card: the full list of matches making
// up that card's numbers in the visible range — who was beaten / lost to, on
// which date, at what score. Backed by GET /stats/matches, which shares its
// filter with /stats so the card and the list can never disagree.
import { useMemo, useState } from "react";
import Modal from "../../../shared/ui/Modal";
import { useLoad } from "../../../shared/useApi";
import { prettyDate } from "../../../shared/dates";
import { DISCIPLINE_SHORT } from "../../../shared/disciplines";
import { resultOf } from "../../../shared/types";
import { trackerApi } from "../api";
import type { Category, Match } from "../types";

export type StatBucket =
  | "overall"
  | "singles"
  | "doubles"
  | "one_v_two"
  | "two_v_one"
  | "vs_pips";
export type ResultFilter = "all" | "W" | "L";

// Match-kind wording used across the app (đánh chơi / đánh độ / đánh giải).
const KIND_LABEL: Record<string, string> = {
  practice_match: "casual",
  official_match: "light stakes",
  tournament_match: "tournament",
};

// "with <partner> vs <opponents>" — mirrors the MatchEditor list wording.
function namesOf(m: Match): string {
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

export default function StatMatchesModal({
  bucket,
  title,
  rangeLabel,
  fromIso,
  toIso,
  initialResult,
  onClose,
}: {
  bucket: StatBucket;
  title: string; // card title, e.g. "vs Pips"
  rangeLabel: string; // shared-timeline label, e.g. "Jul 2026"
  fromIso: string;
  toIso: string;
  initialResult: ResultFilter; // preset when the W / L count was clicked
  onClose: () => void;
}) {
  const [result, setResult] = useState<ResultFilter>(initialResult);
  const { data: matches, error, loading } = useLoad<Match[]>(
    () => trackerApi.statsMatches(fromIso, toIso, bucket),
    [fromIso, toIso, bucket]
  );
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

  const all = matches ?? [];
  const wins = all.filter((m) => resultOf(m) === "W");
  const losses = all.filter((m) => resultOf(m) === "L");
  const shown = result === "all" ? all : result === "W" ? wins : losses;

  return (
    <Modal title={`${title} · ${rangeLabel}`} onClose={onClose}>
      <div className="seg smm-filter">
        <button
          className={`seg-btn${result === "all" ? " active" : ""}`}
          onClick={() => setResult("all")}
        >
          All ({all.length})
        </button>
        <button
          className={`seg-btn${result === "W" ? " active" : ""}`}
          onClick={() => setResult("W")}
        >
          {wins.length}W
        </button>
        <button
          className={`seg-btn${result === "L" ? " active" : ""}`}
          onClick={() => setResult("L")}
        >
          {losses.length}L
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}
      {loading && !matches && <p className="smm-empty">Loading…</p>}
      {matches && shown.length === 0 && (
        <p className="smm-empty">No matches here.</p>
      )}

      <ul className="smm-list">
        {shown.map((m) => {
          const r = resultOf(m);
          const hdc = hdcText(m);
          return (
            <li key={m.id} className="smm-row">
              <span className="smm-date">{prettyDate(m.date)}</span>
              <span className="smm-tag">
                {DISCIPLINE_SHORT[m.discipline] ?? m.discipline}
              </span>
              <span className="smm-names">{namesOf(m)}</span>
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
    </Modal>
  );
}
