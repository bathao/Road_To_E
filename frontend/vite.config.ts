import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built assets work when served by FastAPI from any path.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // During `npm run dev`, forward API calls to the FastAPI backend.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
