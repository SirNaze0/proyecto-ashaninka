// Flujo guiado del experimento (Fase 5): consentimiento → 4 bloques con su cuestionario → cuestionario
// final → fin. Todo el estado vive en IndexedDB (se reanuda tras recargar) y las respuestas se
// envían por una cola idempotente (response_id UUID), como los eventos de la Fase 4.
// Privacidad: solo un código anónimo (P007) y el UUID del dispositivo; ningún dato personal.
import { STORE_EXPERIMENT, STORE_RESPONSES, idbTx, openDb } from "./db";
import { type EventQueue, setStoredSessionId } from "./events";
import { type Route, parseHash } from "./router";
import type { Condition } from "./types";

export type Answers = Record<string, string | number | boolean | null>;
export type Fase = "bloque" | "cuestionario" | "final" | "fin";
export type Estado = "activa" | "completa" | "abandonada";

export interface Bloque {
  posicion: number;
  condicion: Condition;
  slot_noticia: number;
  news_id: number;
  bloqueados_prop: number;
}

export interface ItemDef {
  id: string;
  tipo: "binario" | "entero" | "opcion" | "texto";
  etiqueta: string;
  status: string;
  min?: number;
  max?: number;
  opciones?: string[];
  opcional?: boolean;
}

export interface Instrumentos {
  version: string;
  post_noticia: ItemDef[];
  final: ItemDef[];
}

export interface ExperimentState {
  participant_code: string;
  session_id: string;
  indice: number;
  piloto: boolean;
  consent_version: string;
  bloques: Bloque[];
  instrumentos: Instrumentos;
  fase: Fase;
  posicion: number;
  estado: Estado;
}

export interface ResponseRecord {
  response_id: string;
  session_id: string;
  participant_code: string;
  kind: "post_noticia" | "final";
  posicion: number | null;
  condition: Condition | null;
  news_id: number | null;
  t_client: string;
  answers: Answers;
  /** Motivo si el servidor la rechazó (422): se conserva para revisarla, no se reintenta. */
  rechazada?: string;
}

// ------------------------------------------------------------------ cuadrado de Williams (paridad)
// Misma tabla que backend/app/experiment/latin.py: sirve para verificar que la asignación del
// servidor es la esperada y se prueba contra un vector común (tests/fixtures/williams_vector.json).
export const WILLIAMS_4: Condition[][] = [
  ["C1", "C2", "C4", "C3"],
  ["C2", "C3", "C1", "C4"],
  ["C3", "C4", "C2", "C1"],
  ["C4", "C1", "C3", "C2"],
];

export function secuenciaEsperada(indice: number): { condicion: Condition; slot_noticia: number }[] {
  const fila = WILLIAMS_4[indice % 4];
  const desplazamiento = Math.floor(indice / 4) % 4;
  return fila.map((condicion, k) => ({ condicion, slot_noticia: (k + desplazamiento) % 4 }));
}

/** ``P007`` → 6 (igual que el servidor); ``null`` si el código no es válido. */
export function indiceDeCodigo(codigo: string): number | null {
  const m = /^([A-Z]{1,3})-?(\d{3,4})$/.exec(codigo.trim().toUpperCase());
  if (!m || Number(m[2]) < 1) return null;
  return Number(m[2]) - 1;
}

export function normalizarCodigo(codigo: string): string | null {
  const m = /^([A-Z]{1,3})-?(\d{3,4})$/.exec(codigo.trim().toUpperCase());
  return m ? `${m[1]}${m[2]}` : null;
}

// ------------------------------------------------------------------ máquina de estados y rutas
export type Transicion = "bloque-hecho" | "post-enviado" | "final-enviado";

export function avanzar(s: ExperimentState, t: Transicion): ExperimentState {
  if (t === "bloque-hecho" && s.fase === "bloque") return { ...s, fase: "cuestionario" };
  if (t === "post-enviado" && s.fase === "cuestionario") {
    return s.posicion < s.bloques.length - 1
      ? { ...s, fase: "bloque", posicion: s.posicion + 1 }
      : { ...s, fase: "final" };
  }
  if (t === "final-enviado" && s.fase === "final") return { ...s, fase: "fin" };
  throw new Error(`transición inválida: ${t} desde la fase ${s.fase}`);
}

