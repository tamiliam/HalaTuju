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
  title: 'HalaTuju - SPM & STPM Course Recommendations',
  description: 'Find the right course for your future based on your SPM or STPM results and interests.',
  keywords: ['SPM', 'STPM', 'course recommendation', 'Malaysia', 'education', 'university', 'polytechnic', 'degree'],
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
