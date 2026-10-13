// Prueba de humo en Chromium real: carga el visor, comprueba el modo y guarda una captura.
import { chromium } from "playwright";

const url = process.argv[2] ?? "http://localhost:5173/visor.html?news=1";
const out = process.argv[3] ?? "smoke.png";
const browser = await chromium.launch({
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--autoplay-policy=no-user-gesture-required"],
});
const page = await browser.newPage({ viewport: { width: 800, height: 900 } });
page.on("console", (m) => console.log("[consola]", m.text()));
page.on("pageerror", (e) => console.log("[error]", e.message));
await page.goto(url);
await page.waitForFunction(() => window.__visor?.ready, null, { timeout: 90000 });
console.log(await page.evaluate(() => ({ mode: window.__visor.mode, events: window.__visor.events })));
await page.screenshot({ path: out });
await browser.close();
