import { describe, expect, it } from "vitest";
import { EventQueue, MemoryStore } from "../src/app/events";
import {
  type Answers,
  type ExperimentState,
  ExperimentController,
  ExperimentError,
  type ItemDef,
  MemoryKeyStore,
  MemoryResponseStore,
  type ResponseRecord,
  ResponseQueue,
  WILLIAMS_4,
  avanzar,
  detectarPii,
  guardia,
  indiceDeCodigo,
  normalizarCodigo,
  progresoDesde,
  rutaDeEstado,
  secuenciaEsperada,
  validarRespuestas,
} from "../src/app/experiment";
import { parseHash } from "../src/app/router";
import vector from "./fixtures/williams_vector.json";

const POST: ItemDef[] = [
  ...[1, 2, 3, 4].map((i) => ({ id: `comp_${i}`, tipo: "binario" as const, etiqueta: `c${i}`, status: "PENDIENTE-HABLANTE" })),
  { id: "esfuerzo", tipo: "entero", min: 1, max: 9, etiqueta: "e", status: "x" },
  { id: "acep_facilidad", tipo: "entero", min: 1, max: 5, etiqueta: "f", status: "x" },
  { id: "acep_agrado", tipo: "entero", min: 1, max: 5, etiqueta: "a", status: "x" },
  { id: "acep_confianza", tipo: "entero", min: 1, max: 5, etiqueta: "c", status: "x" },
];
const FINAL: ItemDef[] = [
  { id: "variante", tipo: "opcion", opciones: ["otra", "no_sabe"], etiqueta: "v", status: "x" },
  ...["C1", "C2", "C3", "C4"].map((c) => ({ id: `rank_${c}`, tipo: "entero" as const, min: 1, max: 4, etiqueta: c, status: "x" })),
  { id: "comentario", tipo: "texto", max: 500, opcional: true, etiqueta: "x", status: "x" },
];
const POST_OK: Answers = { comp_1: 1, comp_2: 0, comp_3: 1, comp_4: 1, esfuerzo: 5, acep_facilidad: 4, acep_agrado: 3, acep_confianza: 5 };
const FINAL_OK: Answers = { variante: "otra", rank_C1: 4, rank_C2: 3, rank_C3: 1, rank_C4: 2 };

const NEWS = [11, 12, 13, 14];

function estado(over: Partial<ExperimentState> = {}): ExperimentState {
  const seq = secuenciaEsperada(6);
  return {
    participant_code: "P007",
    session_id: "s".repeat(20),
    indice: 6,
    piloto: false,
    consent_version: "v0",
    bloques: seq.map((b, k) => ({ posicion: k, condicion: b.condicion, slot_noticia: b.slot_noticia, news_id: NEWS[b.slot_noticia], bloqueados_prop: 0 })),
    instrumentos: { version: "t", post_noticia: POST, final: FINAL },
    fase: "bloque",
    posicion: 0,
    estado: "activa",
    ...over,
  };
}

describe("cuadrado de Williams (paridad con el backend)", () => {
  it("coincide con el vector que genera el backend para 32 participantes", () => {
    for (const v of vector) {
      const s = secuenciaEsperada(v.indice);
      expect(s.map((b) => b.condicion)).toEqual(v.condiciones);
      expect(s.map((b) => b.slot_noticia)).toEqual(v.slots);
    }
  });
  it("cada transición ordenada aparece una sola vez", () => {
    const pares = WILLIAMS_4.flatMap((f) => [0, 1, 2].map((k) => `${f[k]}>${f[k + 1]}`));
    expect(new Set(pares).size).toBe(12);
  });
  it("parsea el código del participante", () => {
    expect(indiceDeCodigo("P007")).toBe(6);
    expect(indiceDeCodigo(" p-007 ")).toBe(6);
    expect(normalizarCodigo("ab-0123")).toBe("AB0123");
    for (const malo of ["", "7", "Juan Perez", "P000", "P00", "a@b.com"]) expect(indiceDeCodigo(malo)).toBeNull();
  });
});

