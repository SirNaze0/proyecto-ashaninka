import { NextResponse } from 'next/server'

/**
 * Prototype stand-in for the external ES → CNI Translator Service.
 * Returns sentence-aligned output with a phonological adaptation preview (H1)
 * so the newsroom UI can be exercised end to end.
 */

const LOANWORDS: Record<string, string> = {
  vacuna: 'bakona',
  vacunas: 'bakonasha',
  posta: 'posita',
  médica: 'merika',
  campaña: 'kampania',
  dengue: 'tenke',
  anemia: 'anemia',
  ministerio: 'ministerio',
  salud: 'saro',
  promotor: 'poromotori',
  promotores: 'poromotoriite',
  escuela: 'esekoera',
  cacao: 'kakao',
  cooperativa: 'kooperatiba',
  soles: 'sorishi',
  kilo: 'kiro',
  doctor: 'tokotori',
  hospital: 'ospitari',
  radio: 'rario',
}

const BANK = [
  'Ajatantsi ashi kametsari ainti asheninka anampiki',
  'Iroperotatsi ashi ikantakotiro aparoni kametsari irotake',
  'Ikamantake ashi ashaninka saikatsiri, kametsa oshiyaro',
  'Nantiro antabereentsipe iroperoriite ikantetakenari oka onijatamani',
  'Kameetsa, maaroni okanta, nopokaje, nosankinametoki',
  'Ipatotari ashaninka, ikoakotiro pinkatsari obakerari',
  'Pamerentyari pipankoki, antaroite jenoki',
  'Iriori obametantaniri ikantiri kametsa ojatatye',
]

type Body = { title?: string; category?: string; paragraphs?: string[] }

function splitSentences(paragraph: string) {
  return (paragraph.match(/[^.!?]+[.!?]?/g) ?? [])
    .map((s) => s.trim())
    .filter(Boolean)
}

function hash(input: string) {
  let h = 0
  for (let i = 0; i < input.length; i++) h = (h * 31 + input.charCodeAt(i)) | 0
  return Math.abs(h)
}

export async function POST(request: Request) {
  let body: Body
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Solicitud inválida' }, { status: 400 })
  }

  const paragraphs = Array.isArray(body.paragraphs)
    ? body.paragraphs.filter((p): p is string => typeof p === 'string').slice(0, 12)
    : []

  if (paragraphs.length === 0 || paragraphs.some((p) => p.length > 2000)) {
    return NextResponse.json(
      { error: 'Envíe entre 1 y 12 párrafos de hasta 2000 caracteres.' },
      { status: 400 },
    )
  }

  await new Promise((r) => setTimeout(r, 900))

  const result = paragraphs.map((paragraph, pIndex) =>
    splitSentences(paragraph).map((sentence, sIndex) => {
      const words = sentence.toLowerCase().match(/[a-záéíóúñü]+/g) ?? []
      const loans = Array.from(new Set(words.filter((w) => w in LOANWORDS)))
      const base = BANK[hash(sentence) % BANK.length]
      const textOrig = loans.length > 0 ? `${base}, ${loans.slice(0, 2).join(' ')}-ki.` : `${base}.`
      let h1 = textOrig
      for (const w of loans) h1 = h1.replaceAll(w, LOANWORDS[w])
      return {
        id: `p${pIndex + 1}s${sIndex + 1}`,
        source: sentence,
        text_orig: textOrig,
        h1,
        loanwords: loans,
      }
    }),
  )

  return NextResponse.json({ model: 'traductor-es-cni (prototipo)', paragraphs: result })
}
