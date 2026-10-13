// Tarea 3.6/3.8: reproducción en TIEMPO REAL en Chromium. Mide FPS y el error del reloj del
// cliente (instante usado para evaluar los visemas frente a la recta de audio.currentTime).
//
// Uso: node scripts/realtime.mjs <selection.json> <salida.json> <gpu|swiftshader> [throttle=1] [n=6]
import { readFileSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const [selFile, outFile, config = "gpu", throttle = "1", nClips = "6"] = process.argv.slice(2);
const sel = JSON.parse(readFileSync(selFile, "utf8")).slice(0, Number(nClips));
const base = process.env.BASE ?? "http://localhost:5173";
const args = ["--autoplay-policy=no-user-gesture-required"];
// "gpu": ANGLE sobre Direct3D 11 con la GPU del equipo; "swiftshader": renderizado por software
if (config === "swiftshader") args.push("--use-angle=swiftshader", "--enable-unsafe-swiftshader");
else args.push("--use-angle=d3d11", "--ignore-gpu-blocklist");

const browser = await chromium.launch({ args });
const ctx = await browser.newContext({ viewport: { width: 800, height: 900 } });
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send("Emulation.setCPUThrottlingRate", { rate: Number(throttle) });
page.on("pageerror", (e) => console.log("[error]", e.message));

function lsq(xs, ys) {
  const n = xs.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let sxx = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    sxx += (xs[i] - mx) ** 2;
    sxy += (xs[i] - mx) * (ys[i] - my);
  }
  const m = sxy / sxx;
  return { m, b: my - m * mx };
}
const pct = (a, p) => [...a].sort((x, y) => x - y)[Math.min(a.length - 1, Math.floor(a.length * p))];

const clips = [];
for (const item of sel) {
  await page.goto(`${base}/visor.html?news=${item.news_id}`);
  await page.waitForFunction(() => window.__visor?.ready, null, { timeout: 120000 });
  const mode = await page.evaluate(() => window.__visor.mode);
  if (mode !== "avatar") {
    clips.push({ news_id: item.news_id, mode, events: await page.evaluate(() => window.__visor.events) });
    continue;
  }
  const r = await page.evaluate(async () => {
    const v = window.__visor;
    await v.loadSegment(0);
    const audio = document.querySelector("audio");
    await new Promise((res) => audio.addEventListener("canplaythrough", res, { once: true }));
    const rec = [];
    let alive = true;
    const tick = () => {
      if (!alive) return;
      rec.push([performance.now(), audio.currentTime, v.viewer.time, audio.paused ? 0 : 1]);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    await audio.play();
    await new Promise((res) => audio.addEventListener("ended", res, { once: true }));
    alive = false;
    return { rec, stats: v.viewer.stats(), duration: audio.duration };
  });
  const play = r.rec.filter((x) => x[3] === 1 && x[1] > 0.05);
  const xs = play.map((x) => x[0] / 1000);
  const line = lsq(xs, play.map((x) => x[1]));
  const err = play.map((x, i) => (x[2] - (line.m * xs[i] + line.b)) * 1000);
  const dts = play.slice(1).map((x, i) => x[0] - play[i][0]);
  const fps = 1000 / (dts.reduce((a, b) => a + b, 0) / dts.length);
  clips.push({
    news_id: item.news_id,
    mode,
    duration_s: r.duration,
    fps_media: +fps.toFixed(1),
    fps_p5: +(1000 / pct(dts, 0.95)).toFixed(1),
    intervalo_p95_ms: +pct(dts, 0.95).toFixed(1),
    ms_dibujo_media: +r.stats.meanFrameMs.toFixed(2),
    ms_dibujo_p95: +r.stats.p95FrameMs.toFixed(2),
    pendiente_audio_vs_reloj: +line.m.toFixed(4),
    error_reloj_regimen_ms: {
      // pasado el arranque del audio (primeros 0,5 s de reproducción)
      max_abs: +Math.max(...err.filter((_, i) => play[i][1] > 0.5).map(Math.abs)).toFixed(1),
      p95_abs: +pct(err.filter((_, i) => play[i][1] > 0.5).map(Math.abs), 0.95).toFixed(1),
    },
    error_reloj_ms: {
      max_abs: +Math.max(...err.map(Math.abs)).toFixed(1),
      p95_abs: +pct(err.map(Math.abs), 0.95).toFixed(1),
      media_con_signo: +(err.reduce((a, b) => a + b, 0) / err.length).toFixed(1),
    },
    muestras: play.length,
  });
  console.log(config, `x${throttle}`, JSON.stringify(clips.at(-1)));
}
writeFileSync(outFile, JSON.stringify({ config, throttle: Number(throttle), clips }, null, 1));
await browser.close();
