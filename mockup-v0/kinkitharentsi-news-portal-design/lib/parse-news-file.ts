export const CATEGORIES = ['Salud', 'Educación', 'Clima', 'Comunidad', 'Economía'] as const

export type ParsedNews = {
  title: string
  category: string
  paragraphs: string[]
}

export const ACCEPTED_EXTENSIONS = ['.txt', '.csv', '.json', '.docx'] as const
export const MAX_FILE_BYTES = 2 * 1024 * 1024
const MAX_PARAGRAPHS = 12
const MAX_PARAGRAPH_CHARS = 2000
const MAX_TITLE_CHARS = 160
const MAX_BATCH = 50

const KEYWORDS: Record<string, string[]> = {
  Salud: ['salud', 'vacuna', 'minsa', 'posta', 'dengue', 'anemia', 'médic', 'hospital'],
  Educación: ['escuela', 'educaci', 'docente', 'alumn', 'colegio', 'estudiante', 'minedu'],
  Clima: ['lluvia', 'río', 'clima', 'senamhi', 'inundaci', 'friaje', 'sequía', 'creciente'],
  Economía: ['cacao', 'café', 'precio', 'mercado', 'cosecha', 'venta', 'cooperativa', 'econom'],
  Comunidad: ['asamblea', 'comunal', 'jefe', 'territorio', 'federación', 'comunidad'],
}

const fold = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()

function normalizeCategory(raw: string | undefined, fallbackText: string): string {
  if (raw) {
    const match = CATEGORIES.find((c) => fold(c) === fold(raw))
    if (match) return match
  }
  const haystack = fold(fallbackText)
  let best: string = 'Comunidad'
  let bestScore = 0
  for (const [cat, words] of Object.entries(KEYWORDS)) {
    const score = words.reduce((n, w) => n + (haystack.includes(fold(w)) ? 1 : 0), 0)
    if (score > bestScore) {
      best = cat
      bestScore = score
    }
  }
  return best
}

function finalize(title: string, rawCategory: string | undefined, paragraphs: string[]): ParsedNews {
  const clean = paragraphs
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(0, MAX_PARAGRAPHS)
    .map((p) => p.slice(0, MAX_PARAGRAPH_CHARS))
  const cleanTitle = title.replace(/\s+/g, ' ').trim().slice(0, MAX_TITLE_CHARS)
  return {
    title: cleanTitle || 'Noticia sin título',
    category: normalizeCategory(rawCategory, `${cleanTitle} ${clean.join(' ')}`),
    paragraphs: clean.length ? clean : [''],
  }
}

const TITLE_RE = /^(t[ií]tulo|title)\s*:\s*/i
const CATEGORY_RE = /^(categor[ií]a|category|secci[oó]n)\s*:\s*/i

export function parsePlainText(text: string): ParsedNews {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  let title = ''
  let category: string | undefined
  const body: string[] = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!title && TITLE_RE.test(trimmed)) title = trimmed.replace(TITLE_RE, '')
    else if (!category && CATEGORY_RE.test(trimmed)) category = trimmed.replace(CATEGORY_RE, '')
    else body.push(line)
  }
  let bodyText = body.join('\n').trim()
  if (!title) {
    const [first, ...rest] = bodyText.split('\n')
    title = first ?? ''
    bodyText = rest.join('\n').trim()
  }
  const blocks = bodyText.split(/\n\s*\n/)
  const paragraphs = blocks.length > 1 ? blocks : bodyText.split('\n')
  return finalize(title, category, paragraphs)
}

type JsonNews = Record<string, unknown>

function pick(obj: JsonNews, keys: string[]): unknown {
  for (const k of keys) if (k in obj) return obj[k]
  return undefined
}

