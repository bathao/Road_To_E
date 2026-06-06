// Shared timeline model used by both the Daily Tracker grid and the Analysis
// panel, so a single control drives both.
import {
  addDays,
  addMonths,
  addYears,
  endOfMonth,
  endOfYear,
  monthLabel,
  mondayOf,
  prettyDate,
  startOfMonth,
  startOfYear,
  toIso,
} from "./dates";

export type Mode = "day" | "week" | "month" | "year" | "custom";
export const MODES: Mode[] = ["day", "week", "month", "year", "custom"];
export const MODE_LABEL: Record<Mode, string> = {
  day: "Day",
  week: "Week",
  month: "Month",
  year: "Year",
  custom: "Custom",
};

// Sub-period the comparison chart splits the range into.
export type Unit = "month" | "week" | "day";

export interface Period {
  mode: Mode;
  anchor: Date; // reference date for day/week/month/year
  customFrom: string; // ISO, used when mode === "custom"
  customTo: string;
}

export interface ResolvedRange {
  fromIso: string;
  toIso: string;
  label: string;
}

export function resolveRange(p: Period): ResolvedRange {
  const { mode, anchor, customFrom, customTo } = p;
  if (mode === "day") {
    const iso = toIso(anchor);
    return { fromIso: iso, toIso: iso, label: prettyDate(iso) };
  }
  if (mode === "week") {
    const start = mondayOf(anchor);
    const end = addDays(start, 6);
    return {
      fromIso: toIso(start),
      toIso: toIso(end),
      label: `${prettyDate(toIso(start))} — ${prettyDate(toIso(end))}`,
    };
  }
  if (mode === "month") {
    return {
      fromIso: toIso(startOfMonth(anchor)),
      toIso: toIso(endOfMonth(anchor)),
      label: monthLabel(anchor),
    };
  }
  if (mode === "year") {
    return {
      fromIso: toIso(startOfYear(anchor)),
      toIso: toIso(endOfYear(anchor)),
      label: String(anchor.getFullYear()),
    };
  }
  return {
    fromIso: customFrom,
    toIso: customTo,
    label: `${prettyDate(customFrom)} — ${prettyDate(customTo)}`,
  };
}

export function stepAnchor(mode: Mode, anchor: Date, dir: number): Date {
  if (mode === "day") return addDays(anchor, dir);
  if (mode === "week") return addDays(anchor, dir * 7);
  if (mode === "month") return addMonths(anchor, dir);
  if (mode === "year") return addYears(anchor, dir);
  return anchor;
}

// Comparison-chart granularity. Columns are coarse; Line is finer (daily).
export function chartUnitFor(
  mode: Mode,
  chartType: "bar" | "line",
  fromIso: string,
  toIso: string
): Unit | null {
  if (mode === "day") return null;
  if (mode === "year") return "month";
  if (mode === "week") return "day";
  if (mode === "month") return chartType === "line" ? "day" : "week";
  // custom: derive from span
  const span =
    Math.round(
      (new Date(toIso).getTime() - new Date(fromIso).getTime()) / 86400000
    ) + 1;
  if (span <= 1) return null;
  if (chartType === "line") return span >= 120 ? "month" : "day";
  if (span >= 90) return "month";
  if (span >= 15) return "week";
  return "day";
}
