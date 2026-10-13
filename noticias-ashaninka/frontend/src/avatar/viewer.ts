// Visor del avatar VRM (tarea 3.5): three.js + @pixiv/three-vrm con CARGA DIFERIDA.
//
// Nada de three ni de three-vrm entra en el paquete inicial: `AvatarViewer.create()` los importa
// de forma dinámica, de modo que el avatar queda fuera del presupuesto de 3 MB de la carga
// inicial (PLAN_DESARROLLO §4.7).
//
// Sincronía: en cada fotograma se evalúa la pista de visemas en `clock.now()` (posición del audio
// estimada por `AudioClock`). `renderAt(t)` evalúa y dibuja un instante concreto y se usa para
// medir y capturar de forma determinista (3.7 y 3.8).

import type { VRM } from "@pixiv/three-vrm";
import type * as THREE_NS from "three";
import { AudioClock, type AudioLike, type ClockOptions } from "./clock";
import { Blinker, Gaze, Gestures, REST_POSE, seeded, type BoneName, type BonePose } from "./idle";
import { CHANNEL_TO_VRM, VisemeTrack } from "./viseme-track";

export type Framing = "busto" | "rostro";

export interface ViewerOptions {
  canvas: HTMLCanvasElement;
  width?: number;
  height?: number;
  framing?: Framing;
  /** Escala de los pesos de visemas (la boca de VRM al 100 % se ve exagerada). */
  intensity?: number;
  /** Sin parpadeo, mirada ni gestos y con búfer conservado: para medir y capturar. */
  deterministic?: boolean;
  pixelRatio?: number;
  background?: number | null;
}

export interface FrameStats {
  frames: number;
  meanFrameMs: number;
  p95FrameMs: number;
}

const BONES: BoneName[] = [
  "head",
  "neck",
  "spine",
  "chest",
  "leftUpperArm",
  "leftLowerArm",
  "rightUpperArm",
  "rightLowerArm",
  "rightHand",
];
const VISEME_EXPR = Object.values(CHANNEL_TO_VRM).filter((x): x is string => !!x);

export class AvatarViewer {
  private vrm: VRM | null = null;
  private track: VisemeTrack | null = null;
  private clock: AudioClock | null = null;
  private raf = 0;
  private running = false;
  private lastWall = 0;
  private readonly frameMs: number[] = [];
  private readonly blinker = new Blinker(seeded(7));
  private readonly gaze = new Gaze(seeded(11));
  private readonly gestures = new Gestures();
  private gazeTarget!: THREE_NS.Object3D;
  private readonly intensity: number;
  private readonly deterministic: boolean;
  private lastT = 0;

  private constructor(
    private readonly THREE: typeof THREE_NS,
    private readonly renderer: THREE_NS.WebGLRenderer,
    private readonly scene: THREE_NS.Scene,
    private readonly camera: THREE_NS.PerspectiveCamera,
    private readonly opts: ViewerOptions,
  ) {
    this.intensity = opts.intensity ?? 0.85;
    this.deterministic = opts.deterministic ?? false;
  }

