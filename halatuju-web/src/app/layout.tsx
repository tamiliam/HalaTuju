import type { Metadata } from 'next'
import { Lexend } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const lexend = Lexend({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-lexend',
})

export const metadata: Metadata = {
  title: 'HalaTuju - SPM Course Recommendations',
  description: 'Find the right course for your future based on your SPM results and interests.',
  keywords: ['SPM', 'course recommendation', 'Malaysia', 'education', 'university', 'polytechnic'],
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
          {children}
        </Providers>
      </body>
    </html>
  )
}
