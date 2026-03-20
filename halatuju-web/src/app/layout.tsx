import type { Metadata } from 'next'
import { Lexend } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { ReferralCapture } from '@/components/ReferralCapture'
import { HtmlLang } from '@/components/HtmlLang'

const lexend = Lexend({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-lexend',
})

export const metadata: Metadata = {
  title: 'HalaTuju — Cari Kursus Anda',
  description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,500+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
  keywords: ['SPM', 'STPM', 'course recommendation', 'Malaysia', 'education', 'university', 'polytechnic', 'degree', 'kursus', 'kelayakan'],
  openGraph: {
    title: 'HalaTuju — Cari Kursus Anda',
    description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,500+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
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
    description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,500+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
    images: ['/og-image.png'],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={lexend.variable}>
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
