// Sala de redacción: lectura de archivos (.txt, .csv, .json) al contrato de ingesta de
// PLAN_DESARROLLO.md §2 (`NewsIn`) y cliente de publicación (news → process → build).
// El texto de entrada YA debe estar en asháninka: aquí no se traduce ni se adapta nada.
import { adminHeaders } from "./role";

export type ProvenanceTipo = "traduccion_humana" | "traduccion_automatica" | "automatica_revisada";
export const PROVENANCE_TIPOS: ProvenanceTipo[] = ["traduccion_humana", "traduccion_automatica", "automatica_revisada"];

export interface NewsDraft {
  titulo_cni: string;
  paragraphs: string[];
  titulo_es: string;
  cuerpo_es: string;
  variante_dialectal: string;
  fecha_publicacion: string;
  fuente_original: string;
  procedencia: {
    tipo: ProvenanceTipo;
    sistema: string;
    version: string;
    revisado_por_hablante: boolean;
  };
}

export const ACCEPTED_EXTENSIONS = [".txt", ".csv", ".json"] as const;
export const MAX_FILE_BYTES = 2 * 1024 * 1024;
export const MAX_BATCH = 50;
export const MAX_PARAGRAPHS = 12;
export const MAX_PARAGRAPH_CHARS = 2000;
export const MAX_TITLE_CHARS = 160;

export function emptyDraft(): NewsDraft {
  return {
    titulo_cni: "",
    paragraphs: [""],
    titulo_es: "",
    cuerpo_es: "",
    variante_dialectal: "desconocida",
    fecha_publicacion: "",
    fuente_original: "desconocido",
    procedencia: { tipo: "traduccion_automatica", sistema: "", version: "", revisado_por_hablante: false },
  };
}

const fold = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

function clean(paragraphs: string[]): string[] {
  const out = paragraphs
    .map((p) => p.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .slice(0, MAX_PARAGRAPHS)
    .map((p) => p.slice(0, MAX_PARAGRAPH_CHARS));
  return out.length ? out : [""];
}

function draftFrom(partial: Partial<Record<string, unknown>>, paragraphs: string[]): NewsDraft {
  const d = emptyDraft();
  const str = (k: string) => (typeof partial[k] === "string" ? (partial[k] as string).trim() : "");
  const tipo = str("tipo");
  d.titulo_cni = str("titulo_cni").replace(/\s+/g, " ").slice(0, MAX_TITLE_CHARS);
  d.paragraphs = clean(paragraphs);
  d.titulo_es = str("titulo_es");
  d.cuerpo_es = str("cuerpo_es");
  d.variante_dialectal = str("variante_dialectal") || d.variante_dialectal;
  d.fecha_publicacion = /^\d{4}-\d{2}-\d{2}$/.test(str("fecha_publicacion")) ? str("fecha_publicacion") : "";
  d.fuente_original = str("fuente_original") || d.fuente_original;
  if (PROVENANCE_TIPOS.includes(tipo as ProvenanceTipo)) d.procedencia.tipo = tipo as ProvenanceTipo;
  d.procedencia.sistema = str("sistema");
  d.procedencia.version = str("version");
  d.procedencia.revisado_por_hablante = partial["revisado_por_hablante"] === true;
  return d;
}

const TITLE_RE = /^(t[ií]tulo|title)\s*:\s*/i;

/** `.txt`: «Título: …» opcional; si no hay, la primera línea es el título. Párrafos por línea en blanco. */
export function parsePlainText(text: string): NewsDraft {
  const lines = text.replace(/^﻿/, "").replace(/\r\n?/g, "\n").split("\n");
  let title = "";
  const body: string[] = [];
  for (const line of lines) {
    const t = line.trim();
    if (!title && TITLE_RE.test(t)) title = t.replace(TITLE_RE, "");
    else body.push(line);
  }
  let bodyText = body.join("\n").trim();
  if (!title) {
    const [first, ...rest] = bodyText.split("\n");
    title = first ?? "";
    bodyText = rest.join("\n").trim();
  }
  const blocks = bodyText.split(/\n\s*\n/);
  return draftFrom({ titulo_cni: title }, blocks.length > 1 ? blocks : bodyText.split("\n"));
}

type Json = Record<string, unknown>;

function fromJsonObject(o: Json): NewsDraft {
  const proc = o["procedencia"] && typeof o["procedencia"] === "object" ? (o["procedencia"] as Json) : {};
  const cuerpo = typeof o["cuerpo_cni"] === "string" ? o["cuerpo_cni"] : "";
  const pars = Array.isArray(o["paragraphs"]) ? (o["paragraphs"] as unknown[]).map(String) : cuerpo.split(/\n\s*\n|\n/);
  return draftFrom({ ...o, ...proc }, pars);
}

/** `.json`: un objeto `NewsIn`, una lista, o `{ "noticias": [...] }`. */
export function parseJson(text: string): NewsDraft[] {
  const data = JSON.parse(text.replace(/^﻿/, "")) as unknown;
  const list = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Json)["noticias"])
      ? ((data as Json)["noticias"] as unknown[])
      : [data];
  return list
    .filter((x): x is Json => !!x && typeof x === "object")
    .slice(0, MAX_BATCH)
    .map(fromJsonObject);
}

function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  const first = text.split("\n")[0] ?? "";
  const delim = first.includes(";") && !first.includes(",") ? ";" : ",";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delim) {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      if (row.some((c) => c.trim())) rows.push(row);
      row = [];
      field = "";
    } else field += ch;
  }
  row.push(field);
  if (row.some((c) => c.trim())) rows.push(row);
  return rows;
}

