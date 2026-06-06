import type { LevelRecord, PlayerLevel } from "../types";

const LABEL: Record<PlayerLevel, string> = {
  below: "Dưới tôi",
  equal: "Ngang tôi",
  above: "Hơn tôi",
};

// Win-rate by opponent level as horizontal progress bars — reads cleanly and
// handles "no matches yet" (0-0) gracefully, unlike floating vertical bars.
export default function LevelBars({ levels }: { levels: LevelRecord[] }) {
  return (
    <div className="lvl-rows">
      {levels.map((l) => {
        const s = l.stats;
        const has = s.total > 0;
        const wr = s.win_rate;
        const pctNum = wr === null ? 0 : Math.round(wr * 100);
        return (
          <div className="lvl-row" key={l.level}>
            <span className="lvl-name">{LABEL[l.level]}</span>
            <div className="lvl-track">
              <div
                className={`lvl-fill level-${l.level}`}
                style={{ width: `${pctNum}%` }}
              />
            </div>
            <span className="lvl-meta">
              {has ? (
                <>
                  <b>{wr === null ? "—" : `${pctNum}%`}</b>{" "}
                  <span className="lvl-rec">
                    ({s.wins}-{s.losses}
                    {s.ties ? `-${s.ties}` : ""})
                  </span>
                </>
              ) : (
                <span className="lvl-rec">chưa có trận</span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}
