// Lógica pura de la cola de reproducción (probada con vitest): qué segmento sigue, cuáles están
// bloqueados (solo texto), dónde empieza un párrafo y qué formato de audio elegir.
import type { AudioFiles } from "./types";

export interface PlayerItem {
  idx: number;
  paragraph: number;
  /** URL del audio; `null` = segmento bloqueado (sin P2d): solo texto, nunca se sintetiza. */
  url: string | null;
  blockedReason: string | null;
}

export const RATES = [0.75, 1, 1.25] as const;

export function clampRate(r: number): number {
  return Math.min(1.25, Math.max(0.75, Number.isFinite(r) ? r : 1));
}

/** Posición (en `items`) del siguiente segmento con audio después de `from`, o -1. */
export function nextPlayable(items: PlayerItem[], from: number): number {
  for (let i = from + 1; i < items.length; i++) if (items[i].url) return i;
  return -1;
}

/** Posiciones bloqueadas estrictamente entre `from` y `to` (para avisar sin cortar la reproducción). */
export function blockedBetween(items: PlayerItem[], from: number, to: number): number[] {
  const out: number[] = [];
  for (let i = from + 1; i < (to < 0 ? items.length : to); i++) if (!items[i].url) out.push(i);
  return out;
}

/** Primer segmento con audio del párrafo de `items[pos]` (o el propio `pos` si no hay). */
export function paragraphStart(items: PlayerItem[], pos: number): number {
  const par = items[pos]?.paragraph;
  let first = -1;
  for (let i = 0; i < items.length; i++) {
    if (items[i].paragraph === par && items[i].url) {
      first = i;
      break;
    }
  }
  return first < 0 ? pos : first;
}

/** Primer segmento con audio del párrafo siguiente al de `items[pos]`, o -1. */
export function nextParagraphStart(items: PlayerItem[], pos: number): number {
  const par = items[pos]?.paragraph;
  for (let i = pos + 1; i < items.length; i++) if (items[i].paragraph !== par && items[i].url) return i;
  return -1;
}

/** Opus si el navegador lo reproduce; si no, el MP3 de respaldo. */
export function pickSource(audio: AudioFiles, canPlayType: (mime: string) => string): string {
  return canPlayType('audio/ogg; codecs="opus"') || canPlayType("audio/webm; codecs=opus")
    ? audio.opus
    : audio.mp3;
}
