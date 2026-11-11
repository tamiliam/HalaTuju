'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

/** Legacy route — the pool detail moved to /sponsor/students/[id]. Redirect old links/emails.
 *  TD-074: a ref segment is passed through untouched. An all-digit segment is a pre-TD-074 raw-id
 *  link (an email already sent): it goes to the student LIST (A4.6 review), not to a "not available"
 *  page. Nothing here maps an id to a student. */
export default function SponsorPoolDetailRedirect() {
  const params = useParams()
  const router = useRouter()
  useEffect(() => {
    const segment = String(params?.id ?? '')
    router.replace(/^\d+$/.test(segment) ? '/sponsor/students' : `/sponsor/students/${segment}`)
  }, [params, router])
  return null
}
