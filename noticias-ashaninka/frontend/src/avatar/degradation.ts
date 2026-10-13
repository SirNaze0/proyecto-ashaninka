// Degradación del avatar (tarea 3.6): sondeo de FPS y detección de WebGL.
// Si no hay WebGL o los FPS medidos durante 2 s son menores a 20, se pasa a audio + texto con
// una imagen fija y se REGISTRA el evento (la Fase 5 lo exporta como variable del experimento).

export const FPS_MIN = 20;
export const PROBE_MS = 2000;

export type DegradationReason = "sin-webgl" | "fps-bajos" | "error-carga";

export interface DegradationEvent {
  type: "degradacion" | "avatar-ok";
  reason?: DegradationReason;
  fps?: number;
  at: string; // ISO-8601
  userAgent: string;
}

export function webglAvailable(doc: Pick<Document, "createElement"> = document): boolean {
  try {
    const c = doc.createElement("canvas") as HTMLCanvasElement;
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Decisión pura (probada con vitest): ¿hay que degradar con estas mediciones? */
export function decide(webgl: boolean, fps: number | null): DegradationReason | null {
  if (!webgl) return "sin-webgl";
  if (fps !== null && fps < FPS_MIN) return "fps-bajos";
  return null;
}

/** FPS medidos con requestAnimationFrame durante `ms` milisegundos. */
export function probeFps(ms = PROBE_MS, raf: typeof requestAnimationFrame = requestAnimationFrame): Promise<number> {
  return new Promise((resolve) => {
    let frames = 0;
    let t0 = -1;
    const tick = (t: number) => {
      if (t0 < 0) t0 = t;
      frames++;
      if (t - t0 >= ms) resolve(((frames - 1) * 1000) / (t - t0));
      else raf(tick);
    };
    raf(tick);
  });
}

export function makeEvent(type: DegradationEvent["type"], reason?: DegradationReason, fps?: number): DegradationEvent {
  return {
    type,
    reason,
    fps: fps === undefined ? undefined : Math.round(fps * 10) / 10,
    at: new Date().toISOString(),
    userAgent: typeof navigator === "undefined" ? "" : navigator.userAgent,
  };
}
