// Pantalla de traducción: el traductor por defecto no existe todavía y no debe inventar nada.
import { afterEach, describe, expect, it, vi } from "vitest";
import { translate } from "../src/app/i18n";
import {
  ESTADO_INICIAL,
  TRADUCTOR_PENDIENTE,
  TraductorNoDisponible,
  type TranslateState,
  reducir,
} from "../src/app/translator";

afterEach(() => vi.unstubAllGlobals());

describe("traductor pendiente", () => {
  it("se declara no disponible, rechaza y no hace ninguna petición", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    expect(TRADUCTOR_PENDIENTE.disponible).toBe(false);
    await expect(TRADUCTOR_PENDIENTE.translate("Buenos días")).rejects.toBeInstanceOf(TraductorNoDisponible);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("su rechazo lleva la pantalla al estado «pendiente», sin texto de resultado", async () => {
    let s: TranslateState = reducir(ESTADO_INICIAL, { type: "enviar" });
    expect(s).toEqual({ s: "cargando" });
    const error = await TRADUCTOR_PENDIENTE.translate("hola").catch((e: unknown) => e);
    s = reducir(s, { type: "fallo", error });
    expect(s).toEqual({ s: "pendiente" });
    expect(s).not.toHaveProperty("texto");
  });
});

describe("estados de la pantalla", () => {
  const cargando: TranslateState = { s: "cargando" };

  it("resultado solo con el texto que devuelve el traductor", () => {
    expect(reducir(cargando, { type: "ok", texto: "<salida del traductor>" })).toEqual({ s: "resultado", texto: "<salida del traductor>" });
  });

  it("un resultado vacío es un error, no una traducción", () => {
    expect(reducir(cargando, { type: "ok", texto: "  " })).toEqual({ s: "error", mensaje: "vacio" });
  });

  it("los fallos del servicio se muestran como error con su mensaje", () => {
    expect(reducir(cargando, { type: "fallo", error: new Error("503") })).toEqual({ s: "error", mensaje: "503" });
    expect(reducir(cargando, { type: "fallo", error: "timeout" })).toEqual({ s: "error", mensaje: "timeout" });
  });

  it("editar el texto descarta el resultado anterior, pero no interrumpe una carga", () => {
    expect(reducir({ s: "resultado", texto: "x" }, { type: "editar" })).toEqual(ESTADO_INICIAL);
    expect(reducir({ s: "pendiente" }, { type: "editar" })).toEqual(ESTADO_INICIAL);
    expect(reducir(cargando, { type: "editar" })).toBe(cargando);
  });
});

describe("textos de la pantalla", () => {
  it("existen en castellano y caen al castellano en asháninka (sin texto inventado)", () => {
    for (const k of ["translate.pending", "translate.notAvailable", "nav.translate", "nav.news"]) {
      expect(translate("es", k)).not.toBe(k);
      expect(translate("cni", k)).toBe(translate("es", k));
    }
  });
});