/** Ruta que corresponde al estado actual (la única permitida mientras la sesión está activa). */
export function rutaDeEstado(s: ExperimentState): string {
  if (s.estado === "abandonada") return "#/";
  switch (s.fase) {
    case "bloque":
      return `#/experimento/bloque/${s.posicion}`;
    case "cuestionario":
      return `#/experimento/cuestionario/${s.posicion}`;
    case "final":
      return "#/experimento/final";
    default:
      return "#/experimento/fin";
  }
}

const pathOf = (hash: string) => hash.replace(/^#?\/?/, "#/").split("?")[0].replace(/\/$/, "") || "#";

/** Hash al que hay que redirigir, o ``null`` si la ruta actual es válida. Bloquea el cambio libre
 *  de condición: con una sesión activa solo existe la ruta de la fase actual. */
export function guardia(s: ExperimentState | null, hash: string): string | null {
  if (s && s.estado === "activa") {
    const objetivo = rutaDeEstado(s);
    return pathOf(hash) === pathOf(objetivo) ? null : objetivo;
  }
  const r: Route = parseHash(hash);
  if (r.name === "experiment" && r.step !== "inicio") {
    const destino = s?.estado === "completa" ? "#/experimento/fin" : "#/experimento";
    return pathOf(hash) === pathOf(destino) ? null : destino;
  }
  return null;
}

/** Fase y posición a retomar a partir de lo que el servidor ya recibió (``"post_noticia:0"``…). */
export function progresoDesde(respondidos: string[]): { fase: Fase; posicion: number } {
  const posts = respondidos.filter((r) => r.startsWith("post_noticia:")).length;
  if (posts < 4) return { fase: "bloque", posicion: posts };
  return respondidos.includes("final:-1") ? { fase: "fin", posicion: 3 } : { fase: "final", posicion: 3 };
}

// ------------------------------------------------------------------ validación de cuestionarios
// Misma regla que backend/app/experiment/instrumentos.py (el servidor es la autoridad: si lo que
// pasa aquí se rechazara allá, la respuesta quedaría atascada).
const PII: [string, RegExp][] = [
  ["correo", /[\w.+-]+@[\w-]+\.[\w.-]+/],
  ["enlace o usuario", /https?:\/\/|www\.|(?<!\w)@\w{3,}/],
  ["número largo (teléfono o documento)", /(?:\d[\s.-]?){7,}/],
];

export function detectarPii(texto: string): string | null {
  for (const [nombre, rx] of PII) if (rx.test(texto)) return nombre;
  return null;
}

export function validarRespuestas(defs: ItemDef[], a: Answers): Record<string, string> {
  const err: Record<string, string> = {};
  for (const d of defs) {
    const v = a[d.id];
    if (v === undefined || v === null || v === "") {
      if (!d.opcional) err[d.id] = "falta";
      continue;
    }
    if (d.tipo === "binario" && v !== 0 && v !== 1) err[d.id] = "valor";
    else if (d.tipo === "entero" && (!Number.isInteger(v) || (v as number) < (d.min ?? 0) || (v as number) > (d.max ?? 0)))
      err[d.id] = "rango";
    else if (d.tipo === "opcion" && !d.opciones?.includes(String(v))) err[d.id] = "opcion";
    else if (d.tipo === "texto") {
      if (typeof v !== "string" || v.length > (d.max ?? 0)) err[d.id] = "largo";
      else if (detectarPii(v)) err[d.id] = "pii";
    }
  }
  const ranks = ["C1", "C2", "C3", "C4"].map((c) => a[`rank_${c}`]);
  if (defs.some((d) => d.id === "rank_C1") && ranks.every((r) => typeof r === "number")) {
    if ([...(ranks as number[])].sort().join() !== "1,2,3,4") err.rank_C1 = "ranking";
  }
  return err;
}

// ------------------------------------------------------------------ almacenes
export interface KeyStore {
  get(): Promise<ExperimentState | null>;
  set(s: ExperimentState): Promise<void>;
  clear(): Promise<void>;
}

export class MemoryKeyStore implements KeyStore {
  private v: ExperimentState | null = null;
  async get() {
    return this.v ? structuredClone(this.v) : null;
  }
  async set(s: ExperimentState) {
    this.v = structuredClone(s);
  }
  async clear() {
    this.v = null;
  }
}

export class IdbKeyStore implements KeyStore {
  private db: Promise<IDBDatabase> | null = null;
  private open() {
    this.db ??= openDb();
    return this.db;
  }
  async get() {
    const r = await idbTx<{ key: string; state: ExperimentState } | undefined>(this.open(), STORE_EXPERIMENT, "readonly", (s) => s.get("sesion"));
    return r?.state ?? null;
  }
  async set(state: ExperimentState) {
    await idbTx(this.open(), STORE_EXPERIMENT, "readwrite", (s) => s.put({ key: "sesion", state }));
  }
  async clear() {
    await idbTx(this.open(), STORE_EXPERIMENT, "readwrite", (s) => s.delete("sesion"));
  }
}

export interface ResponseStore {
  put(r: ResponseRecord): Promise<void>;
  all(): Promise<ResponseRecord[]>;
  remove(ids: string[]): Promise<void>;
}

export class MemoryResponseStore implements ResponseStore {
  private readonly m = new Map<string, ResponseRecord>();
  async put(r: ResponseRecord) {
    this.m.set(r.response_id, structuredClone(r));
  }
  async all() {
    return [...this.m.values()].map((r) => structuredClone(r));
  }
  async remove(ids: string[]) {
    for (const id of ids) this.m.delete(id);
  }
}

export class IdbResponseStore implements ResponseStore {
  private db: Promise<IDBDatabase> | null = null;
  private open() {
    this.db ??= openDb();
    return this.db;
  }
  async put(r: ResponseRecord) {
    await idbTx(this.open(), STORE_RESPONSES, "readwrite", (s) => s.put(r));
  }
  async all() {
    return idbTx<ResponseRecord[]>(this.open(), STORE_RESPONSES, "readonly", (s) => s.getAll());
  }
  async remove(ids: string[]) {
    const db = await this.open();
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction(STORE_RESPONSES, "readwrite");
      for (const id of ids) t.objectStore(STORE_RESPONSES).delete(id);
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
    });
  }
}

