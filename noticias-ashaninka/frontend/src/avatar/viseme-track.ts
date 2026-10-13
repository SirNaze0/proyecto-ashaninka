// Pista de visemas: keyframes lineales por tramos generados por el backend (seg_NNN.json).
// Misma regla de evaluación que `sample()` en backend/app/pipeline/viseme/track.py.
// SUPUESTO-LING: el mapa grafema -> visema que produjo estos pesos no está validado (P1).

export interface VisemeBlock {
  status: string;
  map_sha256: string;
  channels: string[];
  smooth_ms: number;
  lead: number;
  duration_s: number;
  keyframes: [number, number[]][];
}

/** Canal del backend -> expresión preset de VRM 1.0 (C = labios cerrados: sin expresión). */
export const CHANNEL_TO_VRM: Record<string, string | null> = {
  A: "aa",
  I: "ih",
  U: "ou",
  E: "ee",
  O: "oh",
  C: null,
};

export class VisemeTrack {
  readonly channels: string[];
  readonly duration: number;
  private readonly kf: [number, number[]][];

  constructor(block: VisemeBlock) {
    this.channels = block.channels;
    this.duration = block.duration_s;
    this.kf = block.keyframes;
  }

  /** Pesos por canal en el instante `t` (segundos). Fuera del rango se mantiene el extremo. */
  sample(t: number, out?: number[]): number[] {
    const n = this.channels.length;
    const res = out ?? new Array<number>(n).fill(0);
    const kf = this.kf;
    if (kf.length === 0) return res.fill(0);
    if (t <= kf[0][0]) return copy(kf[0][1], res);
    if (t >= kf[kf.length - 1][0]) return copy(kf[kf.length - 1][1], res);
    let lo = 0;
    let hi = kf.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (kf[mid][0] <= t) lo = mid;
      else hi = mid;
    }
    const [t0, v0] = kf[lo];
    const [t1, v1] = kf[hi];
    const u = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
    for (let i = 0; i < n; i++) res[i] = v0[i] + (v1[i] - v0[i]) * u;
    return res;
  }

  /** Pesos por expresión VRM (solo canales con expresión asociada). */
  expressions(t: number): Record<string, number> {
    const w = this.sample(t);
    const out: Record<string, number> = {};
    this.channels.forEach((c, i) => {
      const name = CHANNEL_TO_VRM[c];
      if (name) out[name] = w[i];
    });
    return out;
  }
}

function copy(src: number[], dst: number[]): number[] {
  for (let i = 0; i < dst.length; i++) dst[i] = src[i] ?? 0;
  return dst;
}
