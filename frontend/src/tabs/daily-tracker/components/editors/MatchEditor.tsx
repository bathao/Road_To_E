import { useEffect, useState } from "react";
import type { Category, Discipline, Match, MatchIn, Player } from "../../types";
import { trackerApi } from "../../api";
import { validScores } from "../../scores";
import PlayerPicker from "./PlayerPicker";
import { levelShort } from "../../../../shared/levels";
import { DISCIPLINES, DISCIPLINE_SHORT } from "../../../../shared/disciplines";
import { resultOf } from "../../../../shared/types";

const FORMATS = [3, 5, 7];
type HandicapDir = "none" | "give" | "receive";

// "vs Nam (Ngang)" for singles; "+ Partner vs A & B" for the team formats
// (doubles / 1v2 / 2v1 — unused slots just don't render), plus handicap.
function playersLabel(m: Match): string {
  if (m.is_nonplaying) return "";
  const parts: string[] = [];
  if (m.discipline !== "singles") {
    if (m.partner_name) parts.push(`+${m.partner_name}`);
    const opps = [
      m.opponent_name && `${m.opponent_name}${m.opponent_plays_pips ? " 🏓" : ""}`,
      m.opponent2_name &&
        `${m.opponent2_name}${m.opponent2_plays_pips ? " 🏓" : ""}`,
    ].filter(Boolean);
    if (opps.length) parts.push(`vs ${opps.join(" & ")}`);
  } else if (m.opponent_name) {
    const gai = m.opponent_plays_pips ? " 🏓pips" : "";
    parts.push(`vs ${m.opponent_name} (${levelShort(m.opponent_level)})${gai}`);
  }
  // Non-uniform ratios show the per-set sequence ("2-0-2"), uniform the number.
  const hdc = m.handicap_pattern ?? String(Math.abs(m.handicap));
  if (m.handicap > 0) parts.push(`give ${hdc}`);
  else if (m.handicap < 0) parts.push(`receive ${hdc}`);
  return parts.join(" ");
}

// Why a match doesn't move the ELO — only ACTIONABLE reasons get a tag
// (fix = name the opponent / enter points in the Database tab / log the
// score). Pre-anchor and Travel/Rest rows stay untagged: nothing to fix.
const ELO_SKIP_LABEL: Record<string, string> = {
  no_opponent: "opponent not recorded",
  unrated: "player has no points yet (Database tab)",
  no_result: "no score yet",
};

function EloChip({ m }: { m: Match }) {
  if (m.elo_delta != null) {
    const up = m.elo_delta >= 0;
    return (
      <span className={`elo-chip ${up ? "elo-up" : "elo-down"}`} title="ELO change after this match">
        {up ? "+" : ""}
        {m.elo_delta.toFixed(1)}
      </span>
    );
  }
  const label = m.elo_status ? ELO_SKIP_LABEL[m.elo_status] : undefined;
  if (!label) return null;
  return (
    <span className="elo-chip elo-skip" title={`Match not counted for ELO: ${label}`}>
      not counted
    </span>
  );
}

