// Vitest scaffold (2026-10-16, REFACTOR.md Phase 0). Pure modules get unit
// tests here as they are carved out of the big components (pointRules,
// profileDerive, handicap math, tournamentDraft…); no DOM environment yet.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "node",
  },
});
