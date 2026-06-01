import { useEffect, useMemo, useState } from "react";
import type { Category, PhysicalItem } from "../../types";
import { trackerApi } from "../../api";

const YELLOW_RATIO = 0.7;

// Physical Training checklist: tick the exercises done that day. The cell turns
// yellow once at least 70% of the items are ticked.
export default function ChecklistEditor({
  category,
  checked,
  onSave,
}: {
  category: Category;
  checked: string[]; // currently ticked item keys
  onSave: (items: string[]) => void;
}) {
  const [items, setItems] = useState<PhysicalItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(checked)
  );

  useEffect(() => {
    let alive = true;
    trackerApi
      .getPhysicalItems()
      .then((list) => alive && setItems(list))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, []);

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const ratio = items.length ? selected.size / items.length : 0;
  const willBeYellow = ratio >= YELLOW_RATIO;
  const threshold = useMemo(
    () => Math.ceil(items.length * YELLOW_RATIO),
    [items.length]
  );

  return (
    <div className="editor">
      <p className="editor-sub">{category.label}</p>

      <div className="checklist">
        {items.map((it) => {
          const on = selected.has(it.key);
          return (
            <label key={it.key} className={`check-item${on ? " on" : ""}`}>
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggle(it.key)}
              />
              <span>{it.label}</span>
            </label>
          );
        })}
      </div>

      <div className={`checklist-status${willBeYellow ? " yellow" : ""}`}>
        {selected.size}/{items.length} done
        {willBeYellow
          ? " · cell will be yellow 🟡"
          : ` · ${threshold} needed for yellow`}
      </div>

      <button
        className="btn primary"
        onClick={() => onSave(Array.from(selected))}
      >
        Save
      </button>
    </div>
  );
}