describe("máquina de estados y guardia de rutas", () => {
  it("recorre 4 bloques, el cuestionario final y el fin", () => {
    let s = estado();
    const fases: string[] = [];
    for (let k = 0; k < 4; k++) {
      s = avanzar(s, "bloque-hecho");
      fases.push(`${s.fase}${s.posicion}`);
      s = avanzar(s, "post-enviado");
    }
    expect(fases).toEqual(["cuestionario0", "cuestionario1", "cuestionario2", "cuestionario3"]);
    expect(s.fase).toBe("final");
    expect(avanzar(s, "final-enviado").fase).toBe("fin");
  });
  it("rechaza transiciones fuera de orden", () => {
    expect(() => avanzar(estado(), "post-enviado")).toThrow();
    expect(() => avanzar(estado({ fase: "cuestionario" }), "bloque-hecho")).toThrow();
  });
  it("con una sesión activa solo existe la ruta de la fase actual", () => {
    const s = estado({ fase: "bloque", posicion: 2 });
    expect(rutaDeEstado(s)).toBe("#/experimento/bloque/2");
    expect(guardia(s, "#/experimento/bloque/2")).toBeNull();
    expect(guardia(s, "#/")).toBe("#/experimento/bloque/2");
    expect(guardia(s, "")).toBe("#/experimento/bloque/2");
    expect(guardia(s, "#/ajustes")).toBe("#/experimento/bloque/2");
    expect(guardia(s, "#/noticia/1?c=C1")).toBe("#/experimento/bloque/2"); // no se puede cambiar ?c=
    expect(guardia(s, "#/experimento/bloque/3")).toBe("#/experimento/bloque/2"); // ni saltar bloques
    expect(guardia({ ...s, fase: "cuestionario" }, "#/experimento/bloque/2")).toBe("#/experimento/cuestionario/2");
    expect(guardia({ ...s, fase: "final" }, "#/")).toBe("#/experimento/final");
  });
  it("sin sesión activa la navegación es libre salvo las rutas internas del experimento", () => {
    expect(guardia(null, "#/noticia/1?c=C3")).toBeNull();
    expect(guardia(null, "#/experimento")).toBeNull();
    expect(guardia(null, "#/experimento/bloque/1")).toBe("#/experimento");
    expect(guardia(estado({ estado: "abandonada" }), "#/")).toBeNull();
    expect(guardia(estado({ estado: "completa", fase: "fin" }), "#/experimento/bloque/0")).toBe("#/experimento/fin");
    expect(guardia(estado({ estado: "completa", fase: "fin" }), "#/experimento/fin")).toBeNull();
  });
  it("el router entiende las rutas del experimento", () => {
    expect(parseHash("#/experimento")).toEqual({ name: "experiment", step: "inicio", k: 0 });
    expect(parseHash("#/experimento/bloque/2")).toEqual({ name: "experiment", step: "bloque", k: 2 });
    expect(parseHash("#/experimento/cuestionario/3")).toEqual({ name: "experiment", step: "cuestionario", k: 3 });
    expect(parseHash("#/experimento/final")).toMatchObject({ step: "final" });
    expect(parseHash("#/experimento/fin")).toMatchObject({ step: "fin" });
  });
  it("retoma el progreso a partir de lo que ya recibió el servidor", () => {
    expect(progresoDesde([])).toEqual({ fase: "bloque", posicion: 0 });
    expect(progresoDesde(["post_noticia:0", "post_noticia:1"])).toEqual({ fase: "bloque", posicion: 2 });
    const cuatro = [0, 1, 2, 3].map((k) => `post_noticia:${k}`);
    expect(progresoDesde(cuatro)).toEqual({ fase: "final", posicion: 3 });
    expect(progresoDesde([...cuatro, "final:-1"]).fase).toBe("fin");
  });
});

