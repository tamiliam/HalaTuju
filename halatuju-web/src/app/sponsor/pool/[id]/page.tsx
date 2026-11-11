'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

/** Legacy route — the pool detail moved to /sponsor/students/[id]. Redirect old links/emails.
 *  TD-074: the segment is passed through untouched; a pre-TD-074 raw-id link lands on the
 *  "not available" state, because the API answers 404 for anything that is not a ref in the
 *  sponsor's own fence. Nothing here maps an id to a student. */
export default function SponsorPoolDetailRedirect() {
  const params = useParams()
  const router = useRouter()
  useEffect(() => {
    router.replace(`/sponsor/students/${params?.id ?? ''}`)
  }, [params, router])
  return null
}
