import { Info } from 'lucide-react'
import type { Segment } from '@/lib/news-data'
import { cn } from '@/lib/utils'

export function LiveCaptionBar({
  segment,
  index,
  total,
  activeWord,
}: {
  segment: Segment | undefined
  index: number
  total: number
  activeWord: number
}) {
  if (!segment) return null
  const tokens = segment.text.split(/\s+/)

  return (
    <div className="border-t-2 border-terracotta bg-[#0b1110] px-5 py-4 text-[#f7f4ef] md:px-8 md:py-5">
      <div className="mb-2 flex items-center justify-between gap-3 text-[11px] font-bold uppercase tracking-[0.18em] text-[#f7f4ef]/60">
        <span>Teleprompter en vivo</span>
        <span className="font-mono tabular-nums">
          {index + 1} / {total}
        </span>
      </div>
      {segment.blocked && (
        <p className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#FFE27A]">
          <Info className="size-3.5" aria-hidden="true" />
          {segment.blockedNote ?? 'Segmento solo texto'}
        </p>
      )}
      <p
        lang="cni"
        aria-live="polite"
        className="min-h-[4.2em] font-serif text-xl leading-snug md:text-[22px]"
      >
        {tokens.map((t, ti) => (
          <span key={ti}>
            <span
              className={cn(
                'rounded-sm transition-colors duration-150',
                ti === activeWord && !segment.blocked
                  ? 'font-semibold text-[#FFE27A] underline decoration-[#FFE27A] decoration-2 underline-offset-[6px]'
                  : ti < activeWord && !segment.blocked
                    ? 'text-[#f7f4ef]'
                    : 'text-[#f7f4ef]/75',
              )}
            >
              {t}
            </span>{' '}
          </span>
        ))}
      </p>
    </div>
  )
}
