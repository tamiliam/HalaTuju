import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'HalaTuju — Cari Kursus Anda',
  description: 'Masukkan keputusan SPM atau STPM anda dan temui 1,300+ kursus di universiti, politeknik dan TVET yang anda layak. Percuma.',
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

export default async function ReferralRedirect({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params
  redirect(`/?ref=${encodeURIComponent(code)}`)
}
