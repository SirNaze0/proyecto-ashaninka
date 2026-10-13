import { describe, expect, it } from "vitest";
import { AudioClock, type AudioLike } from "../src/avatar/clock";

/** Audio simulado: currentTime avanza a saltos de `step` s y con un retraso fijo `lag` s. */
function simulate(step: number, lag: number, rate = 1) {
  let wall = 1000; // ms
  const audio: AudioLike = { currentTime: 0, paused: false, playbackRate: rate };
  const truth = (w: number) => ((w - 1000) / 1000) * rate;
  const clock = new AudioClock(audio, { now: () => wall });
  const errors: number[] = [];
  for (let i = 0; i < 400; i++) {
    wall += 1000 / 60;
    const real = truth(wall);
    audio.currentTime = Math.max(0, Math.floor((real - lag) / step) * step);
    const est = clock.now();
    if (i > 60) errors.push(est - real);
  }
  return errors;
}

describe("AudioClock", () => {
  it("el error medio es menor que un fotograma aunque currentTime avance a saltos de 40 ms", () => {
    const e = simulate(0.04, 0.0);
    expect(Math.max(...e.map(Math.abs))).toBeLessThan(0.02);
  });
  it("no va nunca hacia atrás y no se adelanta a la posición real", () => {
    const e = simulate(0.02, 0.01);
    expect(Math.max(...e)).toBeLessThanOrEqual(0.001);
  });
  it("respeta la velocidad de reproducción", () => {
    const e = simulate(0.02, 0.0, 1.25);
    expect(Math.max(...e.map(Math.abs))).toBeLessThan(0.03);
  });
  it("en pausa devuelve currentTime (más la compensación de latencia)", () => {
    const audio: AudioLike = { currentTime: 3.2, paused: true, playbackRate: 1 };
    const c = new AudioClock(audio, { now: () => 5000, latencyMs: 30 });
    expect(c.now()).toBeCloseTo(3.23);
  });
  it("no extrapola mientras el audio no ha arrancado (currentTime sigue en 0)", () => {
    let wall = 0;
    const audio: AudioLike = { currentTime: 0, paused: false, playbackRate: 1 };
    const c = new AudioClock(audio, { now: () => wall });
    for (let i = 0; i < 6; i++) {
      wall += 16;
      expect(c.now()).toBe(0);
    }
    wall += 16;
    audio.currentTime = 0.007;
    expect(c.now()).toBeCloseTo(0.007, 2);
  });
  it("un seek hacia atrás reinicia el estimador", () => {
    let wall = 0;
    const audio: AudioLike = { currentTime: 5, paused: false, playbackRate: 1 };
    const c = new AudioClock(audio, { now: () => wall });
    for (let i = 0; i < 10; i++) {
      wall += 16;
      audio.currentTime += 0.016;
      c.now();
    }
    audio.currentTime = 0.5;
    wall += 16;
    expect(c.now()).toBeLessThan(1);
  });
});
