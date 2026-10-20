'use client'

import { Newspaper, PenLine, Radio } from 'lucide-react'
import type { Condition } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import type { Role } from './masthead'

export type View = 'portada' | 'estudio' | 'redaccion'

export function ViewNav({
  view,
  role,
  condition,
  onNavigate,
}: {
  view: View
  role: Role
  condition: Condition
  onNavigate: (v: View) => void
}) {
  const items: { value: View; label: string; icon: typeof Newspaper }[] = [
    { value: 'portada', label: 'Portada del Noticiero', icon: Newspaper },
    { value: 'estudio', label: `Estudio TV en Vivo (Modo ${condition})`, icon: Radio },
    ...(role === 'admin'
      ? [{ value: 'redaccion' as const, label: 'Sala de Redacción y Traducción', icon: PenLine }]
      : []),
  ]

  return (
    <nav
      aria-label="Vistas del noticiero"
      className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85"
    >
      <ul className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 md:px-6">
        {items.map(({ value, label, icon: Icon }) => {
          const active = view === value
          return (
            <li key={value} className="shrink-0">
              <button
                type="button"
                onClick={() => onNavigate(value)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex min-h-14 items-center gap-2 border-b-4 px-4 text-sm font-semibold transition-colors',
                  active
                    ? 'border-terracotta text-foreground'
                    : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
                {value === 'estudio' && (
                  <span className="ml-1 inline-flex items-center gap-1 rounded-sm bg-live px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                    En vivo
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
