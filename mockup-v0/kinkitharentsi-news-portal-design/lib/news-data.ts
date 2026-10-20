export type Condition = 'C1' | 'C2' | 'C3' | 'C4'

export const CONDITIONS: { value: Condition; label: string }[] = [
  { value: 'C1', label: 'C1 — Solo texto' },
  { value: 'C2', label: 'C2 — Voz y texto' },
  { value: 'C3', label: 'C3 — Voz y avatar' },
  { value: 'C4', label: 'C4 — Voz, texto y avatar' },
]

export type Segment = {
  id: string
  text: string
  /** Seconds of synthetic audio. */
  duration: number
  /** Text-only segment, pending phonological adaptation. */
  blocked?: boolean
  blockedNote?: string
  loanwords?: string[]
}

export type NewsItem = {
  id: string
  category: string
  region: string
  dialect: string
  provenance: string
  titleEs: string
  titleCni: string
  snippetCni: string
  summaryEs: string
  image: string
  imageAlt: string
  audioReady: boolean
  durationLabel?: string
  pilot?: boolean
  segments: Segment[]
}

export const NEWS: NewsItem[] = [
  {
    id: 'dev:21',
    category: 'Salud intercultural',
    region: 'Selva Central',
    dialect: 'Asháninka del Ene / Tambo',
    provenance: 'corpus AmericasNLP',
    titleEs:
      'Campaña de salud intercultural y prevención en comunidades de la cuenca del Ene',
    titleCni: 'Ajatantsi ashi kametsari ainti asheninka anampiki Eni',
    snippetCni:
      'Iroperotatsi ashi ikantakotiro aparoni kametsari, ikamantake ashi ashaninka saikatsiri Eni…',
    summaryEs:
      'Promotores de salud y sabios comunales recorren las comunidades con información bilingüe sobre prevención de dengue y anemia.',
    image: '/images/salud-ene.png',
    imageAlt:
      'Promotora de salud conversa con mujeres asháninka bajo una casa comunal techada junto al río Ene.',
    audioReady: true,
    durationLabel: '01:15 min',
    segments: [
      {
        id: 's1',
        text: 'Ajatantsi ashi kametsari ainti asheninka anampiki Eni.',
        duration: 4.4,
      },
      {
        id: 's2',
        text: 'Iroperotatsi ashi ikantakotiro aparoni kametsari irotake.',
        duration: 4.2,
      },
      {
        id: 's3',
        text: 'Ikamantake ashi ashaninka saikatsiri, kametsa oshiyaro.',
        duration: 4.1,
      },
    ],
  },
  {
    id: 'dev:1',
    category: 'Educación',
    region: 'Río Tambo',
    dialect: 'Asháninka del Tambo',
    provenance: 'corpus AmericasNLP',
    titleEs: 'Escuelas bilingües inician el año con nuevos materiales en lengua materna',
    titleCni: 'Ikenantsi obametantsi ashi ashaninka',
    snippetCni: 'Iriori obametantaniri ikantiri kametsa ojatatye ashi obametantsi…',
    summaryEs:
      'Docentes de educación intercultural bilingüe reciben cuadernos de trabajo escritos en asháninka.',
    image: '/images/escuela.png',
    imageAlt:
      'Niños asháninka en un aula de madera atienden a su docente frente a la pizarra.',
    audioReady: true,
    segments: [
      { id: 's1', text: 'Ikenantsi obametantsi ashi ashaninka.', duration: 3.4 },
      {
        id: 's2',
        text: 'Iriori obametantaniri ikantiri kametsa ojatatye.',
        duration: 3.8,
      },
    ],
  },
  {
    id: 'dev:4',
    category: 'Clima',
    region: 'Cuenca del Tambo',
    dialect: 'Variante mixta',
    provenance: 'corpus AmericasNLP',
    titleEs: 'Crecida del río Tambo: recomendaciones para la temporada de lluvias',
    titleCni: 'Antaroite okarati Tambo inkani',
    snippetCni: 'Okarati inkani, antaroite jenoki. Pamerentyari pipankoki…',
    summaryEs:
      'Autoridades comunales recomiendan asegurar canoas y almacenar agua segura ante la subida del caudal.',
    image: '/images/rio-clima.png',
    imageAlt:
      'Río Tambo crecido con agua turbia, una canoa de madera en la orilla y cerros con neblina.',
    audioReady: false,
    segments: [
      { id: 's1', text: 'Okarati inkani, antaroite jenoki.', duration: 3.2 },
      { id: 's2', text: 'Pamerentyari pipankoki.', duration: 2.6 },
    ],
  },
  {
    id: 'dev:8',
    category: 'Comunidad',
    region: 'Puerto Ocopa',
    dialect: 'Asháninka del Perené',
    provenance: 'corpus AmericasNLP',
    titleEs: 'Asamblea comunal elige nuevas autoridades y acuerda vigilancia territorial',
    titleCni: 'Apatotantsi anampiki, ikoakotiro pinkatsari',
    snippetCni: 'Ipatotari ashaninka, ikoakotiro pinkatsari obakerari…',
    summaryEs:
      'La asamblea renovó su junta directiva y aprobó un plan de monitoreo comunitario del bosque.',
    image: '/images/asamblea.png',
    imageAlt:
      'Asamblea comunal asháninka reunida en bancas de madera dentro de una casa comunal techada.',
    audioReady: true,
    segments: [
      { id: 's1', text: 'Apatotantsi anampiki, ikoakotiro pinkatsari.', duration: 3.6 },
      { id: 's2', text: 'Ipatotari ashaninka, ikoakotiro pinkatsari obakerari.', duration: 4 },
    ],
  },
  {
    id: 'dev:34',
    category: 'Economía local',
    region: 'Selva Central',
    dialect: 'Variante mixta',
    provenance: 'corpus AmericasNLP',
    titleEs: 'Kinkitharentsi Asháninka: productores de cacao comparten su cosecha',
    titleCni: 'Kinkitharentsi Asháninka',
    snippetCni: 'Kameetsa, maaroni okanta, nopokaje, nosankinametoki…',
    summaryEs:
      'Pseudo-noticia del corpus de desarrollo utilizada en el piloto de la condición C4.',
    image: '/images/cacao.png',
    imageAlt: 'Manos de un agricultor asháninka sostienen mazorcas de cacao recién abiertas.',
    audioReady: true,
    pilot: true,
    segments: [
      {
        id: 's1',
        text: 'Kameetsa, maaroni okanta, nopokaje, nosankinametoki.',
        duration: 4,
      },
      {
        id: 's2',
        text: 'Nantiro antabereentsipe iroperoriite ikantetakenari oka onijatamani.',
        duration: 4,
      },
      {
        id: 's3',
        text: 'Ikantiri promotor, ipakiro cacao cooperativa-ki, aparoni kilo soles.',
        duration: 4,
        blocked: true,
        blockedNote: 'Solo texto: pendiente de adaptación fonológica (P2d)',
        loanwords: ['promotor', 'cacao', 'cooperativa-ki', 'kilo', 'soles'],
      },
    ],
  },
]

export const FEATURED_ID = 'dev:21'
export const GRID_IDS = ['dev:1', 'dev:4', 'dev:8', 'dev:34']
export const INITIAL_SAVED = ['dev:21', 'dev:1', 'dev:8']

export function totalDuration(segments: Segment[]) {
  return segments.reduce((sum, s) => sum + s.duration, 0)
}

export function formatTime(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
