import { resolve } from "node:path";
import { defineConfig } from "vite";

// Construye cada opción por separado para medir su peso (npm run bench:size).
const entry = process.env.BENCH_ENTRY ?? "three-vrm";
export default defineConfig({
  root: import.meta.dirname,
  build: {
    outDir: resolve(import.meta.dirname, "dist", entry),
    emptyOutDir: true,
    lib: { entry: resolve(import.meta.dirname, `${entry}.ts`), formats: ["es"], fileName: entry },
    minify: true,
    reportCompressedSize: true,
  },
});
