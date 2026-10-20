// Contexto de la aplicación: traducción, ajustes y cola de eventos.
import { createContext } from "preact";
import { useContext } from "preact/hooks";
import type { EventQueue } from "./events";
import type { ExperimentController } from "./experiment";
import type { Lang } from "./i18n";
import type { Role } from "./role";
import type { Settings } from "./settings";

export interface AppCtx {
  t: (key: string, vars?: Record<string, string | number>) => string;
  lang: Lang;
  settings: Settings;
  setSettings: (s: Settings) => void;
  events: EventQueue;
  experiment: ExperimentController;
  online: boolean;
  /** Rol de la interfaz y token administrativo (solo en memoria; ver role.ts). */
  role: Role;
  token: string | null;
}

export const Ctx = createContext<AppCtx>(null as unknown as AppCtx);
export const useApp = (): AppCtx => useContext(Ctx);
