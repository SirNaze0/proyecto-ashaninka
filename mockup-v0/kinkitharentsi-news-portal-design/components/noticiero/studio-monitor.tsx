import Image from 'next/image'
import { AudioLines } from 'lucide-react'
import type { NewsItem } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import { Pill } from './pill'

const BARS = [0.4, 0.8, 0.55, 1, 0.7, 0.45, 0.9, 0.6, 0.35, 0.75, 0.5, 0.85]

export function Waveform({ active, className }: { active: boolean; className?: string }) {
  return (
    <div aria-hidden="true" className={cn('flex h-8 items-center gap-1', className)}>
      {BARS.map((h, i) => (
        <span
          key={i}
          className={cn('w-1 rounded-full bg-highlight', active ? 'wave-bar' : 'opacity-50')}
          style={{
            height: `${h * 100}%`,
            animationDelay: `${i * 0.08}s`,
            transform: active ? undefined : 'scaleY(0.25)',
          }}
        />
      ))}
    </div>
  )
}

export function StudioMonitor({
  item,
  speaking,
  showAvatar,
  stage = false,
}: {
  item: NewsItem
  speaking: boolean
  showAvatar: boolean
  stage?: boolean
}) {
  return (
    <figure
      className={cn(
        'relative overflow-hidden bg-studio',
        stage ? 'aspect-[16/8]' : 'aspect-video rounded-xl border-4 border-studio shadow-xl ring-1 ring-black/40',
      )}
      aria-label="Monitor del estudio de televisión virtual"
    >
      {showAvatar ? (
        <Image
          src="/images/presentadora-ia.png"
          alt="Presentadora virtual asháninka generada por IA, con blazer verde, en el set del noticiero."
          fill
          priority
          sizes={stage ? '(min-width: 900px) 860px, 100vw' : '(min-width: 1024px) 40vw, 100vw'}
          className="object-cover object-[50%_30%]"
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[radial-gradient(circle_at_50%_40%,#1d3a30,#080b0e_70%)] text-studio-foreground">
          <AudioLines className="size-12 text-highlight" aria-hidden="true" />
          <p className="text-sm font-semibold">Modo solo voz · avatar desactivado</p>
        </div>
      )}

      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,0.45)_0%,transparent_30%,transparent_60%,rgba(0,0,0,0.7)_100%)]"
      />

      <div className="absolute left-3 top-3 flex flex-wrap gap-2">
        <Pill variant="live" className="uppercase">
          <span className="size-2 animate-pulse rounded-full bg-white" aria-hidden="true" />
          En aire · 60 FPS
        </Pill>
        <Pill variant="studio" className="font-mono">
          Presentadora IA (CNI) · WebGL
        </Pill>
      </div>

      <div className="absolute bottom-16 right-4 md:bottom-20">
        <Waveform active={speaking} />
        <span className="sr-only">{speaking ? 'La presentadora está hablando' : 'Audio en pausa'}</span>
      </div>

      <figcaption className="absolute inset-x-0 bottom-0 flex items-stretch text-white">
        <span className="flex items-center bg-terracotta px-3 py-2 text-[11px] font-black uppercase tracking-widest md:text-xs">
          Noticia en asháninka <span aria-hidden="true" className="mx-2 opacity-70">|</span>
          <span className="font-mono normal-case tracking-normal">{item.id}</span>
        </span>
        <span className="flex flex-1 items-center gap-2 bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground md:text-sm dark:bg-[#0f3d2e] dark:text-[#f7f4ef]">
          <span aria-hidden="true">·</span>
          <span className="truncate">
            {item.dialect} ({item.provenance.replace('corpus ', '')})
          </span>
        </span>
      </figcaption>
    </figure>
  )
}
