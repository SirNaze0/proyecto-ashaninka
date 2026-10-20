'use client'

import { useState } from 'react'
import {
  Check,
  CircleCheck,
  Languages,
  Loader2,
  Mic,
  Plus,
  Send,
  Trash2,
  TriangleAlert,
  Zap,
} from 'lucide-react'
import type { NewsItem, Segment } from '@/lib/news-data'
import { CATEGORIES, type ParsedNews } from '@/lib/parse-news-file'
import { cn } from '@/lib/utils'
import { FileImport } from './file-import'
import { Pill } from './pill'

type Sentence = {
  id: string
  source: string
  text_orig: string
  h1: string
  loanwords: string[]
  text: string
  useH1: boolean
  reviewed: boolean
}

const SAMPLE_PARAGRAPHS = [
  'El Ministerio de Salud inició una campaña de vacunación en doce comunidades del río Ene. Los promotores de salud viajarán en canoa durante tres semanas.',
  'La campaña incluye charlas sobre prevención del dengue y la anemia infantil. Las sesiones se realizan en asháninka y en castellano.',
  'Las familias pueden acercarse a la posta médica de Puerto Ocopa con su DNI. Los sabios comunales acompañarán cada visita.',
]

const STEPS = ['Redactar en castellano', 'Traducir al asháninka', 'Revisión por hablante nativo', 'Sintetizar y publicar']