function fromJsonObject(obj: JsonNews): ParsedNews {
  const title = String(pick(obj, ['title', 'titulo', 'título', 'titleEs']) ?? '')
  const category = pick(obj, ['category', 'categoria', 'categoría'])
  const rawParagraphs = pick(obj, ['paragraphs', 'parrafos', 'párrafos'])
  const body = pick(obj, ['body', 'cuerpo', 'texto', 'text', 'contenido'])
  const paragraphs = Array.isArray(rawParagraphs)
    ? rawParagraphs.map(String)
    : typeof body === 'string'
      ? body.split(/\n\s*\n|\n/)
      : []
  return finalize(title, typeof category === 'string' ? category : undefined, paragraphs)
}

export function parseJson(text: string): ParsedNews[] {
  const data = JSON.parse(text) as unknown
  const list = Array.isArray(data)
    ? data
    : data && typeof data === 'object' && Array.isArray((data as JsonNews).noticias)
      ? ((data as JsonNews).noticias as unknown[])
      : [data]
  return list
    .filter((x): x is JsonNews => !!x && typeof x === 'object')
    .slice(0, MAX_BATCH)
    .map(fromJsonObject)
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  const delimiter = text.split('\n')[0].includes(';') && !text.split('\n')[0].includes(',') ? ';' : ','
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"'
        i++
      } else if (ch === '"') quoted = false
      else field += ch
    } else if (ch === '"') quoted = true
    else if (ch === delimiter) {
      row.push(field)
      field = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(field)
      if (row.some((c) => c.trim())) rows.push(row)
      row = []
      field = ''
    } else field += ch
  }
  row.push(field)
  if (row.some((c) => c.trim())) rows.push(row)
  return rows
}

export function parseCsv(text: string): ParsedNews[] {
  const [header, ...rows] = parseCsvRows(text.replace(/^\uFEFF/, ''))
  if (!header) return []
  const cols = header.map(fold)
  const idx = (names: string[]) => cols.findIndex((c) => names.includes(c))
  const titleIdx = idx(['titulo', 'title'])
  const catIdx = idx(['categoria', 'category', 'seccion'])
  const bodyIdx = idx(['cuerpo', 'body', 'texto', 'text', 'contenido', 'parrafos'])
  if (titleIdx === -1 || bodyIdx === -1) {
    throw new Error('El CSV debe tener columnas "titulo" y "cuerpo" (y opcionalmente "categoria").')
  }
  return rows.slice(0, MAX_BATCH).map((r) =>
    finalize(r[titleIdx] ?? '', catIdx >= 0 ? r[catIdx] : undefined, (r[bodyIdx] ?? '').split(/\n\s*\n|\n|\s\|\s/)),
  )
}

export async function parseNewsFile(file: File): Promise<ParsedNews[]> {
  const name = file.name.toLowerCase()
  if (file.size > MAX_FILE_BYTES) throw new Error('El archivo supera el límite de 2 MB.')
  if (name.endsWith('.docx')) {
    const mammoth = await import('mammoth')
    const { value } = await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() })
    return [parsePlainText(value)]
  }
  const text = await file.text()
  if (name.endsWith('.json')) return parseJson(text)
  if (name.endsWith('.csv')) return parseCsv(text)
  if (name.endsWith('.txt') || name.endsWith('.md')) return [parsePlainText(text)]
  throw new Error('Formato no admitido. Use .txt, .csv, .json o .docx.')
}

export const DEMO_FILE_NAME = 'noticia_minsa.txt'
export const DEMO_FILE_CONTENT = `Título: MINSA refuerza atención de anemia infantil en comunidades del río Tambo
Categoría: Salud

El Ministerio de Salud enviará brigadas médicas a nueve comunidades asháninka del río Tambo. Las brigadas atenderán a niños menores de cinco años.

Los promotores de salud entregarán suplementos de hierro y realizarán pruebas de hemoglobina. Las madres recibirán orientación sobre alimentación con pescado y sangrecita.

La atención será gratuita en la posta de Poyeni del 4 al 15 de noviembre. Se recomienda llevar el DNI y la tarjeta de control del niño.`
