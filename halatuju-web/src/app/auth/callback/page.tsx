'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import { KEY_GRADES, KEY_STPM_GRADES } from '@/lib/storage'
import { useT } from '@/lib/i18n'

export default function AuthCallbackPage() {
  const router = useRouter()
  const { t } = useT()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const checkSession = async () => {
      // Small delay to let Supabase process the callback
      await new Promise(resolve => setTimeout(resolve, 500))

      const { session, error } = await getSession()
      if (error) {
        setError(error.message)
        return
      }
      if (!session) {
        setError(t('errors.authFailed'))
        return
      }

      // Check if user has a backend profile with NRIC
      const token = session.access_token
      let hasNric = false
      try {
        const profile = await getProfile({ token })
        hasNric = !!profile.nric
      } catch {
        // No profile yet — treat as new user
      }

      if (!hasNric) {
        // New user or missing NRIC → collect IC first
        router.replace('/onboarding/ic')
        return
      }

      // Returning user with NRIC — check if they have onboarding data
      const hasGrades =
        localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
      if (!hasGrades) {
        router.replace('/onboarding/exam-type')
        return
      }

      // Fully set up — go to dashboard
      router.replace('/dashboard')
    }

    checkSession()
  }, [router])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <a href="/login" className="btn-primary">{t('login.backToLogin')}</a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
        <p className="text-gray-600">{t('login.completingSignIn')}</p>
      </div>
    </main>
  )
}