export function RedaccionView({ onPublish }: { onPublish: (item: NewsItem) => void }) {
  const [title, setTitle] = useState('Campaña de vacunación llega a comunidades del río Ene')
  const [category, setCategory] = useState('Salud')
  const [paragraphs, setParagraphs] = useState(SAMPLE_PARAGRAPHS)
  const [result, setResult] = useState<Sentence[][] | null>(null)
  const [status, setStatus] = useState<'idle' | 'translating' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const sentences = result?.flat() ?? []
  const reviewedCount = sentences.filter((s) => s.reviewed).length
  const blockedCount = sentences.filter((s) => s.loanwords.length > 0 && !s.useH1).length
  const step = !result ? 1 : reviewedCount === 0 ? 2 : reviewedCount < sentences.length ? 3 : 4
  const synthSeconds = (sentences.length * 0.3).toFixed(1).replace('.', ',')

  function loadImported(news: ParsedNews) {
    setTitle(news.title)
    setCategory(news.category)
    setParagraphs(news.paragraphs)
    setResult(null)
    setStatus('idle')
    setErrorMessage('')
  }

  async function translate() {
    setStatus('translating')
    setErrorMessage('')
    try {
      const res = await fetch('/api/traducir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, category, paragraphs: paragraphs.filter((p) => p.trim()) }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? 'Error del traductor')
      setResult(
        (data.paragraphs as Omit<Sentence, 'text' | 'useH1' | 'reviewed'>[][]).map((p) =>
          p.map((s) => ({ ...s, text: s.text_orig, useH1: false, reviewed: false })),
        ),
      )
      setStatus('idle')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Error desconocido')
      setStatus('error')
    }
  }

  function updateSentence(id: string, patch: Partial<Sentence>) {
    setResult((prev) => prev?.map((p) => p.map((s) => (s.id === id ? { ...s, ...patch } : s))) ?? null)
  }

  function publish() {
    if (!result) return
    const segments: Segment[] = sentences.map((s) => {
      const blocked = s.loanwords.length > 0 && !s.useH1
      return {
        id: s.id,
        text: s.text,
        duration: Math.max(2.5, s.text.split(/\s+/).length * 0.55),
        blocked,
        blockedNote: blocked ? 'Segmento de texto: préstamos sin adaptar, sin voz' : undefined,
        loanwords: blocked ? s.loanwords : undefined,
      }
    })
    const id = `red:${Date.now().toString().slice(-4)}`
    onPublish({
      id,
      titleEs: title,
      titleCni: segments[0]?.text.split(',')[0].replace(/\.$/, '') ?? title,
      summaryEs: paragraphs[0] ?? '',
      snippetCni: segments[0]?.text ?? '',
      category,
      region: 'Sala de Redacción',
      dialect: 'Variante mixta',
      provenance: 'redacción local',
      image: '/images/asamblea.png',
      imageAlt: 'Asamblea comunal asháninka.',
      audioReady: true,
      segments,
    })
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <h2 className="font-serif text-3xl font-bold">Sala de Redacción y Traducción</h2>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Flujo editorial">
          {STEPS.map((label, i) => {
            const n = i + 1
            const done = n < step
            const current = n === step
            return (
              <li
                key={label}
                aria-current={current ? 'step' : undefined}
                className={cn(
                  'flex min-h-14 items-center gap-3 rounded-lg border px-4 py-2 text-sm font-semibold',
                  current && 'border-primary bg-accent text-accent-foreground',
                  done && 'border-success-foreground/30 bg-success text-success-foreground',
                  !current && !done && 'border-border bg-card text-muted-foreground',
                )}
              >
                <span
                  className={cn(
                    'flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold',
                    current ? 'bg-primary text-primary-foreground' : done ? 'bg-success-foreground text-success' : 'bg-muted',
                  )}
                >
                  {done ? <Check className="size-4" aria-hidden="true" /> : n}
                </span>
                {label}
              </li>
            )
          })}
        </ol>
      </header>

      <FileImport onLoad={loadImported} />

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <section aria-labelledby="col-es" className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 id="col-es" className="text-sm font-bold uppercase tracking-[0.15em]">
              Castellano · Original
            </h3>
            <Pill variant="outline">ES</Pill>
          </div>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Título
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={160}
              className="min-h-11 rounded-md border border-input bg-background px-3 font-serif text-lg font-normal focus-visible:outline-2 focus-visible:outline-ring"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Categoría
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="min-h-11 rounded-md border border-input bg-background px-3 font-normal"
            >
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          {paragraphs.map((p, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor={`parrafo-${i}`} className="text-sm font-semibold">
                  Párrafo {i + 1}
                </label>
                {paragraphs.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setParagraphs(paragraphs.filter((_, j) => j !== i))}
                    aria-label={`Eliminar párrafo ${i + 1}`}
                    className="flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </button>
                )}
              </div>
              <textarea
                id={`parrafo-${i}`}
                value={p}
                maxLength={2000}
                rows={3}
                onChange={(e) => setParagraphs(paragraphs.map((x, j) => (j === i ? e.target.value : x)))}
                className="rounded-md border border-input bg-background px-3 py-2 leading-relaxed focus-visible:outline-2 focus-visible:outline-ring"
              />
            </div>
          ))}
          <div className="flex flex-wrap gap-3 pt-2">
            {paragraphs.length < 12 && (
              <button
                type="button"
                onClick={() => setParagraphs([...paragraphs, ''])}
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-semibold hover:bg-muted"
              >
                <Plus className="size-4" aria-hidden="true" />
                Añadir párrafo
              </button>
            )}
            <button
              type="button"
              onClick={translate}
              disabled={status === 'translating' || !paragraphs.some((p) => p.trim())}
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-bold text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status === 'translating' ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Zap className="size-4" aria-hidden="true" />
              )}
              {status === 'translating' ? 'Traduciendo…' : 'Traducir al Asháninka'}
            </button>
          </div>
          {status === 'error' && (
            <p role="alert" className="text-sm font-semibold text-destructive">
              {errorMessage}
            </p>
          )}
        </section>

        <section aria-labelledby="col-cni" className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 id="col-cni" className="text-sm font-bold uppercase tracking-[0.15em]">
              Asháninka · Traducción
            </h3>
            <Pill variant="outline">CNI</Pill>
          </div>

          {!result ? (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-input px-6 py-16 text-center text-muted-foreground">
              <Languages className="size-8" aria-hidden="true" />
              <p className="max-w-xs">
                La traducción alineada por oración aparecerá aquí para su revisión por un hablante nativo.
              </p>
            </div>
          ) : (
            <>
              <p aria-live="polite" className="text-sm text-muted-foreground">
                {reviewedCount} de {sentences.length} oraciones revisadas
                {blockedCount > 0 && ` · ${blockedCount} se publicarán solo como texto`}
              </p>
              <ol className="flex flex-col gap-4">
                {sentences.map((s, i) => (
                  <SentenceRow key={s.id} index={i} sentence={s} onChange={(patch) => updateSentence(s.id, patch)} />
                ))}
              </ol>
            </>
          )}
        </section>
      </div>

      <footer className="flex flex-col gap-4 rounded-xl border-2 border-primary bg-card p-5 md:flex-row md:items-center md:justify-between md:p-6">
        <div className="flex items-start gap-3">
          <Mic className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <p className="font-semibold">Generación por lotes · Voz MMS</p>
            <p className="text-sm text-muted-foreground">
              {result
                ? `Síntesis estimada: ${synthSeconds} s para ${sentences.length} oraciones en el servidor.`
                : 'Traduzca la noticia para estimar el tiempo de síntesis.'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={publish}
          disabled={!result}
          className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-terracotta px-6 text-base font-bold text-terracotta-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="size-4" aria-hidden="true" />
          Publicar en Noticiero y Estudio
        </button>
      </footer>
    </div>
  )
}

