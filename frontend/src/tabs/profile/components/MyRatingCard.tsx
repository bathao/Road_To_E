// The user's dynamic ELO — the big number, the "còn X tới E" chip, the anchor
// edit and the since-anchor curve. Moved here from the Database tab
// (2026-07-27): the Database keeps other players' STATIC points; my own
// rating is a progress-tracking concern, so it lives on the Profile.
import { useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { pointsLabel } from "../../../shared/rank";
import LineChart from "../../../shared/ui/LineChart";
import { profileApi } from "../api";
import type { MyRating, MyRatingHistory } from "../types";

// The whole project's target band: E starts at 1201 BBTV points.
const RANK_E_FLOOR = 1201;

// "2026-07-27" → "27/07" for chart labels.
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

// "2026-07-27" → "27/07/2026" for the anchor note.
function fmtAnchor(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
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

export default function MyRatingCard() {
  const { data: myRating, setData: setMyRating, error: loadError } =
    useLoad<MyRating>(() => profileApi.getMyRating(), []);
  // Refetches whenever the anchor moves (a manual save changes myRating).
  const { data: history } = useLoad<MyRatingHistory>(
    () => profileApi.ratingHistory(),
    [myRating?.points, myRating?.anchor_date]
  );
  const { run, error, busy } = useMutate();
  const [myDraft, setMyDraft] = useState<string | null>(null); // null = not editing

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
    const out = await run(() => profileApi.setMyRating(n));
    if (out !== undefined) {
      setMyRating(out);
      setMyDraft(null);
    }
  };

  return (
    <section className="va-card">
      <h3>🎯 Điểm ELO của tôi</h3>
      <div className="db-me">
        {myDraft === null ? (
          <>
            <span className="db-me-points">{pointsLabel(myRating?.current)}</span>
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
              )} · đã tính ${myRating.counted_matches} trận (đơn + đôi + 1v2/2v1, chấp đã quy đổi)`
            : "điểm động duy nhất (ELO)"}
        </span>
      </div>
      {(error || loadError) && <div className="pb-error">⚠ {error ?? loadError}</div>}
      {history && <RatingChart history={history} />}
    </section>
  );
}
