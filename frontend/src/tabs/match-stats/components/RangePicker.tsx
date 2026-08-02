import { useMemo } from "react";
import {
  addDays,
  endOfMonth,
  endOfYear,
  fromIso,
  prettyDate,
  startOfYear,
  toIso,
} from "../../../shared/dates";

// YouTube-Studio-style range picker (Profile tab only — the Daily Tracker
// keeps its calendar-anchored PeriodControl, a deliberate split): rolling
// windows ending today chart with no calendar seams, plus whole years,
// recent months and a custom range.

const ROLLING: [string, string, number][] = [
  ["last7", "Last 7 days", 7],
  ["last28", "Last 28 days", 28],
  ["last90", "Last 90 days", 90],
  ["last365", "Last 365 days", 365],
];

const FULL_MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// "last7" … "last365" | "lifetime" | "y:2026" | "m:2026-08" | "custom"
export type RangePreset = string;

export interface PresetRange {
  fromIso: string;
  toIso: string;
  label: string;
}

// Preset → concrete dates. Year/month ranges are clamped to today so charts
// never draw empty future buckets; `firstDate` (earliest tracked data) opens
// the Lifetime range and is null only while it loads.
export function resolvePreset(
  preset: RangePreset,
  customFrom: string,
  customTo: string,
  firstDate: string | null
): PresetRange {
  const today = new Date();
  const rolling = ROLLING.find(([k]) => k === preset);
  if (rolling) {
    return {
      fromIso: toIso(addDays(today, -(rolling[2] - 1))),
      toIso: toIso(today),
      label: rolling[1],
    };
  }
  if (preset === "lifetime") {
    return {
      fromIso: firstDate ?? toIso(startOfYear(today)),
      toIso: toIso(today),
      label: "Lifetime",
    };
  }
  if (preset.startsWith("y:")) {
    const start = new Date(Number(preset.slice(2)), 0, 1);
    const end = endOfYear(start);
    return {
      fromIso: toIso(start),
      toIso: toIso(end > today ? today : end),
      label: preset.slice(2),
    };
  }
  if (preset.startsWith("m:")) {
    const [y, m] = preset.slice(2).split("-").map(Number);
    const start = new Date(y, m - 1, 1);
    const end = endOfMonth(start);
    return {
      fromIso: toIso(start),
      toIso: toIso(end > today ? today : end),
      label: `${FULL_MONTHS[m - 1]} ${y}`,
    };
  }
  return {
    fromIso: customFrom,
    toIso: customTo,
    label: `${prettyDate(customFrom)} — ${prettyDate(customTo)}`,
  };
}

export default function RangePicker({
  preset,
  customFrom,
  customTo,
  firstDate,
  onPreset,
  onCustomFrom,
  onCustomTo,
}: {
  preset: RangePreset;
  customFrom: string;
  customTo: string;
  firstDate: string | null; // earliest tracked data; null while loading
  onPreset: (p: RangePreset) => void;
  onCustomFrom: (iso: string) => void;
  onCustomTo: (iso: string) => void;
}) {
  // Year/month option lists span the tracked history (months capped at 12 —
  // older ones are reachable via the year entries or Custom).
  const { years, months } = useMemo(() => {
    const today = new Date();
    const first = firstDate ? fromIso(firstDate) : today;
    const years: number[] = [];
    for (let y = today.getFullYear(); y >= first.getFullYear(); y--) {
      years.push(y);
    }
    const months: { value: string; label: string }[] = [];
    let cur = new Date(today.getFullYear(), today.getMonth(), 1);
    const floor = new Date(first.getFullYear(), first.getMonth(), 1);
    while (cur >= floor && months.length < 12) {
      months.push({
        value: `m:${toIso(cur).slice(0, 7)}`,
        label:
          cur.getFullYear() === today.getFullYear()
            ? FULL_MONTHS[cur.getMonth()]
            : `${FULL_MONTHS[cur.getMonth()]} ${cur.getFullYear()}`,
      });
      cur = new Date(cur.getFullYear(), cur.getMonth() - 1, 1);
    }
    return { years, months };
  }, [firstDate]);

  const range = resolvePreset(preset, customFrom, customTo, firstDate);

  return (
    <div className="period-control">
      <select
        className="pb-select range-picker-select"
        value={preset}
        onChange={(e) => onPreset(e.target.value)}
      >
        <optgroup label="Rolling">
          {ROLLING.map(([k, lbl]) => (
            <option key={k} value={k}>
              {lbl}
            </option>
          ))}
          <option value="lifetime">Lifetime</option>
        </optgroup>
        <optgroup label="Years">
          {years.map((y) => (
            <option key={y} value={`y:${y}`}>
              {y}
            </option>
          ))}
        </optgroup>
        <optgroup label="Months">
          {months.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </optgroup>
        <optgroup label="Custom">
          <option value="custom">Custom…</option>
        </optgroup>
      </select>

      {preset === "custom" ? (
        <div className="custom-range">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => onCustomFrom(e.target.value)}
          />
          <span>→</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => onCustomTo(e.target.value)}
          />
        </div>
      ) : (
        <span className="analysis-range">
          {prettyDate(range.fromIso)} — {prettyDate(range.toIso)}
        </span>
      )}
    </div>
  );
}
