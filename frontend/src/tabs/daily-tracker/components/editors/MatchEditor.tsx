import { useEffect, useState } from "react";
import type { Category, Discipline, Match, MatchIn } from "../../types";
import { trackerApi } from "../../api";
import { validScores } from "../../scores";

const FORMATS = [3, 5, 7];

function matchLabel(m: Match): string {
  if (m.is_nonplaying) return m.nonplaying_label ?? "—";
  const disc = m.discipline === "doubles" ? "Doubles" : "Singles";
  const res = m.my_sets > m.opp_sets ? "W" : m.my_sets < m.opp_sets ? "L" : "T";
  return `${disc} ${res} ${m.my_sets}-${m.opp_sets}`;
}

// Dropdown-driven match entry — no manual score typing. Pick discipline +
// format, then tap a final score. Plus event autocomplete and Travel/Rest.
export default function MatchEditor({
  category,
  matches,
  onAdd,
  onDelete,
}: {
  category: Category;
  matches: Match[];
  onAdd: (payload: Omit<MatchIn, "date" | "category_id">) => void;
  onDelete: (id: number) => void;
}) {
  const [discipline, setDiscipline] = useState<Discipline>("singles");
  const [bestOf, setBestOf] = useState(5);
  const [eventName, setEventName] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);

  // Event autocomplete (debounced).
  useEffect(() => {
    const q = eventName.trim();
    if (!q) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const events = await trackerApi.searchEvents(q);
        setSuggestions(events.map((e) => e.name).filter((n) => n !== q));
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [eventName]);

  const { wins, losses } = validScores(bestOf);

  const addScore = (my: number, opp: number) => {
    onAdd({
      discipline,
      best_of: bestOf,
      my_sets: my,
      opp_sets: opp,
      event_name: eventName.trim() || null,
    });
  };

  const addNonPlaying = (label: string) => {
    onAdd({ is_nonplaying: true, nonplaying_label: label });
  };

  return (
    <div className="editor">
      <p className="editor-sub">{category.label}</p>

      {/* Existing matches in this cell */}
      {matches.length > 0 && (
        <div className="match-list">
          {matches.map((m) => (
            <div key={m.id} className="match-item">
              <span>
                {matchLabel(m)}
                {m.event_name ? ` · ${m.event_name}` : ""}
              </span>
              <button
                className="icon-btn danger"
                onClick={() => onDelete(m.id)}
                aria-label="Delete match"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Discipline toggle */}
      <div className="seg-row">
        <span className="seg-label">Discipline</span>
        <div className="seg">
          {(["singles", "doubles"] as Discipline[]).map((d) => (
            <button
              key={d}
              className={`seg-btn${discipline === d ? " active" : ""}`}
              onClick={() => setDiscipline(d)}
            >
              {d === "singles" ? "Singles" : "Doubles"}
            </button>
          ))}
        </div>
      </div>

      {/* Format selector */}
      <div className="seg-row">
        <span className="seg-label">Format</span>
        <div className="seg">
          {FORMATS.map((f) => (
            <button
              key={f}
              className={`seg-btn${bestOf === f ? " active" : ""}`}
              onClick={() => setBestOf(f)}
            >
              BO{f}
            </button>
          ))}
        </div>
      </div>

      {/* Event autocomplete */}
      <div className="note-row">
        <label>Event (optional)</label>
        <input
          type="text"
          value={eventName}
          onChange={(e) => setEventName(e.target.value)}
          placeholder="e.g. BBTV Open"
          list="event-suggestions"
        />
        <datalist id="event-suggestions">
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>

      {/* Score picker */}
      <div className="score-picker">
        <div className="score-col">
          <span className="score-head win">Win</span>
          <div className="score-btns">
            {wins.map((s) => (
              <button
                key={`w${s.my}-${s.opp}`}
                className="score-btn win"
                onClick={() => addScore(s.my, s.opp)}
              >
                {s.my}-{s.opp}
              </button>
            ))}
          </div>
        </div>
        <div className="score-col">
          <span className="score-head loss">Loss</span>
          <div className="score-btns">
            {losses.map((s) => (
              <button
                key={`l${s.my}-${s.opp}`}
                className="score-btn loss"
                onClick={() => addScore(s.my, s.opp)}
              >
                {s.my}-{s.opp}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Non-playing quick buttons */}
      <div className="quick-row">
        <button className="btn" onClick={() => addNonPlaying("Travel")}>
          ✈️ Travel
        </button>
        <button className="btn" onClick={() => addNonPlaying("Rest")}>
          😴 Rest
        </button>
      </div>
    </div>
  );
}
