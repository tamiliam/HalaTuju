'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS } from '@/lib/storage'

async function restoreProfileToLocalStorage(token: string) {
  try {
    const profile = await getProfile({ token })
    if (profile.grades && Object.keys(profile.grades).length > 0) {
      localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
    }
    const demo: Record<string, unknown> = {}
    if (profile.gender) demo.gender = profile.gender
    if (profile.nationality) demo.nationality = profile.nationality
    if (profile.colorblind != null) demo.colorblind = profile.colorblind
    if (profile.disability != null) demo.disability = profile.disability
    if (Object.keys(demo).length > 0) {
      localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
    }
    if (profile.student_signals) {
      localStorage.setItem(KEY_QUIZ_SIGNALS, JSON.stringify(profile.student_signals))
    }
    return profile
  } catch {
    return null
  }
}

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
