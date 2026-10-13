// Reloj sincronizado al audio.
//
// `audio.currentTime` solo avanza a saltos (cada 10–40 ms según el navegador) y siempre va un
// poco por detrás de la posición real. El estimador extrapola con el reloj monotónico del
// navegador entre saltos y corrige con un filtro de máximo: la mejor estimación del desfase
// entre ambos relojes es la observación MÁS ALTA de `currentTime - now`, porque el retraso solo
// puede restar. Así el error no se acumula y no hay saltos hacia atrás.

export interface AudioLike {
  currentTime: number;
  paused: boolean;
  playbackRate: number;
}

export interface ClockOptions {
  /** Muestras recientes del filtro de máximo. */
  window?: number;
  /** Compensación fija (ms) de la latencia de salida del audio; positivo = adelantar la boca. */
  latencyMs?: number;
  /** Reloj monotónico en milisegundos (inyectable para pruebas). */
  now?: () => number;
}

export class AudioClock {
  private readonly win: number;
  private readonly latency: number;
  private readonly wall: () => number;
  private readonly offsets: number[] = [];
  private lastAudio = Number.NaN;
  private lastOut = 0;

  constructor(
    private readonly audio: AudioLike,
    opts: ClockOptions = {},
  ) {
    this.win = opts.window ?? 24;
    this.latency = (opts.latencyMs ?? 0) / 1000;
    this.wall = opts.now ?? (() => performance.now());
  }

  /** Reinicia el estimador (al cambiar de segmento o tras un seek). */
  reset(): void {
    this.offsets.length = 0;
    this.lastAudio = Number.NaN;
    this.lastOut = 0;
  }

  /** Posición estimada del audio, en segundos. Monótona mientras se reproduce. */
  now(): number {
    const a = this.audio.currentTime;
    const w = this.wall() / 1000;
    const rate = this.audio.playbackRate || 1;
    if (this.audio.paused) {
      this.lastAudio = Number.NaN;
      this.offsets.length = 0;
      this.lastOut = a + this.latency;
      return this.lastOut;
    }
    if (a === 0 && this.offsets.length === 0) {
      // `play()` ya se llamó pero el audio todavía no arrancó (la salida tarda ~70–100 ms): no
      // se extrapola, o la boca se movería antes de que suene nada.
      this.lastOut = this.latency;
      return this.lastOut;
    }
    if (a !== this.lastAudio) {
      // currentTime se movió: nueva observación. Un salto grande hacia atrás (seek) reinicia.
      if (this.offsets.length && a < this.lastAudio - 0.25) {
        this.offsets.length = 0;
        this.lastOut = 0;
      }
      this.lastAudio = a;
      this.offsets.push(a - w * rate);
      if (this.offsets.length > this.win) this.offsets.shift();
    }
    const best = this.offsets.length ? Math.max(...this.offsets) : a - w * rate;
    const t = w * rate + best + this.latency;
    this.lastOut = Math.max(this.lastOut, t);
    return this.lastOut;
  }
}
