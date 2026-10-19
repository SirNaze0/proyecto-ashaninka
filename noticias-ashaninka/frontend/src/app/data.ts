// Acceso a datos: catálogo, manifiesto 1.1, tiempos por segmento y respaldo NDJSON.
import type { CatalogDetail, CatalogItem, Manifest, Notices, Seg, SegTimings } from "./types";

// Avatar provisional (C4 y pantalla de traducción) y su imagen fija de respaldo
export const VRM_URL = "/models/presentadora_provisional.vrm";
export const FALLBACK_IMG = "/presentadora_fija.svg";

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return (await r.json()) as T;
}

export const fetchCatalog = () => json<CatalogItem[]>("/api/catalog");
export const fetchDetail = (id: number) => json<CatalogDetail>(`/api/catalog/${id}`);
export const fetchMeta = (id: number) => json<CatalogItem>(`/api/catalog/${id}/meta`);
export const fetchTimings = (url: string) => json<SegTimings>(url);

/** Manifiesto por lotes, o `null` si la noticia aún no se sintetizó (404). */
export async function fetchManifest(id: number): Promise<Manifest | null> {
  const r = await fetch(`/static/news/${id}/manifest.json`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`manifiesto ${id}: ${r.status}`);
  return (await r.json()) as Manifest;
}

/** Convierte líneas NDJSON a eventos, tolerando que un fragmento llegue partido entre lecturas. */
export function createNdjsonParser(onEvent: (e: Record<string, unknown>) => void) {
  let buf = "";
  return {
    push(chunk: string) {
      buf += chunk;
      let nl = buf.indexOf("\n");
      while (nl >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) onEvent(JSON.parse(line) as Record<string, unknown>);
        nl = buf.indexOf("\n");
      }
    },
    end() {
      const line = buf.trim();
      buf = "";
      if (line) onEvent(JSON.parse(line) as Record<string, unknown>);
    },
  };
}

export interface StreamHandlers {
  onMeta(notices: Notices, total: number): void;
  onSegment(seg: Seg): void;
  onDone(): void;
}

/** Respaldo bajo demanda: `/api/synthesize/{id}` entrega una oración por línea a medida que se genera. */
export async function streamSynthesis(id: number, h: StreamHandlers, signal?: AbortSignal): Promise<void> {
  const r = await fetch(`/api/synthesize/${id}`, { signal });
  if (!r.ok || !r.body) throw new Error(`síntesis ${id}: ${r.status}`);
  const parser = createNdjsonParser((e) => {
    switch (e.event) {
      case "meta":
        h.onMeta(e.notices as Notices, Number(e.segments));
        break;
      case "segment":
      case "blocked":
        h.onSegment(e as unknown as Seg);
        break;
      case "done":
        h.onDone();
        break;
    }
  });
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.push(value);
  }
  parser.end();
}
