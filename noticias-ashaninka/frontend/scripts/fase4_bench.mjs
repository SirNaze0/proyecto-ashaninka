// Banco de pruebas del cliente de la Fase 4 (tarea 4.7), en Chromium real con CDP.
// Las definiciones están en docs/metrics.md («Fase 4»), escritas antes de medir.
//
// Uso: node scripts/fase4_bench.mjs <carga|ttfa|reproduccion|fps|degradacion|offline|eventos|all>
// Variables: BASE (http://127.0.0.1:8766), SEL (eval/fase4/out/selection.json), OUT (eval/fase4/out),
//            REPS (3), NEWS (todas las de la selección; para pruebas rápidas, un número menor)
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { chromium } from "playwright";

const ROOT = resolve(dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");
const BASE = process.env.BASE ?? "http://127.0.0.1:8766";
const OUT = process.env.OUT ?? resolve(ROOT, "eval/fase4/out");
const SEL = JSON.parse(readFileSync(process.env.SEL ?? resolve(OUT, "selection.json"), "utf8"));
const REPS = Number(process.env.REPS ?? 3);
const NEWS = SEL.slice(0, Number(process.env.NEWS ?? SEL.length));
mkdirSync(OUT, { recursive: true });

const GPU = ["--use-angle=d3d11", "--ignore-gpu-blocklist"];
const SOFT = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"];
const NOGL = ["--disable-3d-apis", "--disable-gpu"];

// Perfil «Regular 4G» de Chrome DevTools: 9 Mbps de bajada, 1,5 Mbps de subida, 150 ms de latencia
const PERFILES = {
  "sin-limite": { cpu: 1, net: null },
  "movil-4x-4g": {
    cpu: 4,
    net: { offline: false, latency: 150, downloadThroughput: (9 * 1024 * 1024) / 8, uploadThroughput: (1.5 * 1024 * 1024) / 8 },
  },
};

const pct = (a, p) => {
  const s = [...a].sort((x, y) => x - y);
  return s.length ? s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] : null;
};
const stats = (a) => {
  const n = a.length;
  const mean = a.reduce((x, y) => x + y, 0) / (n || 1);
  const de = Math.sqrt(a.reduce((x, y) => x + (y - mean) ** 2, 0) / (n > 1 ? n - 1 : 1));
  const r = (x) => (x === null ? null : Math.round(x * 100) / 100);
  return { n, media: r(mean), de: r(de), min: r(Math.min(...a)), p50: r(pct(a, 50)), p95: r(pct(a, 95)), p99: r(pct(a, 99)), max: r(Math.max(...a)) };
};
const save = (name, obj) => {
  writeFileSync(resolve(OUT, name), JSON.stringify(obj, null, 1));
  console.log(`[fase4] -> ${name}`);
};
const url = (id, c, sw = false) => `${BASE}/${sw ? "" : "?nosw=1"}#/noticia/${id}?c=${c}`;

async function abrir(browser, perfil, { bytes = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  const p = PERFILES[perfil];
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: p.cpu });
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: false });
  if (p.net) await cdp.send("Network.emulateNetworkConditions", p.net);
  const net = { reqs: new Map(), bytes: 0, files: [] };
  if (bytes) {
    cdp.on("Network.responseReceived", (e) => net.reqs.set(e.requestId, e.response.url));
    cdp.on("Network.loadingFinished", (e) => {
      net.bytes += e.encodedDataLength;
      net.files.push({ url: net.reqs.get(e.requestId) ?? "?", bytes: e.encodedDataLength });
    });
  }
  return { ctx, page, cdp, net };
}

const listo = (page, c) =>
  c === "C1"
    ? page.waitForSelector("[data-testid=body]", { timeout: 120000 })
    : page.waitForFunction(() => (window.__app?.player?.elements[0].readyState ?? 0) >= 3, null, { timeout: 120000 });

