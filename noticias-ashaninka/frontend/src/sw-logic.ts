// Lógica pura del Service Worker (probada con vitest): respuestas parciales para `Range`.
// <audio> pide `Range: bytes=…`; la caché guarda el archivo completo y el SW debe contestar 206.

export interface ByteRange {
  start: number;
  end: number; // inclusive
}

/** Interpreta `bytes=a-b`, `bytes=a-` y `bytes=-n`. `null` = inválido (416); "none" = sin Range. */
export function parseRange(header: string | null, size: number): ByteRange | null | "none" {
  if (!header) return "none";
  const m = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!m || (m[1] === "" && m[2] === "")) return null;
  let start: number;
  let end: number;
  if (m[1] === "") {
    const n = Number(m[2]);
    if (n === 0) return null;
    start = Math.max(0, size - n);
    end = size - 1;
  } else {
    start = Number(m[1]);
    end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  }
  if (start >= size || start > end) return null;
  return { start, end };
}

export function rangeResponse(buf: ArrayBuffer, header: string | null, contentType: string): Response {
  const size = buf.byteLength;
  const r = parseRange(header, size);
  const base = { "Accept-Ranges": "bytes", "Content-Type": contentType };
  if (r === "none") return new Response(buf, { status: 200, headers: { ...base, "Content-Length": String(size) } });
  if (r === null) return new Response(null, { status: 416, headers: { ...base, "Content-Range": `bytes */${size}` } });
  const part = buf.slice(r.start, r.end + 1);
  return new Response(part, {
    status: 206,
    headers: { ...base, "Content-Length": String(part.byteLength), "Content-Range": `bytes ${r.start}-${r.end}/${size}` },
  });
}

/** Qué estrategia aplica a una ruta (la usa sw.ts; separada para probarla). */
export type Strategy = "shell" | "news-cache-first" | "catalog-network-first" | "runtime-cache-first" | "network";

export function strategyFor(url: URL, method: string, isNavigation: boolean): Strategy {
  if (method !== "GET") return "network";
  const p = url.pathname;
  if (isNavigation) return "shell";
  if (p.startsWith("/static/news/") || p.startsWith("/static/audio/")) return "news-cache-first";
  if (p === "/api/catalog" || p.startsWith("/api/catalog/")) return "catalog-network-first";
  if (p.startsWith("/api/")) return "network";
  if (p.startsWith("/assets/") || p.startsWith("/models/")) return "runtime-cache-first";
  return "shell";
}
