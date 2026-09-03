'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Intake years had a menu row of its own for one sprint (Sabah S2b, 2026-09-02) and became a tab
 * of Programme → Configuration on 2026-09-03. A year is a child of the gift and the row that
 * carries its rules — not a sibling of the gift's own settings.
 *
 * This stays as a permanent redirect, the same shape as `/admin/administration`: it costs one
 * file, and a dead admin link costs somebody a support message. `navigation.ts` matches this path
 * to the Configuration row so a bookmark also lights the correct part of the sidebar.
 *
 * ⚠ THE `?programme=` PARAMETER IS DROPPED ON PURPOSE. Which gift you are in is the breadcrumb's
 * job now (`lib/programmeScope`), and carrying a stale id through a redirect would let a bookmark
 * select a gift silently — the one thing that module refuses to do.
 */
export default function IntakeYearsRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/programme')
  }, [router])
  return null
}
