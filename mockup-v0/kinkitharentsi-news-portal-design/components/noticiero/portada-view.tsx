'use client'

import Image from 'next/image'
import { Clock, CloudDownload, MonitorPlay, Volume2, VolumeX } from 'lucide-react'
import {
  FEATURED_ID,
  GRID_IDS,
  formatTime,
  totalDuration,
  type NewsItem,
} from '@/lib/news-data'
import { Pill } from './pill'

type Props = {
  news: NewsItem[]
  published: NewsItem[]
  saved: Set<string>
  onOpen: (id: string) => void
  onToggleSaved: (id: string) => void
}

export function PortadaView({ news, published, saved, onOpen, onToggleSaved }: Props) {
  const featured = news.find((n) => n.id === FEATURED_ID)!
  const grid = [
    ...published,
    ...GRID_IDS.map((id) => news.find((n) => n.id === id)).filter((n): n is NewsItem => !!n),
  ]

  return (
    <div className="flex flex-col gap-10">
      <FeaturedCard item={featured} isSaved={saved.has(featured.id)} onOpen={onOpen} />

      <section aria-labelledby="mas-noticias">
        <div className="mb-5 flex items-end justify-between gap-4 border-b-2 border-foreground pb-2">
          <h2 id="mas-noticias" className="font-serif text-2xl font-bold">
            Más noticias del corpus
          </h2>
          <p className="text-sm text-muted-foreground">{grid.length} noticias disponibles</p>
        </div>
        <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {grid.map((item) => (
            <li key={item.id}>
              <NewsCard
                item={item}
                isSaved={saved.has(item.id)}
                onOpen={onOpen}
                onToggleSaved={onToggleSaved}
              />
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function FeaturedCard({
  item,
  isSaved,
  onOpen,
}: {
  item: NewsItem
  isSaved: boolean
  onOpen: (id: string) => void
}) {
  return (
    <article
      aria-labelledby="destacado-titulo"
      className="overflow-hidden rounded-xl border border-border bg-card shadow-sm"
    >
      <div className="flex items-center gap-3 bg-terracotta px-5 py-2 text-terracotta-foreground">
        <span className="text-xs font-black uppercase tracking-[0.2em]">Último minuto</span>
        <span aria-hidden="true">/</span>
        <span className="text-xs font-semibold uppercase tracking-[0.2em]">Destacado</span>
      </div>
      <div className="grid lg:grid-cols-[1.15fr_1fr]">
        <div className="relative aspect-[16/10] lg:aspect-auto lg:min-h-[420px]">
          <Image
            src={item.image || '/placeholder.svg'}
            alt={item.imageAlt}
            fill
            priority
            sizes="(min-width: 1024px) 55vw, 100vw"
            className="object-cover"
          />
        </div>
        <div className="flex flex-col gap-5 p-6 md:p-8">
          <div className="flex flex-wrap gap-2">
            <Pill variant="primary" className="uppercase">
              {item.category} · {item.region}
            </Pill>
            <Pill variant="outline">Variante: {item.dialect}</Pill>
            <Pill variant="neutral">
              <Clock className="size-3.5" aria-hidden="true" />
              {item.durationLabel ?? formatTime(totalDuration(item.segments))}
            </Pill>
            {isSaved && (
              <Pill variant="success">
                <CloudDownload className="size-3.5" aria-hidden="true" />
                Guardada para uso sin conexión
              </Pill>
            )}
          </div>
          <h2
            id="destacado-titulo"
            className="font-serif text-3xl font-bold leading-tight text-balance md:text-4xl"
          >
            {item.titleEs}
          </h2>
          <blockquote
            lang="cni"
            className="border-l-4 border-terracotta pl-4 font-serif text-lg italic leading-relaxed text-muted-foreground"
          >
            <span className="sr-only">Avance en asháninka: </span>
            {item.titleCni}. {item.snippetCni}
          </blockquote>
          <p className="leading-relaxed text-pretty">{item.summaryEs}</p>
          <div className="mt-auto pt-2">
            <button
              type="button"
              onClick={() => onOpen(item.id)}
              className="inline-flex min-h-12 items-center gap-2 rounded-md bg-primary px-6 text-base font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90"
            >
              <MonitorPlay className="size-5" aria-hidden="true" />
              Abrir en Estudio Virtual (C4)
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}

function NewsCard({
  item,
  isSaved,
  onOpen,
  onToggleSaved,
}: {
  item: NewsItem
  isSaved: boolean
  onOpen: (id: string) => void
  onToggleSaved: (id: string) => void
}) {
  const titleId = `titulo-${item.id.replace(':', '-')}`
  return (
    <article
      aria-labelledby={titleId}
      className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card"
    >
      <div className="relative aspect-[16/10]">
        <Image
          src={item.image || '/placeholder.svg'}
          alt={item.imageAlt}
          fill
          sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
          className="object-cover"
        />
        <span className="absolute left-3 top-3 rounded-sm bg-studio px-2 py-1 font-mono text-xs font-bold text-studio-foreground">
          {item.id}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <p className="text-xs font-bold uppercase tracking-[0.15em] text-terracotta">
          {item.category} · {item.region}
        </p>
        <h3 id={titleId} className="font-serif text-xl font-bold leading-snug text-balance">
          {item.titleEs}
        </h3>
        <p lang="cni" className="font-serif italic text-muted-foreground">
          {item.titleCni}
        </p>
        <div className="flex flex-wrap gap-2">
          <Pill variant="outline">{item.provenance}</Pill>
          {item.audioReady ? (
            <Pill variant="success">
              <Volume2 className="size-3.5" aria-hidden="true" />
              Audio por lotes listo
            </Pill>
          ) : (
            <Pill variant="warning">
              <VolumeX className="size-3.5" aria-hidden="true" />
              Sin audio / Solo texto
            </Pill>
          )}
          {item.pilot && <Pill variant="warning">Modo piloto</Pill>}
        </div>
        <div className="mt-auto flex flex-wrap gap-2 pt-3">
          <button
            type="button"
            onClick={() => onOpen(item.id)}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <MonitorPlay className="size-4" aria-hidden="true" />
            {item.audioReady ? 'Ver en estudio' : 'Leer en estudio'}
          </button>
          <button
            type="button"
            onClick={() => onToggleSaved(item.id)}
            aria-pressed={isSaved}
            aria-label={isSaved ? `Quitar ${item.id} de sin conexión` : `Guardar ${item.id} sin conexión`}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-muted aria-pressed:border-primary aria-pressed:bg-accent aria-pressed:text-accent-foreground"
          >
            <CloudDownload className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </article>
  )
}
