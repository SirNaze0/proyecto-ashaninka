// Traducción BiTAM en la sala de redacción (MejoraEIntegracion, Fase 3): cliente y volcado al borrador.
// Las cadenas "cni" de estas pruebas son marcadores de prueba, no asháninka real.
import { describe, expect, it, vi } from "vitest";
import {
  MAX_TITLE_CHARS,
  TranslateError,
  type TranslateResponse,
  aplicarTraduccion,
  emptyDraft,
  estadoTraductor,
  tieneTextoCni,
  toPayload,
  traducir,
  validar,
  validarCastellano,
} from "../src/app/newsroom";

const RESPUESTA: TranslateResponse = {
  titulo_cni: "TITULO-CNI [prueba]",
  paragraphs: ["PARRAFO-1 [prueba]", "  PARRAFO-2   [prueba] "],
  oraciones: [
    { parrafo: -1, es: "Título", cni_modelo: "titulo-cni [prueba]", cni: "TITULO-CNI [prueba]" },
    { parrafo: 0, es: "Uno.", cni_modelo: "parrafo-1 [prueba]", cni: "PARRAFO-1 [prueba]" },
  ],
  procedencia: { tipo: "traduccion_automatica", sistema: "BiTAM es2cni", version: "bitam_v5_run", revisado_por_hablante: false, revisor_id: null },
  modelo: "BiTAM es2cni",
  segundos: 1.5,
  avisos: ["Traducción automática: borrador."],
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("aplicarTraduccion", () => {
  it("rellena título, párrafos y procedencia; conserva castellano y metadatos", () => {
    const base = {
      ...emptyDraft(),
      titulo_es: "Título",
      cuerpo_es: "Uno.",
      fecha_publicacion: "2026-11-02",
      fuente_original: "medio X",
      variante_dialectal: "alto Perené",
    };
    const d = aplicarTraduccion(base, RESPUESTA);
    expect(d.titulo_cni).toBe("TITULO-CNI [prueba]");
    expect(d.paragraphs).toEqual(["PARRAFO-1 [prueba]", "PARRAFO-2 [prueba]"]);
    expect(d.procedencia).toEqual({ tipo: "traduccion_automatica", sistema: "BiTAM es2cni", version: "bitam_v5_run", revisado_por_hablante: false });
    expect(d).toMatchObject({ titulo_es: "Título", cuerpo_es: "Uno.", fecha_publicacion: "2026-11-02", fuente_original: "medio X", variante_dialectal: "alto Perené" });
    expect(base.titulo_cni).toBe(""); // función pura: no muta la entrada
  });

  it("nunca deja la traducción como revisada aunque el borrador lo estuviera", () => {
    const base = emptyDraft();
    base.procedencia = { tipo: "automatica_revisada", sistema: "x", version: "y", revisado_por_hablante: true };
    expect(aplicarTraduccion(base, RESPUESTA).procedencia.revisado_por_hablante).toBe(false);
  });

  it("recorta el título al máximo del editor y tolera párrafos vacíos", () => {
    const d = aplicarTraduccion(emptyDraft(), { ...RESPUESTA, titulo_cni: "x".repeat(400), paragraphs: [] });
    expect(d.titulo_cni).toHaveLength(MAX_TITLE_CHARS);
    expect(d.paragraphs).toEqual([""]);
  });

  it("el borrador traducido es publicable y su payload mantiene la procedencia", () => {
    const d = aplicarTraduccion({ ...emptyDraft(), titulo_es: "T", cuerpo_es: "C" }, RESPUESTA);
    expect(validar(d)).toBeNull();
    const p = toPayload(d) as { procedencia: { tipo: string; revisado_por_hablante: boolean }; cuerpo_cni: string; titulo_es: string };
    expect(p.procedencia).toMatchObject({ tipo: "traduccion_automatica", revisado_por_hablante: false });
    expect(p.cuerpo_cni).toBe("PARRAFO-1 [prueba]\n\nPARRAFO-2 [prueba]");
    expect(p.titulo_es).toBe("T");
  });
});

describe("validarCastellano y tieneTextoCni", () => {
  it("exige título y cuerpo dentro de los límites del servidor", () => {
    expect(validarCastellano({ titulo_es: "", cuerpo_es: "x" })).toMatch(/título/);
    expect(validarCastellano({ titulo_es: "t", cuerpo_es: " " })).toMatch(/cuerpo/);
    expect(validarCastellano({ titulo_es: "t".repeat(301), cuerpo_es: "x" })).toMatch(/300/);
    expect(validarCastellano({ titulo_es: "t", cuerpo_es: "x".repeat(8001) })).toMatch(/8000/);
    expect(validarCastellano({ titulo_es: "t", cuerpo_es: "x" })).toBeNull();
  });
  it("detecta texto en asháninka que se reemplazaría", () => {
    expect(tieneTextoCni(emptyDraft())).toBe(false);
    expect(tieneTextoCni({ ...emptyDraft(), titulo_cni: "T" })).toBe(true);
    expect(tieneTextoCni({ ...emptyDraft(), paragraphs: ["", "p"] })).toBe(true);
  });
});

describe("traducir", () => {
  it("envía título y cuerpo sin token (QuitarAdmin)", async () => {
    const f = vi.fn(async () => json(200, RESPUESTA));
    const r = await traducir({ titulo_es: "  Título ", cuerpo_es: "Uno. " }, undefined, f as unknown as typeof fetch);
    expect(r).toEqual(RESPUESTA);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/news/translate");
    expect(init.method).toBe("POST");
    expect(init.headers as Record<string, string>).not.toHaveProperty("x-admin-token");
    expect(JSON.parse(init.body as string)).toEqual({ titulo_es: "Título", cuerpo_es: "Uno." });
  });

  it.each([
    [422, { detail: "el cuerpo supera 8000 caracteres" }],
    [502, { detail: "Error del traductor: el traductor respondió 500" }],
    [503, { detail: "Traductor no disponible: no se pudo conectar" }],
  ])("HTTP %i -> TranslateError con estado y detalle", async (status, body) => {
    const f = vi.fn(async () => json(status, body));
    const err = await traducir({ titulo_es: "t", cuerpo_es: "c" }, undefined, f as unknown as typeof fetch).catch((e) => e);
    expect(err).toBeInstanceOf(TranslateError);
    expect(err.status).toBe(status);
    expect(err.message).toBe(body.detail);
    expect(err.cancelada).toBe(false);
  });

  it("sin conexión -> estado 0", async () => {
    const f = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    const err = await traducir({ titulo_es: "t", cuerpo_es: "c" }, undefined, f as unknown as typeof fetch).catch((e) => e);
    expect(err).toBeInstanceOf(TranslateError);
    expect(err.status).toBe(0);
    expect(err.cancelada).toBe(false);
  });

  it("cancelada por el usuario (AbortController)", async () => {
    const ctl = new AbortController();
    const f = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_res, rej) => init.signal?.addEventListener("abort", () => rej(new DOMException("abort", "AbortError")))),
    );
    const p = traducir({ titulo_es: "t", cuerpo_es: "c" }, ctl.signal, f as unknown as typeof fetch).catch((e) => e);
    ctl.abort();
    const err = await p;
    expect(err).toBeInstanceOf(TranslateError);
    expect(err.cancelada).toBe(true);
  });
});

describe("estadoTraductor", () => {
  it("devuelve el estado del servidor", async () => {
    const f = vi.fn(async () => json(200, { disponible: true, motivo: null, modelo: "BiTAM es2cni", version: "v", dispositivo: "cuda:0" }));
    const s = await estadoTraductor(f as unknown as typeof fetch);
    expect(s).toMatchObject({ disponible: true, dispositivo: "cuda:0" });
    const [url] = f.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/news/translate/status");
  });
  it("nunca lanza: error HTTP o de red -> no disponible con motivo", async () => {
    const e503 = await estadoTraductor(vi.fn(async () => json(503, { detail: "apagado" })) as unknown as typeof fetch);
    expect(e503).toEqual({ disponible: false, motivo: "apagado" });
    const red = await estadoTraductor(
      vi.fn(async () => {
        throw new TypeError("x");
      }) as unknown as typeof fetch,
    );
    expect(red.disponible).toBe(false);
    expect(red.motivo).toMatch(/conexión/);
  });
});