describe("validación de los cuestionarios", () => {
  it("acepta respuestas completas", () => {
    expect(validarRespuestas(POST, POST_OK)).toEqual({});
    expect(validarRespuestas(FINAL, FINAL_OK)).toEqual({});
  });
  it("exige todo lo no opcional y respeta los rangos", () => {
    expect(Object.keys(validarRespuestas(POST, {}))).toHaveLength(8);
    expect(validarRespuestas(POST, { ...POST_OK, esfuerzo: 10 })).toHaveProperty("esfuerzo", "rango");
    expect(validarRespuestas(POST, { ...POST_OK, esfuerzo: 0 })).toHaveProperty("esfuerzo");
    expect(validarRespuestas(POST, { ...POST_OK, comp_1: 2 })).toHaveProperty("comp_1");
    expect(validarRespuestas(POST, { ...POST_OK, acep_agrado: 2.5 })).toHaveProperty("acep_agrado");
    expect(validarRespuestas(FINAL, { ...FINAL_OK, variante: "inventada" })).toHaveProperty("variante");
  });
  it("el ranking debe ser una permutación de 1 a 4", () => {
    expect(validarRespuestas(FINAL, { ...FINAL_OK, rank_C1: 1 })).toHaveProperty("rank_C1", "ranking");
  });
  it("rechaza datos personales en el comentario (igual que el servidor)", () => {
    for (const pii of ["escríbeme a juan@correo.com", "llama al 987 654 321", "mi dni 12345678", "https://x.com"])
      expect(detectarPii(pii)).not.toBeNull();
    expect(validarRespuestas(FINAL, { ...FINAL_OK, comentario: "llama al 987654321" })).toHaveProperty("comentario", "pii");
    expect(detectarPii("Me gustó la voz, 2 veces.")).toBeNull();
  });
});

// ------------------------------------------------------------------ servidor simulado
interface Fake {
  fetchFn: typeof fetch;
  guardadas: Map<string, ResponseRecord>;
  llamadas: string[];
  opciones: { sinRed: boolean; rechazar: Set<string>; falla5xx: boolean; finish409: boolean };
}

function fakeServer(): Fake {
  const guardadas = new Map<string, ResponseRecord>();
  const llamadas: string[] = [];
  const opciones = { sinRed: false, rechazar: new Set<string>(), falla5xx: false, finish409: false };
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  const fetchFn = (async (url: string, init?: RequestInit) => {
    llamadas.push(`${init?.method ?? "GET"} ${url}`);
    if (opciones.sinRed) throw new TypeError("offline");
    if (url === "/api/experiment/config")
      return json(200, { consent_version: "v0", piloto: true, version_instrumentos: "t", post_noticia: POST, final: FINAL });
    if (url === "/api/experiment/sessions") {
      const b = JSON.parse(String(init?.body));
      const i = indiceDeCodigo(b.participant_code) ?? 0;
      return json(201, {
        participant_code: b.participant_code,
        indice: i,
        piloto: true,
        estado: "activa",
        consent_version: b.consent_version,
        bloques: secuenciaEsperada(i).map((s, k) => ({ posicion: k, condicion: s.condicion, slot_noticia: s.slot_noticia, news_id: NEWS[s.slot_noticia], bloqueados_prop: 0 })),
      });
    }
    if (url === "/api/experiment/responses") {
      if (opciones.falla5xx) return json(503, {});
      const lote: ResponseRecord[] = JSON.parse(String(init?.body)).responses;
      if (lote.some((r) => opciones.rechazar.has(r.response_id))) return json(422, { detail: "respuesta inválida" });
      for (const r of lote) guardadas.set(r.response_id, r);
      return json(201, { recibidos: lote.length, nuevos: lote.length, duplicados: 0 });
    }
    if (url.endsWith("/finish")) {
      if (opciones.finish409 || guardadas.size < 5) return json(409, { detail: "faltan" });
      return json(200, { estado: "completa" });
    }
    return json(404, {});
  }) as unknown as typeof fetch;
  return { fetchFn, guardadas, llamadas, opciones };
}

function rec(id: string, extra: Partial<ResponseRecord> = {}): ResponseRecord {
  return {
    response_id: id,
    session_id: "s".repeat(20),
    participant_code: "P007",
    kind: "post_noticia",
    posicion: 0,
    condition: "C3",
    news_id: 11,
    t_client: "2026-10-12T10:00:00.000Z",
    answers: POST_OK,
    ...extra,
  };
}

