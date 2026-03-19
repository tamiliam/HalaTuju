'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Deprecated: IC verification is now handled by AuthGateModal.
 * This page redirects to dashboard, which will trigger the auth gate
 * if the user still needs NRIC verification.
 */
export default function IcOnboardingPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/dashboard')
  }, [router])

  return null
}
