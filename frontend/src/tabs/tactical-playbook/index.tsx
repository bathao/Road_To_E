import { useMemo, useState } from "react";
import { useLoad, useMutate } from "../../shared/useApi";
import Modal from "../../shared/ui/Modal";
import { playbookApi } from "./api";
import { PHASE_ICON } from "./constants";
import TacticCard from "./components/TacticCard";
import TacticEditor from "./components/TacticEditor";
import type {
  LibraryItem,
  PhaseKey,
  PlaybookMeta,
  Tactic,
  TacticIn,
} from "./types";

type PhaseFilter = PhaseKey | "all";

// Turn a stored tactic back into an editable payload (for update / favorite).
function toPayload(t: Tactic): TacticIn {
  return {
    phase: t.phase,
    title: t.title,
    when_to_use: t.when_to_use,
    how_to: t.how_to,
    follow_up: t.follow_up,
    risk: t.risk,
    opponent_styles: t.opponent_styles,
    tags: t.tags,
    confidence: t.confidence,
    is_favorite: t.is_favorite,
    source_key: t.source_key,
  };
}

function haystack(t: {
  title: string;
  when_to_use: string | null;
  how_to: string | null;
  follow_up: string | null;
  risk: string | null;
  tags: string[];
  opponent_styles: string[];
}): string {
  return [
    t.title,
    t.when_to_use,
    t.how_to,
    t.follow_up,
    t.risk,
    ...t.tags,
    ...t.opponent_styles,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export default function TacticalPlaybook() {
  const [phase, setPhase] = useState<PhaseFilter>("all");
  const [search, setSearch] = useState("");
  const [favOnly, setFavOnly] = useState(false);
  const [oppFilter, setOppFilter] = useState("");
  const [libOpen, setLibOpen] = useState(true);

  // null = closed; otherwise the payload + (optional) id being edited.
  const [editing, setEditing] = useState<{
    id: number | null;
    payload: TacticIn;
  } | null>(null);

  // Meta + library load once; tactics reload after every mutation.
  const staticLoad = useLoad<[PlaybookMeta, LibraryItem[]]>(
    () => Promise.all([playbookApi.getMeta(), playbookApi.getLibrary()]),
    []
  );
  const meta = staticLoad.data?.[0] ?? null;
  const library = staticLoad.data?.[1] ?? [];

  const tacticsLoad = useLoad<Tactic[]>(() => playbookApi.getTactics(), []);
  const tactics = tacticsLoad.data ?? [];
  const reloadTactics = tacticsLoad.reload;

  const { run, error: mutateError } = useMutate();
  const error = mutateError ?? tacticsLoad.error ?? staticLoad.error;

  // Which Library items are already in My Tactics (by source_key).
  const addedKeys = useMemo(
    () => new Set(tactics.map((t) => t.source_key).filter(Boolean) as string[]),
    [tactics]
  );

  const q = search.trim().toLowerCase();
  const matchesCommon = (t: Parameters<typeof haystack>[0] & { phase: PhaseKey }) =>
    (phase === "all" || t.phase === phase) &&
    (!q || haystack(t).includes(q)) &&
    (!oppFilter || t.opponent_styles.includes(oppFilter));

  const myFiltered = tactics.filter(
    (t) => matchesCommon(t) && (!favOnly || t.is_favorite)
  );
  const libFiltered = library.filter(matchesCommon);

  // Per-phase counts of My Tactics, shown on the phase selector.
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: tactics.length };
    for (const t of tactics) c[t.phase] = (c[t.phase] ?? 0) + 1;
    return c;
  }, [tactics]);

  const phaseOptions: { key: PhaseFilter; label: string }[] = meta
    ? [{ key: "all", label: "Tất cả" }, ...meta.phases]
    : [{ key: "all", label: "Tất cả" }];

  // ----------------------------------------------------------- mutations
  const openAdd = () => {
    const p: PhaseKey = phase === "all" ? "serve" : phase;
    setEditing({ id: null, payload: { phase: p, title: "" } });
  };

  const openEdit = (t: Tactic) =>
    setEditing({ id: t.id, payload: toPayload(t) });

  const saveEditing = async (payload: TacticIn) => {
    const out = await run(() =>
      editing?.id != null
        ? playbookApi.updateTactic(editing.id, payload)
        : playbookApi.createTactic(payload)
    );
    if (out === undefined) return;
    setEditing(null);
    reloadTactics();
  };

  const addFromLibrary = async (item: LibraryItem) => {
    const out = await run(() =>
      playbookApi.createTactic({
        phase: item.phase,
        title: item.title,
        when_to_use: item.when_to_use,
        how_to: item.how_to,
        follow_up: item.follow_up,
        risk: item.risk,
        opponent_styles: item.opponent_styles,
        tags: item.tags,
        confidence: 0,
        is_favorite: false,
        source_key: item.key,
      })
    );
    if (out !== undefined) reloadTactics();
  };

  const toggleFavorite = async (t: Tactic) => {
    const out = await run(() =>
      playbookApi.updateTactic(t.id, {
        ...toPayload(t),
        is_favorite: !t.is_favorite,
      })
    );
    if (out !== undefined) reloadTactics();
  };

  const remove = async (t: Tactic) => {
    if (!window.confirm(`Xoá chiến thuật "${t.title}"?`)) return;
    // deleteTactic returns void, so return `true` to signal success to `run`.
    const ok = await run(async () => {
      await playbookApi.deleteTactic(t.id);
      return true;
    });
    if (ok) reloadTactics();
  };

  const showIcons = phase === "all";

  return (
    <div className="playbook">
      <div className="pb-toolbar">
        <div className="seg pb-phase-seg">
          {phaseOptions.map((p) => (
            <button
              key={p.key}
              className={`seg-btn${phase === p.key ? " active" : ""}`}
              onClick={() => setPhase(p.key)}
            >
              {p.key !== "all" && (
                <span className="pb-seg-icon">{PHASE_ICON[p.key as PhaseKey]}</span>
              )}
              {p.label}
              {counts[p.key] ? <span className="pb-count">{counts[p.key]}</span> : null}
            </button>
          ))}
        </div>

        <div className="pb-filters">
          <input
            className="pb-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm chiến thuật…"
          />
          <select
            className="pb-select"
            value={oppFilter}
            onChange={(e) => setOppFilter(e.target.value)}
          >
            <option value="">Mọi đối thủ</option>
            {meta?.opponent_styles.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          <button
            className={`btn${favOnly ? " primary" : ""}`}
            onClick={() => setFavOnly((v) => !v)}
            title="Chỉ hiện mục đã ghim"
          >
            ★ Ghim
          </button>
        </div>
      </div>

      {error && <div className="pb-error">{error}</div>}

      {/* ---------------- My Tactics ---------------- */}
      <section className="pb-section">
        <div className="pb-section-head">
          <h3>My Tactics</h3>
          <button className="btn primary" onClick={openAdd}>
            + Thêm chiến thuật
          </button>
        </div>
        {myFiltered.length === 0 ? (
          <p className="pb-empty">
            Chưa có chiến thuật nào{phase !== "all" ? " ở mục này" : ""}. Bấm “+
            Thêm chiến thuật” để tự nhập, hoặc kéo từ Library bên dưới lên.
          </p>
        ) : (
          <div className="pb-grid">
            {myFiltered.map((t) => (
              <TacticCard
                key={t.id}
                mode="owned"
                data={t}
                confidence={t.confidence}
                isFavorite={t.is_favorite}
                showPhaseIcon={showIcons}
                onToggleFavorite={() => toggleFavorite(t)}
                onEdit={() => openEdit(t)}
                onDelete={() => remove(t)}
              />
            ))}
          </div>
        )}
      </section>

      {/* ---------------- Library ---------------- */}
      <section className="pb-section pb-library">
        <div className="pb-section-head">
          <button
            className="pb-collapse"
            onClick={() => setLibOpen((v) => !v)}
            aria-expanded={libOpen}
          >
            {libOpen ? "▾" : "▸"} Library{" "}
            <span className="pb-lib-sub">— kho chiến thuật chung ({libFiltered.length})</span>
          </button>
        </div>
        {libOpen &&
          (libFiltered.length === 0 ? (
            <p className="pb-empty">Không có mục nào khớp bộ lọc.</p>
          ) : (
            <div className="pb-grid">
              {libFiltered.map((item) => (
                <TacticCard
                  key={item.key}
                  mode="library"
                  data={item}
                  added={addedKeys.has(item.key)}
                  showPhaseIcon={showIcons}
                  onAdd={() => addFromLibrary(item)}
                />
              ))}
            </div>
          ))}
      </section>

      {editing && meta && (
        <Modal
          title={editing.id != null ? "Sửa chiến thuật" : "Thêm chiến thuật"}
          onClose={() => setEditing(null)}
        >
          <TacticEditor
            initial={editing.payload}
            meta={meta}
            onSave={saveEditing}
            onCancel={() => setEditing(null)}
          />
        </Modal>
      )}
    </div>
  );
}
