'use client'

import { Check, CloudDownload, Pause, Play, RotateCcw, SkipForward } from 'lucide-react'
import { formatTime } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import type { Playback } from './use-playback'

const SPEEDS = [
  { value: 0.75, label: '0,75×' },
  { value: 1, label: '1×' },
  { value: 1.25, label: '1,25×' },
]

export function AudioDeck({
  playback,
  segmentCount,
  isSaved,
  onToggleSaved,
}: {
  playback: Playback
  segmentCount: number
  isSaved: boolean
  onToggleSaved: () => void
}) {
  const { playing, speed, setSpeed, index, position, total, toggle, repeat, next } = playback
  const pct = total > 0 ? (position / total) * 100 : 0

  return (
    <section
      aria-label="Consola de audio"
      className="flex flex-col gap-5 rounded-xl border border-border bg-card p-5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          className="inline-flex h-14 min-w-36 items-center justify-center gap-2 rounded-full bg-primary px-6 text-base font-bold text-primary-foreground shadow-sm transition-opacity hover:opacity-90"
        >
          {playing ? (
            <Pause className="size-5 fill-current" aria-hidden="true" />
          ) : (
            <Play className="size-5 fill-current" aria-hidden="true" />
          )}
          {playing ? 'Pausar' : 'Reproducir'}
        </button>
        <button
          type="button"
          onClick={repeat}
          className="inline-flex min-h-11 items-center gap-2 rounded-full border border-input bg-background px-4 text-sm font-semibold transition-colors hover:bg-muted"
        >
          <RotateCcw className="size-4" aria-hidden="true" />
          Repetir párrafo
        </button>
        <button
          type="button"
          onClick={next}
          disabled={index >= segmentCount - 1}
          className="inline-flex min-h-11 items-center gap-2 rounded-full border border-input bg-background px-4 text-sm font-semibold transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <SkipForward className="size-4" aria-hidden="true" />
          Párrafo siguiente
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label="Velocidad de reproducción" className="flex rounded-full bg-muted p-1">
          {SPEEDS.map((s) => (
            <button
              key={s.value}
              type="button"
              role="radio"
              aria-checked={speed === s.value}
              onClick={() => setSpeed(s.value)}
              className={cn(
                'min-h-11 min-w-14 rounded-full px-3 text-sm font-bold transition-colors',
                speed === s.value
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <span className="text-xs font-medium text-muted-foreground">Voz sintética MMS · CNI</span>
      </div>

      <div className="flex flex-col gap-2">
        <div
          role="progressbar"
          aria-label="Progreso de la noticia"
          aria-valuemin={0}
          aria-valuemax={Math.round(total)}
          aria-valuenow={Math.round(position)}
          aria-valuetext={`${formatTime(position)} de ${formatTime(total)}`}
          className="relative h-2.5 overflow-hidden rounded-full bg-muted"
        >
          <div className="absolute inset-y-0 left-0 rounded-full bg-terracotta" style={{ width: `${pct}%` }} />
        </div>
        <p className="flex justify-between text-sm font-medium tabular-nums">
          <span>
            Oración {index + 1} de {segmentCount}
          </span>
          <span className="text-muted-foreground">
            {formatTime(position)} / {formatTime(total)}
          </span>
        </p>
      </div>

      <button
        type="button"
        onClick={onToggleSaved}
        aria-pressed={isSaved}
        className={cn(
          'inline-flex min-h-12 items-center justify-center gap-2 rounded-md border-2 px-4 text-sm font-semibold transition-colors',
          isSaved
            ? 'border-success-foreground/40 bg-success text-success-foreground'
            : 'border-primary text-primary hover:bg-accent',
        )}
      >
        {isSaved ? (
          <Check className="size-4" aria-hidden="true" />
        ) : (
          <CloudDownload className="size-4" aria-hidden="true" />
        )}
        {isSaved ? 'Guardada para escuchar sin conexión' : 'Guardar para escuchar sin conexión'}
      </button>
    </section>
  )
}
