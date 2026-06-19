'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

/** Legacy route — the pool detail moved to /sponsor/students/[id]. Redirect old links/emails. */
export default function SponsorPoolDetailRedirect() {
  const params = useParams()
  const router = useRouter()
  useEffect(() => {
    router.replace(`/sponsor/students/${params?.id ?? ''}`)
  }, [params, router])
  return null
}
