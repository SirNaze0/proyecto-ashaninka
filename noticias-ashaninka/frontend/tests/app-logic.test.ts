import { describe, expect, it } from "vitest";
import { createNdjsonParser } from "../src/app/data";
import { activeSpan, Highlighter, highlightable, spansMatch } from "../src/app/highlight";
import { pendingCount, translate } from "../src/app/i18n";
import { blockedBetween, clampRate, nextParagraphStart, nextPlayable, paragraphStart, pickSource, type PlayerItem } from "../src/app/queue";
import { NEWS_HREF, parseHash, newsHref } from "../src/app/router";
import type { Span } from "../src/app/types";
import { parseRange, rangeResponse, strategyFor } from "../src/sw-logic";

const item = (idx: number, paragraph: number, url: string | null): PlayerItem => ({ idx, paragraph, url, blockedReason: url ? null : "bloqueado" });

describe("router", () => {
  it("interpreta las rutas y la condición", () => {
    // la entrada principal es la pantalla de traducción; la lista vive en #/noticias
    expect(parseHash("")).toEqual({ name: "translate" });
    expect(parseHash("#/")).toEqual({ name: "translate" });
    expect(parseHash("#/desconocida")).toEqual({ name: "translate" });
    expect(parseHash("#/noticias")).toEqual({ name: "list" });
    expect(parseHash(NEWS_HREF)).toEqual({ name: "list" });
    expect(parseHash("#/ajustes")).toEqual({ name: "settings" });
    expect(parseHash("#/noticia/7?c=C2")).toEqual({ name: "news", id: 7, condition: "C2" });
    expect(parseHash("#/noticia/7?c=c4")).toEqual({ name: "news", id: 7, condition: "C4" });
    expect(parseHash("#/noticia/7?c=Z9")).toEqual({ name: "news", id: 7, condition: "C3" });
    expect(parseHash("#/noticia/abc")).toEqual({ name: "list" });
    expect(newsHref(3, "C1")).toBe("#/noticia/3?c=C1");
  });
});

describe("cola del reproductor", () => {
  const items = [item(0, 0, "a"), item(1, 0, null), item(2, 1, "c"), item(3, 1, null), item(4, 2, "e")];
  it("encuentra el siguiente segmento con audio", () => {
    expect(nextPlayable(items, 0)).toBe(2);
    expect(nextPlayable(items, 2)).toBe(4);
    expect(nextPlayable(items, 4)).toBe(-1);
  });
  it("lista los bloqueados que se saltan", () => {
    expect(blockedBetween(items, 0, 2)).toEqual([1]);
    expect(blockedBetween(items, 2, -1)).toEqual([3]);
  });
  it("encuentra el inicio del párrafo y el siguiente", () => {
    expect(paragraphStart(items, 3)).toBe(2);
    expect(paragraphStart([item(0, 0, null), item(1, 0, null)], 1)).toBe(1);
    expect(nextParagraphStart(items, 0)).toBe(2);
    expect(nextParagraphStart(items, 4)).toBe(-1);
  });
  it("limita la velocidad a 0,75–1,25 y elige Opus o MP3", () => {
    expect(clampRate(0.1)).toBe(0.75);
    expect(clampRate(3)).toBe(1.25);
    expect(clampRate(Number.NaN)).toBe(1);
    const a = { opus: "x.opus", mp3: "x.mp3", opus_kbps: 25, mp3_kbps: 33 };
    expect(pickSource(a, () => "probably")).toBe("x.opus");
    expect(pickSource(a, () => "")).toBe("x.mp3");
  });
});

const spans: Span[] = [
  { orig_start: 0, orig_end: 5, orig_text: "MINSA", category: "sigla", t0: 0, t1: 1.2 },
  { orig_start: 5, orig_end: 6, orig_text: " ", category: "identity", t0: 1.2, t1: 1.3 },
  { orig_start: 6, orig_end: 10, orig_text: "2026", category: "numero", t0: 1.3, t1: 2.5 },
  { orig_start: 10, orig_end: 11, orig_text: ".", category: "identity", t0: 2.5, t1: 2.5 },
];

