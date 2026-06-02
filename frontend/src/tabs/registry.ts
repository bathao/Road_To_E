// Tab registry. Adding a tab = build a folder under src/tabs/<tab>/ and add one
// entry here. Disabled tabs render the ComingSoon placeholder.
import type { ComponentType } from "react";
import DailyTracker from "./daily-tracker";

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
    id: "training-plan",
    label: "Training Plan",
    icon: "🗂️",
    component: DailyTracker,
    enabled: false,
  },
  {
    id: "motivation",
    label: "Motivation",
    icon: "🔥",
    component: DailyTracker,
    enabled: false,
  },
];
