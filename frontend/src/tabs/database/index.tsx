// Database tab: every player in the pool, with hand-maintained BBTV points.
// Points are STATIC anchors (only the user's own rating is dynamic — the
// upcoming ELO updates it per match); rank (G/F/E…) derives from points.
// The legacy relative labels (below/equal/above) live only in the DB now —
// hidden from this tab, superseded by points.
import { useMemo, useRef, useState } from "react";
import { useLoad, useMutate } from "../../shared/useApi";
import { pointsLabel, rankOf } from "../../shared/rank";
import LineChart from "../../shared/ui/LineChart";
import { databaseApi } from "./api";
import type {
  MyRating,
  MyRatingHistory,
  PlayerDbRow,
  PlayersDbResponse,
} from "./types";

// The whole project's target band: E starts at 1201 BBTV points.
const RANK_E_FLOOR = 1201;

// "2026-07-27" → "27/07" for chart labels.
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

// ELO curve since the anchor. LineChart scales 0..max, which would flatten a
// curve hovering around ~950 — so values are re-based near the observed min
// and formatY maps gridline values back to real ratings.
function RatingChart({ history }: { history: MyRatingHistory }) {
  if (history.points.length < 2) return null;
  const base = Math.min(...history.points.map((p) => p.rating)) - 20;
  return (
    <div className="db-chart">
      <h3>📈 Đường điểm ELO (từ neo {shortDate(history.anchor_date)})</h3>
      <LineChart
        points={history.points.map((p) => ({
          label: shortDate(p.date),
          value: p.rating - base,
          display: String(p.rating),
          tip: p.date,
        }))}
        formatY={(v) => String(Math.round(v + base))}
      />
    </div>
  );
}

// "2026-07-27" → "27/07/2026" for the anchor note.
function fmtAnchor(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function RankChip({ points }: { points: number | null }) {
  const rank = rankOf(points);
  if (!rank) return <span className="db-rank db-rank-none">chưa xếp</span>;
  return <span className={`db-rank db-rank-${rank}`}>{rank}</span>;
}

// One row: points edited locally, saved on blur/Enter (only when changed).
// Save feedback: ✓ fades out on success, red input border on failure.
function PlayerRow({
  p,
  busy,
  onSave,
}: {
  p: PlayerDbRow;
  busy: boolean;
  onSave: (p: PlayerDbRow, points: number | null, playsPips: boolean) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState(p.points === null ? "" : String(p.points));
  const [flash, setFlash] = useState<"saved" | "failed" | null>(null);
  const flashTimer = useRef<number | undefined>(undefined);
  const parsed = draft.trim() === "" ? null : Number(draft);
  const dirty = parsed !== p.points;
  const valid = parsed === null || (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 3000);

  const doSave = async (points: number | null, playsPips: boolean) => {
    const ok = await onSave(p, points, playsPips);
    window.clearTimeout(flashTimer.current);
    setFlash(ok ? "saved" : "failed");
    if (ok) flashTimer.current = window.setTimeout(() => setFlash(null), 1500);
  };

  const save = () => {
    if (!dirty || !valid || parsed === null) return; // clearing isn't supported
    void doSave(parsed, p.plays_pips);
  };

  return (
    <tr className={p.points === null ? "db-row-unrated" : ""}>
      <td className="db-name">{p.name}</td>
      <td className="db-points">
        <input
          type="number"
          min={0}
          max={3000}
          placeholder="—"
          className={flash === "failed" ? "db-input-failed" : undefined}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (flash === "failed") setFlash(null);
          }}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
        />
        {dirty && valid && parsed !== null && (
          <span className="db-dirty" title="Chưa lưu — rời ô hoặc Enter để lưu">
            ●
          </span>
        )}
        {flash === "saved" && !dirty && (
          <span className="db-saved" title="Đã lưu">
            ✓
          </span>
        )}
        {flash === "failed" && (
          <span className="db-failed" title="Lưu thất bại — thử lại">
            ✕
          </span>
        )}
      </td>
      <td>
        <RankChip points={p.points} />
      </td>
      <td className="db-pips">
        <label>
          <input
            type="checkbox"
            checked={p.plays_pips}
            disabled={busy}
            onChange={(e) => void doSave(p.points, e.target.checked)}
          />
          🏓 gai
        </label>
      </td>
      <td className="db-count">{p.matches_played}</td>
    </tr>
  );
}