  static async create(opts: ViewerOptions): Promise<AvatarViewer> {
    const THREE = await import("three");
    const w = opts.width ?? opts.canvas.clientWidth ?? 512;
    const h = opts.height ?? opts.canvas.clientHeight ?? 512;
    const renderer = new THREE.WebGLRenderer({
      canvas: opts.canvas,
      antialias: !opts.deterministic,
      alpha: opts.background === null,
      preserveDrawingBuffer: !!opts.deterministic,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(opts.pixelRatio ?? Math.min(globalThis.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    if (opts.background !== null) renderer.setClearColor(opts.background ?? 0xdde8ee, 1);
    const scene = new THREE.Scene();
    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(0.6, 1.2, 1.5);
    scene.add(key);
    const camera = new THREE.PerspectiveCamera(24, w / h, 0.05, 20);
    return new AvatarViewer(THREE, renderer, scene, camera, opts);
  }

  /** Descarga y prepara el modelo VRM. Lanza si el archivo no es un VRM válido. */
  async load(url: string): Promise<void> {
    const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
    const { VRMLoaderPlugin, VRMUtils } = await import("@pixiv/three-vrm");
    const loader = new GLTFLoader();
    loader.register((p) => new VRMLoaderPlugin(p));
    const gltf = await loader.loadAsync(url);
    const vrm = gltf.userData.vrm as VRM | undefined;
    if (!vrm) throw new Error("el archivo no contiene un VRM");
    VRMUtils.rotateVRM0(vrm); // los VRM 0.x miran a -Z
    this.scene.add(vrm.scene);
    this.vrm = vrm;
    this.gazeTarget = new this.THREE.Object3D();
    this.scene.add(this.gazeTarget);
    if (vrm.lookAt) vrm.lookAt.target = this.gazeTarget;
    this.frameCamera();
    this.applyPose([]);
    vrm.update(0);
  }

  private frameCamera(): void {
    const head = this.vrm?.humanoid.getNormalizedBoneNode("head");
    if (!head) return;
    const p = head.getWorldPosition(new this.THREE.Vector3());
    const closeup = (this.opts.framing ?? "busto") === "rostro";
    const dist = closeup ? 0.55 : 1.35;
    const lookY = closeup ? p.y + 0.045 : p.y - 0.05; // el hueso `head` está en la base del cuello
    this.camera.position.set(p.x, lookY, p.z + dist);
    this.camera.lookAt(p.x, lookY, p.z);
    this.gazeTarget.position.set(p.x, p.y + 0.1, p.z + dist);
  }

  setTrack(track: VisemeTrack | null): void {
    this.track = track;
  }

  attachAudio(audio: AudioLike, opts?: ClockOptions): AudioClock {
    this.clock = new AudioClock(audio, opts);
    return this.clock;
  }

  playGesture(name: string): void {
    this.gestures.play(name, this.lastT);
  }

  gestureNames(): string[] {
    return this.gestures.names();
  }

  get ready(): boolean {
    return this.vrm !== null;
  }

  /** Último instante (s) con el que se evaluaron los visemas. */
  get time(): number {
    return this.lastT;
  }

  /** Bucle en tiempo real: el reloj sale del audio si hay uno; si no, avanza con el navegador. */
  start(): void {
    if (this.running) return;
    this.running = true;
    this.lastWall = performance.now();
    const loop = (now: number) => {
      if (!this.running) return;
      const dt = (now - this.lastWall) / 1000;
      this.lastWall = now;
      const t0 = performance.now();
      this.frame(this.clock ? this.clock.now() : this.lastT + dt, dt);
      this.frameMs.push(performance.now() - t0);
      if (this.frameMs.length > 600) this.frameMs.shift();
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }

  /** Evalúa y dibuja el instante `t` (s). Determinista si el visor se creó con `deterministic`. */
  renderAt(t: number): void {
    this.frame(t, 1 / 60);
  }

  /** Peso actual de una expresión VRM (para pruebas y para la medición de la boca). */
  expression(name: string): number {
    return this.vrm?.expressionManager?.getValue(name) ?? 0;
  }

  /** Dibuja con todos los visemas en 0 salvo `weights` (calibración de la región de la boca). */
  renderExpressions(weights: Record<string, number>): void {
    const em = this.vrm?.expressionManager;
    if (!this.vrm || !em) return;
    this.applyPose([]);
    for (const e of VISEME_EXPR) em.setValue(e, weights[e] ?? 0);
    em.setValue("blink", 0);
    this.vrm.update(0);
    this.renderer.render(this.scene, this.camera);
  }

  stats(): FrameStats {
    const a = [...this.frameMs].sort((x, y) => x - y);
    const mean = a.reduce((s, x) => s + x, 0) / (a.length || 1);
    return { frames: a.length, meanFrameMs: mean, p95FrameMs: a[Math.floor(a.length * 0.95)] ?? 0 };
  }

  dispose(): void {
    this.stop();
    this.renderer.dispose();
    this.vrm?.scene.removeFromParent();
    this.vrm = null;
  }

  // ---------------------------------------------------------------- interno
  private frame(t: number, dt: number): void {
    const vrm = this.vrm;
    if (!vrm) return;
    this.lastT = t;
    const em = vrm.expressionManager;
    if (em) {
      const w = this.track ? this.track.expressions(t) : {};
      for (const e of VISEME_EXPR) em.setValue(e, Math.min(1, (w[e] ?? 0) * this.intensity));
      em.setValue("blink", this.deterministic ? 0 : this.blinker.value(t));
    }
    if (!this.deterministic) {
      const g = this.gaze.at(t);
      const head = vrm.humanoid.getNormalizedBoneNode("head");
      if (head) {
        const p = head.getWorldPosition(new this.THREE.Vector3());
        this.gazeTarget.position.set(p.x + g.x, p.y + 0.1 + g.y, p.z + 1.35);
      }
    }
    this.applyPose(this.deterministic ? [] : this.gestures.poseAt(t));
    vrm.update(dt);
    this.renderer.render(this.scene, this.camera);
  }

  private applyPose(poses: BonePose[]): void {
    const humanoid = this.vrm?.humanoid;
    if (!humanoid) return;
    for (const bone of BONES) {
      const node = humanoid.getNormalizedBoneNode(bone);
      if (!node) continue;
      let x = 0;
      let y = 0;
      let z = 0;
      for (const p of [REST_POSE, ...poses]) {
        const e = p[bone];
        if (e) {
          x += e.x ?? 0;
          y += e.y ?? 0;
          z += e.z ?? 0;
        }
      }
      node.rotation.set(x, y, z);
    }
  }
}