describe("resaltado", () => {
  it("solo resalta fragmentos con letras o dígitos y duración", () => {
    expect(highlightable(spans)).toEqual([0, 2]);
  });
  it("el fragmento activo es el último que empezó (sin parpadeo entre palabras)", () => {
    const c = highlightable(spans);
    expect(activeSpan(spans, c, -0.1)).toBe(-1);
    expect(activeSpan(spans, c, 0)).toBe(0);
    expect(activeSpan(spans, c, 1.25)).toBe(0); // en el espacio se mantiene MINSA
    expect(activeSpan(spans, c, 1.3)).toBe(2);
    expect(activeSpan(spans, c, 99)).toBe(2);
  });
  it("los fragmentos reconstruyen la oración", () => {
    expect(spansMatch(spans, "MINSA 2026.")).toBe(true);
    expect(spansMatch(spans, "otro texto")).toBe(false);
  });
  it("cambia la clase solo cuando cambia el fragmento y registra el desfase", () => {
    const els = new Map<string, Set<string>>();
    const mk = (k: string) => ({
      classList: { add: (c: string) => els.get(k)?.add(c), remove: (c: string) => els.get(k)?.delete(c) },
      scrollIntoView: () => {},
    });
    ["3|0", "3|2"].forEach((k) => els.set(k, new Set()));
    const root = {
      querySelector: (sel: string) => {
        const m = /data-seg="(\d+)"\] \[data-span="(\d+)"/.exec(sel);
        const k = `${m?.[1]}|${m?.[2]}`;
        return els.has(k) ? mk(k) : null;
      },
    } as unknown as HTMLElement;
    let t = 0;
    const hl = new Highlighter(root, () => t);
    hl.setSegment(3, spans);
    hl.step();
    expect(els.get("3|0")?.has("hl")).toBe(true);
    t = 1.32;
    hl.step();
    expect(els.get("3|0")?.has("hl")).toBe(false);
    expect(els.get("3|2")?.has("hl")).toBe(true);
    hl.step(); // sin cambio: no se registra otra vez
    expect(hl.log).toEqual([
      { seg: 3, span: 0, clock_t: 0, t0: 0 },
      { seg: 3, span: 2, clock_t: 1.32, t0: 1.3 },
    ]);
    hl.reset();
    expect(els.get("3|2")?.has("hl")).toBe(false);
  });
  it("reintenta si el texto con fragmentos aún no está en el DOM", () => {
    const root = { querySelector: () => null } as unknown as HTMLElement;
    const hl = new Highlighter(root, () => 0.5);
    hl.setSegment(1, spans);
    hl.step();
    expect(hl.log).toHaveLength(0);
  });
});

describe("NDJSON", () => {
  it("une líneas partidas entre lecturas", () => {
    const got: Record<string, unknown>[] = [];
    const p = createNdjsonParser((e) => got.push(e));
    p.push('{"event":"meta","segments":2}\n{"event":"seg');
    p.push('ment","idx":0}\n{"event":"done"}');
    p.end();
    expect(got.map((e) => e.event)).toEqual(["meta", "segment", "done"]);
  });
});

describe("i18n", () => {
  it("cae al castellano si el asháninka está pendiente y nunca inventa texto", () => {
    expect(translate("cni", "list.title")).toBe(translate("es", "list.title"));
    expect(translate("es", "news.numbered", { n: 4 })).toBe("Noticia 4");
    expect(translate("es", "no.existe")).toBe("no.existe");
    expect(pendingCount()).toBeGreaterThan(30);
  });
});

describe("Service Worker (lógica pura)", () => {
  it("interpreta los rangos de bytes", () => {
    expect(parseRange(null, 100)).toBe("none");
    expect(parseRange("bytes=0-9", 100)).toEqual({ start: 0, end: 9 });
    expect(parseRange("bytes=90-", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=-10", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=0-999", 100)).toEqual({ start: 0, end: 99 });
    expect(parseRange("bytes=100-", 100)).toBeNull();
    expect(parseRange("basura", 100)).toBeNull();
  });
  it("responde 206 con Content-Range y 416 si no es satisfacible", async () => {
    const buf = new Uint8Array(100).map((_, i) => i).buffer;
    const r = rangeResponse(buf, "bytes=10-19", "audio/ogg");
    expect(r.status).toBe(206);
    expect(r.headers.get("Content-Range")).toBe("bytes 10-19/100");
    expect(new Uint8Array(await r.arrayBuffer())[0]).toBe(10);
    expect(rangeResponse(buf, "bytes=500-", "audio/ogg").status).toBe(416);
    expect(rangeResponse(buf, null, "audio/ogg").status).toBe(200);
  });
  it("elige la estrategia por ruta", () => {
    const u = (p: string) => new URL(p, "http://x");
    expect(strategyFor(u("/static/audio/ab/x.opus"), "GET", false)).toBe("news-cache-first");
    expect(strategyFor(u("/static/news/1/manifest.json"), "GET", false)).toBe("news-cache-first");
    expect(strategyFor(u("/api/catalog/1"), "GET", false)).toBe("catalog-network-first");
    expect(strategyFor(u("/api/events"), "POST", false)).toBe("network");
    expect(strategyFor(u("/api/synthesize/1"), "GET", false)).toBe("network");
    expect(strategyFor(u("/assets/three.js"), "GET", false)).toBe("runtime-cache-first");
    expect(strategyFor(u("/models/a.vrm"), "GET", false)).toBe("runtime-cache-first");
    expect(strategyFor(u("/"), "GET", true)).toBe("shell");
  });
});
