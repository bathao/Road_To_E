// Point charter: logs one singles match rally by rally (2026-10-10), laid
// out as a LEDGER (user, same evening: "thiết kế từng điểm kiểu từng dòng
// … tôi chọn kiểu giao ở các option ở trên, nó hiện xuống dưới dòng đó,
// xong tôi viết tiếp diễn biến"):
//
//   setup row   — who served first in set 1, typed / derived set scores
//   palette     — the chips for the NEXT thing to say (serve → stroke +
//                 landing spot → how the point ended), context-dependent
//   live row    — "Point 5 · 3–1 · Thảo giao" + the rally so far, growing
//                 as chips are tapped; Save / Undo live on this row
//   ledger      — every logged point of the set, newest first, one line
//                 each, with the score it produced and a ✕
//
// Score, point number and server are derived (2 serves each, 1 each from
// 10-10, the first server alternates per set). Right / Middle / Left are
// ALWAYS the receiver's side of the table. A shot that missed needs no
// landing spot ("Vy đỡ ra ngoài" = Đỡ / cú khác + ✗).
import { useEffect, useMemo, useState } from "react";
import type { Match } from "../../daily-tracker/types";
import type {
  MatchLog,
  OppServeSeen,
  Point,
  PointIn,
  Serve,
  ServeIn,
  SetScore,
  Shot,
} from "../types";
import {
  AMOUNTS,
  BALLS,
  LENGTHS,
  MOTIONS,
  PLACES,
  SPINS,
  STANCES,
  STROKES,
  labelOf,
  placeLabel,
  serveDesc,
  type Ball,
  type Choice,
  type Place,
  type Side,
  type Stroke,
} from "../vocab";

const other = (s: Side): Side => (s === "me" ? "opp" : "me");

type Partial_ = Partial<Shot> & { fromSeen?: boolean; name?: string };
interface Draft {
  shots: Shot[];
  partial: Partial_ | null; // the shot being built
  end: "winner" | "error" | null;
  forced: boolean;
  note: string;
}
const emptyDraft = (): Draft => ({ shots: [], partial: null, end: null, forced: false, note: "" });

function setOver(me: number, opp: number): boolean {
  return Math.max(me, opp) >= 11 && Math.abs(me - opp) >= 2;
}
function serverFor(first: Side, me: number, opp: number): Side {
  const total = me + opp;
  if (me >= 10 && opp >= 10) return total % 2 === 0 ? first : other(first);
  return Math.floor(total / 2) % 2 === 0 ? first : other(first);
}
const serveReady = (p: Partial_ | null) => !!(p && p.serve && p.spin && p.length);
const winnerOf = (shots: Shot[], end: "winner" | "error"): Side => {
  const last = shots[shots.length - 1].h;
  return end === "winner" ? last : other(last);
};
const sameServe = (a: Partial_ | OppServeSeen, b: Partial_ | OppServeSeen) =>
  (["stance", "motion", "spin", "amount", "length"] as const).every(
    (k) => (a[k] ?? null) === (b[k] ?? null)
  );

function ChipRow<C extends string>({
  label,
  choices,
  value,
  onPick,
  extra,
}: {
  label: string;
  choices: Choice<C>[];
  value: string | null | undefined;
  onPick: (c: C) => void;
  extra?: React.ReactNode;
}) {
  return (
    <div className="ml-row">
      <div className="ml-lab">{label}</div>
      <div className="ml-chips">
        {choices.map((c) => (
          <button
            key={c.code}
            type="button"
            className={`ml-chip${value === c.code ? " on" : ""}`}
            onClick={() => onPick(c.code)}
          >
            {c.label}
            <kbd>{c.key}</kbd>
          </button>
        ))}
        {extra}
      </div>
    </div>
  );
}

