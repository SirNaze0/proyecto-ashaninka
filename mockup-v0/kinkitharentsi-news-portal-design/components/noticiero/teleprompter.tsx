'use client'

import { Info } from 'lucide-react'
import type { Segment } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import { Pill } from './pill'

function splitWord(token: string) {
  const match = token.match(/^(.*?)([.,;:!?…]*)$/)
  return { word: match?.[1] ?? token, punct: match?.[2] ?? '' }
}

export function Teleprompter({
  segments,
  activeIndex,
  activeWord,
  onSeek,
}: {
  segments: Segment[]
  activeIndex: number
  activeWord: number
  onSeek: (i: number) => void
}) {
  return (
    <div lang="cni" className="flex flex-col gap-4 font-serif text-xl leading-[1.8] md:text-[22px]">
      {segments.map((seg, i) => {
        const active = i === activeIndex
        const tokens = seg.text.split(/\s+/)

        if (seg.blocked) {
          return (
            <div
              key={seg.id}
              aria-current={active ? 'true' : undefined}
              className={cn(
                'rounded-r-lg border-l-4 border-info-foreground bg-info p-4 md:p-5',
                active && 'ring-2 ring-warning-foreground/60',
              )}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 font-sans">
                <Pill variant="warning">
                  <Info className="size-3.5" aria-hidden="true" />
                  {seg.blockedNote}
                </Pill>
                <span className="text-xs font-medium text-info-foreground">Nota editorial</span>
              </div>
              <p className="text-foreground">
                {tokens.map((t, ti) => {
                  const { word } = splitWord(t)
                  const isLoan = seg.loanwords?.includes(word.toLowerCase())
                  return (
                    <span key={ti}>
                      {isLoan ? (
                        <span
                          lang="es"
                          className="underline decoration-warning-foreground decoration-dotted decoration-2 underline-offset-4"
                          title="Préstamo del castellano sin adaptar"
                        >
                          {t}
                        </span>
                      ) : (
                        t
                      )}{' '}
                    </span>
                  )
                })}
              </p>
              <button
                type="button"
                onClick={() => onSeek(i)}
                className="mt-2 min-h-11 font-sans text-sm font-semibold text-info-foreground underline underline-offset-4"
              >
                Ir a este segmento (sin voz)
              </button>
            </div>
          )
        }

        return (
          <button
            type="button"
            key={seg.id}
            aria-current={active ? 'true' : undefined}
            className={cn(
              'block w-full rounded-r-md border-l-4 py-1 pl-4 text-left transition-colors md:pl-5',
              active ? 'border-terracotta text-foreground' : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
            )}
            onClick={() => onSeek(i)}
          >
            {tokens.map((t, ti) => {
              const { word, punct } = splitWord(t)
              const highlighted = active && ti === activeWord
              return (
                <span key={ti}>
                  <span
                    className={cn(
                      'rounded-md transition-colors',
                      highlighted && 'bg-highlight px-1.5 py-0.5 font-semibold text-highlight-foreground',
                    )}
                  >
                    {word}
                  </span>
                  {punct}{' '}
                </span>
              )
            })}
          </button>
        )
      })}
    </div>
  )
}
