// Tab registry. Adding a tab = build a folder under src/tabs/<tab>/ and add one
// entry here. Disabled tabs render the ComingSoon placeholder.
import type { ComponentType } from "react";
import ComingSoon from "./ComingSoon";
import DailyTracker from "./daily-tracker";
import MatchStats from "./match-stats";
import PlayerProfile from "./profile";
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
    id: "head-coach",
    label: "Coach",
    icon: "🧠",
    component: HeadCoach,
    enabled: true,
  },
  {
    id: "match-stats",
    label: "Match Stats",
    icon: "📊",
    component: MatchStats,
    enabled: true,
  },
  {
    id: "profile",
    label: "Profile",
    icon: "🪪",
    component: PlayerProfile,
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
    id: "motivation",
    label: "Motivation",
    icon: "🔥",
    // Disabled tabs never render their component (AppShell shows ComingSoon),
    // but point at the real placeholder to avoid confusion.
    component: ComingSoon,
    enabled: false,
  },
];
