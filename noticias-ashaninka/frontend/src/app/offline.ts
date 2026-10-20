// «Guardar para escuchar sin conexión»: baja el manifiesto, los tiempos y el audio de la noticia
// a la misma caché que usa el Service Worker (`na-news-v1`), para que se pueda abrir sin red.
import { pickSource } from "./queue";
import type { Manifest } from "./types";

export const NEWS_CACHE = "na-news-v1";
export const CATALOG_CACHE = "na-catalog-v1";

async function put(cache: Cache, url: string): Promise<boolean> {
  const r = await fetch(url);
  if (!r.ok) return false;
  await cache.put(new Request(url), r);
  return true;
}

/** Guarda una noticia completa; devuelve cuántos archivos quedaron guardados. */
export async function saveNews(id: number, withAudio: boolean): Promise<number> {
  if (typeof caches === "undefined") throw new Error("Cache API no disponible");
  const cache = await caches.open(NEWS_CACHE);
  const catalog = await caches.open(CATALOG_CACHE);
  let n = 0;
  for (const u of ["/api/catalog", `/api/catalog/${id}`, `/api/catalog/${id}/meta`]) {
    const r = await fetch(u);
    if (r.ok) {
      await catalog.put(new Request(u), r);
      n++;
    }
  }
  if (!withAudio) return n;
  const mUrl = `/static/news/${id}/manifest.json`;
  const mRes = await fetch(mUrl);
  if (!mRes.ok) return n;
  await cache.put(new Request(mUrl), mRes.clone());
  n++;
  const manifest = (await mRes.json()) as Manifest;
  const probe = typeof Audio === "undefined" ? () => "" : (m: string) => new Audio().canPlayType(m);
  for (const s of manifest.segments) {
    if (!s.audio) continue;
    const urls = [pickSource(s.audio, probe), s.timings].filter((u): u is string => !!u);
    for (const u of urls) if (await put(cache, u)) n++;
  }
  return n;
}

/** Cuántas noticias hay guardadas para uso sin conexión (solo lee la caché local, sin red). */
export async function savedCount(): Promise<number> {
  if (typeof caches === "undefined") return 0;
  try {
    const keys = await (await caches.open(NEWS_CACHE)).keys();
    return keys.filter((r) => /\/static\/news\/\d+\/manifest\.json$/.test(new URL(r.url).pathname)).length;
  } catch {
    return 0;
  }
}

export async function isSaved(id: number): Promise<boolean> {
  if (typeof caches === "undefined") return false;
  return !!(await caches.match(`/static/news/${id}/manifest.json`));
}
