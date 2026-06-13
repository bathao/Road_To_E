import type { DayType, ExerciseTarget } from "./types";

// Each exercise maps to a schematic pose illustration (bundled SVG, no copyright).
// A real GIF dropped at /exercises/<key>.gif still takes priority (tried first).
const POSE: Record<string, string> = {
  quad_set: "supine-leg-raise",
  straight_leg_raise: "supine-leg-raise",
  short_arc_quad: "knee-mobility",
  knee_mobility: "knee-mobility",
  side_leg_raise: "side-leg-raise",
  inner_thigh_raise: "inner-thigh",
  prone_leg_raise: "prone-leg-raise",
  glute_bridge: "glute-bridge",
  single_leg_glute_bridge: "glute-bridge",
  wall_sit_shallow: "wall-sit",
  mini_squat: "wall-sit",
  lateral_lunge: "side-lunge",
  plank: "plank",
  plank_knee_rotation: "plank-knee-rotation",
  plank_shoulder_tap: "plank-shoulder-tap",
  bird_dog: "bird-dog",
  dead_bug: "supine-crunch",
  crunch: "supine-crunch",
  bicycle_crunch: "supine-crunch",
  double_leg_lift_hold: "supine-crunch",
  side_plank: "side-plank",
  standing_trunk_twist: "standing-twist",
  wood_chop: "standing-twist",
  russian_twist: "standing-twist",
  single_leg_balance: "standing",
  single_leg_eyes_closed: "standing",
  toe_stand_hold: "standing",
  calf_raise: "standing",
  gentle_bounce: "standing",
  march_in_place: "standing",
  lateral_toe_steps: "standing",
  wall_pushup: "wall-pushup",
  wrist_curl: "wrist-curl",
  scapular_yt: "scapular-yt",
  hip_hinge: "hip-hinge",
  thoracic_rotation: "thoracic-rotation",
  hamstring_stretch: "stretch",
  quad_stretch: "stretch",
  groin_stretch: "stretch",
};

/** Pose-illustration SVG path for an exercise key (defaults to a standing figure). */
export function poseSvg(key: string): string {
  return `/exercises/poses/${POSE[key] ?? "standing"}.svg`;
}

export const DAY_ICON: Record<DayType, string> = {
  legs: "🦵",
  core: "🌀",
  balance: "⚖️",
};

export const DAY_LABEL: Record<DayType, string> = {
  legs: "Chân",
  core: "Lõi",
  balance: "Cân bằng",
};

// "3×20" / "3×45s", with a per-side suffix when relevant.
export function formatTarget(t: ExerciseTarget, perSide: boolean): string {
  const sets = t.sets ?? 1;
  const body = t.sec != null ? `${sets}×${t.sec}s` : `${sets}×${t.reps ?? 0}`;
  return perSide ? `${body} / bên` : body;
}

// A short WebAudio "ting" so checking an exercise feels tactile — no asset file.
export function playTing(): void {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
    osc.start();
    osc.stop(ctx.currentTime + 0.26);
    osc.onended = () => ctx.close();
  } catch {
    /* audio is a nicety; ignore if the browser blocks it */
  }
}
