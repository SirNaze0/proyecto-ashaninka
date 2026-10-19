// Enrutador por hash (sin dependencias): #/ (traductor) · #/noticias · #/noticia/{id}?c=C3 · #/ajustes ·
// #/experimento[/...]
import { CONDITIONS, type Condition } from "./types";

export type Route =
  | { name: "translate" }
  | { name: "list" }
  | { name: "news"; id: number; condition: Condition }
  | { name: "settings" }
  | { name: "experiment"; step: ExperimentStep; k: number };

export type ExperimentStep = "inicio" | "bloque" | "cuestionario" | "final" | "fin";
const STEPS: ExperimentStep[] = ["bloque", "cuestionario", "final", "fin"];

export const DEFAULT_CONDITION: Condition = "C3";
/** Lista de noticias (antes en `#/`, que ahora es la pantalla de traducción). */
export const NEWS_HREF = "#/noticias";

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "ajustes") return { name: "settings" };
  if (parts[0] === "noticias") return { name: "list" };
  if (parts[0] === "experimento") {
    const step = STEPS.find((s) => s === parts[1]) ?? "inicio";
    const k = /^[0-3]$/.test(parts[2] ?? "") ? Number(parts[2]) : 0;
    return { name: "experiment", step, k };
  }
  if (parts[0] === "noticia" && /^\d+$/.test(parts[1] ?? "")) {
    const c = new URLSearchParams(query).get("c")?.toUpperCase();
    const condition = CONDITIONS.find((x) => x === c) ?? DEFAULT_CONDITION;
    return { name: "news", id: Number(parts[1]), condition };
  }
  if (parts[0] === "noticia") return { name: "list" }; // id mal formado: a la lista, como antes
  return { name: "translate" };
}

export function newsHref(id: number, condition: Condition): string {
  return `#/noticia/${id}?c=${condition}`;
}
