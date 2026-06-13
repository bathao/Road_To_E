import type { DayType, ExerciseTarget } from "./types";

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
