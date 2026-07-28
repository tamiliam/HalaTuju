'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

// The Invite page was reorganised into the Administration panel (2026-07-15), and that panel
// became real routes in N3b (2026-07-28). Retargeted straight at Staff rather than left to
// bounce through /admin/administration — an old bookmark deserves one hop, not two.
export default function AdminInviteRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/organisation/staff')
  }, [router])
  return null
}
