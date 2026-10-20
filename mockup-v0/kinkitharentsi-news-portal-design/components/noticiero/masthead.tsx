'use client'

import { CloudDownload, KeyRound, LockKeyhole, Moon, Sun, UserRound } from 'lucide-react'
import { CONDITIONS, type Condition } from '@/lib/news-data'
import { cn } from '@/lib/utils'
import { Pill } from './pill'

export type Theme = 'light' | 'dark'
export type Role = 'ciudadano' | 'admin'

const ROLES: { value: Role; label: string; icon: typeof UserRound }[] = [
  { value: 'ciudadano', label: 'Vista Ciudadano (Público)', icon: UserRound },
  { value: 'admin', label: 'Panel Administrador (Redacción)', icon: LockKeyhole },
]

function RoleSwitcher({ role, onRoleChange }: { role: Role; onRoleChange: (r: Role) => void }) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <div role="radiogroup" aria-label="Rol de usuario" className="flex rounded-full border border-input bg-muted p-1">
        {ROLES.map(({ value, label, icon: Icon }) => {
          const active = role === value
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onRoleChange(value)}
              className={cn(
                'inline-flex min-h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors',
                active
                  ? value === 'admin'
                    ? 'bg-terracotta text-terracotta-foreground shadow-sm'
                    : 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          )
        })}
      </div>
      {role === 'admin' && (
        <Pill variant="warning" className="font-mono">
          <KeyRound className="size-3.5" aria-hidden="true" />
          x-admin-token activo
        </Pill>
      )}
    </div>
  )
}
export type TextSize = 'md' | 'lg' | 'xl'

const TEXT_SIZES: { value: TextSize; label: string; aria: string }[] = [
  { value: 'md', label: 'A', aria: 'Texto normal' },
  { value: 'lg', label: 'A+', aria: 'Texto grande' },
  { value: 'xl', label: 'A++', aria: 'Texto muy grande' },
]

export function Masthead({
  savedCount,
  condition,
  onConditionChange,
  theme,
  onThemeChange,
  textSize,
  onTextSizeChange,
  role,
  onRoleChange,
}: {
  role: Role
  onRoleChange: (r: Role) => void
  savedCount: number
  condition: Condition
  onConditionChange: (c: Condition) => void
  theme: Theme
  onThemeChange: (t: Theme) => void
  textSize: TextSize
  onTextSizeChange: (s: TextSize) => void
}) {
  return (
    <header className="border-b-4 border-primary bg-card">
      <div className="border-b border-border bg-background/60">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-2 md:px-6">
          <p className="text-xs font-medium text-muted-foreground">
            {role === 'admin' ? 'Sesión de redacción autenticada' : 'Acceso público al noticiero comunitario'}
          </p>
          <RoleSwitcher role={role} onRoleChange={onRoleChange} />
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 md:px-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <div
            aria-hidden="true"
            className="grid size-14 shrink-0 grid-cols-2 grid-rows-2 gap-1 rounded-md bg-primary p-2"
          >
            <span className="rounded-sm bg-terracotta" />
            <span className="rounded-sm bg-primary-foreground" />
            <span className="rounded-sm bg-primary-foreground" />
            <span className="rounded-sm bg-terracotta" />
          </div>
          <div>
            <h1 className="font-serif text-2xl font-bold leading-tight tracking-tight text-balance md:text-3xl">
              <span className="tracking-wider">KINKITHARENTSI</span>
              <span className="text-terracotta"> · </span>
              <span className="font-semibold">Noticiero en Lengua Asháninka</span>
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Servicio informativo multimodal con voz sintética e IA
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Pill variant="success">
            <span className="relative flex size-2.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-success-foreground opacity-60" />
              <span className="relative inline-flex size-2.5 rounded-full bg-success-foreground" />
            </span>
            En línea · PWA Lista
          </Pill>
          <Pill variant="neutral">
            <CloudDownload className="size-3.5" aria-hidden="true" />
            <span aria-live="polite">
              {savedCount} {savedCount === 1 ? 'noticia guardada' : 'noticias guardadas'} sin conexión
            </span>
          </Pill>

          <label className="flex min-h-11 items-center gap-2 rounded-md border border-input bg-background px-3 text-sm">
            <span className="font-medium text-muted-foreground">Modo de presentación:</span>
            <select
              value={condition}
              onChange={(e) => onConditionChange(e.target.value as Condition)}
              className="min-h-11 cursor-pointer bg-transparent font-semibold text-foreground focus-visible:outline-none"
            >
              {CONDITIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>

          <div
            role="group"
            aria-label="Tamaño del texto"
            className="flex overflow-hidden rounded-md border border-input"
          >
            {TEXT_SIZES.map((s) => (
              <button
                key={s.value}
                type="button"
                aria-label={s.aria}
                aria-pressed={textSize === s.value}
                onClick={() => onTextSizeChange(s.value)}
                className={cn(
                  'min-h-11 min-w-11 px-2 text-sm font-bold transition-colors',
                  textSize === s.value
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background text-foreground hover:bg-muted',
                )}
              >
                {s.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => onThemeChange(theme === 'dark' ? 'light' : 'dark')}
            aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo estudio oscuro'}
            className="flex min-h-11 min-w-11 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-muted"
          >
            {theme === 'dark' ? (
              <Sun className="size-5" aria-hidden="true" />
            ) : (
              <Moon className="size-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
