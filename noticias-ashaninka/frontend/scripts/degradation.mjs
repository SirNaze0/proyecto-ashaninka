// Tarea 3.6: prueba la degradación en un Chromium real.
//   A) sin WebGL (--disable-3d-apis)  -> debe quedar en imagen fija con el evento "sin-webgl"
//   B) CPU muy lenta + renderizado por software -> debe quedar fija con "fps-bajos" si los FPS < 20
//   C) condiciones normales (GPU)     -> avatar con el evento "avatar-ok"
// Uso: node scripts/degradation.mjs <salida.json>
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const out = process.argv[2] ?? "degradacion.json";
const base = process.env.BASE ?? "http://localhost:5173";

async function caso(nombre, args, throttle = 1, news = 1) {
  const browser = await chromium.launch({ args });
  const ctx = await browser.newContext({ viewport: { width: 800, height: 900 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: throttle });
  await page.goto(`${base}/visor.html?news=${news}`);
  await page.waitForFunction(() => window.__visor?.ready || window.__avatarEvents?.length, null, { timeout: 180000 });
  await page.waitForFunction(() => window.__visor?.mode, null, { timeout: 180000 });
  const r = await page.evaluate(() => ({
    modo: window.__visor.mode,
    eventos: window.__avatarEvents,
    hayCanvas: !!document.querySelector("canvas"),
    hayImagenFija: !!document.querySelector("img[alt*='imagen fija']"),
    audioDisponible: !!document.querySelector("audio"),
    textoVisible: document.querySelector("p[aria-live]")?.textContent?.length > 0,
  }));
  await browser.close();
  console.log(nombre, JSON.stringify(r));
  return { nombre, throttle, args, ...r };
}

const casos = [];
casos.push(await caso("A-sin-webgl", ["--disable-3d-apis", "--disable-gpu"]));
casos.push(await caso("C-normal-gpu", ["--use-angle=d3d11", "--ignore-gpu-blocklist"]));
casos.push(await caso("B-cpu-20x-software", ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"], 20));
writeFileSync(out, JSON.stringify({ casos }, null, 1));
