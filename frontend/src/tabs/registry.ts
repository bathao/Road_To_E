// Tab registry. Adding a tab = build a folder under src/tabs/<tab>/ and add one
// entry here. Disabled tabs render the ComingSoon placeholder.
import type { ComponentType } from "react";
import ComingSoon from "./ComingSoon";
import DailyTracker from "./daily-tracker";
import DatabaseTab from "./database";
import Journal from "./journal";
import MatchStats from "./match-stats";
import Tactics from "./tactics";
import TrainingCenter from "./training-center";
import HeadCoach from "./head-coach";

export interface TabDef {
  id: string;
  label: string;
  icon: string; // emoji, keeps things dependency-free
  component: ComponentType;
  enabled: boolean;
}

export const TABS: TabDef[] = [
  {
    id: "daily-tracker",
    label: "Daily Tracker",
    icon: "📅",
    component: DailyTracker,
    enabled: true,
  },
  {
    // The old standalone Profile tab was merged in here 2026-07-30: general
    // info on top, match stats in the middle, training cards at the bottom.
    // The folder keeps its match-stats name; only the label/icon changed.
    id: "match-stats",
    label: "Profile",
    icon: "🪪",
    component: MatchStats,
    enabled: true,
  },
  {
    // Daily table-tennis diary (2026-08-20): coach reminders + own lessons.
    // Replaced the grid's Coach & Recap row — same store, new surface.
    id: "journal",
    label: "Journal",
    icon: "📔",
    component: Journal,
    enabled: true,
  },
  {
    id: "head-coach",
    label: "Coach",
    icon: "🧠",
    component: HeadCoach,
    enabled: true,
  },
  {
    // "Chiến Thuật" — per-opponent SINGLES scouting + AI game plans
    // (2026-08-15; doubles/1v2/2v1 deliberately out of scope).
    id: "tactics",
    label: "Singles Tactics",
    icon: "🎯",
    component: Tactics,
    enabled: true,
  },
  {
    id: "training-center",
    label: "Training Center",
    icon: "💪",
    component: TrainingCenter,
    enabled: true,
  },
  {
    id: "database",
    label: "Database",
    icon: "🗄️",
    component: DatabaseTab,
    enabled: true,
  },
  {
    id: "motivation",
    label: "Motivation",
    icon: "🔥",
    // Disabled tabs never render their component (AppShell shows ComingSoon),
    // but point at the real placeholder to avoid confusion.
    component: ComingSoon,
    enabled: false,
  },
];
