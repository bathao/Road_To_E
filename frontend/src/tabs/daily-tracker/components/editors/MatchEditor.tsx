import { useEffect, useRef, useState } from "react";
import type {
  Category,
  Discipline,
  Match,
  MatchIn,
  Player,
  PlayerLevel,
  Tournament,
  TournamentEntry,
} from "../../types";
import { trackerApi } from "../../api";
import { validScores } from "../../scores";
import EloDeltaChip from "../../../../shared/ui/EloDeltaChip";
import PlayerPicker from "./PlayerPicker";
import { levelShort } from "../../../../shared/levels";
import { DISCIPLINES, DISCIPLINE_SHORT } from "../../../../shared/disciplines";
import {
  hdcLabel,
  nextRound,
  ROUND_LABEL,
  ROUND_SHORT,
} from "../../../../shared/matches";
import type { TournamentRound } from "../../../../shared/matches";
import { resultOf } from "../../../../shared/types";

const FORMATS = [3, 5, 7];
type HandicapDir = "none" | "give" | "receive";

// One pickable "what am I playing in" option: a tournament's registered
// discipline (entry). Usually exactly one per day; more when the user
// entered several disciplines (or two tournaments overlap).
export interface TournamentCtx {
  tournament: Tournament;
  entry: TournamentEntry;
}

const ROUND_OPTIONS = Object.entries(ROUND_LABEL) as [TournamentRound, string][];
// Ladder order for the depth comparison below (insertion order of the map).
const ROUND_KEYS = Object.keys(ROUND_LABEL) as TournamentRound[];

// Auto-advancing Round default (user 2026-08-09): after a knockout WIN the
// picker pre-selects the NEXT round; a loss means knocked out, so it stays
// put; group results never advance (bracket size unknown — the first
// knockout round is picked by hand). Entry-linked cells read the ENTRY's
// deepest decided round from the server (so day 2 of a multi-day event
// continues where day 1 ended); unlinked cells (back-filling an old event)
// derive the same rule from the cell's own matches.
function defaultRound(ctx: TournamentCtx | null, ms: Match[]): TournamentRound {
  let latest: TournamentRound | null = null;
  let won = false;
  if (ctx) {
    if (ctx.entry.latest_round) {
      latest = ctx.entry.latest_round as TournamentRound;
      won = ctx.entry.latest_round_won ?? false;
    }
  } else {
    let best: Match | null = null;
    let bestDepth = -1;
    for (const m of ms) {
      if (m.is_nonplaying || m.my_sets === m.opp_sets) continue; // undecided
      const depth = ROUND_KEYS.indexOf((m.round ?? "group") as TournamentRound);
      if (depth >= bestDepth) {
        best = m; // ties → the later match wins (cell order = entry order)
        bestDepth = depth;
      }
    }
    if (best) {
      latest = (best.round ?? "group") as TournamentRound;
      won = best.my_sets > best.opp_sets;
    }
  }
  if (!latest || latest === "group") return "group";
  return won ? nextRound(latest) : latest;
}

