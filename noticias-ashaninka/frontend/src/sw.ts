/// <reference lib="webworker" />
// Service Worker de la PWA (tarea 4.4), escrito a mano para controlar `Range`.
//  - shell: precarga (lista inyectada al compilar; NO incluye el avatar, que va fuera del presupuesto).
//  - /static/news y /static/audio: caché primero (el audio se nombra por su hash: inmutable).
//    Se guarda el archivo completo y se contesta 206 a las peticiones `Range`.
//  - /api/catalog: red primero con la caché de respaldo (sin conexión).
//  - /assets y /models (avatar): se guardan al usarse por primera vez.
import { rangeResponse, strategyFor } from "./sw-logic";

declare const self: ServiceWorkerGlobalScope;
declare const __PRECACHE__: string[];
declare const __VERSION__: string;

const SHELL = `na-shell-${__VERSION__}`;
const NEWS = "na-news-v1"; // también la escribe la página al «guardar para escuchar sin conexión»
const RUNTIME = "na-runtime-v1";
const CATALOG = "na-catalog-v1";

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(SHELL)
      .then((c) => c.addAll(__PRECACHE__))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("na-shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function newsCacheFirst(req: Request): Promise<Response> {
  const cache = await caches.open(NEWS);
  const key = new Request(req.url); // sin cabecera Range: la entrada guardada es el archivo completo
  let hit = await cache.match(key);
  if (!hit) {
    const net = await fetch(key); // pide el archivo completo aunque el cliente pida un rango
    if (net.ok && net.status === 200) {
      await cache.put(key, net.clone());
      hit = net;
    } else return net;
  }
  const range = req.headers.get("range");
  if (!range) return hit;
  return rangeResponse(await hit.arrayBuffer(), range, hit.headers.get("content-type") ?? "application/octet-stream");
}

async function catalogNetworkFirst(req: Request): Promise<Response> {
  const cache = await caches.open(CATALOG);
  try {
    const net = await fetch(req);
    if (net.ok) await cache.put(req, net.clone());
    return net;
  } catch {
    const hit = await cache.match(req);
    if (hit) return hit;
    return new Response(JSON.stringify({ detail: "sin conexión" }), {
      status: 503,
      headers: { "content-type": "application/json" },
    });
  }
}

async function runtimeCacheFirst(req: Request): Promise<Response> {
  const cache = await caches.open(RUNTIME);
  const hit = await cache.match(req);
  if (hit) return hit;
  const net = await fetch(req);
  if (net.ok && net.status === 200) await cache.put(req, net.clone());
  return net;
}

async function shell(req: Request): Promise<Response> {
  const cache = await caches.open(SHELL);
  if (req.mode === "navigate") {
    try {
      return await fetch(req);
    } catch {
      return (await cache.match("/index.html")) ?? Response.error();
    }
  }
  return (await cache.match(req, { ignoreSearch: true })) ?? fetch(req);
}

const HANDLERS = {
  shell,
  "news-cache-first": newsCacheFirst,
  "catalog-network-first": catalogNetworkFirst,
  "runtime-cache-first": runtimeCacheFirst,
};

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  const s = strategyFor(url, e.request.method, e.request.mode === "navigate");
  if (s === "network") return;
  e.respondWith(HANDLERS[s](e.request));
});
