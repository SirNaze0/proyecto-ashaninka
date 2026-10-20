// Ajustes persistidos (idioma y tamaño del texto). El almacenamiento puede fallar (modo privado):
// todo se envuelve en try/catch y la app funciona sin él.
import type { Lang } from "./i18n";

export interface Settings {
  lang: Lang;
  /** 0 = normal, 1 = grande, 2 = muy grande, 3 = extra grande. */
  textSize: 0 | 1 | 2 | 3;
  /** `auto` sigue la preferencia del sistema; `light`/`dark` la fuerzan. */
  theme: Theme;
}

export type Theme = "auto" | "light" | "dark";
export const THEMES: Theme[] = ["auto", "light", "dark"];

export const TEXT_SCALES = [1, 1.25, 1.5, 2] as const;
const KEY = "na-settings";
const DEFAULTS: Settings = { lang: "es", textSize: 0, theme: "auto" };

export function loadSettings(): Settings {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Settings>;
    return {
      lang: raw.lang === "cni" ? "cni" : "es",
      textSize: [0, 1, 2, 3].includes(raw.textSize as number) ? (raw.textSize as Settings["textSize"]) : 0,
      theme: THEMES.includes(raw.theme as Theme) ? (raw.theme as Theme) : "auto",
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(s: Settings): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* sin almacenamiento: se usa solo en esta sesión */
  }
}