// "BBTV Open · Singles hạng E" — how one entry shows in the picker.
function ctxLabel(c: TournamentCtx): string {
  const disc = c.entry.discipline[0].toUpperCase() + c.entry.discipline.slice(1);
  return `${c.tournament.name} · ${disc}${c.entry.division ? ` ${c.entry.division}` : ""}`;
}

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
  const hdc = hdcLabel(m.handicap, m.handicap_pattern);
  if (hdc) parts.push(hdc);
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
    return (
      <EloDeltaChip delta={m.elo_delta} title="ELO change after this match" />
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
// optional handicap, then tap a final score. Plus event autocomplete.
// (Travel/Rest quick buttons removed 2026-08-04 — old non-playing rows still
// render in the list and can be deleted, there's just no way to add new ones.)
// ✏️ on a saved match loads it back into the same form for editing — score
// buttons then SELECT instead of save, and 💾 Save commits via PUT.
export default function MatchEditor({
  category,
  matches,
  tournamentCtx = [],
  onAdd,
  onUpdate,
  onDelete,
  onEliminate,
}: {
  category: Category;
  matches: Match[];
  // Tournament(s) running on this cell's date (tournament row only).
  tournamentCtx?: TournamentCtx[];
  onAdd: (payload: Omit<MatchIn, "date" | "category_id">) => void;
  // Resolves true when the PUT landed (edit mode only exits on success).
  onUpdate: (
    id: number,
    payload: Omit<MatchIn, "date" | "category_id">
  ) => Promise<boolean>;
  onDelete: (id: number) => void;
  // Mark the selected entry knocked out — the banner disappears (the entry
  // leaves tournamentCtx) and the event's remaining days stop collecting
  // matches for it. Once EVERY entry is out the tournament retires straight
  // to the Profile record (undo via the card's ☠ chip only exists while
  // another entry keeps the card alive).
  onEliminate?: (entryId: number) => void;
}) {
  const [discipline, setDiscipline] = useState<Discipline>("singles");
  const [bestOf, setBestOf] = useState(5);
  const [eventName, setEventName] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const [opponent, setOpponent] = useState<Player | null>(null);
  const [opponent2, setOpponent2] = useState<Player | null>(null);
  const [partner, setPartner] = useState<Player | null>(null);

  // Tournament mode. The round picker shows on every tournament-row cell
  // (even without a linked tournament — back-filling an old event); the
  // banner/entry pick/partner prefill need an actual tournament that day.
  const isTournamentCell = category.key === "tournament_match";
  const [entryIdx, setEntryIdx] = useState(0);
  // Clamp instead of ?? null: eliminating the selected entry shrinks the
  // list (knocked-out entries leave tournamentCtx) — a remaining entry
  // should take over the banner rather than it vanishing on a stale index.
  // The <select> renders the SAME clamped index, or it would sit blank
  // (controlled value pointing at a removed option) while the banner shows
  // the clamped entry.
  const selIdx = Math.min(entryIdx, Math.max(tournamentCtx.length - 1, 0));
  const selCtx = tournamentCtx.length > 0 ? tournamentCtx[selIdx] : null;
  // Default round = auto-advance from the deepest decided round (win → next
  // round pre-picked, loss → stays). Re-derived after every save/delete and
  // on entry switch — see the effect below (never while editing a match).
  const [round, setRound] = useState<TournamentRound>(() =>
    defaultRound(selCtx, matches)
  );

  // Applying the picked entry: doubles registrations lock the discipline and
  // pre-fill the registered partner (still editable per match — the pair can
  // change on the day); the tournament name pre-fills the Event box.
  // Also re-applied after an edit ends, so the add form comes back pre-filled.
  // The ref remembers what the prefill wrote: switching to another entry
  // must replace ITS OWN leftover but never a user-typed name (review find
  // 2026-08-09: two overlapping tournaments → matches saved for B still
  // carried A's event name).
  const prefilledEvent = useRef<string | null>(null);
  const applyEntryPrefill = () => {
    if (!selCtx) return;
    setEventName((cur) => {
      if (cur.trim() && cur !== prefilledEvent.current) return cur; // user's
      prefilledEvent.current = selCtx.tournament.name;
      return selCtx.tournament.name;
    });
    if (selCtx.entry.discipline === "doubles") {
      setDiscipline("doubles");
      if (selCtx.entry.partner_id) {
        setPartner({
          id: selCtx.entry.partner_id,
          name: selCtx.entry.partner_name ?? "?",
          level: "equal", // display-only here; the id is what gets saved
          plays_pips: false,
        });
      }
    } else if (selCtx.entry.discipline === "singles") {
      setDiscipline("singles");
    }
    // Team entries: ties mix singles + doubles — leave the choice manual.
  };
  useEffect(() => {
    if (!selCtx) {
      // The entry left the ctx (just knocked out): its own Event prefill
      // must not linger and silently label unlinked matches — a user-typed
      // name stays. Never while editing (the form holds the match's data).
      if (!editingMatch)
        setEventName((cur) => (cur === prefilledEvent.current ? "" : cur));
      return;
    }
    applyEntryPrefill();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selCtx?.entry.id]);

  const [handicapDir, setHandicapDir] = useState<HandicapDir>("none");
  // A preset from HANDICAP_PATTERNS, or "custom" (digits in customPattern).
  const [handicapChoice, setHandicapChoice] = useState("2-2-2");
  const [customPattern, setCustomPattern] = useState("");

  // Edit mode: the saved match currently loaded into the form (null = adding).
  // While editing, the score buttons select instead of save; selScore holds
  // the pick (pre-set to the match's current score).
  const [editingMatch, setEditingMatch] = useState<Match | null>(null);
  const [selScore, setSelScore] = useState<{ my: number; opp: number } | null>(
    null
  );
  // Whether the user touched the Round dropdown during THIS edit — a match
  // saved without a round must not silently inherit the picker's leftover
  // value on save.
  const [roundTouched, setRoundTouched] = useState(false);

  // Re-derive the Round default when a save/delete lands (matches change,
  // and afterMutate's tournament refetch updates entry.latest_round) or the
  // picked entry changes: win 1/32 → the picker jumps to 1/16 by itself.
  // Guarded while editing — beginEdit owns the picker there. Deps are a
  // CONTENT signature, not array identity (the parent rebuilds both props
  // every render) — an unsaved manual pick survives unrelated re-renders.
  const matchesKey = matches
    .map((m) => `${m.id}:${m.my_sets}-${m.opp_sets}:${m.round ?? ""}`)
    .join("|");
  useEffect(() => {
    if (editingMatch) return;
    setRound(defaultRound(selCtx, matches));
    setRoundTouched(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    editingMatch,
    selCtx?.entry.id,
    selCtx?.entry.latest_round,
    selCtx?.entry.latest_round_won,
    matchesKey,
  ]);

  // Signed handicap + optional per-set pattern → the three form fields.
  // Shared by the last-handicap prefill and by loading a match for edit.
  const applyHandicap = (hdc: number, pattern: string | null | undefined) => {
    if (hdc === 0) {
      setHandicapDir("none");
      return;
    }
    setHandicapDir(hdc > 0 ? "give" : "receive");
    const digits = (pattern ?? "").replace(/\D/g, "");
    const abs = Math.abs(hdc);
    // Uniform ratios come back as a plain int → present as N-N-N.
    const p = digits ? digits.split("").join("-") : `${abs}-${abs}-${abs}`;
    if (HANDICAP_PATTERNS.includes(p)) {
      setHandicapChoice(p);
    } else {
      setHandicapChoice("custom");
      setCustomPattern(digits || String(abs).repeat(3));
    }
  };

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
  // Skipped while editing — the form already holds the match's own handicap.
  useEffect(() => {
    if (editingMatch || discipline !== "singles" || !opponent) return;
    let alive = true;
    trackerApi
      .lastHandicap(opponent.id)
      .then((r) => {
        if (!alive || !r.found) return;
        applyHandicap(r.handicap, r.handicap_pattern);
      })
      .catch(() => {}); // suggestion only — never block entry
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opponent, discipline, editingMatch]);

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

  // ---- edit mode ----

  // Match rows only carry id/name/level/pips — enough for the picker to work
  // (the id is what gets saved); the points chip is patched in by `enrich`.
  const toPlayer = (
    id: number,
    name: string | null,
    level: PlayerLevel | null,
    pips: boolean
  ): Player => ({ id, name: name ?? "?", level: level ?? "equal", plays_pips: pips });

  // Cosmetic: swap the placeholder for the real DB row (points chip). Only
  // replaces the slot if the user hasn't changed/cleared it meanwhile.
  const enrich = (
    id: number | null | undefined,
    name: string | null | undefined,
    set: (fn: (cur: Player | null) => Player | null) => void
  ) => {
    if (id == null || !name) return;
    trackerApi
      .searchPlayers(name)
      .then((rs) => {
        const p = rs.find((r) => r.id === id);
        if (p) set((cur) => (cur && cur.id === id ? p : cur));
      })
      .catch(() => {});
  };

  const startEdit = (m: Match) => {
    setEditingMatch(m);
    setRoundTouched(false);
    setSelScore({ my: m.my_sets, opp: m.opp_sets });
    setDiscipline(m.discipline);
    setBestOf(m.best_of);
    setEventName(m.event_name ?? "");
    setOpponent(
      m.opponent_id != null
        ? toPlayer(m.opponent_id, m.opponent_name, m.opponent_level, m.opponent_plays_pips)
        : null
    );
    setOpponent2(
      m.opponent2_id != null
        ? toPlayer(m.opponent2_id, m.opponent2_name, m.opponent2_level, m.opponent2_plays_pips)
        : null
    );
    setPartner(
      m.partner_id != null
        ? toPlayer(m.partner_id, m.partner_name, m.partner_level, false)
        : null
    );
    applyHandicap(m.handicap, m.handicap_pattern);
    // Round-less match: show "Group" (null renders as group stage everywhere)
    // instead of the add-form's auto-advance leftover — an untouched save
    // keeps null, so the picker must not display e.g. "1/8" it won't write.
    setRound((m.round as TournamentRound) ?? "group");
    enrich(m.opponent_id, m.opponent_name, setOpponent);
    enrich(m.opponent2_id, m.opponent2_name, setOpponent2);
    enrich(m.partner_id, m.partner_name, setPartner);
  };

  // Back to a clean add form (also runs after a successful save).
  const resetForm = () => {
    setEditingMatch(null);
    setRoundTouched(false);
    setSelScore(null);
    setOpponent(null);
    setOpponent2(null);
    setPartner(null);
    setHandicapDir("none");
    setHandicapChoice("2-2-2");
    setCustomPattern("");
    setEventName("");
    applyEntryPrefill(); // tournament cells get their name/partner back
  };

  // Changing the format mid-edit can orphan the picked score (3-2 under
  // BO3). The match's ORIGINAL score is always accepted — imported/legacy
  // rows can hold scores validScores() never offers (e.g. a 1-1 tie), and
  // "fix the handicap, keep the score" must still be saveable for them.
  const scoreValid =
    selScore != null &&
    ((editingMatch != null &&
      selScore.my === editingMatch.my_sets &&
      selScore.opp === editingMatch.opp_sets) ||
      [...wins, ...losses].some(
        (s) => s.my === selScore.my && s.opp === selScore.opp
      ));

  const saveEdit = async () => {
    if (!editingMatch || !selScore || !scoreValid) return;
    const ok = await onUpdate(editingMatch.id, {
      discipline,
      best_of: bestOf,
      my_sets: selScore.my,
      opp_sets: selScore.opp,
      event_name: eventName.trim() || null,
      note: editingMatch.note, // not editable here — carry through
      opponent_id: opponent?.id ?? null,
      opponent2_id: hasOpp2 ? opponent2?.id ?? null : null,
      partner_id: hasPartner ? partner?.id ?? null : null,
      handicap,
      handicap_pattern: handicapPattern,
      // The tournament link is not re-pickable when editing — keep it as-is.
      tournament_entry_id: editingMatch.tournament_entry_id ?? null,
      // Round follows the picker only if the user touched it this edit —
      // otherwise the match keeps its stored value (incl. "no round").
      round: isTournamentCell
        ? roundTouched
          ? round
          : editingMatch.round ?? null
        : editingMatch.round ?? null,
    });
    if (ok) resetForm();
  };

  // Score buttons: save immediately when adding, select when editing.
  const pickScore = (my: number, opp: number) => {
    if (editingMatch) setSelScore({ my, opp });
    else addScore(my, opp);
  };

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
      tournament_entry_id: selCtx?.entry.id ?? null,
      round: isTournamentCell ? round : null,
    });
    // Clear the opponent(s) so the next person can be picked right away.
    // Partner + handicap + format are kept (usually the same across a session).
    setOpponent(null);
    setOpponent2(null);
  };

  return (
    <div className="editor">
      <p className="editor-sub">{category.label}</p>

      {/* Tournament banner: which competition/entry this match belongs to. */}
      {selCtx && (
        <div className="tour-banner">
          <span className="tour-banner-name">
            🏆 {selCtx.tournament.name}
            {selCtx.entry.division ? ` · ${selCtx.entry.division}` : ""}
          </span>
          {selCtx.entry.discipline === "doubles" && selCtx.entry.partner_name && (
            <span className="tour-chip">
              🤝 with {selCtx.entry.partner_name}
            </span>
          )}
          {onEliminate && !editingMatch && (
            <button
              className="btn tour-out-btn"
              title="Knocked out of this event — no more matches to enter; once every entry is out, the tournament moves to the Profile record with its result"
              onClick={() => {
                if (
                  window.confirm(
                    `Mark "${ctxLabel(selCtx)}" as knocked out?\n` +
                      "No more matches will be collected for it, and once " +
                      "every entry is out the tournament moves to the " +
                      "Profile tab's Tournament Record."
                  )
                )
                  onEliminate(selCtx.entry.id);
              }}
            >
              ☠ Knocked out
            </button>
          )}
          {tournamentCtx.length > 1 && (
            <select
              className="pb-select tour-entry-pick"
              value={selIdx}
              // Locked while editing: saveEdit keeps the match's stored
              // entry link, so re-picking here would prefill the form
              // (discipline/partner/event) without moving the link.
              disabled={!!editingMatch}
              title={
                editingMatch
                  ? "The tournament link can't be changed while editing"
                  : undefined
              }
              onChange={(e) => setEntryIdx(Number(e.target.value))}
            >
              {tournamentCtx.map((c, i) => (
                <option key={c.entry.id} value={i}>
                  {ctxLabel(c)}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Round: group stage by default; knockout rounds as far as I survive. */}
      {isTournamentCell && (
        <div className="seg-row">
          <span className="seg-label">Round</span>
          <select
            className="pb-select"
            value={round}
            onChange={(e) => {
              setRound(e.target.value as TournamentRound);
              setRoundTouched(true);
            }}
          >
            {ROUND_OPTIONS.map(([k, lbl]) => (
              <option key={k} value={k}>
                {lbl}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Edit mode banner */}
      {editingMatch && (
        <div className="match-edit-banner">
          <span>✏️ Editing this match — adjust below, then Save</span>
          <button className="btn" onClick={resetForm}>
            Cancel
          </button>
        </div>
      )}

      {/* Existing matches in this cell, FILTERED to the picked entry on a
          multi-event day (user 2026-08-23: "lọc theo giải đang chọn") —
          unlinked rows stay visible under any pick. Matches of other
          events show by switching the dropdown; a knocked-out event's
          matches come back once no entry is selectable (ctx empty → full
          list) or after un-marking ☠ on the card / Profile record. */}
      {(() => {
        const row = (m: Match) => (
          <div
            key={m.id}
            className={`match-item${editingMatch?.id === m.id ? " editing" : ""}`}
          >
            <span>
              {m.is_nonplaying
                ? m.nonplaying_label ?? "—"
                : `${DISCIPLINE_SHORT[m.discipline]} ${resultOf(m)} ${m.my_sets}-${m.opp_sets}`}
              {playersLabel(m) ? ` · ${playersLabel(m)}` : ""}
              {m.round && ROUND_SHORT[m.round] ? ` · ${ROUND_SHORT[m.round]}` : ""}
              {m.event_name ? ` · ${m.event_name}` : ""}
              <EloChip m={m} />
            </span>
            <span className="match-item-btns">
              {!m.is_nonplaying && (
                <button
                  className="icon-btn"
                  onClick={() => startEdit(m)}
                  aria-label="Edit match"
                  title="Edit match"
                >
                  ✏️
                </button>
              )}
              <button
                className="icon-btn danger"
                onClick={() => {
                  // Deleting the row currently loaded into the form would
                  // strand a phantom edit whose Save can only 404.
                  if (editingMatch?.id === m.id) resetForm();
                  onDelete(m.id);
                }}
                aria-label="Delete match"
              >
                ✕
              </button>
            </span>
          </div>
        );
        const mine = selCtx
          ? matches.filter(
              (m) =>
                m.tournament_entry_id == null ||
                m.tournament_entry_id === selCtx.entry.id
            )
          : matches;
        return mine.length > 0 ? (
          <div className="match-list">{mine.map(row)}</div>
        ) : null;
      })()}

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

      {/* Score picker (adding: tap = save; editing: tap = select, 💾 saves) */}
      <div className="score-picker">
        <div className="score-col">
          <span className="score-head win">Win</span>
          <div className="score-btns">
            {wins.map((s) => (
              <button
                key={`w${s.my}-${s.opp}`}
                className={`score-btn win${
                  editingMatch && selScore?.my === s.my && selScore?.opp === s.opp
                    ? " selected"
                    : ""
                }`}
                onClick={() => pickScore(s.my, s.opp)}
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
                className={`score-btn loss${
                  editingMatch && selScore?.my === s.my && selScore?.opp === s.opp
                    ? " selected"
                    : ""
                }`}
                onClick={() => pickScore(s.my, s.opp)}
              >
                {s.my}-{s.opp}
              </button>
            ))}
          </div>
        </div>
      </div>

      {editingMatch && (
        /* Edit mode: explicit save (the common edit keeps the score as-is) */
        <div className="quick-row">
          <button
            className="btn primary"
            onClick={saveEdit}
            disabled={!scoreValid}
            title={scoreValid ? undefined : "Pick a score for this format"}
          >
            💾 Save changes
          </button>
          <button className="btn" onClick={resetForm}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