describe("ResponseQueue", () => {
  it("guardar dos veces la misma respuesta no la duplica", async () => {
    const q = new ResponseQueue(new MemoryResponseStore());
    await q.add(rec("a".repeat(20)));
    await q.add(rec("a".repeat(20)));
    expect(await q.pending()).toBe(1);
  });
  it("envía por lotes y vacía la cola; sin red las conserva", async () => {
    const f = fakeServer();
    const q = new ResponseQueue(new MemoryResponseStore(), { fetchFn: f.fetchFn, batch: 2 });
    for (const c of "abcde") await q.add(rec(c.repeat(20), { posicion: "abcde".indexOf(c) }));
    f.opciones.sinRed = true;
    expect(await q.flush()).toBe(0);
    expect(await q.pending()).toBe(5);
    f.opciones.sinRed = false;
    expect(await q.flush()).toBe(5);
    expect(await q.pending()).toBe(0);
    expect(f.guardadas.size).toBe(5);
    expect(f.llamadas.filter((l) => l.includes("responses"))).toHaveLength(1 + 3); // 1 fallida + 3 lotes
  });
  it("con un error del servidor las conserva para reintentar", async () => {
    const f = fakeServer();
    f.opciones.falla5xx = true;
    const q = new ResponseQueue(new MemoryResponseStore(), { fetchFn: f.fetchFn });
    await q.add(rec("a".repeat(20)));
    expect(await q.flush()).toBe(0);
    expect(await q.pending()).toBe(1);
  });
  it("aísla la respuesta rechazada (422) sin bloquear las demás", async () => {
    const f = fakeServer();
    f.opciones.rechazar.add("m".repeat(20));
    const q = new ResponseQueue(new MemoryResponseStore(), { fetchFn: f.fetchFn });
    await q.add(rec("b".repeat(20)));
    await q.add(rec("m".repeat(20), { posicion: 1 }));
    await q.add(rec("c".repeat(20), { posicion: 2 }));
    expect(await q.flush()).toBe(2);
    expect(f.guardadas.size).toBe(2);
    expect(await q.pending()).toBe(0);
    const r = await q.rejected();
    expect(r).toHaveLength(1);
    expect(r[0].rechazada).toContain("inválida");
    expect(await q.flush()).toBe(0); // no se reintenta indefinidamente
  });
});

// ------------------------------------------------------------------ controlador
function crear(f: Fake, keys = new MemoryKeyStore(), responses = new MemoryResponseStore()) {
  let n = 0;
  const events = new EventQueue(new MemoryStore(), { sessionId: "d".repeat(24), fetchFn: f.fetchFn, uuid: () => `ev-${String(n++).padStart(18, "0")}` });
  const ex = new ExperimentController(keys, new ResponseQueue(responses, { fetchFn: f.fetchFn }), events, {
    fetchFn: f.fetchFn,
    uuid: () => `r${String(n++).padStart(19, "0")}`,
  });
  return { ex, events, keys, responses };
}

