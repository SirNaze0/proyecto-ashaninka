// Sala de redacción: lectura de archivos al contrato de ingesta, validación y publicación.
import { describe, expect, it, vi } from "vitest";
import { PublishError, emptyDraft, parseCsv, parseJson, parsePlainText, publicar, toPayload, validar } from "../src/app/newsroom";
import { puedeVerRedaccion, verificarToken } from "../src/app/role";

describe("parsePlainText", () => {
  it("toma «Título:» y separa párrafos por línea en blanco", () => {
    const d = parsePlainText("Título: Uno dos\n\nPrimer párrafo.\n\nSegundo párrafo.");
    expect(d.titulo_cni).toBe("Uno dos");
    expect(d.paragraphs).toEqual(["Primer párrafo.", "Segundo párrafo."]);
  });
  it("sin «Título:» la primera línea es el título", () => {
    const d = parsePlainText("Titular\nlinea a\nlinea b");
    expect(d.titulo_cni).toBe("Titular");
    expect(d.paragraphs).toEqual(["linea a", "linea b"]);
  });
  it("recorta a 12 párrafos de 2000 caracteres", () => {
    const d = parsePlainText(`T\n${Array.from({ length: 20 }, () => "x".repeat(3000)).join("\n\n")}`);
    expect(d.paragraphs).toHaveLength(12);
    expect(d.paragraphs[0]).toHaveLength(2000);
  });
});

describe("parseJson", () => {
  it("acepta un objeto NewsIn con procedencia", () => {
    const [d] = parseJson(
      JSON.stringify({
        titulo_cni: "T",
        cuerpo_cni: "a\n\nb",
        variante_dialectal: "alto Perené",
        fecha_publicacion: "2026-10-04",
        procedencia: { tipo: "traduccion_humana", sistema: "equipo", revisado_por_hablante: true },
      }),
    );
    expect(d.paragraphs).toEqual(["a", "b"]);
    expect(d.variante_dialectal).toBe("alto Perené");
    expect(d.procedencia).toMatchObject({ tipo: "traduccion_humana", sistema: "equipo", revisado_por_hablante: true });
  });
  it("acepta lista y {noticias: [...]}, máximo 50", () => {
    const n = { titulo_cni: "T", cuerpo_cni: "c" };
    expect(parseJson(JSON.stringify([n, n]))).toHaveLength(2);
    expect(parseJson(JSON.stringify({ noticias: Array.from({ length: 80 }, () => n) }))).toHaveLength(50);
  });
  it("una procedencia desconocida cae al valor seguro (automática, sin revisar)", () => {
    const [d] = parseJson(JSON.stringify({ titulo_cni: "T", cuerpo_cni: "c", procedencia: { tipo: "inventada" } }));
    expect(d.procedencia.tipo).toBe("traduccion_automatica");
    expect(d.procedencia.revisado_por_hablante).toBe(false);
  });
});

describe("parseCsv", () => {
  it("lee columnas del contrato, con comillas y separador ;", () => {
    const [a, b] = parseCsv('titulo_cni;cuerpo_cni;tipo\n"Uno";"p1\n\np2";traduccion_humana\nDos;solo;\n');
    expect(a.paragraphs).toEqual(["p1", "p2"]);
    expect(a.procedencia.tipo).toBe("traduccion_humana");
    expect(b.titulo_cni).toBe("Dos");
  });
  it("exige titulo_cni y cuerpo_cni", () => {
    expect(() => parseCsv("a,b\n1,2")).toThrow(/titulo_cni/);
  });
});

describe("validar y toPayload", () => {
  it("exige título y cuerpo", () => {
    expect(validar(emptyDraft())).toMatch(/título/);
    expect(validar({ ...emptyDraft(), titulo_cni: "T" })).toMatch(/cuerpo/);
  });
  it("revisada por hablante no puede ser «automática» a secas", () => {
    const d = { ...emptyDraft(), titulo_cni: "T", paragraphs: ["p"] };
    d.procedencia = { ...d.procedencia, revisado_por_hablante: true };
    expect(validar(d)).toMatch(/revisada/);
  });
  it("el cuerpo se une con líneas en blanco y los vacíos van como null", () => {
    const d = { ...emptyDraft(), titulo_cni: " T ", paragraphs: ["a", "", "b"] };
    const p = toPayload(d) as { cuerpo_cni: string; titulo_es: unknown; fecha_publicacion: unknown; procedencia: Record<string, unknown> };
    expect(p.cuerpo_cni).toBe("a\n\nb");
    expect(p.titulo_es).toBeNull();
    expect(p.fecha_publicacion).toBeNull();
    expect(p.procedencia).toMatchObject({ tipo: "traduccion_automatica", sistema: null, revisor_id: null });
  });
});

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

describe("publicar", () => {
  it("encadena crear → procesar → sintetizar → segmentos con el token", async () => {
    const f = vi.fn(async (url: string | URL | Request, _init?: RequestInit) => {
      const u = String(url);
      if (u.endsWith("/process")) return ok({ segmentos: 3 });
      if (u.endsWith("/build")) return ok({ noticias: 1 });
      if (u.endsWith("/segments")) return ok([{ tts_ready: true }, { tts_ready: true }, { tts_ready: false }]);
      return ok({ id: 7 });
    });
    const d = { ...emptyDraft(), titulo_cni: "T", paragraphs: ["p"] };
    const r = await publicar(d, "tok", f as unknown as typeof fetch);
    expect(r).toEqual({ id: 7, segmentos: 3, conAudio: 2, bloqueados: 1 });
    expect(f.mock.calls.map((c) => String(c[0]))).toEqual(["/api/news", "/api/news/7/process", "/api/news/7/build", "/api/news/7/segments"]);
    for (const c of f.mock.calls) expect((c[1] as RequestInit).headers).toMatchObject({ "x-admin-token": "tok" });
  });
  it("informa el paso que falló", async () => {
    const f = vi.fn(async (url: string | URL | Request) =>
      String(url).endsWith("/build") ? new Response(JSON.stringify({ detail: "boom" }), { status: 500 }) : ok({ id: 1, segmentos: 1 }),
    );
    const d = { ...emptyDraft(), titulo_cni: "T", paragraphs: ["p"] };
    await expect(publicar(d, "tok", f as unknown as typeof fetch)).rejects.toMatchObject({ paso: "sintetizar", status: 500, message: "boom" });
    await expect(publicar(d, "tok", (() => Promise.reject(new Error("x"))) as unknown as typeof fetch)).rejects.toBeInstanceOf(PublishError);
  });
});

describe("rol y token", () => {
  it("verificarToken distingue ok, rechazado y red", async () => {
    const r = (status: number) => (async () => new Response("[]", { status })) as unknown as typeof fetch;
    expect(await verificarToken("t", r(200))).toBe("ok");
    expect(await verificarToken("t", r(403))).toBe("rechazado");
    expect(await verificarToken("t", r(500))).toBe("red");
    expect(await verificarToken("t", (() => Promise.reject(new Error("x"))) as unknown as typeof fetch)).toBe("red");
    expect(await verificarToken("  ", r(200))).toBe("rechazado");
  });
  it("la redacción exige rol administrador y token verificado", () => {
    expect(puedeVerRedaccion("ciudadano", "t")).toBe(false);
    expect(puedeVerRedaccion("admin", null)).toBe(false);
    expect(puedeVerRedaccion("admin", "t")).toBe(true);
  });
});