// ------------------------------------------------------------------ 1. carga inicial
async function carga(browser) {
  const filas = [];
  const casos = [
    ["C1", 5],
    ["C2", 5],
    ["C3", NEWS.length],
    ["C4", 5],
  ];
  for (const perfil of Object.keys(PERFILES)) {
    for (const [c, n] of casos) {
      for (const news of NEWS.slice(0, Math.min(n, NEWS.length))) {
        const { ctx, page, net } = await abrir(browser, perfil, { bytes: true });
        await page.goto(url(news.news_id, c));
        await listo(page, c);
        await page.waitForTimeout(300);
        if (c === "C4") {
          await page.waitForFunction(() => document.querySelector("[data-avatar-mode]")?.dataset.avatarMode !== "cargando", null, { timeout: 180000 });
          await page.waitForTimeout(500);
        }
        const util = net.files.filter((f) => f.bytes > 0 && !/^blob:|^data:/.test(f.url));
        const esAvatar = (u) => /(three|GLTFLoader|viewer|create-avatar|AvatarPanel)[^/]*\.js|\.vrm/.test(u);
        const avatar = util.filter((f) => esAvatar(f.url)).reduce((x, f) => x + f.bytes, 0);
        const total = util.reduce((x, f) => x + f.bytes, 0);
        const porTipo = {};
        for (const f of util) {
          const ext = f.url.split("?")[0].split(".").pop();
          const k = /^\d+:\d+\//.test(ext) || ext.length > 6 ? "api" : ext;
          porTipo[k] = (porTipo[k] ?? 0) + f.bytes;
        }
        filas.push({ perfil, condicion: c, news_id: news.news_id, bytes_iniciales: total - avatar, bytes_avatar_diferido: avatar, bytes_total: total, peticiones: util.length, por_extension: porTipo });
        await ctx.close();
      }
    }
  }
  const resumen = {};
  for (const c of ["C1", "C2", "C3", "C4"]) {
    const f = filas.filter((x) => x.condicion === c);
    resumen[c] = {
      inicial_max_mb: Math.max(...f.map((x) => x.bytes_iniciales)) / 1e6,
      inicial_media_mb: f.reduce((s, x) => s + x.bytes_iniciales, 0) / f.length / 1e6,
      avatar_diferido_max_mb: Math.max(...f.map((x) => x.bytes_avatar_diferido)) / 1e6,
      total_max_mb: Math.max(...f.map((x) => x.bytes_total)) / 1e6,
    };
  }
  save("carga.json", { filas, resumen });
}

// ------------------------------------------------------------------ 2. TTFA del cliente
async function medirTtfa(page, link) {
  if (link) await page.goto(link);
  await page.waitForFunction(() => { const b = document.querySelector("[data-testid=play]"); return b && !b.disabled; }, null, { timeout: 120000 });
  await page.evaluate(() => {
    window.__m = {};
    document.addEventListener("click", () => (window.__m.click = performance.now()), { capture: true, once: true });
    const on = () => (window.__m.playing ??= performance.now());
    window.__app.player.elements.forEach((a) => a.addEventListener("playing", on, { once: true }));
  });
  await page.click("[data-testid=play]");
  await page.waitForFunction(() => window.__m.playing, null, { timeout: 120000 });
  const m = await page.evaluate(() => window.__m);
  return { ttfa_ms: m.playing - m.click, arranque_ms: m.playing };
}

