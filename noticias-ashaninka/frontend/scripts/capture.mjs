// Tareas 3.7 y 3.8: captura determinista del canvas con Playwright.
//
// Para cada oración seleccionada dibuja el avatar fotograma a fotograma (renderAt) a 50 Hz,
// mide la apertura de la boca RENDERIZADA y guarda un JPEG cada 2 fotogramas (25 fps) para el
// clip. No depende de la velocidad del equipo ni de la GPU: el tiempo es el de la pista, no el
// del reloj. El reloj en tiempo real se mide aparte (scripts/realtime.mjs).
//
// Uso: node scripts/capture.mjs <selection.json> <carpeta_salida> [url_base]
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const [selFile, outDir, base = "http://localhost:5173"] = process.argv.slice(2);
if (!selFile || !outDir) {
  console.error("uso: node scripts/capture.mjs <selection.json> <carpeta_salida> [url_base]");
  process.exit(2);
}
const HZ = 50;
const CHUNK = 50;
const sel = JSON.parse(readFileSync(selFile, "utf8"));
mkdirSync(join(outDir, "signals"), { recursive: true });

const browser = await chromium.launch({
  args: process.env.GL === "default" ? [] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 640, height: 720 } });
page.on("pageerror", (e) => console.log("[error]", e.message));
const t0 = Date.now();

for (const item of sel) {
  const id = item.news_id;
  if (existsSync(join(outDir, "signals", `news_${id}.json`))) continue; // reanudable
  await page.goto(`${base}/visor.html?news=${id}&framing=rostro&deterministic=1&size=512`);
  await page.waitForFunction(() => window.__visor?.ready, null, { timeout: 120000 });
  const dur = await page.evaluate(async () => {
    await window.__visor.loadSegment(0);
    const v = window.__visor;
    const canvas = document.querySelector("canvas");
    v.cal = v.calibrateMouth(v.viewer, canvas);
    return { dur: v.manifest.segments[0].duration_s, mask: v.cal.maskPixels, ref: v.cal.ref };
  });
  const n = Math.floor(dur.dur * HZ);
  const signal = [];
  const framesDir = join(outDir, "frames", String(id));
  mkdirSync(framesDir, { recursive: true });
  for (let k0 = 0; k0 < n; k0 += CHUNK) {
    const times = Array.from({ length: Math.min(CHUNK, n - k0) }, (_, i) => (k0 + i) / HZ);
    const r = await page.evaluate(
      ([times, k0]) => {
        const v = window.__visor;
        return v.captureSignal(v.viewer, document.querySelector("canvas"), v.cal, times, k0, 2);
      },
      [times, k0],
    );
    signal.push(...r.signal);
    let j = 0;
    for (let i = 0; i < times.length; i++) {
      if ((k0 + i) % 2 === 0) {
        const b64 = r.frames[j++].split(",")[1];
        writeFileSync(join(framesDir, `${String((k0 + i) / 2).padStart(5, "0")}.jpg`), Buffer.from(b64, "base64"));
      }
    }
  }
  writeFileSync(
    join(outDir, "signals", `news_${id}.json`),
    JSON.stringify({ news_id: id, hz: HZ, duration_s: dur.dur, mask_pixels: dur.mask, signal }),
  );
  console.log(`[3.7] noticia ${id}: ${n} fotogramas, máscara ${dur.mask} px (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
}
await browser.close();
