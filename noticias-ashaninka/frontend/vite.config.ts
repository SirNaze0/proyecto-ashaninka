import { createHash } from "node:crypto";
import preact from "@preact/preset-vite";
import { type Plugin, defineConfig } from "vite";

// El backend (FastAPI) sirve /static y /api; en desarrollo se reenvían desde Vite.
const BACKEND = process.env.NA_BACKEND ?? "http://127.0.0.1:8000";

/**
 * Inyecta en `sw.js` la lista de precarga del *shell* (el cierre estático del punto de entrada de
 * la PWA: HTML, JS y CSS iniciales). El avatar (three, three-vrm, VRM) se carga con import()
 * dinámico y queda FUERA: no entra en el presupuesto inicial de 3 MB.
 */
function swPrecache(): Plugin {
  return {
    name: "na-sw-precache",
    apply: "build",
    generateBundle(_o, bundle) {
      const files = new Set<string>(["/", "/index.html", "/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/presentadora_fija.svg"]);
      const entry = Object.values(bundle).find((c) => c.type === "chunk" && c.isEntry && c.facadeModuleId?.endsWith("index.html"));
      const seen = new Set<string>();
      const visit = (name: string) => {
        const c = bundle[name];
        if (!c || c.type !== "chunk" || seen.has(name)) return;
        seen.add(name);
        files.add("/" + c.fileName);
        c.imports.forEach(visit);
        c.viteMetadata?.importedCss.forEach((f) => files.add("/" + f));
      };
      if (entry) visit(entry.fileName);
      const sw = Object.values(bundle).find((c) => c.type === "chunk" && c.name === "sw");
      if (!sw || sw.type !== "chunk") throw new Error("no se generó sw.js");
      const list = [...files].sort();
      const version = createHash("sha256").update(list.join("|")).digest("hex").slice(0, 10);
      sw.code = sw.code.replace(/\b__PRECACHE__\b/g, JSON.stringify(list)).replace(/\b__VERSION__\b/g, JSON.stringify(version));
    },
  };
}

export default defineConfig({
  plugins: [preact(), swPrecache()],
  build: {
    manifest: true,
    rollupOptions: {
      input: { index: "index.html", visor: "visor.html", sw: "src/sw.ts" },
      output: {
        entryFileNames: (chunk) => (chunk.name === "sw" ? "sw.js" : "assets/[name]-[hash].js"),
      },
    },
  },
  server: { proxy: { "/static": BACKEND, "/api": BACKEND } },
  test: { include: ["tests/**/*.test.ts"], environment: "node" },
});
