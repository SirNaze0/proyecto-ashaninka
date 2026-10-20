import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Inter, Source_Serif_4 } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  variable: '--font-source-serif',
})

export const metadata: Metadata = {
  title: 'Kinkitharentsi · Noticiero Intercultural Asháninka',
  description:
    'Servicio informativo multimodal en castellano y asháninka con voz sintética, presentadora virtual con IA y sala de redacción y traducción asistida.',
  generator: 'v0.app',
  icons: {
    icon: [
      { url: '/icon-light-32x32.png', media: '(prefers-color-scheme: light)' },
      { url: '/icon-dark-32x32.png', media: '(prefers-color-scheme: dark)' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#F7F4EF' },
    { media: '(prefers-color-scheme: dark)', color: '#0F1419' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" className={`${inter.variable} ${sourceSerif.variable}`}>
      <body className="antialiased">
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