// ------------------------------------------------------------------ cola de respuestas
export interface ResponseQueueOptions {
  endpoint?: string;
  fetchFn?: typeof fetch;
  batch?: number;
}

export class ResponseQueue {
  private flushing: Promise<number> | null = null;
  constructor(
    private readonly store: ResponseStore,
    private readonly o: ResponseQueueOptions = {},
  ) {}

  /** Guarda (``put`` por response_id: guardar dos veces la misma respuesta no la duplica). */
  async add(r: ResponseRecord): Promise<void> {
    await this.store.put(r);
  }

  async pending(): Promise<number> {
    return (await this.store.all()).filter((r) => !r.rechazada).length;
  }

  async rejected(): Promise<ResponseRecord[]> {
    return (await this.store.all()).filter((r) => r.rechazada);
  }

  /** Envía lo pendiente; devuelve cuántas respuestas confirmó el servidor. */
  flush(): Promise<number> {
    this.flushing ??= this.doFlush().finally(() => {
      this.flushing = null;
    });
    return this.flushing;
  }

  private async post(batch: ResponseRecord[]): Promise<Response | null> {
    const f = this.o.fetchFn ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
    const limpias = batch.map(({ rechazada: _r, ...resto }) => resto);
    try {
      return await f(this.o.endpoint ?? "/api/experiment/responses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ responses: limpias }),
        keepalive: true,
      });
    } catch {
      return null; // sin red: se conservan
    }
  }

  private async doFlush(): Promise<number> {
    const size = this.o.batch ?? 20;
    const todas = (await this.store.all().catch(() => [] as ResponseRecord[])).filter((r) => !r.rechazada);
    let enviadas = 0;
    for (let i = 0; i < todas.length; i += size) {
      const lote = todas.slice(i, i + size);
      const r = await this.post(lote);
      if (!r) break;
      if (r.ok) {
        await this.store.remove(lote.map((x) => x.response_id));
        enviadas += lote.length;
      } else if (r.status === 422) {
        // un lote inválido no guarda nada: se reenvían una por una para aislar la mala
        for (const una of lote) {
          const ru = lote.length === 1 ? r : await this.post([una]);
          if (!ru) return enviadas;
          if (ru.ok) {
            await this.store.remove([una.response_id]);
            enviadas++;
          } else if (ru.status === 422) {
            const detalle = await ru.json().then((j) => String(j.detail ?? "422"), () => "422");
            await this.store.put({ ...una, rechazada: detalle });
          } else return enviadas;
        }
      } else break; // 5xx u otro: se conservan para reintentar
    }
    return enviadas;
  }
}