export default function PointCharter({
  match,
  names,
  serves,
  log,
  busy,
  onAddPoint,
  onDeletePoint,
  onSaveSets,
  onAddServe,
}: {
  match: Match;
  names: Record<Side, string>;
  serves: Serve[];
  log: MatchLog;
  busy: boolean;
  onAddPoint: (p: PointIn) => Promise<boolean>;
  onDeletePoint: (id: number) => Promise<void>;
  onSaveSets: (sets: SetScore[]) => Promise<void>;
  onAddServe: (s: ServeIn) => Promise<Serve | undefined>;
}) {
  const setCount = Math.max(1, match.my_sets + match.opp_sets);
  const [cur, setCur] = useState(0);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [addingServe, setAddingServe] = useState(false);
  const [newServe, setNewServe] = useState<Partial<ServeIn>>({});

  // Typed set scores live locally while editing; saved on blur.
  const [typed, setTyped] = useState<SetScore[]>([]);
  useEffect(() => {
    setTyped(
      Array.from({ length: setCount }, (_, i) => {
        const row = log.sets.find((s) => s.set_no === i + 1);
        return row ?? { set_no: i + 1, my_points: null, opp_points: null, first_server: null };
      })
    );
  }, [log.sets, setCount]);

  const firstServer: Side = typed[0]?.first_server ?? "me";
  const firstServerOf = (i: number): Side => (i % 2 === 0 ? firstServer : other(firstServer));

  const pointsBySet = useMemo(() => {
    const out: Point[][] = Array.from({ length: setCount }, () => []);
    log.points.forEach((p) => {
      if (p.set_no >= 1 && p.set_no <= setCount) out[p.set_no - 1].push(p);
    });
    return out;
  }, [log.points, setCount]);

  const scoreOf = (i: number, upto?: number) => {
    const pts = pointsBySet[i].slice(0, upto);
    let me = 0, opp = 0;
    pts.forEach((p) => (p.winner === "me" ? me++ : opp++));
    return { me, opp };
  };
  const setScore = (i: number): { me: number | null; opp: number | null; fromPts: boolean } => {
    if (pointsBySet[i].length) return { ...scoreOf(i), fromPts: true };
    const t = typed[i];
    return { me: t?.my_points ?? null, opp: t?.opp_points ?? null, fromPts: false };
  };

  const sc = scoreOf(cur);
  const server = serverFor(firstServerOf(cur), sc.me, sc.opp);
  const over = setOver(sc.me, sc.opp);
  const hitter: Side = draft.shots.length ? other(draft.shots[draft.shots.length - 1].h) : server;
  const pointNo = pointsBySet[cur].length + 1;

  // ---- set scores / first server ----
  const saveSets = (rows: SetScore[]) => {
    void onSaveSets(rows.filter((r) => r.my_points != null || r.opp_points != null || r.first_server));
  };
  const setFirst = (s: Side) => {
    const rows = typed.map((r, i) => (i === 0 ? { ...r, first_server: s } : r));
    setTyped(rows);
    saveSets(rows);
  };
  const editTyped = (i: number, side: "my_points" | "opp_points", v: string) => {
    setTyped((rows) => rows.map((r, j) => (j === i ? { ...r, [side]: v === "" ? null : Number(v) } : r)));
  };

  // ---- draft building ----
  const commitServe = (d: Draft, place: Place): Draft => {
    const p = d.partial!;
    const shot: Shot = {
      h: server, serve: true, serve_id: p.serve_id ?? null,
      stance: p.stance ?? null, motion: p.motion ?? null, spin: p.spin ?? null,
      amount: p.amount ?? null, length: p.length ?? null, place,
    };
    return { ...d, shots: [shot], partial: null };
  };
  const pickMyServe = (s: Serve) =>
    setDraft((d) => {
      const partial: Partial_ = {
        h: "me", serve: true, serve_id: s.id, name: s.name,
        stance: s.stance, motion: s.motion, spin: s.spin, amount: s.amount, length: s.length,
      };
      // A repertoire serve carries its landing spot: one tap commits it.
      return s.place ? commitServe({ ...d, partial }, s.place) : { ...d, partial };
    });
  const pickSeen = (s: OppServeSeen) =>
    setDraft((d) => ({
      ...d,
      partial: { h: "opp", serve: true, fromSeen: true, stance: s.stance, motion: s.motion, spin: s.spin, amount: s.amount, length: s.length },
    }));
  const setServeAttr = (k: "stance" | "motion" | "spin" | "amount" | "length", v: string) =>
    setDraft((d) => ({ ...d, partial: { ...(d.partial ?? {}), h: server, serve: true, fromSeen: false, name: undefined, serve_id: null, [k]: v } }));
  const pickStroke = (s: Stroke) =>
    setDraft((d) => ({ ...d, partial: { ...(d.partial ?? {}), h: hitter, stroke: s } }));
  const pickBall = (b: Ball) =>
    setDraft((d) => ({ ...d, partial: { ...(d.partial ?? {}), h: hitter, ball: d.partial?.ball === b ? null : b } }));
  const pickPlace = (place: Place) =>
    setDraft((d) => {
      const p = d.partial;
      if (!d.shots.length) {
        if (!serveReady(p)) return d;
        return commitServe(d, place);
      }
      if (p?.stroke) {
        return { ...d, shots: [...d.shots, { h: hitter, stroke: p.stroke, ball: p.ball ?? null, place }], partial: null };
      }
      return d;
    });
  const changeServePlace = (place: Place) =>
    setDraft((d) => (d.shots.length === 1 ? { ...d, shots: [{ ...d.shots[0], place }] } : d));

  // ✓ / ✗ on the LAST shot; ✗ while a stroke is half-built = that stroke
  // missed (no landing spot).
  const endPoint = (kind: "winner" | "error") =>
    setDraft((d) => {
      if (kind === "error" && d.partial?.stroke && d.shots.length) {
        return {
          ...d,
          shots: [...d.shots, { h: hitter, stroke: d.partial.stroke, ball: d.partial.ball ?? null, place: null }],
          partial: null,
          end: "error",
        };
      }
      if (!d.shots.length) return d;
      return { ...d, end: kind, partial: null };
    });
  const undo = () =>
    setDraft((d) => {
      if (d.end) return { ...d, end: null, forced: false };
      if (d.partial) return { ...d, partial: null };
      return { ...d, shots: d.shots.slice(0, -1) };
    });
  const save = async () => {
    if (!draft.end || !draft.shots.length || busy) return;
    const ok = await onAddPoint({
      set_no: cur + 1,
      server,
      shots: draft.shots,
      end_kind: draft.end,
      forced: draft.end === "error" && draft.forced,
      note: draft.note.trim() || null,
    });
    if (ok) setDraft(emptyDraft());
  };

  // ---- keyboard ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const tag = t?.tagName;
      if (tag === "INPUT" || tag === "SELECT") return;
      if (tag === "TEXTAREA" && e.key !== "Enter") return;
      const k = e.key, up = k.toUpperCase();
      if (k === "Enter" && draft.end) { e.preventDefault(); void save(); return; }
      if (tag === "TEXTAREA") return;
      if (k === "Backspace") { e.preventDefault(); undo(); return; }
      if (draft.end) {
        if (up === "U") setDraft((d) => ({ ...d, forced: false }));
        if (up === "F") setDraft((d) => ({ ...d, forced: true }));
        return;
      }
      if (up === "R" || up === "M" || up === "L") {
        if (draft.shots.length === 1 && !draft.partial) changeServePlace(up as Place);
        else pickPlace(up as Place);
        return;
      }
      if (draft.shots.length) {
        if (up === "W") { endPoint("winner"); return; }
        if (up === "E") { endPoint("error"); return; }
        if (draft.partial?.stroke) {
          const b = BALLS.find((x) => x.key === up);
          if (b) { pickBall(b.code); return; }
        }
        const s = STROKES.find((x) => x.key === k);
        if (s) pickStroke(s.code);
        return;
      }
      const n = parseInt(k, 10);
      if (!isNaN(n) && n >= 1) {
        if (server === "me" && serves[n - 1]) pickMyServe(serves[n - 1]);
        if (server === "opp" && log.opp_serves_seen[n - 1]) pickSeen(log.opp_serves_seen[n - 1]);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, server, serves, log.opp_serves_seen, cur, busy, hitter]);

  // ---- render helpers ----
  const serveName = (sh: Shot | Partial_) => {
    const mine = sh.serve_id != null ? serves.find((s) => s.id === sh.serve_id) : null;
    return mine ? mine.name : serveDesc(sh);
  };
  const shotText = (sh: Shot) =>
    sh.serve
      ? `giao ${serveName(sh)} → ${placeLabel(sh.place)}`
      : `${labelOf(STROKES, sh.stroke)}${sh.ball ? ` (${labelOf(BALLS, sh.ball).toLowerCase()})` : ""} → ${placeLabel(sh.place)}`;
  const rallyOf = (shots: Shot[]) =>
    shots.map((sh, i) => (
      <span key={i} className="ml-seg-wrap">
        {i > 0 && <span className="ml-arrow">›</span>}
        <span className={`ml-rs ${sh.h}`}>
          <span className="who">{names[sh.h]}</span>
          {shotText(sh)}
        </span>
      </span>
    ));

  const p = draft.partial;
  const seen = log.opp_serves_seen;
  const w = draft.end ? winnerOf(draft.shots, draft.end) : null;
  const last = draft.shots[draft.shots.length - 1];
  const lastName = last ? (last.serve ? "giao bóng" : labelOf(STROKES, last.stroke)) : "";

  const canSaveServe = !!(newServe.name?.trim() && newServe.spin && newServe.length);
  const saveServe = async () => {
    if (!canSaveServe) return;
    const created = await onAddServe({
      name: newServe.name!.trim(),
      stance: newServe.stance ?? null,
      motion: newServe.motion ?? null,
      spin: newServe.spin!,
      amount: newServe.amount ?? null,
      length: newServe.length!,
      place: newServe.place ?? null,
    });
    if (created) {
      setAddingServe(false);
      setNewServe({});
      pickMyServe(created);
    }
  };

  const setsWon = { me: 0, opp: 0 };
  for (let i = 0; i < setCount; i++) {
    const s = setScore(i);
    if (s.me != null && s.opp != null && setOver(s.me, s.opp)) (s.me > s.opp ? setsWon.me++ : setsWon.opp++);
  }

  // What the live row says the user is about to add.
  const draftText = p
    ? p.serve
      ? `${p.name ?? serveDesc(p)} → ?`
      : `${labelOf(STROKES, p.stroke)}${p.ball ? ` (${labelOf(BALLS, p.ball).toLowerCase()})` : ""} → ?`
    : draft.shots.length
      ? "cú tiếp…"
      : "giao bóng…";

  return (
    <div className="ml-charter">
      {/* ---- setup: first server + set scores ---- */}
      <div className="ml-setup">
        <div className="ml-blk">
          <span className="ml-lab">Set 1 · who served first</span>
          <div className="ml-seg">
            {(["me", "opp"] as Side[]).map((s) => (
              <button key={s} type="button" className={firstServer === s ? `on ${s}` : ""} onClick={() => setFirst(s)}>
                {names[s]}
              </button>
            ))}
          </div>
          <span className="ml-hint">Later sets alternate automatically.</span>
        </div>
        <div className="ml-blk">
          <span className="ml-lab">Set scores · type them, or they fill in from the points</span>
          <div className="ml-setrow">
            {Array.from({ length: setCount }, (_, i) => {
              const s = setScore(i);
              const fs = firstServerOf(i);
              return (
                <div key={i} className={`ml-setbox${i === cur ? " active" : ""}`}>
                  <span className="t">
                    Set {i + 1} · <span className={`ml-${fs}`}>{names[fs]}</span> giao đầu
                  </span>
                  <span className="sc">
                    <input
                      id={`ml-set-${match.id}-${i}-me`}
                      value={s.me ?? ""}
                      placeholder="–"
                      disabled={s.fromPts}
                      inputMode="numeric"
                      onChange={(e) => editTyped(i, "my_points", e.target.value.replace(/\D/g, ""))}
                      onBlur={() => saveSets(typed)}
                    />
                    –
                    <input
                      id={`ml-set-${match.id}-${i}-opp`}
                      value={s.opp ?? ""}
                      placeholder="–"
                      disabled={s.fromPts}
                      inputMode="numeric"
                      onChange={(e) => editTyped(i, "opp_points", e.target.value.replace(/\D/g, ""))}
                      onBlur={() => saveSets(typed)}
                    />
                  </span>
                  <span className={`from${s.fromPts ? " pts" : ""}`}>
                    {s.fromPts ? `${pointsBySet[i].length} pts logged ✓` : s.me != null || s.opp != null ? "typed score" : "no score"}
                  </span>
                  {i !== cur && (
                    <button type="button" className="open" onClick={() => { setCur(i); setDraft(emptyDraft()); }}>
                      {pointsBySet[i].length ? "open" : "log points ›"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        <div className="ml-summary">
          Sets <b className="ml-me">{setsWon.me}</b> – <b className="ml-opp">{setsWon.opp}</b>
          <span className="ml-hint"> · match result {match.my_sets}–{match.opp_sets}</span>
        </div>
      </div>

      {/* ---- palette ---- */}
      <div className="ml-card ml-palette">
        <div className="ml-now">
          <span className="ml-now-set">Set {cur + 1}</span>
          <span className="ml-now-pt">Point {pointNo}</span>
          <span className="ml-now-score"><b className="ml-me">{sc.me}</b> – <b className="ml-opp">{sc.opp}</b></span>
          {!over && (
            <span className={`ml-now-srv ${server}`}>🏓 {names[server]} giao bóng</span>
          )}
        </div>

        <div className="ml-stage">
          {over ? (
            <div className="ml-setover">
              Set {cur + 1} over · {sc.me}–{sc.opp} to {sc.me > sc.opp ? names.me : names.opp}
              {cur < setCount - 1 && (
                <button type="button" className="btn" onClick={() => { setCur(cur + 1); setDraft(emptyDraft()); }}>
                  Set {cur + 2} ›
                </button>
              )}
              <span className="ml-hint">· delete a point below to correct it</span>
            </div>
          ) : draft.end ? (
            <>
              {draft.end === "error" && (
                <ChipRow
                  label="Lỗi"
                  choices={[
                    { code: "unforced", label: "Tự hỏng (unforced)", key: "U" },
                    { code: "forced", label: "Bị ép hỏng (forced)", key: "F" },
                  ]}
                  value={draft.forced ? "forced" : "unforced"}
                  onPick={(c) => setDraft((d) => ({ ...d, forced: c === "forced" }))}
                />
              )}
              <div className="ml-row">
                <div className="ml-lab">Ghi chú</div>
                <textarea
                  id={`ml-note-${match.id}`}
                  className="ml-note"
                  value={draft.note}
                  placeholder="Điều chip không tả được — vd: 'quả mổ xuống ngắn, tôi đứng xa bàn quá'"
                  onChange={(e) => setDraft((d) => ({ ...d, note: e.target.value }))}
                />
              </div>
            </>
          ) : draft.shots.length === 0 ? (
            server === "me" ? (
              <>
                <div className="ml-row">
                  <div className="ml-lab">Bài giao của tôi</div>
                  <div className="ml-chips">
                    {serves.map((s, i) => (
                      <button key={s.id} type="button" className="ml-chip srv me" onClick={() => pickMyServe(s)}>
                        <span className="n">{s.name}<kbd>{i + 1}</kbd></span>
                        <span className="d">{serveDesc(s)}{s.place ? ` → ${labelOf(PLACES, s.place)}` : ""}</span>
                      </button>
                    ))}
                    {!addingServe && (
                      <button type="button" className="ml-chip ghost" onClick={() => setAddingServe(true)}>
                        ＋ Thêm bài giao mới
                      </button>
                    )}
                  </div>
                </div>
                {addingServe && (
                  <div className="ml-addform">
                    <span className="ml-sub-h">Bài giao mới · lưu vào kho của {names.me}, dùng cho mọi đối thủ</span>
                    <input
                      id={`ml-newserve-${match.id}`}
                      type="text"
                      className="pb-input"
                      placeholder="Tên bài giao, vd: Lệch phải · ngang-xuống ngắn trái"
                      value={newServe.name ?? ""}
                      onChange={(e) => setNewServe((n) => ({ ...n, name: e.target.value }))}
                    />
                    <ChipRow label="Vị trí đứng" choices={STANCES} value={newServe.stance} onPick={(c) => setNewServe((n) => ({ ...n, stance: c }))} />
                    <ChipRow label="Động tác" choices={MOTIONS} value={newServe.motion} onPick={(c) => setNewServe((n) => ({ ...n, motion: c }))} />
                    <ChipRow label="Xoáy" choices={SPINS} value={newServe.spin} onPick={(c) => setNewServe((n) => ({ ...n, spin: c }))} />
                    <ChipRow label="Độ xoáy" choices={AMOUNTS} value={newServe.amount} onPick={(c) => setNewServe((n) => ({ ...n, amount: c }))} />
                    <ChipRow label="Độ dài" choices={LENGTHS} value={newServe.length} onPick={(c) => setNewServe((n) => ({ ...n, length: c }))} />
                    <ChipRow label="Rơi (bàn đối thủ)" choices={PLACES} value={newServe.place} onPick={(c) => setNewServe((n) => ({ ...n, place: c }))} />
                    <div className="ml-actions">
                      <button type="button" className="btn primary" disabled={!canSaveServe || busy} onClick={() => void saveServe()}>Save serve</button>
                      <button type="button" className="btn" onClick={() => { setAddingServe(false); setNewServe({}); }}>Cancel</button>
                    </div>
                  </div>
                )}
                {p?.serve && (
                  <ChipRow label={`Rơi (bàn ${names.opp})`} choices={PLACES} value={null} onPick={pickPlace} />
                )}
                <span className="ml-hint">
                  Phải / Giữa / Trái luôn theo phía <b>người đỡ</b>: giao qua Phải = bên phải của {names.opp}.
                </span>
              </>
            ) : (
              <>
                {seen.length > 0 && (
                  <div className="ml-row">
                    <div className="ml-lab">Kiểu giao của {names.opp} đã thấy</div>
                    <div className="ml-chips">
                      {seen.map((s, i) => (
                        <button
                          key={i}
                          type="button"
                          className={`ml-chip srv opp${p?.fromSeen && sameServe(p, s) ? " on" : ""}`}
                          onClick={() => pickSeen(s)}
                        >
                          <span className="n">{serveDesc(s)}<kbd>{i + 1}</kbd></span>
                          <span className="d">đã thấy {s.count}×</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {(!seen.length || !p?.fromSeen) && (
                  <>
                    {seen.length > 0 && <span className="ml-sub-h">…hoặc kiểu giao mới của {names.opp}:</span>}
                    <ChipRow label="Vị trí đứng" choices={STANCES} value={p?.fromSeen ? null : p?.stance} onPick={(c) => setServeAttr("stance", c)} />
                    <ChipRow label="Động tác" choices={MOTIONS} value={p?.fromSeen ? null : p?.motion} onPick={(c) => setServeAttr("motion", c)} />
                    <ChipRow label="Xoáy" choices={SPINS} value={p?.fromSeen ? null : p?.spin} onPick={(c) => setServeAttr("spin", c)} />
                    <ChipRow label="Độ xoáy" choices={AMOUNTS} value={p?.fromSeen ? null : p?.amount} onPick={(c) => setServeAttr("amount", c)} />
                    <ChipRow label="Độ dài" choices={LENGTHS} value={p?.fromSeen ? null : p?.length} onPick={(c) => setServeAttr("length", c)} />
                  </>
                )}
                {serveReady(p) && (
                  <ChipRow label={`Rơi (bàn ${names.me})`} choices={PLACES} value={null} onPick={pickPlace} />
                )}
              </>
            )
          ) : (
            <>
              {draft.shots.length === 1 && !p && (
                <ChipRow label={`Giao rơi (bàn ${names[other(server)]})`} choices={PLACES} value={draft.shots[0].place} onPick={changeServePlace} />
              )}
              <ChipRow label={`${names[hitter]} đánh`} choices={STROKES} value={p?.stroke} onPick={pickStroke} />
              {p?.stroke && (
                <ChipRow label="Bóng tới (tùy chọn)" choices={BALLS} value={p.ball} onPick={pickBall} />
              )}
              <ChipRow
                label={`Rơi (bàn ${names[other(hitter)]})`}
                choices={PLACES}
                value={null}
                onPick={pickPlace}
                extra={
                  p?.stroke ? (
                    <button type="button" className="ml-chip err" onClick={() => endPoint("error")}>
                      ✗ {names[hitter]} {labelOf(STROKES, p.stroke)} hỏng (lưới / ra ngoài)<kbd>E</kbd>
                    </button>
                  ) : undefined
                }
              />
              {!p?.stroke && (
                <div className="ml-row">
                  <div className="ml-lab">Kết thúc</div>
                  <div className="ml-chips">
                    <button type="button" className="ml-chip big win" onClick={() => endPoint("winner")}>
                      ✓ {names[last.h]} {lastName} ăn điểm trực tiếp<kbd>W</kbd>
                    </button>
                    <button type="button" className="ml-chip big err" onClick={() => endPoint("error")}>
                      ✗ {names[last.h]} {lastName} hỏng (lưới / ra ngoài)<kbd>E</kbd>
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ---- live row ---- */}
        {!over && (
          <div className={`ml-line live${draft.end ? (w === "me" ? " won-me" : " won-opp") : ""}`}>
            <span className="ml-line-no">#{pointNo}</span>
            <span className="ml-line-sc">{sc.me}–{sc.opp}</span>
            <span className={`ml-srvdot ${server}`} title={`${names[server]} serves`} />
            <span className="ml-line-rally">
              {rallyOf(draft.shots)}
              {!draft.end ? (
                <span className="ml-seg-wrap">
                  {draft.shots.length > 0 && <span className="ml-arrow">›</span>}
                  <span className={`ml-rs ${hitter} draft`}>
                    <span className="who">{names[hitter]}</span>
                    {draftText}
                  </span>
                </span>
              ) : (
                <span className="ml-seg-wrap">
                  <span className="ml-arrow">›</span>
                  <span className={`ml-rs end ${draft.end === "winner" ? "win" : "err"}`}>
                    {draft.end === "winner" ? "✓ ăn điểm" : draft.forced ? "✗ bị ép hỏng" : "✗ tự hỏng"} · <b>+1 {names[w!]}</b> → {sc.me + (w === "me" ? 1 : 0)}–{sc.opp + (w === "opp" ? 1 : 0)}
                  </span>
                </span>
              )}
            </span>
            <span className="ml-line-actions">
              {draft.end && (
                <button type="button" className="btn primary" disabled={busy} onClick={() => void save()}>
                  Save point <kbd>Enter</kbd>
                </button>
              )}
              {(draft.shots.length > 0 || draft.partial) && (
                <button type="button" className="btn" onClick={undo}>↶ Undo <kbd>⌫</kbd></button>
              )}
            </span>
          </div>
        )}
      </div>

      {/* ---- ledger: logged points of this set, newest first ---- */}
      <div className="ml-card">
        <h4 className="ml-card-h">
          <span>Points · set {cur + 1}</span>
          <span className="cnt">{pointsBySet[cur].length ? `${pointsBySet[cur].length} logged · newest first` : ""}</span>
        </h4>
        {pointsBySet[cur].length === 0 ? (
          <p className="ml-empty">No points yet in this set.</p>
        ) : (
          <div className="ml-ledger">
            {[...pointsBySet[cur]].reverse().map((pt, idx) => {
              const i = pointsBySet[cur].length - 1 - idx;
              const after = scoreOf(cur, i + 1);
              return (
                <div key={pt.id} className={`ml-line ${pt.winner === "me" ? "won-me" : "won-opp"}`}>
                  <span className="ml-line-no">#{i + 1}</span>
                  <span className="ml-line-sc">{after.me}–{after.opp}</span>
                  <span className={`ml-srvdot ${pt.server}`} title={`${names[pt.server]} served`} />
                  <span className="ml-line-rally">
                    {rallyOf(pt.shots)}
                    <span className="ml-seg-wrap">
                      <span className="ml-arrow">›</span>
                      <span className={`ml-rs end ${pt.end_kind === "winner" ? "win" : "err"}`}>
                        {pt.end_kind === "winner" ? "✓ ăn điểm" : pt.forced ? "✗ bị ép hỏng" : "✗ tự hỏng"} · <b>+1 {names[pt.winner]}</b>
                      </span>
                    </span>
                    {pt.note && <span className="ml-pt-note">“{pt.note}”</span>}
                  </span>
                  <span className="ml-line-actions">
                    <button type="button" className="ml-del" title="Delete this point" disabled={busy} onClick={() => void onDeletePoint(pt.id)}>✕</button>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
