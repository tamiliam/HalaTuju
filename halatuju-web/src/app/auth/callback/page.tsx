'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { restoreProfileToLocalStorage } from '@/lib/profile-restore'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Clear pending auth action — we handle everything here
      localStorage.removeItem(KEY_PENDING_AUTH_ACTION)

      // Check profile: NRIC status + restore data to localStorage
      try {
        const profile = await restoreProfileToLocalStorage(session.access_token)
        if (profile?.nric) {
          // Returning user with NRIC — go to dashboard or onboarding
          const hasGrades = localStorage.getItem(KEY_GRADES)
          router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
        } else {
          // No NRIC — needs IC verification
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
