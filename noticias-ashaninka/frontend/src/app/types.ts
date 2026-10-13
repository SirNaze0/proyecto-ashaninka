// Tipos compartidos de la PWA (Fase 4). Reflejan el manifiesto 1.1 y los seg_NNN.json del backend.
import type { VisemeBlock } from "../avatar/viseme-track";

export type Condition = "C1" | "C2" | "C3" | "C4";
export const CONDITIONS: Condition[] = ["C1", "C2", "C3", "C4"];

export interface AudioFiles {
  opus: string;
  mp3: string;
  opus_kbps: number;
  mp3_kbps: number;
}

export interface Seg {
  idx: number;
  paragraph_idx: number;
  text_orig: string;
  tts_ready: boolean;
  audio: AudioFiles | null;
  duration_s: number | null;
  timings: string | null;
  blocked_reason: string | null;
}

export interface Notices {
  synthetic_voice: string;
  license?: string;
  commercial_use?: boolean;
  non_commercial_warning?: string | null;
  dialect?: string;
}

export interface Manifest {
  schema_version: string;
  news_id: number;
  titulo_cni: string;
  fecha_publicacion: string | null;
  notices: Notices;
  segments: Seg[];
  total_duration_s: number;
  segments_with_audio: number;
  segments_blocked: number;
}

/** Fragmento del texto ORIGINAL con su tiempo de audio (mapa de alineación 1.5c proyectado). */
export interface Span {
  orig_start: number;
  orig_end: number;
  orig_text: string;
  category: string;
  t0: number;
  t1: number;
}

export interface SegTimings {
  idx: number;
  text_orig: string;
  spans: Span[];
  visemes: VisemeBlock;
}

export interface CatalogItem {
  id: number;
  titulo_cni: string;
  variante_dialectal: string;
  fecha_publicacion: string | null;
  procedencia_tipo: string;
  revisado_por_hablante: boolean;
  apta_experimento: boolean;
  segmentos: number;
  segmentos_con_audio: number;
  segmentos_bloqueados: number;
  duracion_s: number | null;
  manifest_url: string | null;
}

export interface CatalogSegment {
  idx: number;
  paragraph_idx: number;
  text_orig: string;
  tts_ready: boolean;
  blocked_reason: string | null;
}

export interface CatalogDetail {
  id: number;
  titulo_cni: string;
  variante_dialectal: string;
  fecha_publicacion: string | null;
  procedencia_tipo: string;
  apta_experimento: boolean;
  manifest_url: string | null;
  parrafos: CatalogSegment[][];
  avisos: Record<string, string>;
}

/** Metadatos sin texto del cuerpo (`/api/catalog/{id}/meta`). */
export type CatalogMeta = CatalogItem;