async function ttfa(browser) {
  const salida = {};
  for (const perfil of Object.keys(PERFILES)) {
    const frio = [], caliente = [], arranqueFrio = [], arranqueCaliente = [];
    // En frío: contexto nuevo (sin Service Worker ni caché) en cada repetición
    for (const news of NEWS) {
      for (let r = 0; r < REPS; r++) {
        const { ctx, page } = await abrir(browser, perfil);
        const m = await medirTtfa(page, url(news.news_id, "C3"));
        frio.push(m.ttfa_ms); arranqueFrio.push(m.arranque_ms);
        await ctx.close();
      }
    }
    // En caliente: la noticia ya se guardó para uso sin conexión y el Service Worker la sirve
    const { ctx, page } = await abrir(browser, perfil);
    for (const news of NEWS) {
      await page.goto(url(news.news_id, "C3", true));
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.reload();
      await page.waitForSelector("[data-testid=save-offline]");
      await page.click("[data-testid=save-offline]");
      await page.waitForFunction(() => document.querySelector("[data-testid=save-status]")?.textContent?.includes("Guardada"), null, { timeout: 120000 });
      for (let r = 0; r < REPS; r++) {
        await page.reload(); // el Service Worker ya controla la página y la noticia está en su caché
        const m = await medirTtfa(page, null);
        caliente.push(m.ttfa_ms); arranqueCaliente.push(m.arranque_ms);
      }
    }
    await ctx.close();
    salida[perfil] = {
      frio: stats(frio), caliente: stats(caliente),
      arranque_completo_frio: stats(arranqueFrio), arranque_completo_caliente: stats(arranqueCaliente),
    };
    console.log(perfil, JSON.stringify(salida[perfil]));
  }
  // C4: TTFA con el avatar cargándose en paralelo (peor caso para la CPU lenta)
  salida.c4 = {};
  for (const perfil of Object.keys(PERFILES)) {
    const v = [];
    for (const news of NEWS.slice(0, 10)) {
      const { ctx, page } = await abrir(browser, perfil);
      v.push((await medirTtfa(page, url(news.news_id, "C4"))).ttfa_ms);
      await ctx.close();
    }
    salida.c4[perfil] = stats(v);
  }
  save("ttfa.json", { repeticiones: REPS, noticias: NEWS.length, condicion: "C3 (C4 aparte)", resultados: salida });
}

// ------------------------------------------------------------------ 3. reproducción completa
async function reproducir(page, news, c) {
  await page.goto(url(news.news_id, c));
  await page.waitForFunction(() => { const b = document.querySelector("[data-testid=play]"); return b && !b.disabled; }, null, { timeout: 120000 });
  if (c === "C4") await page.waitForFunction(() => document.querySelector("[data-avatar-mode]")?.dataset.avatarMode !== "cargando", null, { timeout: 180000 });
  // todos los tiempos de los segmentos cargados antes de empezar (no se mide la red aquí)
  await page.waitForFunction((n) => window.__app.R.timings.size >= n, news.con_audio, { timeout: 120000 });
  await page.click("[data-testid=play]");
  await page.waitForFunction(() => document.querySelector("[data-testid=status]")?.textContent === "Fin de la noticia", null, { timeout: 300000 });
  return page.evaluate(() => {
    const R = window.__app.R;
    return {
      timeline: window.__app.player.timeline,
      log: R.hl?.log ?? [],
      spans: [...R.timings.entries()].map(([idx, tm]) => ({ idx, spans: tm.spans.map((s) => ({ t: s.orig_text, t0: s.t0, t1: s.t1 })) })),
      items: window.__app.player.items.map((i) => ({ idx: i.idx, url: !!i.url })),
      bloqueados: [...document.querySelectorAll("[data-blocked='1']")].length,
      emitidos: window.__app.events.emitted.length,
    };
  });
}

function analizar(r) {
  const huecos = [];
  for (let i = 0; i + 1 < r.timeline.length; i++) {
    const a = r.timeline[i], b = r.timeline[i + 1];
    if (a.type === "ended" && b.type === "playing") huecos.push(b.t - a.t);
  }
  const desfases = r.log.map((c) => (c.clock_t - c.t0) * 1000);
  const esperados = new Set();
  for (const s of r.spans) s.spans.forEach((sp, i) => { if (sp.t1 > sp.t0 && /[\p{L}\p{N}]/u.test(sp.t)) esperados.add(`${s.idx}:${i}`); });
  const vistos = new Set(r.log.map((c) => `${c.seg}:${c.span}`));
  let cubiertos = 0;
  esperados.forEach((k) => vistos.has(k) && cubiertos++);
  return { huecos, desfases, esperados: esperados.size, cubiertos, bloqueados: r.bloqueados, emitidos: r.emitidos };
}

