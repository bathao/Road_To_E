// "About me" scouting file on the Profile tab (moved here from the Tactics
// tab 2026-10-10 — user: "Scouting about Me cũng ko nên nằm đây … move qua
// Profile … ko nên duplicate display này với mọi đối thủ"). Same data, same
// widgets: global facts (player_id null) the coach never re-asks, plus the
// fixed intake questions that are still unanswered.
import { useLoad, useMutate } from "../../../shared/useApi";
import { tacticsApi } from "../../tactics/api";
import FactsPanel from "../../tactics/components/FactsPanel";
import IntakeCard from "../../tactics/components/IntakeCard";
import { ME_INTAKE, type IntakeItem } from "../../tactics/intake";
import type { FactKind, FactsOut } from "../../tactics/types";

export default function ScoutingMeCard() {
  const { run, error, busy, clearError } = useMutate();
  // The facts endpoint is keyed by opponent; 0 = no opponent → only the
  // global me-list comes back filled.
  const { data: facts, setData: setFacts } = useLoad<FactsOut>(
    () => tacticsApi.getFacts(0),
    []
  );
  const refresh = async () => {
    const out = await run(() => tacticsApi.getFacts(0));
    if (out !== undefined) setFacts(out);
  };
  const add = async (kind: FactKind, text: string) => {
    const out = await run(() => tacticsApi.addFact(null, kind, text));
    if (out === undefined) return false;
    await refresh();
    return true;
  };
  const answer = async (item: IntakeItem, text: string) => {
    const out = await run(() => tacticsApi.addFact(null, item.kind, text, item.key));
    if (out === undefined) return false;
    await refresh();
    return true;
  };
  const edit = async (id: number, text: string) => {
    const out = await run(() => tacticsApi.updateFact(id, text));
    if (out === undefined) return false;
    await refresh();
    return true;
  };
  const remove = async (id: number) => {
    const out = await run(() => tacticsApi.deleteFact(id));
    if (out !== undefined) await refresh();
  };

  return (
    <section className="stats-card prof-scouting">
      <h3>🔍 Scouting file · about me</h3>
      {error && (
        <div className="error-banner" onClick={clearError}>⚠ {error}</div>
      )}
      <FactsPanel
        title="What the AI coach knows about my game"
        hint="Saved once, read for every opponent — the coach never re-asks these. It also files anything about you it spots in your notes (🧠)."
        facts={facts?.me ?? []}
        busy={busy}
        intake={
          <IntakeCard
            items={ME_INTAKE}
            facts={facts?.me ?? []}
            busy={busy}
            onAnswer={answer}
          />
        }
        onAdd={add}
        onEdit={edit}
        onDelete={remove}
      />
    </section>
  );
}
