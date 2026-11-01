/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dashboard talks to the API through this dev server, so the browser sees one origin and needs no CORS.
// (The API also allows http://127.0.0.1:5173 explicitly, for anyone who serves the dashboard another way.)
const api = process.env.MINISAT_API_URL ?? "http://127.0.0.1:8000";
const proxy = { "/api": api, "/health": api };
const port = Number(process.env.MINISAT_DASHBOARD_PORT ?? 5173);

export default defineConfig({
  root: "dashboard",
  plugins: [react()],
  server: { host: "127.0.0.1", port, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: true },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    globals: false,
  },
});
