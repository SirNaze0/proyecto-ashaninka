// Noticias automáticas de TV Perú (NoticiasTVPeru): cliente de /api/feed y formato del estado.
// El SERVIDOR descarga, traduce (BiTAM), sintetiza y publica; aquí solo se elige el intervalo, se pide
// «Refrescar ahora» y se muestra el estado. Nada de este archivo genera texto en asháninka.

export interface FeedResultado {
  inicio: string;
  nuevas: number;
  publicadas: { news_id: number; url: string }[];
  errores: number;
  pendientes: number;
  motivo: string | null;
  duracion_s?: number;
}

export interface FeedStatus {
  habilitado: boolean;
  fuente: string;
  fuente_url: string;
  intervalo_min: number;
  intervalos_permitidos: number[];
  max_por_ciclo: number;
  ejecutando: boolean;
  ultima_ejecucion: string | null;
  proxima_ejecucion: string | null;
  ultimo_resultado: FeedResultado | null;
  items: Record<"pendiente" | "publicada" | "error" | "descartada", number>;
}

export type RunResult = "iniciado" | "en-curso" | "apagado" | "error";

export async function fetchFeedStatus(f: typeof fetch = fetch): Promise<FeedStatus | null> {
  try {
    const r = await f("/api/feed/status");
    return r.ok ? ((await r.json()) as FeedStatus) : null;
  } catch {
    return null;
  }
}

export async function setIntervalo(min: number, f: typeof fetch = fetch): Promise<FeedStatus | null> {
  try {
    const r = await f("/api/feed/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intervalo_min: min }),
    });
    return r.ok ? ((await r.json()) as FeedStatus) : null;
  } catch {
    return null;
  }
}

export async function refrescarAhora(f: typeof fetch = fetch): Promise<RunResult> {
  try {
    const r = await f("/api/feed/run", { method: "POST" });
    if (r.status === 202) return "iniciado";
    if (r.status === 409) return "en-curso";
    if (r.status === 503) return "apagado";
    return "error";
  } catch {
    return "error";
  }
}

/** «hace 5 min», «hace 2 h», «en 10 min»… (`ahora` inyectable para probar). */
export function relativo(iso: string | null, ahora: number = Date.now()): { clave: string; n: number } | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const min = Math.round((t - ahora) / 60000);
  const abs = Math.abs(min);
  if (abs < 1) return { clave: min <= 0 ? "feed.time.justNow" : "feed.time.soon", n: 0 };
  const futuro = min > 0;
  if (abs < 60) return { clave: futuro ? "feed.time.inMin" : "feed.time.agoMin", n: abs };
  const h = Math.round(abs / 60);
  return { clave: futuro ? "feed.time.inH" : "feed.time.agoH", n: h };
}

/** Clave i18n y variables del resumen del último ciclo. */
export function resumenUltimo(s: FeedStatus): { clave: string; vars: Record<string, string | number> } | null {
  const r = s.ultimo_resultado;
  if (!r) return null;
  if (r.publicadas.length > 0) return { clave: "feed.last.published", vars: { n: r.publicadas.length, p: r.pendientes } };
  if (r.motivo) return { clave: "feed.last.failed", vars: { m: r.motivo } };
  return { clave: "feed.last.nothing", vars: { p: r.pendientes } };
}

/** Tiempo de sondeo del estado: rápido mientras corre un ciclo, lento si no. */
export const sondeoMs = (s: FeedStatus | null): number => (s?.ejecutando ? 5_000 : 60_000);
