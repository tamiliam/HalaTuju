'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { KEY_PENDING_AUTH_ACTION } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Land back on the page the sign-in was started from, so a Google login
      // begun on the apply (or quiz) page returns there rather than always going
      // to /dashboard. Previously this hardcoded /dashboard, which raced with the
      // auth gate's own redirect. The gate still reopens on the destination to
      // sync the profile. Other reasons resume correctly from /dashboard.
      let dest = '/dashboard'
      try {
        const pending = localStorage.getItem(KEY_PENDING_AUTH_ACTION)
        if (pending) {
          const reason = JSON.parse(pending)?.reason
          if (reason === 'apply') dest = '/scholarship/apply'
          else if (reason === 'quiz') dest = '/quiz'
        }
      } catch { /* ignore malformed pending action */ }
      router.replace(dest)
    }
    handle()
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Redirecting...</div>
    </div>
  )
}
