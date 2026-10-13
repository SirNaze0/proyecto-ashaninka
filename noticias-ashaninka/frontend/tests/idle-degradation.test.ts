import { describe, expect, it } from "vitest";
import { decide, FPS_MIN, makeEvent } from "../src/avatar/degradation";
import { Blinker, Gaze, Gestures, REST_POSE, builtinClips, limitPose, seeded } from "../src/avatar/idle";

describe("degradación", () => {
  it("sin WebGL o con menos de 20 FPS se degrada; con 20 o más no", () => {
    expect(decide(false, null)).toBe("sin-webgl");
    expect(decide(true, FPS_MIN - 0.1)).toBe("fps-bajos");
    expect(decide(true, FPS_MIN)).toBeNull();
    expect(decide(true, 60)).toBeNull();
  });
  it("el evento queda registrado con fecha y motivo", () => {
    const e = makeEvent("degradacion", "fps-bajos", 12.34);
    expect(e.reason).toBe("fps-bajos");
    expect(e.fps).toBe(12.3);
    expect(Number.isNaN(Date.parse(e.at))).toBe(false);
  });
});

describe("parpadeo, mirada y gestos", () => {
  it("el parpadeo es reproducible, acotado y cierra y abre", () => {
    const vals = (seed: number) => {
      const b = new Blinker(seeded(seed));
      return Array.from({ length: 1200 }, (_, i) => b.value(i / 60));
    };
    expect(vals(3)).toEqual(vals(3));
    const v = vals(3);
    expect(Math.max(...v)).toBeGreaterThan(0.9);
    expect(Math.min(...v)).toBe(0);
    expect(v.every((x) => x >= 0 && x <= 1)).toBe(true);
  });
  it("la mirada se mantiene dentro de la amplitud", () => {
    const g = new Gaze(seeded(5), 0.08);
    for (let t = 0; t < 30; t += 0.05) {
      const p = g.at(t);
      expect(Math.abs(p.x)).toBeLessThanOrEqual(0.08 + 1e-9);
      expect(Math.abs(p.y)).toBeLessThanOrEqual(0.04 + 1e-9);
    }
  });
  it("hay 4 clips con los mismos nombres", () => {
    expect(new Gestures().names()).toEqual(["reposo-hablando", "saludo-apertura", "asentir", "despedida"]);
  });
  it("los clips son deltas sutiles: brazos <= 0,06 rad y cabeza/torso sin ir hacia atrás (<= 0,08)", () => {
    const brazos = ["leftUpperArm", "leftLowerArm", "rightUpperArm", "rightLowerArm", "rightHand"] as const;
    const eje = ["head", "neck", "spine", "chest"] as const;
    for (const c of builtinClips()) {
      for (let t = 0; t <= c.duration; t += 0.01) {
        const p = c.pose(t);
        for (const b of brazos)
          for (const a of ["x", "y", "z"] as const) expect(Math.abs(p[b]?.[a] ?? 0)).toBeLessThanOrEqual(0.06 + 1e-9);
        for (const b of eje) {
          expect(p[b]?.x ?? 0).toBeGreaterThanOrEqual(-1e-12);
          for (const a of ["x", "y", "z"] as const) expect(Math.abs(p[b]?.[a] ?? 0)).toBeLessThanOrEqual(0.08);
        }
      }
    }
  });
  it("los clips que no son de bucle empiezan y terminan en la pose de reposo (delta 0)", () => {
    for (const c of builtinClips().filter((x) => !x.loop))
      for (const t of [0, c.duration]) {
        const p = c.pose(t);
        for (const e of Object.values(p)) for (const v of Object.values(e ?? {})) expect(Math.abs(v)).toBeLessThan(1e-9);
      }
  });
  it("limitPose recorta un clip hostil y nunca levanta el brazo ni echa la cabeza atrás", () => {
    const r = limitPose([REST_POSE, { rightUpperArm: { z: -2.5, y: 1 }, head: { x: -0.5, y: 0.5 }, spine: { x: 1 } }]);
    expect(r.rightUpperArm).toEqual({ x: 0, y: 0.06, z: -0.06 });
    expect(r.head).toEqual({ x: 0, y: 0.06, z: 0 });
    expect(r.spine?.x).toBe(0.05);
  });
  it("un clip desconocido lanza y uno activo expira", () => {
    const g = new Gestures();
    expect(() => g.play("nada", 0)).toThrow();
    g.play("asentir", 10);
    expect(g.poseAt(10.5)).toHaveLength(2);
    expect(g.poseAt(12)).toHaveLength(1);
  });
});