describe("ExperimentController", () => {
  it("recorre la sesión completa: 4 bloques, cuestionarios, final y cierre idempotente", async () => {
    const f = fakeServer();
    const { ex, events } = crear(f);
    await ex.load();
    expect(ex.state).toBeNull();
    const s = await ex.start("p-007");
    expect(s.participant_code).toBe("P007");
    expect(s.bloques.map((b) => b.condicion)).toEqual(["C3", "C4", "C2", "C1"]); // fila 2 de Williams
    expect(s.bloques.map((b) => b.news_id)).toEqual([12, 13, 14, 11]); // rotación (desplazamiento 1)
    const vistas: string[] = [];
    for (let k = 0; k < 4; k++) {
      expect(ex.bloqueActual?.posicion).toBe(k);
      vistas.push(ex.bloqueActual?.condicion ?? "");
      await ex.terminarBloque(true);
      expect(ex.state?.fase).toBe("cuestionario");
      await ex.enviarPostNoticia(POST_OK);
    }
    expect([...vistas].sort()).toEqual(["C1", "C2", "C3", "C4"]);
    expect(ex.state?.fase).toBe("final");
    await ex.enviarFinal(FINAL_OK);
    expect(ex.state?.fase).toBe("fin");
    expect(await ex.cerrar()).toBe(true);
    expect(ex.state?.estado).toBe("completa");
    expect(await ex.cerrar()).toBe(true);
    expect(f.guardadas.size).toBe(5);
    const tipos = events.emitted.map((e) => e.type);
    expect(tipos.filter((t) => t === "block-end")).toHaveLength(4);
    expect(tipos).toContain("consent");
    expect(tipos).toContain("session-finish");
    // los block-end llevan la condición y la noticia de su bloque (así los une la exportación)
    const fin = events.emitted.filter((e) => e.type === "block-end");
    expect(fin.map((e) => e.condition)).toEqual(["C3", "C4", "C2", "C1"]);
    expect(fin.map((e) => e.payload.reason)).toEqual(Array(4).fill("completo"));
  });

  it("rechaza respuestas inválidas sin avanzar", async () => {
    const f = fakeServer();
    const { ex } = crear(f);
    await ex.start("P001");
    await ex.terminarBloque(true);
    await expect(ex.enviarPostNoticia({ ...POST_OK, esfuerzo: 12 })).rejects.toBeInstanceOf(ExperimentError);
    expect(ex.state?.fase).toBe("cuestionario");
    expect(f.guardadas.size).toBe(0);
  });

  it("se reanuda tras recargar con el mismo almacenamiento", async () => {
    const f = fakeServer();
    const a = crear(f);
    await a.ex.start("P002");
    await a.ex.terminarBloque(true);
    await a.ex.enviarPostNoticia(POST_OK);
    const b = crear(f, a.keys, a.responses); // «recarga»: nuevo controlador, mismo IndexedDB
    const s = await b.ex.load();
    expect(s?.fase).toBe("bloque");
    expect(s?.posicion).toBe(1);
    expect(s?.participant_code).toBe("P002");
  });

  it("sin red no se puede iniciar y avisa; un código inválido ni siquiera llama al servidor", async () => {
    const f = fakeServer();
    const { ex } = crear(f);
    await expect(ex.start("Juan Perez")).rejects.toMatchObject({ tipo: "codigo" });
    expect(f.llamadas).toHaveLength(0);
    f.opciones.sinRed = true;
    await expect(ex.start("P001")).rejects.toMatchObject({ tipo: "red" });
    expect(ex.state).toBeNull();
  });

  it("detecta una asignación distinta del cuadrado de Williams", async () => {
    const f = fakeServer();
    const orig = f.fetchFn;
    const { ex } = crear({
      ...f,
      fetchFn: (async (u: string, i?: RequestInit) => {
        const r = await orig(u, i);
        if (u !== "/api/experiment/sessions") return r;
        const j = await r.json();
        j.bloques.reverse();
        return new Response(JSON.stringify(j), { status: 201 });
      }) as unknown as typeof fetch,
    });
    await expect(ex.start("P001")).rejects.toMatchObject({ tipo: "asignacion" });
  });

  it("cerrar() queda pendiente si hay respuestas sin enviar y se completa al volver la red", async () => {
    const f = fakeServer();
    const { ex } = crear(f);
    await ex.start("P003");
    f.opciones.sinRed = true;
    for (let k = 0; k < 4; k++) {
      await ex.terminarBloque(true);
      await ex.enviarPostNoticia(POST_OK);
    }
    await ex.enviarFinal(FINAL_OK);
    expect(await ex.cerrar()).toBe(false);
    expect(ex.state?.estado).toBe("activa");
    expect(await ex.responses.pending()).toBe(5);
    f.opciones.sinRed = false;
    expect(await ex.cerrar()).toBe(true);
    expect(f.guardadas.size).toBe(5);
    expect(await ex.responses.pending()).toBe(0);
  });

  it("abandonar libera la navegación y registra el evento", async () => {
    const f = fakeServer();
    const { ex, events } = crear(f);
    await ex.start("P004");
    await ex.abandonar();
    expect(ex.state?.estado).toBe("abandonada");
    expect(guardia(ex.state, "#/")).toBeNull();
    expect(events.emitted.some((e) => e.type === "abandon")).toBe(true);
  });
});
