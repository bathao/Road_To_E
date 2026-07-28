import { useMemo, useState } from "react";
import type { Aspect, Polarity, Trait, TraitIn } from "../types";
import { ASPECT_LABEL, ASPECT_ORDER, POLARITY_LABEL } from "../labels";

interface Props {
  traits: Trait[];
  onAdd: (payload: TraitIn) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}

export default function TraitBoard({ traits, onAdd, onDelete }: Props) {
  const [aspect, setAspect] = useState<Aspect>("forehand");
  const [polarity, setPolarity] = useState<Polarity>("strength");
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);

  // Group by aspect → { strengths, weaknesses }.
  const grouped = useMemo(() => {
    const map = new Map<Aspect, { strengths: Trait[]; weaknesses: Trait[] }>();
    for (const t of traits) {
      if (!map.has(t.aspect)) map.set(t.aspect, { strengths: [], weaknesses: [] });
      const g = map.get(t.aspect)!;
      if (t.polarity === "strength") g.strengths.push(t);
      else if (t.polarity === "weakness") g.weaknesses.push(t);
    }
    return map;
  }, [traits]);

  const add = async () => {
    if (!text.trim()) return;
    setAdding(true);
    try {
      await onAdd({ aspect, polarity, text: text.trim() });
      setText("");
    } finally {
      setAdding(false);
    }
  };

  const orderedAspects = ASPECT_ORDER.filter((a) => grouped.has(a));

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>🧬 Approved findings library</h3>
        <span className="va-muted">{traits.length} findings</span>
      </div>

      {orderedAspects.length === 0 ? (
        <p className="va-muted">
          No approved findings yet. Analyze a clip then <b>Approve</b> the correct
          findings, or add one manually below.
        </p>
      ) : (
        <div className="va-trait-groups">
          {orderedAspects.map((a) => {
            const g = grouped.get(a)!;
            return (
              <div key={a} className="va-trait-group">
                <div className="va-trait-aspect">{ASPECT_LABEL[a]}</div>
                <div className="va-trait-cols">
                  <ul className="va-trait-list va-strength">
                    {g.strengths.map((t) => (
                      <li key={t.id}>
                        <span>{t.text}</span>
                        <button className="va-x" title="Delete" onClick={() => onDelete(t.id)}>×</button>
                      </li>
                    ))}
                  </ul>
                  <ul className="va-trait-list va-weakness">
                    {g.weaknesses.map((t) => (
                      <li key={t.id}>
                        <span>{t.text}</span>
                        <button className="va-x" title="Delete" onClick={() => onDelete(t.id)}>×</button>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="va-trait-add">
        <select className="pb-select" value={aspect} onChange={(e) => setAspect(e.target.value as Aspect)}>
          {ASPECT_ORDER.map((a) => (
            <option key={a} value={a}>{ASPECT_LABEL[a]}</option>
          ))}
        </select>
        <select className="pb-select" value={polarity} onChange={(e) => setPolarity(e.target.value as Polarity)}>
          <option value="strength">{POLARITY_LABEL.strength}</option>
          <option value="weakness">{POLARITY_LABEL.weakness}</option>
        </select>
        <input className="pb-input" placeholder="Add a finding manually…" value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void add(); }} />
        <button className="btn primary" disabled={adding || !text.trim()} onClick={add}>Add</button>
      </div>
    </section>
  );
}
