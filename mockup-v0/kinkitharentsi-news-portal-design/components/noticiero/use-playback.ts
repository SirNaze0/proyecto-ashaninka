'use client'

import { useEffect, useState } from 'react'
import type { Segment } from '@/lib/news-data'

const TICK_MS = 100

export type Playback = ReturnType<typeof usePlayback>

export function usePlayback(segments: Segment[], initialElapsed = 0) {
  const [index, setIndex] = useState(0)
  const [elapsed, setElapsed] = useState(initialElapsed)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)

  const current = segments[index]

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      setElapsed((e) => e + (TICK_MS / 1000) * speed)
    }, TICK_MS)
    return () => window.clearInterval(id)
  }, [playing, speed])

  useEffect(() => {
    if (!current || elapsed < current.duration) return
    if (index < segments.length - 1) {
      setIndex(index + 1)
      setElapsed(0)
    } else {
      setPlaying(false)
      setElapsed(current.duration)
    }
  }, [elapsed, current, index, segments.length])

  const total = segments.reduce((sum, s) => sum + s.duration, 0)
  const before = segments.slice(0, index).reduce((sum, s) => sum + s.duration, 0)

  const wordCount = current?.text.split(/\s+/).length ?? 0
  const activeWord =
    current && !current.blocked
      ? Math.min(wordCount - 1, Math.floor((elapsed / current.duration) * wordCount))
      : -1

  function toggle() {
    if (!playing && index === segments.length - 1 && elapsed >= (current?.duration ?? 0)) {
      setIndex(0)
      setElapsed(0)
    }
    setPlaying((p) => !p)
  }

  function seek(i: number) {
    setIndex(Math.max(0, Math.min(segments.length - 1, i)))
    setElapsed(0)
  }

  return {
    index,
    elapsed,
    playing,
    speed,
    setSpeed,
    current,
    activeWord,
    position: before + elapsed,
    total,
    toggle,
    repeat: () => seek(index),
    next: () => seek(index + 1),
    seek,
  }
}
