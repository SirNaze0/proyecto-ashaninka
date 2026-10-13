// Orquesta el avatar con degradación (tarea 3.6): WebGL -> carga diferida -> sondeo de FPS de 2 s.
// Si algo falla o los FPS son < 20 se muestra una imagen fija (audio + texto siguen funcionando)
// y se REGISTRA el evento.

import { decide, makeEvent, probeFps, webglAvailable, type DegradationEvent } from "./degradation";
import type { AvatarViewer, Framing } from "./viewer";

export interface AvatarOptions {
  vrmUrl: string;
  fallbackImage: string;
  width?: number;
  height?: number;
  framing?: Framing;
  /** Medición y captura: sin gestos, parpadeo ni mirada, y sin sondeo de FPS. */
  deterministic?: boolean;
  onEvent?: (e: DegradationEvent) => void;
}

export interface AvatarHandle {
  mode: "avatar" | "fijo";
  viewer: AvatarViewer | null;
  events: DegradationEvent[];
  dispose(): void;
}

declare global {
  interface Window {
    __avatarEvents?: DegradationEvent[];
  }
}

export async function createAvatar(container: HTMLElement, opts: AvatarOptions): Promise<AvatarHandle> {
  const events: DegradationEvent[] = [];
  const log = (e: DegradationEvent) => {
    events.push(e);
    (window.__avatarEvents ??= []).push(e);
    opts.onEvent?.(e);
  };
  const fallback = (): AvatarHandle => {
    container.replaceChildren();
    const img = document.createElement("img");
    img.src = opts.fallbackImage;
    img.alt = "Presentadora (imagen fija)";
    img.width = opts.width ?? 320;
    img.height = opts.height ?? 320;
    container.append(img);
    return { mode: "fijo", viewer: null, events, dispose: () => container.replaceChildren() };
  };

  if (!webglAvailable()) {
    log(makeEvent("degradacion", "sin-webgl"));
    return fallback();
  }
  const canvas = document.createElement("canvas");
  canvas.width = opts.width ?? 320;
  canvas.height = opts.height ?? 320;
  container.replaceChildren(canvas);
  let viewer: AvatarViewer;
  try {
    // Import dinámico: three y three-vrm quedan fuera del paquete inicial
    const { AvatarViewer } = await import("./viewer");
    viewer = await AvatarViewer.create({
      canvas,
      framing: opts.framing,
      deterministic: opts.deterministic,
      width: opts.width,
      height: opts.height,
      pixelRatio: opts.deterministic ? 1 : undefined,
    });
    await viewer.load(opts.vrmUrl);
  } catch {
    log(makeEvent("degradacion", "error-carga"));
    return fallback();
  }
  if (opts.deterministic) {
    return { mode: "avatar", viewer, events, dispose: () => viewer.dispose() };
  }
  viewer.start();
  const fps = await probeFps();
  const reason = decide(true, fps);
  if (reason) {
    viewer.dispose();
    log(makeEvent("degradacion", reason, fps));
    return fallback();
  }
  log(makeEvent("avatar-ok", undefined, fps));
  return { mode: "avatar", viewer, events, dispose: () => viewer.dispose() };
}
