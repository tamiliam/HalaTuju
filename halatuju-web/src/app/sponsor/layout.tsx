'use client'

import { SponsorAuthProvider } from '@/lib/sponsor-auth-context'

export default function SponsorLayout({ children }: { children: React.ReactNode }) {
  return <SponsorAuthProvider>{children}</SponsorAuthProvider>
}
