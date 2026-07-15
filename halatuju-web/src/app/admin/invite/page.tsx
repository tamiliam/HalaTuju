'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

// The Invite page was reorganised into the Administration panel (2026-07-15). Keep this
// route as a permanent redirect so old bookmarks/links still land in the right place.
export default function AdminInviteRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/administration')
  }, [router])
  return null
}
