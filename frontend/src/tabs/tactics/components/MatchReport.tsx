// Shot statistics derived from charted points — one match, or every charted
// match against one opponent. Pure rendering of the backend's StatsOut.
import type { Serve, Stats } from "../types";
import {
  ATTACK_STROKES,
  RALLY_BUCKETS,
  STROKES,
  labelOf,
  placeLabel,
  serveDesc,
} from "../vocab";

const pct = (won: number, played: number) =>
  played ? `${Math.round((100 * won) / played)}%` : "—";

export default function MatchReport({
  stats,
  serves,
  names,
}: {
  stats: Stats;
  serves: Serve[];
  names: { me: string; opp: string };
}) {
  if (!stats.points) {
    return <p className="ml-empty">Stats appear as points get logged.</p>;
  }
  const atkRows = STROKES.filter((s) => ATTACK_STROKES.has(s.code) && stats.attacks[s.code]);
  const errRows = (t: Record<string, [number, number]>, who: string) =>
    Object.entries(t).map(([k, v]) => (
      <tr key={who + k}>
        <td>{who}: {labelOf(STROKES, k)}</td>
        <td className="num">{v[0]}</td>
        <td className="num">{v[1]}</td>
      </tr>
    ));
  const winRows = (t: Record<string, number>, who: string) =>
    Object.entries(t).map(([k, v]) => (
      <tr key={who + k}>
        <td>{who}: {labelOf(STROKES, k)}</td>
        <td className="num">{v}</td>
      </tr>
    ));
  const serveLabel = (s: Stats["serves"][number]) => {
    const mine = s.serve_id != null ? serves.find((x) => x.id === s.serve_id) : null;
    return `${mine ? mine.name : serveDesc(s)} → ${placeLabel(s.place)}`;
  };

  return (
    <div className="ml-report">
      <div className="ml-kpis">
        <div className="ml-kpi"><span className="k">Points</span><span className="v"><b className="ml-me">{stats.points_me}</b> – <b className="ml-opp">{stats.points_opp}</b></span><span className="s">{stats.matches} match{stats.matches === 1 ? "" : "es"} · {stats.points} pts</span></div>
        <div className="ml-kpi"><span className="k">On my serve</span><span className="v">{pct(stats.on_my_serve[1], stats.on_my_serve[0])}</span><span className="s">{stats.on_my_serve[1]} / {stats.on_my_serve[0]} won</span></div>
        <div className="ml-kpi"><span className="k">On {names.opp}'s serve</span><span className="v">{pct(stats.on_opp_serve[1], stats.on_opp_serve[0])}</span><span className="s">{stats.on_opp_serve[1]} / {stats.on_opp_serve[0]} won</span></div>
        <div className="ml-kpi"><span className="k">From 8–8 on</span><span className="v"><b className="ml-me">{stats.clutch[0]}</b> – <b className="ml-opp">{stats.clutch[1]}</b></span><span className="s">clutch points</span></div>
      </div>

      <div className="ml-report-grid">
        <div>
          <p className="ml-stat-h">Cú tấn công của tôi · ăn / thua / hỏng · theo điểm rơi bên bàn {names.opp}</p>
          <div className="ml-table-wrap">
            <table className="ml-table">
              <thead><tr><th>Cú</th><th className="num">Phải</th><th className="num">Giữa</th><th className="num">Trái</th><th className="num">Tổng</th></tr></thead>
              <tbody>
                {atkRows.length === 0 && <tr><td colSpan={5} className="ml-empty">No attacking shots logged yet.</td></tr>}
                {atkRows.map((s) => {
                  const row = stats.attacks[s.code];
                  const tot = [0, 0, 0];
                  // "-" = missed with no landing spot given: counts in the total only.
                  Object.values(row).forEach((v) => v.forEach((n, i) => (tot[i] += n)));
                  const cell = (v?: [number, number, number]) =>
                    v && v[0] + v[1] + v[2] ? (
                      <><span className="ml-good">{v[0]}</span> / {v[1]} / <span className="ml-bad">{v[2]}</span></>
                    ) : (
                      <span className="ml-dim">·</span>
                    );
                  return (
                    <tr key={s.code}>
                      <td>{s.label}</td>
                      <td className="num">{cell(row.R)}</td>
                      <td className="num">{cell(row.M)}</td>
                      <td className="num">{cell(row.L)}</td>
                      <td className="num">{cell(tot as [number, number, number])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <p className="ml-stat-h">Lỗi · tự hỏng / bị ép</p>
          <table className="ml-table">
            <thead><tr><th>Cú</th><th className="num">Tự hỏng</th><th className="num">Bị ép</th></tr></thead>
            <tbody>
              {Object.keys(stats.errors_me).length + Object.keys(stats.errors_opp).length === 0 && (
                <tr><td colSpan={3} className="ml-empty">None yet.</td></tr>
              )}
              {errRows(stats.errors_me, names.me)}
              {errRows(stats.errors_opp, names.opp)}
            </tbody>
          </table>
        </div>

        <div>
          <p className="ml-stat-h">Cú ăn điểm trực tiếp</p>
          <table className="ml-table">
            <thead><tr><th>Cú</th><th className="num">Số lần</th></tr></thead>
            <tbody>
              {Object.keys(stats.winners_me).length + Object.keys(stats.winners_opp).length === 0 && (
                <tr><td colSpan={2} className="ml-empty">None yet.</td></tr>
              )}
              {winRows(stats.winners_me, names.me)}
              {winRows(stats.winners_opp, names.opp)}
            </tbody>
          </table>
        </div>

        <div>
          <p className="ml-stat-h">Giao bóng · số điểm / % người giao thắng</p>
          <table className="ml-table">
            <thead><tr><th>Bài giao → rơi</th><th className="num">Điểm</th><th className="num">Thắng</th></tr></thead>
            <tbody>
              {stats.serves.map((s, i) => (
                <tr key={i}>
                  <td><span className={`ml-srvdot ${s.side}`} />{s.side === "me" ? names.me : names.opp}: {serveLabel(s)}</td>
                  <td className="num">{s.played}</td>
                  <td className="num">{pct(s.won, s.played)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <p className="ml-stat-h">Đỡ giao bóng · điểm thắng / thua / đỡ hư</p>
          <table className="ml-table">
            <thead><tr><th>Cú đỡ</th><th className="num">Thắng</th><th className="num">Thua</th><th className="num">Đỡ hư</th></tr></thead>
            <tbody>
              {Object.keys(stats.receive_me).length + Object.keys(stats.receive_opp).length === 0 && <tr><td colSpan={4} className="ml-empty">None yet.</td></tr>}
              {Object.entries(stats.receive_me).map(([k, v]) => (
                <tr key={"me" + k}><td>{names.me}: {labelOf(STROKES, k)}</td><td className="num">{v[0]}</td><td className="num">{v[1]}</td><td className="num"><span className={v[2] ? "ml-bad" : "ml-dim"}>{v[2]}</span></td></tr>
              ))}
              {Object.entries(stats.receive_opp).map(([k, v]) => (
                <tr key={"opp" + k}><td>{names.opp}: {labelOf(STROKES, k)}</td><td className="num">{v[0]}</td><td className="num">{v[1]}</td><td className="num"><span className={v[2] ? "ml-bad" : "ml-dim"}>{v[2]}</span></td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <p className="ml-stat-h">Độ dài rally · điểm {names.me} / {names.opp}</p>
          <table className="ml-table">
            <tbody>
              {RALLY_BUCKETS.map(([code, label]) => {
                const v = stats.rally_len[code] ?? [0, 0];
                return (
                  <tr key={code}><td>{label}</td><td className="num"><span className="ml-me">{v[0]}</span> / <span className="ml-opp">{v[1]}</span></td></tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {stats.notes.length > 0 && (
        <div>
          <p className="ml-stat-h">Ghi chú theo điểm</p>
          <ul className="ml-notes">
            {stats.notes.map((n, i) => (
              <li key={i}>
                <span className="ml-dim">{n.date ? `${n.date} · ` : ""}set {n.set_no} · {n.score}</span> “{n.note}”
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
