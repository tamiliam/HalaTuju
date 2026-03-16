'use client'

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { KEY_REFERRAL_SOURCE } from '@/lib/storage'

/**
 * Captures ?ref= URL parameter and persists to localStorage.
 * Existing referral is NOT overwritten (first touch wins).
 */
export function useReferral() {
  const searchParams = useSearchParams()

  useEffect(() => {
    const ref = searchParams.get('ref')
    if (ref && !localStorage.getItem(KEY_REFERRAL_SOURCE)) {
      localStorage.setItem(KEY_REFERRAL_SOURCE, ref.toLowerCase().trim())
    }
  }, [searchParams])
}