// Common per-set handicap ratios ("2-0-2" = set 1: 2, set 2: 0, set 3: 2).
// Anything else goes through "Custom…" (digits typed by hand).
const HANDICAP_PATTERNS = [
  "0-2-0",
  "2-0-2",
  "2-2-2",
  "2-3-2",
  "3-2-3",
  "3-3-3",
  "3-4-3",
  "4-3-4",
  "4-4-4",
  "4-5-4",
  "5-4-5",
  "5-5-5", // maximum chấp ratio (the ELO bonus ladder caps here too)
];

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
  // A preset from HANDICAP_PATTERNS, or "custom" (digits in customPattern).
  const [handicapChoice, setHandicapChoice] = useState("2-2-2");
  const [customPattern, setCustomPattern] = useState("");

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

  // Remember the ratio per opponent: picking a singles opponent pre-fills
  // the handicap from the last match against them (Tuấn Gỗ → được chấp
  // 4-4-4, Lợi Phạm → 2-2-2…). The user can still change it before saving.
  useEffect(() => {
    if (discipline !== "singles" || !opponent) return;
    let alive = true;
    trackerApi
      .lastHandicap(opponent.id)
      .then((r) => {
        if (!alive || !r.found) return;
        if (r.handicap === 0) {
          setHandicapDir("none");
          return;
        }
        setHandicapDir(r.handicap > 0 ? "give" : "receive");
        const digits = (r.handicap_pattern ?? "").replace(/\D/g, "");
        const abs = Math.abs(r.handicap);
        // Uniform ratios come back as a plain int → present as N-N-N.
        const pattern = digits
          ? digits.split("").join("-")
          : `${abs}-${abs}-${abs}`;
        if (HANDICAP_PATTERNS.includes(pattern)) {
          setHandicapChoice(pattern);
        } else {
          setHandicapChoice("custom");
          setCustomPattern(digits || String(abs).repeat(3));
        }
      })
      .catch(() => {}); // suggestion only — never block entry
    return () => {
      alive = false;
    };
  }, [opponent, discipline]);

  const { wins, losses } = validScores(bestOf);

  // Which player slots the chosen format uses.
  const hasPartner = discipline === "doubles" || discipline === "two_v_one";
  const hasOpp2 = discipline === "doubles" || discipline === "one_v_two";

  // Per-set digits of the chosen ratio. Uniform ("2-2-2") is stored as the
  // plain signed int like before; only mixed ratios carry a pattern, with
  // `handicap` = signed rounded per-set average (min 1 so the sign survives)
  // — sign-based analytics stay valid either way.
  const patternDigits = (
    handicapChoice === "custom" ? customPattern : handicapChoice
  )
    .split("")
    .filter((c) => c >= "0" && c <= "9")
    .map(Number);
  const uniform = new Set(patternDigits).size <= 1;
  const points =
    patternDigits.length === 0
      ? 0
      : uniform
      ? patternDigits[0]
      : Math.max(
          1,
          Math.round(
            patternDigits.reduce((a, b) => a + b, 0) / patternDigits.length
          )
        );
  const handicap =
    handicapDir === "give" ? points : handicapDir === "receive" ? -points : 0;
  const handicapPattern =
    handicapDir !== "none" && !uniform ? patternDigits.join("-") : null;

  const addScore = (my: number, opp: number) => {
    onAdd({
      discipline,
      best_of: bestOf,
      my_sets: my,
      opp_sets: opp,
      event_name: eventName.trim() || null,
      opponent_id: opponent?.id ?? null,
      opponent2_id: hasOpp2 ? opponent2?.id ?? null : null,
      partner_id: hasPartner ? partner?.id ?? null : null,
      handicap,
      handicap_pattern: handicapPattern,
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
                  : `${DISCIPLINE_SHORT[m.discipline]} ${resultOf(m)} ${m.my_sets}-${m.opp_sets}`}
                {playersLabel(m) ? ` · ${playersLabel(m)}` : ""}
                {m.event_name ? ` · ${m.event_name}` : ""}
                <EloChip m={m} />
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
          {DISCIPLINES.map(([d, lbl]) => (
            <button
              key={d}
              className={`seg-btn${discipline === d ? " active" : ""}`}
              onClick={() => setDiscipline(d)}
            >
              {lbl}
            </button>
          ))}
        </div>
      </div>

      {/* Players */}
      {hasPartner && (
        <PlayerPicker label="Partner" value={partner} onChange={setPartner} />
      )}
      <PlayerPicker
        label={hasOpp2 ? "Opponent 1" : "Opponent"}
        value={opponent}
        onChange={setOpponent}
        pipsEditable
      />
      {hasOpp2 && (
        <PlayerPicker
          label="Opponent 2"
          value={opponent2}
          onChange={setOpponent2}
          pipsEditable
        />
      )}

      {/* Handicap (optional) */}
      <div className="seg-row handicap-row">
        <span className="seg-label">Handicap</span>
        <div className="seg">
          {(
            [
              ["none", "None"],
              ["give", "I give"],
              ["receive", "I receive"],
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
          <div className="handicap-pick">
            <select
              className="pb-select"
              value={handicapChoice}
              onChange={(e) => setHandicapChoice(e.target.value)}
            >
              {HANDICAP_PATTERNS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
              <option value="custom">Custom…</option>
            </select>
            {handicapChoice === "custom" && (
              <input
                type="text"
                inputMode="numeric"
                className="pb-input handicap-custom"
                placeholder="e.g. 42024"
                value={customPattern}
                onChange={(e) =>
                  setCustomPattern(e.target.value.replace(/\D/g, ""))
                }
              />
            )}
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
