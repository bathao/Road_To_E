// Tab registry. Adding a tab = build a folder under src/tabs/<tab>/ and add one
// entry here. Disabled tabs render the ComingSoon placeholder.
import type { ComponentType } from "react";
import DailyTracker from "./daily-tracker";
import TacticalPlaybook from "./tactical-playbook";
import MatchStats from "./match-stats";
import VideoAnalysis from "./video-analysis";
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
    id: "tactical-playbook",
    label: "Tactical Playbook",
    icon: "♟️",
    component: TacticalPlaybook,
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
    id: "video-analysis",
    label: "Phân tích kỹ thuật",
    icon: "📝",
    component: VideoAnalysis,
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
    component: DailyTracker,
    enabled: false,
  },
];
