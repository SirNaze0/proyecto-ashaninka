import { describe, expect, it } from "vitest";
import { VisemeTrack, type VisemeBlock } from "../src/avatar/viseme-track";

const block = (kf: [number, number[]][]): VisemeBlock => ({
  status: "SUPUESTO-LING",
  map_sha256: "x",
  channels: ["A", "I", "U", "E", "O", "C"],
  smooth_ms: 50,
  lead: 0.5,
  duration_s: 1,
  keyframes: kf,
});

describe("VisemeTrack", () => {
  const track = new VisemeTrack(
    block([
      [0.1, [1, 0, 0, 0, 0, 0]],
      [0.2, [0, 1, 0, 0, 0, 0]],
      [0.3, [0, 0, 0, 0, 0, 1]],
    ]),
  );
  it("mantiene los extremos fuera del rango", () => {
    expect(track.sample(0)).toEqual([1, 0, 0, 0, 0, 0]);
    expect(track.sample(5)).toEqual([0, 0, 0, 0, 0, 1]);
  });
  it("interpola linealmente entre keyframes (misma regla que el backend)", () => {
    const m = track.sample(0.15);
    expect(m[0]).toBeCloseTo(0.5);
    expect(m[1]).toBeCloseTo(0.5);
  });
  it("traduce canales a expresiones VRM y omite el cierre labial", () => {
    expect(track.expressions(0.1)).toEqual({ aa: 1, ih: 0, ou: 0, ee: 0, oh: 0 });
    expect("C" in track.expressions(0.3)).toBe(false);
  });
  it("una pista vacía da ceros", () => {
    expect(new VisemeTrack(block([])).sample(0.2)).toEqual([0, 0, 0, 0, 0, 0]);
  });
  it("un salto (dos knots al mismo instante) no divide por cero", () => {
    const t = new VisemeTrack(
      block([
        [0.1, [1, 0, 0, 0, 0, 0]],
        [0.2, [1, 0, 0, 0, 0, 0]],
        [0.2, [0, 1, 0, 0, 0, 0]],
        [0.3, [0, 1, 0, 0, 0, 0]],
      ]),
    );
    expect(Number.isFinite(t.sample(0.2)[0])).toBe(true);
    expect(t.sample(0.25)[1]).toBeCloseTo(1);
  });
});
