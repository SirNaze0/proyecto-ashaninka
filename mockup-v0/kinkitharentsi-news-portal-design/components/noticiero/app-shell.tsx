'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { type Condition, INITIAL_SAVED, NEWS, type NewsItem } from '@/lib/news-data'
import { Masthead, type Role, type TextSize, type Theme } from './masthead'
import { ViewNav, type View } from './view-nav'
import { PortadaView } from './portada-view'
import { EstudioView } from './estudio-view'
import { RedaccionView } from './redaccion-view'

export function AppShell() {
  const [view, setView] = useState<View>('portada')
  const [role, setRole] = useState<Role>('ciudadano')
  const [theme, setTheme] = useState<Theme>('light')
  const [textSize, setTextSize] = useState<TextSize>('md')
  const [condition, setCondition] = useState<Condition>('C4')
  const [saved, setSaved] = useState<Set<string>>(() => new Set(INITIAL_SAVED))
  const [published, setPublished] = useState<NewsItem[]>([])
  const [selectedId, setSelectedId] = useState('dev:34')

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.classList.toggle('light', theme === 'light')
    root.dataset.textSize = textSize
  }, [theme, textSize])

  const navigate = useCallback((next: View) => {
    setView(next)
    window.scrollTo({ top: 0 })
  }, [])

  const changeRole = useCallback((next: Role) => {
    setRole(next)
    if (next === 'ciudadano') setView((v) => (v === 'redaccion' ? 'portada' : v))
  }, [])

  const allNews = useMemo(() => [...published, ...NEWS], [published])
  const selected = allNews.find((n) => n.id === selectedId) ?? NEWS[NEWS.length - 1]
  const activeView: View = role === 'ciudadano' && view === 'redaccion' ? 'portada' : view

  const openInStudio = useCallback(
    (id: string) => {
      setSelectedId(id)
      navigate('estudio')
    },
    [navigate],
  )

  const toggleSaved = useCallback((id: string) => {
    setSaved((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const publish = useCallback(
    (item: NewsItem) => {
      setPublished((prev) => [item, ...prev.filter((p) => p.id !== item.id)])
      openInStudio(item.id)
    },
    [openInStudio],
  )

  return (
    <div className="min-h-dvh">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-3 focus:text-primary-foreground"
      >
        Saltar al contenido
      </a>
      <Masthead
        savedCount={saved.size}
        condition={condition}
        onConditionChange={setCondition}
        theme={theme}
        onThemeChange={setTheme}
        textSize={textSize}
        onTextSizeChange={setTextSize}
        role={role}
        onRoleChange={changeRole}
      />
      <ViewNav view={activeView} role={role} condition={condition} onNavigate={navigate} />
      <main id="contenido" className="mx-auto w-full max-w-7xl px-4 pb-24 pt-6 md:px-6 lg:pt-8">
        {activeView === 'portada' && (
          <PortadaView
            news={allNews}
            published={published}
            saved={saved}
            onOpen={openInStudio}
            onToggleSaved={toggleSaved}
          />
        )}
        {activeView === 'estudio' && (
          <EstudioView
            key={selected.id}
            item={selected}
            condition={condition}
            isSaved={saved.has(selected.id)}
            onToggleSaved={() => toggleSaved(selected.id)}
            onBack={() => navigate('portada')}
          />
        )}
        {activeView === 'redaccion' && role === 'admin' && <RedaccionView onPublish={publish} />}
      </main>
      <footer className="border-t border-border bg-card">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between md:px-6">
          <p>
            <span className="font-serif font-semibold text-foreground">Kinkitharentsi</span> ·
            Prototipo de investigación. Contenido bajo licencia CC-BY-NC-4.0.
          </p>
          <p>Voz sintética MMS · Presentadora virtual generada con IA</p>
        </div>
      </footer>
    </div>
  )
}
