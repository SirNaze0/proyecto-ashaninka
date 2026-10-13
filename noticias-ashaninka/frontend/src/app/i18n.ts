// Interfaz bilingüe (tarea 4.1). El castellano está completo; el asháninka está PENDIENTE de
// traducción por un hablante: `cni.json` lleva las mismas claves con `null` y nunca se inventa
// texto. Mientras un valor sea null se muestra el castellano.
import cni from "./i18n/cni.json";
import es from "./i18n/es.json";

export type Lang = "es" | "cni";
export const LANGS: Lang[] = ["es", "cni"];

const TABLES: Record<Lang, Record<string, string | null>> = {
  es: es as Record<string, string | null>,
  cni: cni as Record<string, string | null>,
};

export function translate(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const raw = TABLES[lang][key] ?? TABLES.es[key] ?? key;
  return raw.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`));
}

/** Cuántas cadenas del asháninka siguen pendientes (se informa en Ajustes). */
export function pendingCount(): number {
  return Object.entries(TABLES.cni).filter(([k, v]) => !k.startsWith("_") && v === null).length;
}
