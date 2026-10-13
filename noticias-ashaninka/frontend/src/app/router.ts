// Enrutador por hash (sin dependencias): #/ · #/noticia/{id}?c=C3 · #/ajustes
import { CONDITIONS, type Condition } from "./types";

export type Route =
  | { name: "list" }
  | { name: "news"; id: number; condition: Condition }
  | { name: "settings" };

export const DEFAULT_CONDITION: Condition = "C3";

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "ajustes") return { name: "settings" };
  if (parts[0] === "noticia" && /^\d+$/.test(parts[1] ?? "")) {
    const c = new URLSearchParams(query).get("c")?.toUpperCase();
    const condition = CONDITIONS.find((x) => x === c) ?? DEFAULT_CONDITION;
    return { name: "news", id: Number(parts[1]), condition };
  }
  return { name: "list" };
}

export function newsHref(id: number, condition: Condition): string {
  return `#/noticia/${id}?c=${condition}`;
}
