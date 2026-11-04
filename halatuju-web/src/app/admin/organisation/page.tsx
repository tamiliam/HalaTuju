'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * T5c P5b (owner, 2026-11-05): the Organisation Overview and the Programmes landing became ONE page, "Overview",
 * on `/admin/organisation/programmes` (the pending cards above the programme cards). This route stays as a
 * redirect so an old bookmark or emailed link still lands on it. Its counts (staff, vetting, invitations) are now
 * the per-person pending cards, read from `my-pending/`.
 */
export default function OrganisationRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/organisation/programmes')
  }, [router])
  return null
}