export default function DatabaseTab() {
  const { data, setData, error: loadError } = useLoad<PlayersDbResponse>(
    () => databaseApi.list(),
    []
  );
  const { data: myRating, setData: setMyRating } = useLoad<MyRating>(
    () => databaseApi.getMyRating(),
    []
  );
  // Refetches whenever the anchor moves (a manual save changes myRating).
  const { data: history } = useLoad<MyRatingHistory>(
    () => databaseApi.ratingHistory(),
    [myRating?.points, myRating?.anchor_date]
  );
  const { run, error, busy, clearError } = useMutate();
  const [query, setQuery] = useState("");
  const [myDraft, setMyDraft] = useState<string | null>(null); // null = not editing

  const players = data?.players ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? players.filter((p) => p.name.toLowerCase().includes(q)) : players;
  }, [players, query]);
  const rated = players.filter((p) => p.points !== null).length;

  const saveRow = async (
    p: PlayerDbRow,
    points: number | null,
    playsPips: boolean
  ): Promise<boolean> => {
    const out = await run(() =>
      databaseApi.updatePlayer(p.id, {
        name: p.name,
        level: p.level,
        note: p.note ?? null,
        plays_pips: playsPips,
        points,
      })
    );
    if (out === undefined || !data) return false;
    // Patch locally — no full reload, the list keeps its scroll position.
    setData({
      players: data.players.map((x) =>
        x.id === p.id ? { ...x, points, plays_pips: playsPips } : x
      ),
    });
    return true;
  };

  // Saving the unchanged anchor is blocked: a new anchor restarts the ELO
  // replay from today, so an accidental re-save would drop every counted
  // match (the backend guards this too).
  const myDraftDirty =
    myDraft !== null &&
    myDraft.trim() !== "" &&
    Number(myDraft) !== myRating?.points;

  const saveMyRating = async () => {
    const n = Number(myDraft);
    if (!myDraftDirty || Number.isNaN(n) || n < 0 || n > 3000) return;
    const out = await run(() => databaseApi.setMyRating(n));
    if (out !== undefined) {
      setMyRating(out);
      setMyDraft(null);
    }
  };

  return (
    <div className="db-tab">
      <div className="db-head">
        <div>
          <h2>🗄️ Database VĐV</h2>
          <p className="db-sub">
            Điểm của từng người — mốc tĩnh, anh tự cập nhật khi họ lên/xuống
            trình. Trình (G/F/E…) suy ra từ điểm.
          </p>
        </div>
        <div className="db-me">
          <span className="db-me-label">Điểm của tôi</span>
          {myDraft === null ? (
            <>
              <span className="db-me-points">
                {pointsLabel(myRating?.current)}
              </span>
              {myRating && myRating.current < RANK_E_FLOOR && (
                <span
                  className="db-me-to-e"
                  title={`Hạng E bắt đầu từ ${RANK_E_FLOOR} điểm`}
                >
                  còn {RANK_E_FLOOR - myRating.current} tới E
                </span>
              )}
              <button
                className="btn"
                title="Sửa mốc neo — ELO sẽ tính lại từ hôm nay"
                onClick={() => setMyDraft(String(myRating?.points ?? ""))}
              >
                Sửa
              </button>
            </>
          ) : (
            <>
              <input
                type="number"
                min={0}
                max={3000}
                value={myDraft}
                onChange={(e) => setMyDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveMyRating();
                }}
              />
              <button
                className="btn primary"
                disabled={busy || !myDraftDirty}
                title={
                  myDraftDirty
                    ? "Đặt neo mới từ hôm nay — ELO tính lại từ đây"
                    : "Điểm neo chưa thay đổi"
                }
                onClick={saveMyRating}
              >
                Lưu
              </button>
              <button className="btn" onClick={() => setMyDraft(null)}>
                Hủy
              </button>
            </>
          )}
          <span className="db-me-note">
            {myRating
              ? `ELO động · neo ${myRating.points} từ ${fmtAnchor(
                  myRating.anchor_date
                )} · đã tính ${myRating.counted_matches} trận (đơn + đôi, chấp đã quy đổi)`
              : "điểm động duy nhất (ELO)"}
          </span>
        </div>
      </div>

      {(error || loadError) && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error ?? loadError}
        </div>
      )}

      <div className="db-toolbar">
        <input
          type="text"
          className="db-search"
          placeholder="Tìm tên…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="db-progress">
          Đã xếp điểm {rated}/{players.length} người
        </span>
      </div>

      {history && <RatingChart history={history} />}

      <div className="db-table-wrap">
        <table className="db-table">
          <thead>
            <tr>
              <th>Tên</th>
              <th>Điểm</th>
              <th>Trình</th>
              <th>Đánh gai</th>
              <th title="Số lần xuất hiện trong các trận (đối thủ/đồng đội)">
                Trận
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <PlayerRow key={p.id} p={p} busy={busy} onSave={saveRow} />
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="db-empty">Không có ai khớp “{query}”.</div>
        )}
      </div>
    </div>
  );
}
