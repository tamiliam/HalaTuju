'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * The Administration hub was a single page doing five jobs, and existed because there was no
 * sidebar to reach its parts. N3b split it into real routes — Organisation overview, Staff,
 * Organisations, Referral partners — and this stays as a permanent redirect so old bookmarks,
 * emailed links and the Manual's screenshots still land somewhere sensible.
 *
 * Kept indefinitely: it costs one file, and a dead admin link costs someone a support message.
 */
export default function AdministrationRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/organisation')
  }, [router])
  return null
}
