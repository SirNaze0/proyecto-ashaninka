'use client'

import { useState } from 'react'
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  Columns2,
  EyeOff,
  FileText,
  MonitorPlay,
  Scale,
  TriangleAlert,
} from 'lucide-react'
import { CONDITIONS, type Condition, type NewsItem } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import { AudioDeck } from './audio-deck'
import { LiveCaptionBar } from './live-caption-bar'
import { Pill } from './pill'
import { StudioMonitor } from './studio-monitor'
import { Teleprompter } from './teleprompter'
import { type Playback, usePlayback } from './use-playback'

type Layout = 'centrado' | 'paralela'

const LAYOUTS: { value: Layout; label: string; icon: typeof MonitorPlay }[] = [
  { value: 'centrado', label: 'Vista Estudio Centrado (TV)', icon: MonitorPlay },
  { value: 'paralela', label: 'Vista Lectura Paralela', icon: Columns2 },
]

type ViewProps = {
  item: NewsItem
  condition: Condition
  isSaved: boolean
  onToggleSaved: () => void
  onBack: () => void
}

export function EstudioView(props: ViewProps) {
  const { item, condition, onBack } = props
  const [layout, setLayout] = useState<Layout>('centrado')
  const playback = usePlayback(item.segments, item.id === 'dev:34' ? 0.9 : 0)
  const conditionLabel = CONDITIONS.find((c) => c.value === condition)!.label.replace(' — ', ' · ')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Volver a la portada
        </button>
        <div className="flex flex-wrap items-center gap-3">
          <Pill variant="primary">{conditionLabel}</Pill>
          <div role="radiogroup" aria-label="Diseño del estudio" className="flex rounded-full border border-input bg-muted p-1">
            {LAYOUTS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={layout === value}
                onClick={() => setLayout(value)}
                className={cn(
                  'inline-flex min-h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors',
                  layout === value ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {layout === 'centrado' ? (
        <CenteredStudio {...props} playback={playback} />
      ) : (
        <ParallelReading {...props} playback={playback} />
      )}
    </div>
  )
}

function CenteredStudio({ item, condition, isSaved, onToggleSaved, playback }: ViewProps & { playback: Playback }) {
  const hasAudio = condition !== 'C1'
  const hasAvatar = condition === 'C3' || condition === 'C4'
  const hasText = condition !== 'C3'
  const speaking = playback.playing && !playback.current?.blocked

  return (
    <article aria-labelledby="noticia-titulo" className="mx-auto flex w-full max-w-[860px] flex-col gap-4">
      <header className="flex flex-col gap-1 text-center">
        <p className="text-xs font-bold uppercase tracking-[0.15em] text-terracotta">
          {item.category} · {item.region}
        </p>
        <h2 id="noticia-titulo" className="font-serif text-2xl font-bold leading-tight text-balance md:text-3xl">
          {item.titleCni}
        </h2>
        <p className="text-base text-muted-foreground text-pretty">{item.titleEs}</p>
      </header>

      <EthicsCallout item={item} defaultOpen={false} />

      {hasAudio ? (
        <section
          aria-label="Estudio de televisión virtual"
          className="overflow-hidden rounded-2xl border-4 border-studio bg-studio shadow-2xl ring-1 ring-black/40"
        >
          <StudioMonitor item={item} speaking={speaking} showAvatar={hasAvatar} stage />
          {hasText ? (
            <LiveCaptionBar
              segment={playback.current}
              index={playback.index}
              total={item.segments.length}
              activeWord={playback.activeWord}
            />
          ) : (
            <p className="flex items-center justify-center gap-2 border-t-2 border-terracotta bg-[#0b1110] px-5 py-4 text-sm text-[#f7f4ef]/75">
              <EyeOff className="size-4" aria-hidden="true" />
              Teleprompter oculto en la condición C3 (voz y avatar)
            </p>
          )}
        </section>
      ) : (
        <C1Notice />
      )}

      {hasAudio && (
        <AudioDeck
          playback={playback}
          segmentCount={item.segments.length}
          isSaved={isSaved}
          onToggleSaved={onToggleSaved}
        />
      )}

      {hasText && (
        <details className="group rounded-xl border border-border bg-card" open={!hasAudio}>
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 text-sm font-bold [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-2">
              <FileText className="size-4 text-primary" aria-hidden="true" />
              Transcripción completa en asháninka
            </span>
            <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <div className="border-t border-border px-5 py-5 md:px-8">
            <Teleprompter
              segments={item.segments}
              activeIndex={playback.index}
              activeWord={hasAudio ? playback.activeWord : -1}
              onSeek={playback.seek}
            />
          </div>
        </details>
      )}
    </article>
  )
}

function ParallelReading({
  item,
  condition,
  isSaved,
  onToggleSaved,
  playback,
}: ViewProps & { playback: Playback }) {
  const hasAudio = condition !== 'C1'
  const hasAvatar = condition === 'C3' || condition === 'C4'
  const hasText = condition !== 'C3'
  const speaking = playback.playing && !playback.current?.blocked

  return (
    <div className="grid gap-8 lg:grid-cols-[2fr_3fr] lg:items-start">
      {hasAudio ? (
        <aside aria-label="Estudio de televisión y consola de audio" className="flex flex-col gap-5 lg:sticky lg:top-20">
          <StudioMonitor item={item} speaking={speaking} showAvatar={hasAvatar} />
          <AudioDeck
            playback={playback}
            segmentCount={item.segments.length}
            isSaved={isSaved}
            onToggleSaved={onToggleSaved}
          />
        </aside>
      ) : (
        <C1Notice />
      )}

      <article aria-labelledby="noticia-titulo" className="flex flex-col gap-6">
        <header className="flex flex-col gap-4">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-terracotta">
            {item.category} · {item.region}
          </p>
          <h2 id="noticia-titulo" className="font-serif text-3xl font-bold leading-tight text-balance md:text-4xl">
            Noticia {item.id} — {item.titleCni}
          </h2>
          <p className="text-lg leading-relaxed text-muted-foreground text-pretty">{item.titleEs}</p>
        </header>

        <EthicsCallout item={item} defaultOpen />

        <section aria-label="Teleprompter sincronizado" className="rounded-xl border border-border bg-card p-5 md:p-8">
          <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-3">
            <h2 className="text-sm font-bold uppercase tracking-[0.15em]">Teleprompter · Texto en asháninka</h2>
            {hasAudio && hasText && (
              <span className="text-xs text-muted-foreground">Toque una oración para escucharla</span>
            )}
          </div>
          {hasText ? (
            <Teleprompter
              segments={item.segments}
              activeIndex={playback.index}
              activeWord={hasAudio ? playback.activeWord : -1}
              onSeek={playback.seek}
            />
          ) : (
            <div className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
              <EyeOff className="size-8" aria-hidden="true" />
              <p className="max-w-sm">
                Texto oculto en la condición C3 (voz y avatar). La noticia se transmite solo por audio y
                presentadora virtual.
              </p>
            </div>
          )}
        </section>
      </article>
    </div>
  )
}

function C1Notice() {
  return (
    <aside className="flex flex-col gap-3 rounded-xl border border-dashed border-input bg-card p-6 lg:sticky lg:top-20">
      <FileText className="size-8 text-primary" aria-hidden="true" />
      <h2 className="font-serif text-xl font-bold">Condición C1 · Solo texto</h2>
      <p className="text-muted-foreground">
        En esta condición experimental la noticia se presenta únicamente como texto, sin voz ni
        presentadora virtual. Cambie el modo de presentación en la cabecera para activar el estudio.
      </p>
    </aside>
  )
}

function EthicsCallout({ item, defaultOpen }: { item: NewsItem; defaultOpen: boolean }) {
  return (
    <details className="group rounded-xl border border-border bg-card open:shadow-sm" open={defaultOpen}>
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 text-sm font-bold [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-2">
          <Scale className="size-4 text-primary" aria-hidden="true" />
          Aviso ético y de licencia
        </span>
        <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="flex flex-col gap-3 border-t border-border px-5 py-4">
        <div className="flex flex-wrap gap-2">
          <Pill variant="info">
            <Bot className="size-3.5" aria-hidden="true" />
            Voz y presentadora sintéticas generadas por IA
          </Pill>
          <Pill variant="outline">Licencia: CC-BY-NC-4.0 (Uso no comercial)</Pill>
          <Pill variant="outline">Variante: {item.dialect.toLowerCase().replace('variante ', '')}</Pill>
          {item.pilot && (
            <Pill variant="warning">
              <TriangleAlert className="size-3.5" aria-hidden="true" />
              Pseudo-noticia del corpus: modo piloto
            </Pill>
          )}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          La presentadora y su voz no corresponden a una persona real. Los textos provienen del corpus
          AmericasNLP y son revisados por hablantes nativos antes de su difusión comunitaria.
        </p>
      </div>
    </details>
  )
}
