'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Check for pending auth action (from AuthGateModal Google flow)
      const pending = localStorage.getItem(KEY_PENDING_AUTH_ACTION)
      if (pending) {
        // Go back — AuthProvider will detect session + pending action
        // and re-open the auth gate at the right step
        const hasGrades = localStorage.getItem(KEY_GRADES)
        router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
        return
      }

      // Direct login (not from auth gate) — check NRIC
      try {
        const profile = await getProfile({ token: session.access_token })
        if (profile.nric) {
          const hasGrades = localStorage.getItem(KEY_GRADES)
          router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
        } else {
          router.replace('/onboarding/ic')
        }
      } catch {
        router.replace('/onboarding/ic')
      }
    }
    handle()
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Redirecting...</div>
    </div>
  )
}