/** `.csv`: columnas `titulo_cni` y `cuerpo_cni` obligatorias; el resto del contrato es opcional. */
export function parseCsv(text: string): NewsDraft[] {
  const [header, ...rows] = csvRows(text.replace(/^﻿/, ""));
  if (!header) return [];
  const cols = header.map(fold);
  const at = (name: string) => cols.indexOf(name);
  const ti = at("titulo_cni");
  const bi = at("cuerpo_cni");
  if (ti === -1 || bi === -1) throw new Error('El CSV debe tener las columnas "titulo_cni" y "cuerpo_cni".');
  const optional = ["titulo_es", "cuerpo_es", "variante_dialectal", "fecha_publicacion", "fuente_original", "tipo", "sistema", "version"];
  return rows.slice(0, MAX_BATCH).map((r) => {
    const extra: Json = { titulo_cni: r[ti] ?? "" };
    for (const k of optional) if (at(k) >= 0) extra[k] = r[at(k)] ?? "";
    if (at("revisado_por_hablante") >= 0) extra["revisado_por_hablante"] = fold(r[at("revisado_por_hablante")] ?? "") === "true";
    return draftFrom(extra, (r[bi] ?? "").split(/\n\s*\n|\n|\s\|\s/));
  });
}

export async function parseNewsFile(file: File): Promise<NewsDraft[]> {
  const name = file.name.toLowerCase();
  if (file.size > MAX_FILE_BYTES) throw new Error("El archivo supera el límite de 2 MB.");
  const text = await file.text();
  if (name.endsWith(".json")) return parseJson(text);
  if (name.endsWith(".csv")) return parseCsv(text);
  if (name.endsWith(".txt")) return [parsePlainText(text)];
  throw new Error("Formato no admitido. Use .txt, .csv o .json.");
}

/** Plantilla del formato (celdas en asháninka VACÍAS: nunca se inventa texto). */
export const PLANTILLA_CSV =
  "titulo_cni,cuerpo_cni,variante_dialectal,fecha_publicacion,fuente_original,tipo,sistema,version,revisado_por_hablante\n" +
  ',,desconocida,,desconocido,traduccion_automatica,,,false\n';

/** Falta algo obligatorio antes de enviar. */
export function validar(d: NewsDraft): string | null {
  if (!d.titulo_cni.trim()) return "falta el título en asháninka";
  if (!d.paragraphs.some((p) => p.trim())) return "falta el cuerpo en asháninka";
  if (d.procedencia.revisado_por_hablante && d.procedencia.tipo === "traduccion_automatica")
    return "una traducción automática revisada por un hablante debe marcarse «automática revisada»";
  return null;
}

/** Borrador → cuerpo de `POST /api/news` (contrato §2). */
export function toPayload(d: NewsDraft): Record<string, unknown> {
  const p = d.procedencia;
  return {
    titulo_cni: d.titulo_cni.trim(),
    cuerpo_cni: d.paragraphs.map((x) => x.trim()).filter(Boolean).join("\n\n"),
    titulo_es: d.titulo_es.trim() || null,
    cuerpo_es: d.cuerpo_es.trim() || null,
    variante_dialectal: d.variante_dialectal.trim() || "desconocida",
    fecha_publicacion: d.fecha_publicacion || null,
    fuente_original: d.fuente_original.trim() || "desconocido",
    procedencia: {
      tipo: p.tipo,
      sistema: p.sistema.trim() || null,
      version: p.version.trim() || null,
      revisado_por_hablante: p.revisado_por_hablante,
      revisor_id: null,
    },
  };
}

// ------------------------------------------------------------------ publicación
export interface PublishResult {
  id: number;
  segmentos: number;
  conAudio: number;
  bloqueados: number;
}

export class PublishError extends Error {
  constructor(
    readonly paso: "crear" | "procesar" | "sintetizar",
    readonly status: number,
    detalle: string,
  ) {
    super(detalle);
    this.name = "PublishError";
  }
}

async function call(token: string, paso: PublishError["paso"], url: string, init: RequestInit, f: typeof fetch): Promise<unknown> {
  let r: Response;
  try {
    r = await f(url, { ...init, headers: { ...adminHeaders(token), "Content-Type": "application/json" } });
  } catch {
    throw new PublishError(paso, 0, "sin conexión con el servidor");
  }
  if (!r.ok) {
    let detalle = `HTTP ${r.status}`;
    try {
      const j = (await r.json()) as { detail?: unknown };
      if (typeof j.detail === "string") detalle = j.detail;
      else if (j.detail) detalle = JSON.stringify(j.detail).slice(0, 200);
    } catch {
      /* cuerpo no JSON */
    }
    throw new PublishError(paso, r.status, detalle);
  }
  return r.status === 204 ? null : await r.json();
}

/** Contrato §2 → `process` (pipeline de texto) → `build` (audio por lotes). */
export async function publicar(d: NewsDraft, token: string, f: typeof fetch = fetch): Promise<PublishResult> {
  const created = (await call(token, "crear", "/api/news", { method: "POST", body: JSON.stringify(toPayload(d)) }, f)) as { id: number };
  const id = created.id;
  const proc = (await call(token, "procesar", `/api/news/${id}/process`, { method: "POST" }, f)) as { segmentos: number };
  await call(token, "sintetizar", `/api/news/${id}/build`, { method: "POST" }, f);
  const segs = (await call(token, "procesar", `/api/news/${id}/segments`, { method: "GET" }, f)) as { tts_ready: boolean }[];
  const conAudio = segs.filter((s) => s.tts_ready).length;
  return { id, segmentos: proc.segmentos, conAudio, bloqueados: segs.length - conAudio };
}