async function reproduccion(browser) {
  const salida = {};
  const casos = [["C3", "sin-limite", NEWS], ["C3", "movil-4x-4g", NEWS], ["C4", "sin-limite", NEWS.slice(0, 10)], ["C4", "movil-4x-4g", NEWS.slice(0, 10)]];
  for (const [c, perfil, lista] of casos) {
    const huecos = [], desf = [];
    let esp = 0, cub = 0, bloq = 0, completas = 0;
    for (const news of lista) {
      const { ctx, page } = await abrir(browser, perfil);
      try {
        const a = analizar(await reproducir(page, news, c));
        huecos.push(...a.huecos); desf.push(...a.desfases);
        esp += a.esperados; cub += a.cubiertos; bloq += a.bloqueados; completas++;
      } catch (e) {
        console.log("falla", c, perfil, news.news_id, String(e).slice(0, 120));
      }
      await ctx.close();
    }
    const abs = desf.map(Math.abs);
    salida[`${c}/${perfil}`] = {
      noticias: lista.length, completas, huecos_ms: stats(huecos),
      desfase_resaltado_ms: { ...stats(desf), abs_p95: pct(abs, 95), abs_max: Math.max(...abs) },
      cobertura_pct: esp ? (100 * cub) / esp : null, fragmentos_esperados: esp, fragmentos_resaltados: cub, bloqueados_mostrados: bloq,
    };
    console.log(`${c}/${perfil}`, JSON.stringify(salida[`${c}/${perfil}`]));
  }
  save("reproduccion.json", salida);
}

// ------------------------------------------------------------------ 4. FPS y degradación en C4
async function fpsCaso(nombre, args, cpu, c4News) {
  const browser = await chromium.launch({ args });
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: cpu });
  await page.goto(url(c4News.news_id, "C4"));
  await page.waitForFunction(() => document.querySelector("[data-avatar-mode]")?.dataset.avatarMode !== "cargando", null, { timeout: 280000 });
  const modo = await page.evaluate(() => document.querySelector("[data-avatar-mode]").dataset.avatarMode);
  await page.waitForFunction(() => { const b = document.querySelector("[data-testid=play]"); return b && !b.disabled; }, null, { timeout: 60000 });
  await page.click("[data-testid=play]");
  await page.waitForTimeout(800);
  const fps = await page.evaluate(
    () => new Promise((res) => { let n = 0, t0 = 0; const f = (t) => { if (!t0) t0 = t; n++; if (t - t0 >= 5000) res(((n - 1) * 1000) / (t - t0)); else requestAnimationFrame(f); }; requestAnimationFrame(f); }),
  );
  const stats3d = await page.evaluate(() => window.__app.R.handle?.viewer?.stats?.() ?? null);
  const eventos = await page.evaluate(() => window.__app.events.emitted.filter((e) => e.type === "avatar-ok" || e.type === "degradacion").map((e) => ({ tipo: e.type, razon: e.payload.reason, fps: e.payload.fps })));
  const gl = await page.evaluate(() => { const c = document.createElement("canvas"); const g = c.getContext("webgl2") || c.getContext("webgl"); const x = g?.getExtension("WEBGL_debug_renderer_info"); return x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : null; });
  await page.evaluate(() => window.__app.events.flush());
  const delivered = await page.evaluate(() => window.__app.events.pending());
  await browser.close();
  return { nombre, args, cpu_throttle: cpu, modo, fps_5s: Math.round(fps * 10) / 10, dibujo: stats3d, eventos, renderer: gl, eventos_pendientes_tras_flush: delivered };
}

async function fps() {
  const largo = [...NEWS].sort((a, b) => b.duracion_s - a.duracion_s)[0]; // ≥ 5 s de audio
  const filas = [
    await fpsCaso("gpu-x1", GPU, 1, largo),
    await fpsCaso("gpu-cpu4x", GPU, 4, largo),
    await fpsCaso("software-x1", SOFT, 1, largo),
    await fpsCaso("software-cpu4x", SOFT, 4, largo),
  ];
  save("fps.json", { noticia: largo.news_id, duracion_s: largo.duracion_s, casos: filas });
}

async function degradacion() {
  const largo = NEWS.find((n) => n.con_audio >= 2) ?? NEWS[0];
  const filas = [
    await fpsCaso("A-sin-webgl", NOGL, 1, largo),
    await fpsCaso("B-cpu-20x-software", SOFT, 20, largo),
    await fpsCaso("C-normal-gpu", GPU, 1, largo),
  ];
  save("degradacion.json", { noticia: largo.news_id, casos: filas });
}

