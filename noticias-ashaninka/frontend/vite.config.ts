import preact from "@preact/preset-vite";
import { defineConfig } from "vite";

// El backend (FastAPI) sirve /static y /api; en desarrollo se reenvían desde Vite.
const BACKEND = process.env.NA_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [preact()],
  build: {
    manifest: true,
    rollupOptions: { input: { index: "index.html", visor: "visor.html" } },
  },
  server: { proxy: { "/static": BACKEND, "/api": BACKEND } },
  test: { include: ["tests/**/*.test.ts"], environment: "node" },
});
