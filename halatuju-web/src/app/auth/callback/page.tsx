'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Always go to dashboard. AuthProvider will:
      // 1. Detect the session
      // 2. Fetch profile from API
      // 3. Set status to 'ready', 'needs-nric', or 'anonymous'
      // 4. Write profile to localStorage as cache
      // The dashboard's onboarding guard will redirect if no grades.
      router.replace('/dashboard')
    }
    handle()
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Redirecting...</div>
    </div>
  )
}
