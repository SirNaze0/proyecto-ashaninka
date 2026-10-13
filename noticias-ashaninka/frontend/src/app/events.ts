// Cola de eventos del experimento (tarea 4.4): se guardan en IndexedDB y se envían por lotes a
// POST /api/events cuando hay red. Cada evento lleva un UUID: reenviar es idempotente.
// Privacidad: solo un UUID anónimo de sesión, la condición y datos de uso; nada personal.
import { STORE_EVENTS, openDb } from "./db";
import type { Condition } from "./types";

export type EventPayload = Record<string, string | number | boolean | null>;

export interface ClientEventIn {
  event_id: string;
  session_id: string;
  condition: Condition | null;
  news_id: number | null;
  type: string;
  t_client: string;
  payload: EventPayload;
}

export interface EventStore {
  add(e: ClientEventIn): Promise<void>;
  all(limit: number): Promise<ClientEventIn[]>;
  remove(ids: string[]): Promise<void>;
  count(): Promise<number>;
}

export class MemoryStore implements EventStore {
  private readonly m = new Map<string, ClientEventIn>();
  async add(e: ClientEventIn) {
    this.m.set(e.event_id, e);
  }
  async all(limit: number) {
    return [...this.m.values()].slice(0, limit);
  }
  async remove(ids: string[]) {
    for (const id of ids) this.m.delete(id);
  }
  async count() {
    return this.m.size;
  }
}

const STORE = STORE_EVENTS;

export class IdbStore implements EventStore {
  private db: Promise<IDBDatabase> | null = null;

  private open(): Promise<IDBDatabase> {
    this.db ??= openDb();
    return this.db;
  }

  private async tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const r = fn(t.objectStore(STORE));
      t.oncomplete = () => resolve(r.result);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  }

  async add(e: ClientEventIn) {
    await this.tx("readwrite", (s) => s.put(e));
  }
  async all(limit: number) {
    return this.tx("readonly", (s) => s.getAll(undefined, limit));
  }
  async remove(ids: string[]) {
    const db = await this.open();
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction(STORE, "readwrite");
      for (const id of ids) t.objectStore(STORE).delete(id);
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
    });
  }
  async count() {
    return this.tx("readonly", (s) => s.count());
  }
}

export interface QueueOptions {
  sessionId: string;
  endpoint?: string;
  fetchFn?: typeof fetch;
  batch?: number;
  uuid?: () => string;
  now?: () => Date;
}

export class EventQueue {
  private ctx: { condition: Condition | null; news_id: number | null } = {
    condition: null,
    news_id: null,
  };
  private flushing: Promise<number> | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  /** Eventos emitidos en esta sesión de la página (para las pruebas y la medición). */
  readonly emitted: ClientEventIn[] = [];

  constructor(
    private readonly store: EventStore,
    private readonly o: QueueOptions,
  ) {}

  get sessionId(): string {
    return this.o.sessionId;
  }

  /** Fase 5: los eventos de una sesión experimental llevan el UUID con el que se creó. */
  useSession(id: string): void {
    this.o.sessionId = id;
  }

  setContext(condition: Condition | null, newsId: number | null): void {
    this.ctx = { condition, news_id: newsId };
  }

  async emit(type: string, payload: EventPayload = {}): Promise<void> {
    const e: ClientEventIn = {
      event_id: (this.o.uuid ?? (() => crypto.randomUUID()))(),
      session_id: this.o.sessionId,
      condition: this.ctx.condition,
      news_id: this.ctx.news_id,
      type,
      t_client: (this.o.now ?? (() => new Date()))().toISOString(),
      payload,
    };
    this.emitted.push(e);
    try {
      await this.store.add(e);
    } catch {
      return; // sin almacenamiento (modo privado): el evento se pierde, la app sigue
    }
    this.schedule();
  }

  /** Envía lo pendiente en lotes. Devuelve cuántos eventos se confirmaron. */
  flush(): Promise<number> {
    this.flushing ??= this.doFlush().finally(() => {
      this.flushing = null;
    });
    return this.flushing;
  }

  pending(): Promise<number> {
    return this.store.count();
  }

  private schedule(): void {
    if (this.timer || typeof navigator !== "undefined" && navigator.onLine === false) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.flush();
    }, 1500);
  }

  private async doFlush(): Promise<number> {
    const f = this.o.fetchFn ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
    const size = this.o.batch ?? 100;
    let sent = 0;
    for (;;) {
      const events = await this.store.all(size).catch(() => [] as ClientEventIn[]);
      if (events.length === 0) break;
      try {
        const r = await f(this.o.endpoint ?? "/api/events", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ events }),
          keepalive: true,
        });
        if (!r.ok) break; // 4xx/5xx: se conservan para reintentar
        await this.store.remove(events.map((e) => e.event_id));
        sent += events.length;
      } catch {
        break; // sin red: se conservan
      }
    }
    return sent;
  }
}

export function setStoredSessionId(id: string): void {
  try {
    localStorage.setItem("na-session-id", id);
  } catch {
    /* sin almacenamiento */
  }
}

export function getSessionId(): string {
  try {
    const k = "na-session-id";
    let v = localStorage.getItem(k);
    if (!v) {
      v = crypto.randomUUID();
      localStorage.setItem(k, v);
    }
    return v;
  } catch {
    return crypto.randomUUID();
  }
}
