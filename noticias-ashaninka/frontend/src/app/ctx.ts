// Contexto de la aplicación: traducción, ajustes y cola de eventos.
import { createContext } from "preact";
import { useContext } from "preact/hooks";
import type { EventQueue } from "./events";
import type { Lang } from "./i18n";
import type { Settings } from "./settings";

export interface AppCtx {
  t: (key: string, vars?: Record<string, string | number>) => string;
  lang: Lang;
  settings: Settings;
  setSettings: (s: Settings) => void;
  events: EventQueue;
  online: boolean;
}

export const Ctx = createContext<AppCtx>(null as unknown as AppCtx);
export const useApp = (): AppCtx => useContext(Ctx);
