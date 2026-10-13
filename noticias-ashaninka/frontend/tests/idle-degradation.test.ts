import { describe, expect, it } from "vitest";
import { decide, FPS_MIN, makeEvent } from "../src/avatar/degradation";
import { Blinker, Gaze, Gestures, builtinClips, seeded } from "../src/avatar/idle";

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
  it("hay 4 clips y el saludo empieza y termina en la pose base", () => {
    const g = new Gestures();
    expect(g.names()).toEqual(["reposo-hablando", "saludo-apertura", "asentir", "despedida"]);
    const saludo = builtinClips().find((c) => c.name === "saludo-apertura")!;
    expect(saludo.pose(0).rightUpperArm?.z).toBeCloseTo(1.25);
    expect(saludo.pose(saludo.duration).rightUpperArm?.z).toBeCloseTo(1.25);
    expect(saludo.pose(saludo.duration / 2).rightUpperArm?.z).toBeLessThan(0);
  });
  it("un clip desconocido lanza y uno activo expira", () => {
    const g = new Gestures();
    expect(() => g.play("nada", 0)).toThrow();
    g.play("asentir", 10);
    expect(g.poseAt(10.5)).toHaveLength(2);
    expect(g.poseAt(12)).toHaveLength(1);
  });
});
