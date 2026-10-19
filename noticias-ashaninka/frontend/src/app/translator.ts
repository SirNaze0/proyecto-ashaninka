// Traducción castellano → asháninka (pantalla de entrada). El traductor es el de la tesis de una
// compañera y TODAVÍA NO ESTÁ INTEGRADO: no existe endpoint ni contrato de API acordado, así que la
// implementación por defecto no llama a ninguna URL y nunca devuelve texto. Nada aquí simula una
// traducción.
//
// Para conectar el modelo real (ver PLAN_DESARROLLO.md §2):
//   1. Acordar con la compañera la API (entrada, salida, versión, límites, ortografía de salida, P7).
//   2. Exponerla en el MISMO origen (ruta del backend): la CSP solo permite `connect-src 'self'`.
//   3. Implementar `Translator` con `disponible: true` y pasarla a `TranslatePanel`.
//   4. Voz y avatar del resultado: hoy solo existen para noticias guardadas (`/api/synthesize/{id}`,
//      manifiesto por lotes); la vía prevista es el contrato `POST /api/news` (con token de
//      administración) + `process` + `batch`, y luego `Presentation` en C2–C4.

export interface Translator {
  /** `false` mientras el servicio no esté integrado: la pantalla lo declara y no promete resultado. */
  readonly disponible: boolean;
  /** Texto en castellano → texto en asháninka. Rechaza con un `Error` si falla. */
  translate(texto: string, signal?: AbortSignal): Promise<string>;
}

export class TraductorNoDisponible extends Error {
  constructor() {
    super("El servicio de traducción está pendiente de integración.");
    this.name = "TraductorNoDisponible";
  }
}

/** Implementación por defecto: no hay traductor. No hace peticiones ni inventa respuestas. */
export const TRADUCTOR_PENDIENTE: Translator = {
  disponible: false,
  translate: () => Promise.reject(new TraductorNoDisponible()),
};

// ------------------------------------------------------------------ estados de la pantalla
export type TranslateState =
  | { s: "inicial" }
  | { s: "cargando" }
  | { s: "resultado"; texto: string }
  | { s: "error"; mensaje: string }
  | { s: "pendiente" };

export type TranslateAction =
  | { type: "enviar" }
  | { type: "ok"; texto: string }
  | { type: "fallo"; error: unknown }
  | { type: "editar" };

export const ESTADO_INICIAL: TranslateState = { s: "inicial" };

export function reducir(state: TranslateState, a: TranslateAction): TranslateState {
  switch (a.type) {
    case "enviar":
      return { s: "cargando" };
    case "ok":
      // un resultado vacío no es una traducción: se trata como error, no se muestra nada inventado
      return a.texto.trim() ? { s: "resultado", texto: a.texto } : { s: "error", mensaje: "vacio" };
    case "fallo":
      if (a.error instanceof TraductorNoDisponible) return { s: "pendiente" };
      return { s: "error", mensaje: a.error instanceof Error ? a.error.message : String(a.error) };
    case "editar":
      // al cambiar el texto, el resultado anterior deja de corresponderle
      return state.s === "cargando" ? state : ESTADO_INICIAL;
  }
}
