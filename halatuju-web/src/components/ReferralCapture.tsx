'use client'

import { Suspense } from 'react'
import { useReferral } from '@/hooks/useReferral'

function ReferralCaptureInner() {
  useReferral()
  return null
}

export function ReferralCapture() {
  return (
    <Suspense fallback={null}>
      <ReferralCaptureInner />
    </Suspense>
  )
}
