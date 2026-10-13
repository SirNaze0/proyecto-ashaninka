import { describe, expect, it } from "vitest";
import { EventQueue, MemoryStore } from "../src/app/events";
import { SegmentPlayer, type PlayerHooks } from "../src/app/player";
import type { PlayerItem } from "../src/app/queue";

/** <audio> falso: play() deja la reproducción "en curso" hasta que la prueba llame a finish(). */
class FakeAudio extends EventTarget {
  src = "";
  preload = "";
  preservesPitch = false;
  playbackRate = 1;
  currentTime = 0;
  paused = true;
  loads: string[] = [];
  load() {
    this.loads.push(this.src);
  }
  pause() {
    this.paused = true;
  }
  removeAttribute() {}
  async play() {
    this.paused = false;
    this.dispatchEvent(new Event("playing"));
  }
  finish() {
    this.paused = true;
    this.dispatchEvent(new Event("ended"));
  }
}

function setup(items: PlayerItem[], complete = true) {
  const log: string[] = [];
  const audios: FakeAudio[] = [];
  const hooks: PlayerHooks = {
    onSegmentStart: (i) => log.push(`start:${i.idx}`),
    onSegmentEnd: (i) => log.push(`end:${i.idx}`),
    onBlocked: (i) => log.push(`blocked:${i.idx}`),
    onState: (s) => log.push(`state:${s}`),
    onFinished: () => log.push("finished"),
    onEvent: (t) => log.push(`ev:${t}`),
  };
  const p = new SegmentPlayer(hooks, () => {
    const a = new FakeAudio();
    audios.push(a);
    return a as unknown as HTMLAudioElement;
  });
  p.append(items, complete);
  return { p, log, audios };
}

const it_ = (idx: number, par: number, url: string | null): PlayerItem => ({ idx, paragraph: par, url, blockedReason: url ? null : "bloqueado" });
const tick = () => new Promise((r) => setTimeout(r, 0));

describe("SegmentPlayer", () => {
  it("encadena segmentos con dos <audio>, precarga el siguiente y salta el bloqueado sin detenerse", async () => {
    const { p, log, audios } = setup([it_(0, 0, "a.opus"), it_(1, 0, null), it_(2, 1, "c.opus")]);
    await p.play();
    expect(log).toContain("start:0");
    expect(audios[1].loads).toEqual(["c.opus"]); // el siguiente ya está cargado en el otro <audio>
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    expect(log).toContain("blocked:1");
    expect(log).toContain("start:2");
    expect(p.audio).toBe(audios[1] as unknown as HTMLAudioElement);
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    expect(log.at(-1)).toBe("finished");
    expect(p.state).toBe("finished");
    expect(log.filter((l) => l === "ev:blocked-shown")).toHaveLength(1);
  });

  it("repetir párrafo vuelve al primer segmento con audio del párrafo", async () => {
    const { p, log } = setup([it_(0, 0, "a"), it_(1, 1, "b"), it_(2, 1, "c")]);
    await p.play();
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    log.length = 0;
    p.repeatParagraph();
    await tick();
    expect(log).toContain("ev:repeat-paragraph");
    expect(log).toContain("start:1");
    expect(p.cur).toBe(1);
  });

  it("pausa y reanuda, y limita la velocidad", async () => {
    const { p, log } = setup([it_(0, 0, "a")]);
    await p.play();
    p.pause();
    expect(p.state).toBe("paused");
    await p.play();
    expect(p.state).toBe("playing");
    p.setRate(5);
    expect(p.rate).toBe(1.25);
    expect((p.audio as unknown as FakeAudio).playbackRate).toBe(1.25);
    expect(log.filter((l) => l === "ev:pause")).toHaveLength(1);
  });

  it("espera los segmentos que llegan por streaming y sigue al llegar", async () => {
    const { p, log } = setup([it_(0, 0, "a")], false);
    await p.play();
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    expect(p.state).toBe("buffering");
    p.append([it_(1, 0, "b")], false);
    await tick();
    expect(log).toContain("start:1");
    p.markComplete();
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    expect(p.state).toBe("finished");
  });

  it("prime() precarga el primer audio y play() lo reutiliza", async () => {
    const { p, audios } = setup([it_(0, 0, null), it_(1, 0, "b")]);
    p.prime();
    expect(audios[0].loads).toEqual(["b"]);
    await p.play();
    expect(audios[0].loads).toEqual(["b"]); // no se volvió a cargar
  });

  it("registra la línea de tiempo de playing/ended", async () => {
    const { p } = setup([it_(0, 0, "a"), it_(1, 0, "b")]);
    await p.play();
    (p.audio as unknown as FakeAudio).finish();
    await tick();
    expect(p.timeline.map((m) => `${m.type}:${m.pos}`)).toEqual(["playing:0", "ended:0", "playing:1"]);
  });
});

describe("EventQueue", () => {
  const mk = (ok: () => boolean) => {
    const store = new MemoryStore();
    const sent: { events: { event_id: string }[] }[] = [];
    let n = 0;
    const q = new EventQueue(store, {
      sessionId: "11111111-1111-1111-1111-111111111111",
      uuid: () => `00000000-0000-0000-0000-${String(++n).padStart(12, "0")}`,
      batch: 2,
      fetchFn: (async (_u: string, init: RequestInit) => {
        if (!ok()) throw new TypeError("sin red");
        sent.push(JSON.parse(init.body as string));
        return new Response("{}", { status: 201 });
      }) as unknown as typeof fetch,
    });
    return { q, store, sent };
  };

  it("guarda sin red y entrega todo en lotes al volver, sin duplicados", async () => {
    let online = false;
    const { q, store, sent } = mk(() => online);
    q.setContext("C3", 5);
    for (let i = 0; i < 5; i++) await q.emit("play", { idx: i });
    expect(await q.flush()).toBe(0);
    expect(await store.count()).toBe(5);
    online = true;
    expect(await q.flush()).toBe(5);
    expect(await store.count()).toBe(0);
    expect(sent.map((b) => b.events.length)).toEqual([2, 2, 1]);
    const ids = sent.flatMap((b) => b.events.map((e) => e.event_id));
    expect(new Set(ids).size).toBe(5);
  });

  it("conserva los eventos si el servidor responde con error", async () => {
    const store = new MemoryStore();
    const q = new EventQueue(store, {
      sessionId: "11111111-1111-1111-1111-111111111111",
      fetchFn: (async () => new Response("{}", { status: 500 })) as unknown as typeof fetch,
    });
    await q.emit("pause");
    expect(await q.flush()).toBe(0);
    expect(await store.count()).toBe(1);
  });

  it("no incluye datos personales: solo sesión anónima, condición y noticia", async () => {
    const { q } = mk(() => true);
    q.setContext("C4", 9);
    await q.emit("degradacion", { reason: "sin-webgl" });
    const e = q.emitted[0];
    expect(Object.keys(e).sort()).toEqual(["condition", "event_id", "news_id", "payload", "session_id", "t_client", "type"]);
    expect(e.condition).toBe("C4");
  });
});