// ------------------------------------------------------------------ 5. sin conexión y cola de eventos
async function offline(browser) {
  const filas = [];
  const casos = [NEWS[0], NEWS.find((n) => n.bloqueados > 0) ?? NEWS[1], NEWS[2]];
  for (const c of ["C1", "C2", "C3"]) {
    for (const news of casos) {
      const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(url(news.news_id, c, true));
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 30000 });
      await page.waitForSelector("[data-testid=save-offline]");
      await page.click("[data-testid=save-offline]");
      await page.waitForFunction(() => document.querySelector("[data-testid=save-status]")?.textContent?.includes("Guardada"), null, { timeout: 120000 });
      await ctx.setOffline(true);
      await page.reload();
      let abre = false, reproduce = null;
      try {
        await page.waitForSelector(c === "C2" ? "[data-testid=play]" : "[data-testid=body]", { timeout: 20000 });
        abre = true;
        if (c !== "C1") {
          await page.waitForFunction(() => { const b = document.querySelector("[data-testid=play]"); return b && !b.disabled; }, null, { timeout: 20000 });
          await page.click("[data-testid=play]");
          await page.waitForFunction(() => document.querySelector("[data-testid=status]")?.textContent === "Fin de la noticia", null, { timeout: 120000 });
          reproduce = await page.evaluate(() => window.__app.events.emitted.filter((e) => e.type === "segment-end").length);
        }
      } catch (e) {
        console.log("offline falla", c, news.news_id, String(e).slice(0, 100));
      }
      filas.push({ condicion: c, news_id: news.news_id, bloqueados: news.bloqueados, abre_sin_red: abre, segmentos_reproducidos: reproduce, segmentos_con_audio: news.con_audio });
      await ctx.close();
    }
  }
  save("offline.json", { filas, ok: filas.every((f) => f.abre_sin_red && (f.condicion === "C1" || f.segmentos_reproducidos === f.segmentos_con_audio)) });
}

async function eventos(browser) {
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(url(NEWS[0].news_id, "C3"));
  await page.waitForSelector("[data-testid=body]");
  const antes = (await (await page.request.get(`${BASE}/api/events/summary`, { headers: { "x-admin-token": process.env.NA_ADMIN_TOKEN ?? "bench-fase4-token-0123456789" } })).json()).total;
  await ctx.setOffline(true);
  const N = 25;
  await page.evaluate(async (n) => { for (let i = 0; i < n; i++) await window.__app.events.emit("pause", { idx: i }); }, N);
  const pendientes = await page.evaluate(() => window.__app.events.pending());
  await ctx.setOffline(false);
  for (let i = 0; i < 40 && (await page.evaluate(() => window.__app.events.pending())) > 0; i++) await page.waitForTimeout(250);
  await page.evaluate(() => window.__app.events.flush());
  const pend2 = await page.evaluate(() => window.__app.events.pending());
  const despues = (await (await page.request.get(`${BASE}/api/events/summary`, { headers: { "x-admin-token": process.env.NA_ADMIN_TOKEN ?? "bench-fase4-token-0123456789" } })).json()).total;
  const muestra = await page.evaluate(() => window.__app.events.emitted.slice(0, 5));
  const reenvio = await (await page.request.post(`${BASE}/api/events`, { data: { events: muestra } })).json();
  save("eventos.json", { emitidos_sin_red: N, pendientes_sin_red: pendientes, pendientes_al_volver: pend2, recibidos_servidor: despues - antes, entregados_pct: ((despues - antes) / (N + 1)) * 100, duplicados_al_reenviar: reenvio.recibidos - reenvio.nuevos, nuevos_al_reenviar: reenvio.nuevos });
  await ctx.close();
}

const tarea = process.argv[2] ?? "all";
const browser = await chromium.launch({ args: GPU });
try {
  if (["carga", "all"].includes(tarea)) await carga(browser);
  if (["ttfa", "all"].includes(tarea)) await ttfa(browser);
  if (["reproduccion", "all"].includes(tarea)) await reproduccion(browser);
  if (["offline", "all"].includes(tarea)) await offline(browser);
  if (["eventos", "all"].includes(tarea)) await eventos(browser);
} finally {
  await browser.close();
}
if (["fps", "all"].includes(tarea)) await fps();
if (["degradacion", "all"].includes(tarea)) await degradacion();
