// Cliente y formato del lector de TV Perú (NoticiasTVPeru).
import { describe, expect, it, vi } from "vitest";
import { type FeedStatus, fetchFeedStatus, refrescarAhora, relativo, resumenUltimo, setIntervalo, sondeoMs } from "../src/app/feed";

const BASE: FeedStatus = {
  habilitado: true,
  fuente: "TV Perú",
  fuente_url: "https://www.tvperu.gob.pe/rss.xml",
  intervalo_min: 30,
  intervalos_permitidos: [0, 15, 30, 60, 180, 360],
  max_por_ciclo: 3,
  ejecutando: false,
  ultima_ejecucion: null,
  proxima_ejecucion: null,
  ultimo_resultado: null,
  items: { pendiente: 0, publicada: 0, error: 0, descartada: 0 },
};
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("cliente /api/feed", () => {
  it("estado: devuelve null si el servidor no responde o no tiene la función", async () => {
    expect(await fetchFeedStatus(vi.fn(async () => json(200, BASE)) as unknown as typeof fetch)).toEqual(BASE);
    expect(await fetchFeedStatus(vi.fn(async () => json(404, {})) as unknown as typeof fetch)).toBeNull();
    expect(
      await fetchFeedStatus(
        vi.fn(async () => {
          throw new TypeError("x");
        }) as unknown as typeof fetch,
      ),
    ).toBeNull();
  });

  it("cambia el intervalo con PUT y sin token", async () => {
    const f = vi.fn(async () => json(200, { ...BASE, intervalo_min: 60 }));
    const s = await setIntervalo(60, f as unknown as typeof fetch);
    expect(s?.intervalo_min).toBe(60);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/feed/config");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ intervalo_min: 60 });
    expect(init.headers).not.toHaveProperty("x-admin-token");
  });

  it.each([
    [202, "iniciado"],
    [409, "en-curso"],
    [503, "apagado"],
    [500, "error"],
  ] as const)("refrescar: HTTP %i -> %s", async (status, esperado) => {
    expect(await refrescarAhora(vi.fn(async () => json(status, {})) as unknown as typeof fetch)).toBe(esperado);
  });
});

describe("formato", () => {
  const ahora = Date.parse("2026-11-02T12:00:00Z");
  it.each([
    [null, null],
    ["no es fecha", null],
    ["2026-11-02T12:00:10Z", { clave: "feed.time.justNow", n: 0 }],
    ["2026-11-02T11:55:00Z", { clave: "feed.time.agoMin", n: 5 }],
    ["2026-11-02T12:30:00Z", { clave: "feed.time.inMin", n: 30 }],
    ["2026-11-02T09:00:00Z", { clave: "feed.time.agoH", n: 3 }],
    ["2026-11-02T18:00:00Z", { clave: "feed.time.inH", n: 6 }],
  ])("relativo(%s)", (iso, esperado) => {
    expect(relativo(iso, ahora)).toEqual(esperado);
  });

  it("resume el último ciclo", () => {
    expect(resumenUltimo(BASE)).toBeNull();
    const r = { inicio: "x", nuevas: 5, publicadas: [{ news_id: 1, url: "u" }], errores: 0, pendientes: 2, motivo: null };
    expect(resumenUltimo({ ...BASE, ultimo_resultado: r })).toEqual({ clave: "feed.last.published", vars: { n: 1, p: 2 } });
    expect(resumenUltimo({ ...BASE, ultimo_resultado: { ...r, publicadas: [], motivo: "traductor no disponible" } })).toEqual({
      clave: "feed.last.failed",
      vars: { m: "traductor no disponible" },
    });
    expect(resumenUltimo({ ...BASE, ultimo_resultado: { ...r, publicadas: [] } })?.clave).toBe("feed.last.nothing");
  });

  it("sondea rápido solo mientras corre un ciclo", () => {
    expect(sondeoMs({ ...BASE, ejecutando: true })).toBe(5_000);
    expect(sondeoMs(BASE)).toBe(60_000);
    expect(sondeoMs(null)).toBe(60_000);
  });
});