// ------------------------------------------------------------------ controlador
export class ExperimentError extends Error {
  constructor(
    readonly tipo: "red" | "codigo" | "conflicto" | "asignacion" | "estado",
    mensaje: string,
  ) {
    super(mensaje);
  }
}

export interface ControllerOptions {
  fetchFn?: typeof fetch;
  now?: () => Date;
  uuid?: () => string;
}

export class ExperimentController {
  state: ExperimentState | null = null;
  loaded = false;
  private readonly subs = new Set<() => void>();

  constructor(
    private readonly store: KeyStore,
    readonly responses: ResponseQueue,
    private readonly events: EventQueue,
    private readonly o: ControllerOptions = {},
  ) {}

  private get f(): typeof fetch {
    return this.o.fetchFn ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
  }
  private now = () => (this.o.now ?? (() => new Date()))().toISOString();
  private uuid = () => (this.o.uuid ?? (() => crypto.randomUUID()))();

  subscribe(fn: () => void): () => void {
    this.subs.add(fn);
    return () => this.subs.delete(fn);
  }

  private async set(s: ExperimentState | null): Promise<void> {
    this.state = s;
    try {
      if (s) await this.store.set(s);
      else await this.store.clear();
    } catch {
      /* sin almacenamiento: la sesión sigue en memoria */
    }
    for (const fn of this.subs) fn();
  }

  async load(): Promise<ExperimentState | null> {
    try {
      this.state = await this.store.get();
    } catch {
      this.state = null;
    }
    // los eventos deben llevar el mismo UUID de dispositivo con el que se creó la sesión
    if (this.state && this.state.session_id !== this.events.sessionId) {
      this.events.useSession(this.state.session_id);
      setStoredSessionId(this.state.session_id);
    }
    this.loaded = true;
    for (const fn of this.subs) fn();
    return this.state;
  }

