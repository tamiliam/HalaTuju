'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Gift programmes had a menu row of its own for one sprint (Sabah S2b, 2026-09-02) and moved onto
 * Organisation → Overview on 2026-09-03, because the gifts an organisation runs are what that
 * organisation IS rather than a separate feature — and the row was a whole sidebar entry for a
 * list of one.
 *
 * This stays as a permanent redirect, the same shape as `/admin/administration`: it costs one
 * file, and a dead admin link costs somebody a support message. `navigation.ts` matches this path
 * to the Overview row so a bookmark also lights the correct part of the sidebar.
 */
export default function ProgrammesRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/organisation')
  }, [router])
  return null
}
