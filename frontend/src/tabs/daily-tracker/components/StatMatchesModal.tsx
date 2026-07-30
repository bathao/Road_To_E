// Drill-down behind one Analysis stat card: the full list of matches making
// up that card's numbers in the visible range — who was beaten / lost to, on
// which date, at what score. Backed by GET /stats/matches, which shares its
// filter with /stats so the card and the list can never disagree.
import { useState } from "react";
import Modal from "../../../shared/ui/Modal";
import { useLoad } from "../../../shared/useApi";
import { resultOf } from "../../../shared/types";
import { trackerApi } from "../api";
import type { Match } from "../types";
import MatchRowList from "./MatchRowList";

export type StatBucket =
  | "overall"
  | "singles"
  | "doubles"
  | "one_v_two"
  | "two_v_one"
  | "vs_pips";
export type ResultFilter = "all" | "W" | "L";

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

      <MatchRowList matches={shown} />
    </Modal>
  );
}
