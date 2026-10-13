// Resaltado sincronizado (tarea 4.3). El texto que se muestra es el ORIGINAL ("MINSA", "2026");
// el audio dice su forma expandida. `spans` (seg_NNN.json) ya trae, por fragmento original, el
// intervalo de audio proyectado con el mapa de alineación de la Fase 1: mientras suena la glosa
// y la sigla, se resalta "MINSA" completo.
import type { Span } from "./types";

const HAS_WORD = /[\p{L}\p{N}]/u;

/** Posiciones de los fragmentos que se pueden resaltar: con letras o dígitos y duración > 0. */
export function highlightable(spans: Span[]): number[] {
  const out: number[] = [];
  spans.forEach((s, i) => {
    if (s.t1 > s.t0 && HAS_WORD.test(s.orig_text)) out.push(i);
  });
  return out;
}

/**
 * Fragmento activo en el instante `t` (s): el último resaltable con `t0 <= t`. Entre dos palabras
 * se mantiene la anterior (sin parpadeo) y tras la última se mantiene la última. -1 si aún no
 * empezó ninguno. `candidates` viene de `highlightable` (se calcula una vez por segmento).
 */
export function activeSpan(spans: Span[], candidates: number[], t: number): number {
  let lo = 0;
  let hi = candidates.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (spans[candidates[mid]].t0 <= t) {
      found = candidates[mid];
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/** El texto de los fragmentos reconstruye la oración? Si no, se muestra texto plano. */
export function spansMatch(spans: Span[], text: string): boolean {
  return spans.map((s) => s.orig_text).join("") === text;
}

export interface HighlightChange {
  seg: number;
  span: number;
  /** Posición del audio según el reloj (s) en el instante en que se aplicó el cambio. */
  clock_t: number;
  /** Inicio previsto del fragmento (s). `clock_t - t0` es el desfase del resaltado. */
  t0: number;
}

/** Resalta con requestAnimationFrame y registra cada cambio para medir el desfase. */
export class Highlighter {
  private spans: Span[] = [];
  private cand: number[] = [];
  private seg = -1;
  private current = -1;
  private raf = 0;
  private running = false;
  readonly log: HighlightChange[] = [];

  constructor(
    private readonly root: HTMLElement,
    private readonly clock: () => number | null,
    private readonly raq: typeof requestAnimationFrame = (cb) => requestAnimationFrame(cb),
  ) {}

  setSegment(seg: number, spans: Span[]): void {
    this.clear();
    this.seg = seg;
    this.spans = spans;
    this.cand = highlightable(spans);
    this.current = -1;
  }

  /** Quita el resaltado y olvida el segmento (al terminar o al cambiar a un segmento bloqueado). */
  reset(): void {
    this.clear();
    this.seg = -1;
    this.spans = [];
    this.cand = [];
    this.current = -1;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    const tick = () => {
      if (!this.running) return;
      this.step();
      this.raf = this.raq(tick);
    };
    this.raf = this.raq(tick);
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }

  /** Un paso del bucle (público para pruebas). */
  step(): void {
    if (this.seg < 0) return;
    const t = this.clock();
    if (t === null) return;
    const i = activeSpan(this.spans, this.cand, t);
    if (i === this.current) return;
    const next = this.el(i);
    if (i >= 0 && !next) return; // el texto con fragmentos aún no se dibujó: se reintenta en el cuadro siguiente
    this.el(this.current)?.classList.remove("hl");
    if (next) {
      next.classList.add("hl");
      next.scrollIntoView?.({ block: "nearest", behavior: "auto" });
    }
    this.current = i;
    if (i >= 0) this.log.push({ seg: this.seg, span: i, clock_t: t, t0: this.spans[i].t0 });
  }

  private el(i: number): Element | null {
    if (i < 0) return null;
    return this.root.querySelector(`[data-seg="${this.seg}"] [data-span="${i}"]`);
  }

  private clear(): void {
    this.el(this.current)?.classList.remove("hl");
  }
}
