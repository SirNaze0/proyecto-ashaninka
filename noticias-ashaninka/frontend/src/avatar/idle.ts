// Parpadeo, mirada sutil y gestos procedurales de la presentadora.
//
// Los gestos son procedurales (rotaciones de huesos normalizados de VRM) y NO clips de Mixamo:
// Mixamo exige cuenta de Adobe y términos propios para cada descarga, así que no se puede
// automatizar ni versionar. El diseño deja `Gestures.register()` para sumar clips retargeteados
// cuando el modelo final de VRoid esté listo (ver docs/avatar.md).

export interface Rng {
  (): number;
}

/** Generador pseudoaleatorio determinista (mulberry32) para que los clips sean reproducibles. */
export function seeded(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Parpadeo: intervalos de 2–6 s y cierre de ~180 ms (triangular). */
export class Blinker {
  private next: number;
  private start = -1;
  constructor(
    private readonly rng: Rng = seeded(7),
    private readonly closeMs = 180,
  ) {
    this.next = 1 + this.rng() * 2;
  }

  /** Peso de `blink` (0..1) en el instante `t` (segundos). */
  value(t: number): number {
    if (this.start < 0 && t >= this.next) this.start = t;
    if (this.start >= 0) {
      const u = (t - this.start) / (this.closeMs / 1000);
      if (u >= 1) {
        this.start = -1;
        this.next = t + 2 + this.rng() * 4;
        return 0;
      }
      return 1 - Math.abs(2 * u - 1);
    }
    return 0;
  }
}

/** Mirada: deriva lenta alrededor de la cámara, con una sacada nueva cada 1,5–4 s. */
export class Gaze {
  private from = { x: 0, y: 0 };
  private to = { x: 0, y: 0 };
  private t0 = 0;
  private hold = 1.5;
  constructor(
    private readonly rng: Rng = seeded(11),
    private readonly amplitude = 0.08,
  ) {}

  /** Desplazamiento (metros, en el plano de la cámara) del objetivo de la mirada. */
  at(t: number): { x: number; y: number } {
    if (t - this.t0 >= this.hold) {
      this.from = { ...this.to };
      this.to = {
        x: (this.rng() * 2 - 1) * this.amplitude,
        y: (this.rng() * 2 - 1) * this.amplitude * 0.5,
      };
      this.t0 = t;
      this.hold = 1.5 + this.rng() * 2.5;
    }
    const u = Math.min(1, (t - this.t0) / 0.18); // sacada rápida
    const e = u * u * (3 - 2 * u);
    return {
      x: this.from.x + (this.to.x - this.from.x) * e,
      y: this.from.y + (this.to.y - this.from.y) * e,
    };
  }
}

export type BoneName =
  | "head"
  | "neck"
  | "spine"
  | "chest"
  | "leftUpperArm"
  | "leftLowerArm"
  | "rightUpperArm"
  | "rightLowerArm"
  | "rightHand";
export type BonePose = Partial<Record<BoneName, Euler>>;
export interface Euler {
  x?: number;
  y?: number;
  z?: number;
}

export interface Clip {
  name: string;
  duration: number;
  loop?: boolean;
  /** DELTAS (radianes) a sumar a REST_POSE en el instante `t` del clip, 0..duration; nunca poses absolutas. */
  pose(t: number): BonePose;
}

const smooth = (u: number) => u * u * (3 - 2 * u);
/** Entrada y salida suaves de 0,35 s para que ningún clip dé tirones. */
function envelope(t: number, d: number, edge = 0.35): number {
  return smooth(Math.max(0, Math.min(1, t / edge))) * smooth(Math.max(0, Math.min(1, (d - t) / edge)));
}

/** Pose de reposo con los brazos abajo (el VRM normalizado está en T). Los clips se SUMAN a ella. */
export const REST_POSE: BonePose = {
  leftUpperArm: { z: -1.25 },
  leftLowerArm: { z: -0.12 },
  rightUpperArm: { z: 1.25 },
  rightLowerArm: { z: 0.12 },
};

type Rango = [number, number];
interface LimitesHueso {
  x: Rango;
  y: Rango;
  z: Rango;
}
const ARM: LimitesHueso = { x: [-0.06, 0.06], y: [-0.06, 0.06], z: [-0.06, 0.06] };
const HEAD: LimitesHueso = { x: [0, 0.06], y: [-0.06, 0.06], z: [-0.06, 0.06] }; // x >= 0: nunca hacia atrás
const TORSO: LimitesHueso = { x: [0, 0.05], y: [-0.05, 0.05], z: [-0.05, 0.05] };

/** Rango (rad) del delta procedural por hueso y eje, respecto a REST_POSE. */
export const POSE_LIMITS: Record<BoneName, LimitesHueso> = {
  head: HEAD,
  neck: HEAD,
  spine: TORSO,
  chest: TORSO,
  leftUpperArm: ARM,
  leftLowerArm: ARM,
  rightUpperArm: ARM,
  rightLowerArm: ARM,
  rightHand: ARM,
};

const clamp = (v: number, [lo, hi]: Rango) => Math.min(hi, Math.max(lo, v));

/** Suma los deltas de varias poses y los recorta a POSE_LIMITS (también los clips registrados luego). */
export function limitPose(poses: BonePose[]): BonePose {
  const out: BonePose = {};
  for (const bone of Object.keys(POSE_LIMITS) as BoneName[]) {
    let x = 0;
    let y = 0;
    let z = 0;
    for (const p of poses) {
      const e = p[bone];
      if (e) {
        x += e.x ?? 0;
        y += e.y ?? 0;
        z += e.z ?? 0;
      }
    }
    const l = POSE_LIMITS[bone];
    out[bone] = { x: clamp(x, l.x), y: clamp(y, l.y), z: clamp(z, l.z) };
  }
  return out;
}

export function builtinClips(): Clip[] {
  // Saludo y despedida: la presentadora no levanta el brazo; solo un asentimiento y un micro-gesto del antebrazo
  const cortesia = (t: number, d: number, forearm: number): BonePose => {
    const e = envelope(t, d);
    return {
      head: { x: 0.05 * e, z: Math.sin(t * 2) * 0.03 * e },
      chest: { x: 0.02 * e },
      rightLowerArm: { z: -forearm * e },
    };
  };
  return [
    {
      // Reposo hablando: respiración y balanceo suave de cabeza/torso, en bucle
      name: "reposo-hablando",
      duration: 6,
      loop: true,
      pose: (t) => ({
        chest: { x: (1 - Math.cos(t * 1.4)) * 0.006 },
        spine: { z: Math.sin(t * 0.5) * 0.01 },
        head: { x: (1 - Math.cos(t * 0.9)) * 0.01, y: Math.sin(t * 0.6) * 0.03 },
      }),
    },
    { name: "saludo-apertura", duration: 2.6, pose: (t) => cortesia(t, 2.6, 0.05) },
    {
      name: "asentir",
      duration: 1.1,
      pose: (t) => {
        const n = Math.sin((t / 1.1) * Math.PI) ** 2;
        return { head: { x: 0.05 * n }, neck: { x: 0.02 * n } };
      },
    },
    {
      name: "despedida",
      duration: 3.0,
      pose: (t) => {
        const p = cortesia(t, 3.0, 0.04);
        return { ...p, spine: { x: smooth(Math.max(0, Math.min(1, (t - 2.2) / 0.5))) * 0.04 * envelope(t, 3.0, 0.2) } };
      },
    },
  ];
}

export class Gestures {
  private readonly clips = new Map<string, Clip>();
  private current: { clip: Clip; start: number } | null = null;
  private readonly base: Clip;

  constructor(clips: Clip[] = builtinClips()) {
    clips.forEach((c) => this.register(c));
    this.base = this.clips.get("reposo-hablando") as Clip;
  }

  register(clip: Clip): void {
    this.clips.set(clip.name, clip);
  }

  names(): string[] {
    return [...this.clips.keys()];
  }

  play(name: string, now: number): void {
    const clip = this.clips.get(name);
    if (!clip) throw new Error(`clip desconocido: ${name}`);
    this.current = { clip, start: now };
  }

  /** Poses a sumar en el instante `now`: el reposo en bucle más el clip activo, si lo hay. */
  poseAt(now: number): BonePose[] {
    const out: BonePose[] = [this.base.pose(now % this.base.duration)];
    if (this.current) {
      const t = now - this.current.start;
      if (t >= this.current.clip.duration) this.current = null;
      else out.push(this.current.clip.pose(t));
    }
    return out;
  }
}