  /** Crea la sesión en el servidor (consentimiento aceptado) y arranca el primer bloque. */
  async start(codigo: string): Promise<ExperimentState> {
    const code = normalizarCodigo(codigo);
    const indice = indiceDeCodigo(codigo);
    if (!code || indice === null) throw new ExperimentError("codigo", "código inválido");
    let cfg: { consent_version: string; piloto: boolean; post_noticia: ItemDef[]; final: ItemDef[]; version_instrumentos: string };
    let ses: { bloques: Bloque[]; piloto: boolean; consent_version: string; estado: Estado };
    let progreso: { fase: Fase; posicion: number } = { fase: "bloque", posicion: 0 };
    try {
      const rc = await this.f("/api/experiment/config");
      if (!rc.ok) throw new Error(String(rc.status));
      cfg = await rc.json();
      const rs = await this.f("/api/experiment/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          participant_code: code,
          session_id: this.events.sessionId,
          consent: true,
          consent_version: cfg.consent_version,
        }),
      });
      if (rs.status === 409) throw new ExperimentError("conflicto", await rs.json().then((j) => String(j.detail), () => "conflicto"));
      if (rs.status === 422) throw new ExperimentError("codigo", await rs.json().then((j) => JSON.stringify(j.detail), () => "422"));
      if (!rs.ok) throw new Error(String(rs.status));
      ses = await rs.json();
      if (ses.estado !== "activa") throw new ExperimentError("conflicto", "la sesión de este código ya fue cerrada");
      if (rs.status === 200) {
        // el código ya existía (p. ej. se borró el almacenamiento local): se retoma donde quedó
        const rp = await this.f(`/api/experiment/sessions/${code}`);
        if (rp.ok) progreso = progresoDesde((await rp.json()).respondidos ?? []);
      }
    } catch (e) {
      if (e instanceof ExperimentError) throw e;
      throw new ExperimentError("red", "sin conexión con el servidor");
    }
    // la asignación del servidor debe coincidir con la fila de Williams esperada
    const esperada = secuenciaEsperada(indice);
    const ok =
      ses.bloques.length === 4 &&
      ses.bloques.every((b, k) => b.condicion === esperada[k].condicion && b.slot_noticia === esperada[k].slot_noticia);
    if (!ok) throw new ExperimentError("asignacion", "la asignación recibida no coincide con el cuadrado de Williams");
    const nuevo: ExperimentState = {
      participant_code: code,
      session_id: this.events.sessionId,
      indice,
      piloto: ses.piloto,
      consent_version: ses.consent_version,
      bloques: ses.bloques,
      instrumentos: { version: cfg.version_instrumentos, post_noticia: cfg.post_noticia, final: cfg.final },
      fase: progreso.fase,
      posicion: progreso.posicion,
      estado: "activa",
    };
    this.events.setContext(null, null);
    void this.events.emit("consent", { participant: code });
    await this.set(nuevo);
    return nuevo;
  }

  private req(): ExperimentState {
    if (!this.state) throw new ExperimentError("estado", "no hay sesión experimental");
    return this.state;
  }

  get bloqueActual(): Bloque | null {
    const s = this.state;
    return s ? (s.bloques[s.posicion] ?? null) : null;
  }

  /** El participante terminó la noticia y pasa a su cuestionario. */
  async terminarBloque(completo: boolean): Promise<void> {
    const s = this.req();
    const b = s.bloques[s.posicion];
    this.events.setContext(b.condicion, b.news_id);
    await this.events.emit("block-end", { posicion: b.posicion, reason: completo ? "completo" : "incompleto" });
    await this.set(avanzar(s, "bloque-hecho"));
  }

  async enviarPostNoticia(answers: Answers): Promise<void> {
    const s = this.req();
    const b = s.bloques[s.posicion];
    const err = validarRespuestas(s.instrumentos.post_noticia, answers);
    if (Object.keys(err).length) throw new ExperimentError("estado", `respuestas inválidas: ${Object.keys(err).join(", ")}`);
    await this.responses.add({
      response_id: this.uuid(),
      session_id: s.session_id,
      participant_code: s.participant_code,
      kind: "post_noticia",
      posicion: b.posicion,
      condition: b.condicion,
      news_id: b.news_id,
      t_client: this.now(),
      answers,
    });
    this.events.setContext(b.condicion, b.news_id);
    void this.events.emit("questionnaire-submit", { posicion: b.posicion });
    await this.set(avanzar(s, "post-enviado"));
    void this.responses.flush();
  }

  async enviarFinal(answers: Answers): Promise<void> {
    const s = this.req();
    const err = validarRespuestas(s.instrumentos.final, answers);
    if (Object.keys(err).length) throw new ExperimentError("estado", `respuestas inválidas: ${Object.keys(err).join(", ")}`);
    await this.responses.add({
      response_id: this.uuid(),
      session_id: s.session_id,
      participant_code: s.participant_code,
      kind: "final",
      posicion: null,
      condition: null,
      news_id: null,
      t_client: this.now(),
      answers,
    });
    this.events.setContext(null, null);
    void this.events.emit("questionnaire-submit", { posicion: -1 });
    await this.set(avanzar(s, "final-enviado"));
    void this.responses.flush();
  }

  /** Sincroniza lo pendiente y cierra la sesión en el servidor. ``true`` si quedó completa. */
  async cerrar(): Promise<boolean> {
    const s = this.req();
    if (s.estado === "completa") return true;
    await this.responses.flush();
    if ((await this.responses.pending()) > 0) return false;
    try {
      const r = await this.f(`/api/experiment/sessions/${s.participant_code}/finish`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ estado: "completa" }),
      });
      if (!r.ok) return false;
    } catch {
      return false;
    }
    this.events.setContext(null, null);
    void this.events.emit("session-finish", { blocks: s.bloques.length });
    await this.set({ ...s, estado: "completa" });
    void this.events.flush();
    return true;
  }

  /** Abandono voluntario (con confirmación en la interfaz): libera la navegación. */
  async abandonar(): Promise<void> {
    const s = this.req();
    this.events.setContext(this.bloqueActual?.condicion ?? null, this.bloqueActual?.news_id ?? null);
    await this.events.emit("abandon", { posicion: s.posicion });
    await this.set({ ...s, estado: "abandonada" });
    void this.events.flush();
    try {
      await this.f(`/api/experiment/sessions/${s.participant_code}/finish`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ estado: "abandonada" }),
      });
    } catch {
      /* sin red: el servidor la deja activa; el evento abandon ya quedó en la cola */
    }
  }

  /** Olvida la sesión de este dispositivo (para iniciar otro participante). */
  async olvidar(): Promise<void> {
    await this.set(null);
  }
}
