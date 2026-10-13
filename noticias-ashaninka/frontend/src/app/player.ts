// Reproductor por segmentos (tarea 4.2): dos <audio> alternos; mientras suena uno, el otro ya
// tiene el siguiente cargado. Los segmentos bloqueados (solo texto) se avisan y se saltan sin
// detener la reproducción continua.
import { type PlayerItem, clampRate, nextParagraphStart, nextPlayable, paragraphStart } from "./queue";

export type PlayerState = "idle" | "playing" | "paused" | "buffering" | "finished";

export interface PlayerHooks {
  /** Empieza a sonar el segmento `pos` (posición en `items`). `audio` es el <audio> activo. */
  onSegmentStart(item: PlayerItem, pos: number, audio: HTMLAudioElement): void;
  onSegmentEnd(item: PlayerItem, pos: number): void;
  /** Se salta un segmento bloqueado: hay que mostrarlo como solo texto. */
  onBlocked(item: PlayerItem, pos: number): void;
  onState(state: PlayerState): void;
  onFinished(): void;
  onEvent(type: string, payload?: Record<string, string | number | boolean | null>): void;
}

export interface TimelineMark {
  type: "playing" | "ended";
  pos: number;
  t: number;
}

interface Slot {
  audio: HTMLAudioElement;
  pos: number; // posición en items que tiene cargada (-1 = ninguna)
}

export class SegmentPlayer {
  items: PlayerItem[] = [];
  state: PlayerState = "idle";
  rate = 1;
  cur = -1;
  /** Marcas de `playing` y `ended` de cada segmento: base de TTFA y del hueco entre segmentos. */
  readonly timeline: TimelineMark[] = [];
  private complete = false;
  private slots: Slot[];
  private active = 0;
  private waitingFrom = -1;
  private disposed = false;

  constructor(
    private readonly hooks: PlayerHooks,
    audioFactory: () => HTMLAudioElement = () => new Audio(),
  ) {
    this.slots = [0, 1].map(() => {
      const audio = audioFactory();
      audio.preload = "auto";
      audio.preservesPitch = true;
      audio.addEventListener("ended", () => this.ended(audio));
      audio.addEventListener("playing", () => this.mark("playing", audio));
      audio.addEventListener("error", () => this.hooks.onEvent("error", { message: "audio" }));
      return { audio, pos: -1 };
    });
  }

  /** <audio> que suena (o sonó) ahora. */
  get audio(): HTMLAudioElement {
    return this.slots[this.active].audio;
  }

  /** Los dos <audio>, para crearles un reloj a cada uno. */
  get elements(): HTMLAudioElement[] {
    return this.slots.map((s) => s.audio);
  }

  /** Agrega segmentos (el respaldo por streaming los entrega de a uno). `complete` = no vendrán más. */
  append(items: PlayerItem[], complete: boolean): void {
    this.items.push(...items);
    this.complete = complete;
    if (this.state === "buffering" && this.waitingFrom >= 0) {
      const from = this.waitingFrom;
      this.waitingFrom = -1;
      void this.startAt(from);
    } else if (this.cur >= 0) this.preloadNext();
  }

  /** Precarga el primer segmento con audio (así el TTFA al pulsar «Reproducir» es mínimo). */
  prime(): void {
    const first = this.items.findIndex((i) => i.url);
    if (first >= 0 && this.slots[0].pos !== first && this.cur < 0) this.load(this.slots[0], first);
  }

  markComplete(): void {
    this.complete = true;
    if (this.state === "buffering" && this.waitingFrom >= 0) void this.startAt(this.waitingFrom);
  }

  async play(): Promise<void> {
    if (this.state === "paused") {
      this.setState("playing");
      this.hooks.onEvent("play", { idx: this.items[this.cur]?.idx ?? -1 });
      await this.audio.play().catch(() => this.hooks.onEvent("error", { message: "play" }));
      return;
    }
    if (this.state === "playing" || this.state === "buffering") return;
    this.hooks.onEvent("play", { idx: this.items[0]?.idx ?? -1 });
    await this.startAt(0);
  }

