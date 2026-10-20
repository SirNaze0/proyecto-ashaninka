'use client'

import { useId, useRef, useState } from 'react'
import { CircleCheck, FileUp, Layers, Loader2, Sparkles, Upload } from 'lucide-react'
import {
  ACCEPTED_EXTENSIONS,
  DEMO_FILE_CONTENT,
  DEMO_FILE_NAME,
  type ParsedNews,
  parseNewsFile,
  parsePlainText,
} from '@/lib/parse-news-file'
import { cn } from '@/lib/utils'
import { Pill } from './pill'

type QueueItem = ParsedNews & { key: string }

export function FileImport({ onLoad }: { onLoad: (news: ParsedNews, source: string) => void }) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState<'idle' | 'reading' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [loadedKey, setLoadedKey] = useState<string | null>(null)
  const [fileName, setFileName] = useState('')

  function accept(items: ParsedNews[], source: string) {
    if (!items.length) throw new Error('No se encontraron noticias en el archivo.')
    const withKeys = items.map((n, i) => ({ ...n, key: `${source}-${i}` }))
    setFileName(source)
    setQueue(withKeys.length > 1 ? withKeys : [])
    setLoadedKey(withKeys[0].key)
    onLoad(withKeys[0], source)
    setStatus('idle')
    setMessage(
      withKeys.length > 1
        ? `${withKeys.length} noticias detectadas en ${source}. Se cargó la primera en el editor.`
        : `Noticia cargada desde ${source}: ${withKeys[0].paragraphs.length} párrafos · categoría ${withKeys[0].category}.`,
    )
  }

  async function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setStatus('reading')
    setMessage('')
    try {
      accept(await parseNewsFile(file), file.name)
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'No se pudo leer el archivo.')
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  function simulateDemo() {
    setStatus('reading')
    setMessage('')
    window.setTimeout(() => accept([parsePlainText(DEMO_FILE_CONTENT)], DEMO_FILE_NAME), 450)
  }

  function loadFromQueue(item: QueueItem) {
    setLoadedKey(item.key)
    onLoad(item, fileName)
    setMessage(`Cargada en el editor: «${item.title}».`)
  }

  return (
    <section aria-labelledby="importar-titulo" className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 id="importar-titulo" className="text-sm font-bold uppercase tracking-[0.15em]">
            Importar noticia desde archivo
          </h3>
          <p className="text-sm text-muted-foreground">
            El título, la categoría y los párrafos se extraen automáticamente.
          </p>
        </div>
        <button
          type="button"
          onClick={simulateDemo}
          disabled={status === 'reading'}
          className="inline-flex min-h-11 items-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-semibold hover:bg-muted disabled:opacity-60"
        >
          <Sparkles className="size-4 text-terracotta" aria-hidden="true" />
          Simular carga de archivo{' '}
          <span className="font-mono text-xs">{DEMO_FILE_NAME}</span>
        </button>
      </div>

      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handleFiles(e.dataTransfer.files)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors',
          dragging ? 'border-primary bg-accent' : 'border-input bg-background hover:border-primary/60 hover:bg-muted/50',
        )}
      >
        {status === 'reading' ? (
          <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
        ) : (
          <Upload className="size-8 text-primary" aria-hidden="true" />
        )}
        <span className="font-semibold">
          {status === 'reading' ? 'Leyendo archivo…' : 'Arrastre un archivo aquí o haga clic para seleccionarlo'}
        </span>
        <span className="flex flex-wrap justify-center gap-2">
          {ACCEPTED_EXTENSIONS.map((ext) => (
            <Pill key={ext} variant="outline" className="font-mono">
              {ext}
            </Pill>
          ))}
        </span>
        <span className="text-xs text-muted-foreground">
          CSV y JSON admiten varias noticias por archivo (lote). Máximo 2 MB.
        </span>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>

      {message && (
        <p
          role={status === 'error' ? 'alert' : 'status'}
          className={cn(
            'flex items-start gap-2 text-sm font-semibold',
            status === 'error' ? 'text-destructive' : 'text-success-foreground',
          )}
        >
          {status !== 'error' && <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />}
          {message}
        </p>
      )}

      {queue.length > 1 && (
        <div className="flex flex-col gap-2">
          <h4 className="flex items-center gap-2 text-sm font-bold">
            <Layers className="size-4 text-primary" aria-hidden="true" />
            Lote de noticias · {queue.length}
          </h4>
          <ul className="flex max-h-64 flex-col divide-y divide-border overflow-y-auto rounded-lg border border-border">
            {queue.map((item, i) => {
              const active = item.key === loadedKey
              return (
                <li key={item.key} className={cn('flex items-center gap-3 px-4 py-3', active && 'bg-accent')}>
                  <span className="font-mono text-xs text-muted-foreground">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{item.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.category} · {item.paragraphs.length} párrafos
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => loadFromQueue(item)}
                    disabled={active}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-input bg-background px-3 text-sm font-semibold hover:bg-muted disabled:border-transparent disabled:bg-primary disabled:text-primary-foreground"
                  >
                    <FileUp className="size-4" aria-hidden="true" />
                    {active ? 'En el editor' : 'Cargar'}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
