import { useEffect, useState } from "react";
import type { Category, Discipline, Match, MatchIn, Player } from "../../types";
import { trackerApi } from "../../api";
import { validScores } from "../../scores";
import PlayerPicker, { levelShort } from "./PlayerPicker";

const FORMATS = [3, 5, 7];
type HandicapDir = "none" | "give" | "receive";

function resultLetter(m: Match): string {
  return m.my_sets > m.opp_sets ? "W" : m.my_sets < m.opp_sets ? "L" : "T";
}

// "vs Nam (Ngang)" for singles, "+ Partner vs A, B" for doubles, plus handicap.
function playersLabel(m: Match): string {
  if (m.is_nonplaying) return "";
  const parts: string[] = [];
  if (m.discipline === "doubles") {
    if (m.partner_name) parts.push(`+${m.partner_name}`);
    const opps = [
      m.opponent_name && `${m.opponent_name}${m.opponent_plays_pips ? " 🏓" : ""}`,
      m.opponent2_name &&
        `${m.opponent2_name}${m.opponent2_plays_pips ? " 🏓" : ""}`,
    ].filter(Boolean);
    if (opps.length) parts.push(`vs ${opps.join(" & ")}`);
  } else if (m.opponent_name) {
    const gai = m.opponent_plays_pips ? " 🏓gai" : "";
    parts.push(`vs ${m.opponent_name} (${levelShort(m.opponent_level)})${gai}`);
  }
  if (m.handicap > 0) parts.push(`chấp ${m.handicap}`);
  else if (m.handicap < 0) parts.push(`được chấp ${-m.handicap}`);
  return parts.join(" ");
}

// Dropdown-driven match entry. Pick discipline + format + the player(s) + an
// optional handicap, then tap a final score. Plus event autocomplete & Travel/Rest.
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

  const [opponent, setOpponent] = useState<Player | null>(null);
  const [opponent2, setOpponent2] = useState<Player | null>(null);
  const [partner, setPartner] = useState<Player | null>(null);

  const [handicapDir, setHandicapDir] = useState<HandicapDir>("none");
  const [handicapPoints, setHandicapPoints] = useState(2);

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

  const handicap =
    handicapDir === "give"
      ? handicapPoints
      : handicapDir === "receive"
      ? -handicapPoints
      : 0;

  const addScore = (my: number, opp: number) => {
    onAdd({
      discipline,
      best_of: bestOf,
      my_sets: my,
      opp_sets: opp,
      event_name: eventName.trim() || null,
      opponent_id: opponent?.id ?? null,
      opponent2_id: discipline === "doubles" ? opponent2?.id ?? null : null,
      partner_id: discipline === "doubles" ? partner?.id ?? null : null,
      handicap,
    });
    // Clear the opponent(s) so the next person can be picked right away.
    // Partner + handicap + format are kept (usually the same across a session).
    setOpponent(null);
    setOpponent2(null);
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
                {m.is_nonplaying
                  ? m.nonplaying_label ?? "—"
                  : `${m.discipline === "doubles" ? "D" : "S"} ${resultLetter(m)} ${m.my_sets}-${m.opp_sets}`}
                {playersLabel(m) ? ` · ${playersLabel(m)}` : ""}
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

      {/* Players */}
      {discipline === "doubles" && (
        <PlayerPicker label="Partner" value={partner} onChange={setPartner} />
      )}
      <PlayerPicker
        label={discipline === "doubles" ? "Đối thủ 1" : "Đối thủ"}
        value={opponent}
        onChange={setOpponent}
        pipsEditable
      />
      {discipline === "doubles" && (
        <PlayerPicker
          label="Đối thủ 2"
          value={opponent2}
          onChange={setOpponent2}
          pipsEditable
        />
      )}

      {/* Handicap (optional) */}
      <div className="seg-row handicap-row">
        <span className="seg-label">Chấp</span>
        <div className="seg">
          {(
            [
              ["none", "Không"],
              ["give", "Tôi chấp"],
              ["receive", "Được chấp"],
            ] as [HandicapDir, string][]
          ).map(([dir, lbl]) => (
            <button
              key={dir}
              className={`seg-btn${handicapDir === dir ? " active" : ""}`}
              onClick={() => setHandicapDir(dir)}
            >
              {lbl}
            </button>
          ))}
        </div>
        {handicapDir !== "none" && (
          <div className="handicap-stepper">
            <button
              className="icon-btn"
              onClick={() => setHandicapPoints((n) => Math.max(1, n - 1))}
            >
              −
            </button>
            <span className="handicap-num">{handicapPoints}</span>
            <button
              className="icon-btn"
              onClick={() => setHandicapPoints((n) => Math.min(20, n + 1))}
            >
              +
            </button>
            <span className="handicap-unit">quả</span>
          </div>
        )}
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