function SentenceRow({
  index,
  sentence: s,
  onChange,
}: {
  index: number
  sentence: Sentence
  onChange: (patch: Partial<Sentence>) => void
}) {
  const blocked = s.loanwords.length > 0 && !s.useH1
  const fieldId = `oracion-${s.id}`

  return (
    <li className={cn('flex flex-col gap-3 rounded-lg border p-4', s.reviewed ? 'border-success-foreground/40' : 'border-border')}>
      <p className="text-sm text-muted-foreground">
        <span className="font-mono font-bold text-foreground">{index + 1}.</span> {s.source}
      </p>
      <label htmlFor={fieldId} className="sr-only">
        Traducción de la oración {index + 1}
      </label>
      <textarea
        id={fieldId}
        lang="cni"
        rows={2}
        value={s.text}
        onChange={(e) => onChange({ text: e.target.value, reviewed: false })}
        className="rounded-md border border-input bg-background px-3 py-2 font-serif text-lg leading-relaxed focus-visible:outline-2 focus-visible:outline-ring"
      />
      {s.loanwords.length > 0 && (
        <div className="flex flex-col gap-2 rounded-md bg-muted p-3 text-sm">
          <p>
            <span className="font-semibold">Adaptación fonológica (H1):</span>{' '}
            <span lang="cni" className="font-serif italic">
              {s.h1}
            </span>
          </p>
          <label className="flex min-h-11 cursor-pointer items-center gap-2 font-semibold">
            <input
              type="checkbox"
              checked={s.useH1}
              onChange={(e) => onChange({ useH1: e.target.checked, text: e.target.checked ? s.h1 : s.text_orig, reviewed: false })}
              className="size-5 accent-[var(--primary)]"
            />
            Usar adaptación H1 ({s.loanwords.join(', ')})
          </label>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {blocked ? (
          <Pill variant="warning">
            <TriangleAlert className="size-3.5" aria-hidden="true" />
            Contiene préstamos sin adaptar
          </Pill>
        ) : (
          <Pill variant="success">
            <CircleCheck className="size-3.5" aria-hidden="true" />
            Listo para voz MMS
          </Pill>
        )}
        <button
          type="button"
          aria-pressed={s.reviewed}
          onClick={() => onChange({ reviewed: !s.reviewed })}
          className={cn(
            'inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors',
            s.reviewed ? 'border-transparent bg-primary text-primary-foreground' : 'border-input bg-background hover:bg-muted',
          )}
        >
          <Check className="size-4" aria-hidden="true" />
          {s.reviewed ? 'Revisada' : 'Marcar como revisada'}
        </button>
      </div>
    </li>
  )
}
