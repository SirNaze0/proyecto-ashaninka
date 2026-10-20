import { cn } from '@/lib/utils'

const VARIANTS = {
  neutral: 'bg-secondary text-secondary-foreground border-border',
  primary: 'bg-primary text-primary-foreground border-transparent',
  outline: 'bg-transparent text-foreground border-input',
  terracotta: 'bg-terracotta text-terracotta-foreground border-transparent',
  live: 'bg-live text-white border-transparent',
  warning: 'bg-warning text-warning-foreground border-warning-foreground/30',
  info: 'bg-info text-info-foreground border-info-foreground/30',
  success: 'bg-success text-success-foreground border-success-foreground/30',
  studio: 'bg-black/70 text-white border-white/20 backdrop-blur',
} as const

export type PillVariant = keyof typeof VARIANTS

export function Pill({
  variant = 'neutral',
  className,
  children,
}: {
  variant?: PillVariant
  className?: string
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold leading-none tracking-wide',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