  pause(): void {
    if (this.state !== "playing") return;
    this.audio.pause();
    this.setState("paused");
    this.hooks.onEvent("pause", {
      idx: this.items[this.cur]?.idx ?? -1,
      position_s: Math.round(this.audio.currentTime * 100) / 100,
    });
  }

  toggle(): void {
    if (this.state === "playing") this.pause();
    else void this.play();
  }

  setRate(r: number): void {
    this.rate = clampRate(r);
    for (const s of this.slots) s.audio.playbackRate = this.rate;
    this.hooks.onEvent("rate", { rate: this.rate });
  }

  repeatParagraph(): void {
    if (this.cur < 0) return;
    const start = paragraphStart(this.items, this.cur);
    this.hooks.onEvent("repeat-paragraph", { paragraph: this.items[this.cur].paragraph });
    void this.startAt(start);
  }

  nextParagraph(): void {
    if (this.cur < 0) return;
    const n = nextParagraphStart(this.items, this.cur);
    if (n >= 0) {
      this.hooks.onEvent("seek", { idx: this.items[n].idx });
      void this.startAt(n);
    }
  }

  dispose(): void {
    this.disposed = true;
    for (const s of this.slots) {
      s.audio.pause();
      s.audio.removeAttribute("src");
      s.audio.load();
    }
  }

  // ------------------------------------------------------------------ internos
  private setState(s: PlayerState): void {
    this.state = s;
    this.hooks.onState(s);
  }

  private mark(type: TimelineMark["type"], audio: HTMLAudioElement): void {
    const slot = this.slots.find((s) => s.audio === audio);
    if (slot) this.timeline.push({ type, pos: slot.pos, t: performance.now() });
  }

  /** Empieza en `pos` (o en el siguiente con audio), avisando de los bloqueados que se saltan. */
  private async startAt(pos: number): Promise<void> {
    if (this.disposed) return;
    let p = pos;
    while (p < this.items.length && !this.items[p].url) {
      this.hooks.onBlocked(this.items[p], p);
      this.hooks.onEvent("blocked-shown", { idx: this.items[p].idx });
      p++;
    }
    if (p >= this.items.length) {
      if (this.complete) {
        this.audio.pause();
        this.setState("finished");
        this.hooks.onFinished();
      } else {
        this.waitingFrom = p;
        this.setState("buffering");
      }
      return;
    }
    const slotIdx = this.slots.findIndex((s) => s.pos === p);
    const reuse = slotIdx >= 0;
    const idx = reuse ? slotIdx : this.active === 0 && this.cur >= 0 ? 1 : 0;
    // al cambiar de segmento se detiene el que suena (repetir párrafo, saltos) sin pisar la precarga
    if (idx !== this.active || !reuse) this.audio.pause();
    const slot = this.slots[idx];
    if (!reuse) this.load(slot, p);
    else slot.audio.currentTime = 0;
    this.active = idx;
    this.cur = p;
    slot.audio.playbackRate = this.rate;
    this.setState("playing");
    this.hooks.onSegmentStart(this.items[p], p, slot.audio);
    this.hooks.onEvent("segment-start", { idx: this.items[p].idx });
    try {
      await slot.audio.play();
    } catch {
      this.hooks.onEvent("error", { message: "play-rechazado" });
      this.setState("paused");
    }
    this.preloadNext();
  }

  private load(slot: Slot, pos: number): void {
    slot.pos = pos;
    slot.audio.src = this.items[pos].url as string;
    slot.audio.load();
  }

  private preloadNext(): void {
    const n = nextPlayable(this.items, this.cur);
    if (n < 0) return;
    const other = this.slots[1 - this.active];
    if (other.pos !== n) this.load(other, n);
  }

  private ended(audio: HTMLAudioElement): void {
    if (audio !== this.audio || this.state !== "playing") return;
    this.mark("ended", audio);
    const item = this.items[this.cur];
    this.hooks.onSegmentEnd(item, this.cur);
    this.hooks.onEvent("segment-end", { idx: item.idx });
    void this.startAt(this.cur + 1);
  }
}
