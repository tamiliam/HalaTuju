import type { Metadata } from 'next'
import { Lexend, Inter, IBM_Plex_Sans } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { ReferralCapture } from '@/components/ReferralCapture'
import { HtmlLang } from '@/components/HtmlLang'
import { THEME_BOOT_SRC } from '@/lib/theme'

const lexend = Lexend({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-lexend',
})

// Inter — registered as a CSS variable here (root, server component, where next/font resolves
// cleanly) and applied to the sponsor portal only. The rest of HalaTuju stays on Lexend.
const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

// IBM Plex Sans — registered as a CSS variable here and applied (via the `font-plex` Tailwind
// family) to the four ORGANISATION admin modules only: invite, payments, contracts, sources.
// The rest of HalaTuju stays on Lexend; the sponsor portal stays on Inter.
const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-ibm-plex-sans',
})

export const metadata: Metadata = {
  // Base URL so relative OG/Twitter image paths resolve to the production host
  // (without this, social-share previews can resolve the image to the wrong host).
  metadataBase: new URL('https://halatuju.xyz'),
  title: 'HalaTuju — Cari Kursus Anda',
  description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,300+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
  keywords: ['SPM', 'STPM', 'course recommendation', 'Malaysia', 'education', 'university', 'polytechnic', 'degree', 'kursus', 'kelayakan'],
  openGraph: {
    title: 'HalaTuju — Cari Kursus Anda',
    description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,300+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
    url: 'https://halatuju.xyz',
    siteName: 'HalaTuju',
    locale: 'ms_MY',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'HalaTuju — Cari Kursus Anda',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'HalaTuju — Cari Kursus Anda',
    description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,300+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
    images: ['/og-image.png'],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${lexend.variable} ${inter.variable} ${ibmPlexSans.variable}`}>
      <head>
        {/*
          Paints the person's theme before the first pixel (Layer 1 F1). Render-blocking on
          purpose: the account's copy of Light/Dark/Auto arrives with the session, which is after
          first paint, so resolving it in React would make a dark user watch every page turn white
          then dark. See public/theme-boot.js — it sets one attribute and globals.css does the rest.
        */}
        {/*
          The synchronous-script rule is suppressed on the next line as A DELIBERATE EXCEPTION, not
          an oversight. That rule exists to stop render-blocking scripts delaying first paint — and
          here, delaying first paint is precisely the requirement: the attribute has to be on <html>
          BEFORE the first pixel, or a dark user sees a white flash on every navigation. Both
          `async` and `defer` run after paint and would put the flash straight back. The cost is one
          ~700-byte same-origin file that caches after the first request.
        */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src={THEME_BOOT_SRC} />
      </head>
      <body className="font-sans">
        <Providers>
          <HtmlLang />
          <ReferralCapture />
          {children}
        </Providers>
      </body>
    </html>
  )
}
