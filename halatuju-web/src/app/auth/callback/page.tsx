'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { KEY_PENDING_AUTH_ACTION, KEY_SPONSOR_SIGNIN } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    // Resolve the destination SYNCHRONOUSLY, on mount, before any await. The auth
    // context's "resume" effect reads the same KEY_PENDING_AUTH_ACTION and DELETES
    // it once the session settles — which happens within the delay below. If we
    // read the key after the await it is already gone and we wrongly fall back to
    // /dashboard. That is exactly why repeat logins (NRIC already on file, so the
    // auth gate finishes instantly) flashed the apply page then got bounced to the
    // dashboard, while the first login — paused on the NRIC step — happened to win
    // the race. Reading it here captures the destination before it can be removed.
    let dest = '/dashboard'
    // A sponsor sign-in takes precedence and uses its OWN one-shot flag (not
    // KEY_PENDING_AUTH_ACTION), so the auth-context resume effect never opens the
    // student NRIC modal for a sponsor. Sponsors have no NRIC and don't need one.
    let sponsorSignin = false
    try {
      if (sessionStorage.getItem(KEY_SPONSOR_SIGNIN)) {
        sponsorSignin = true
        sessionStorage.removeItem(KEY_SPONSOR_SIGNIN)
        dest = '/sponsor'
      }
    } catch { /* sessionStorage unavailable — ignore */ }
    try {
      const pending = !sponsorSignin && localStorage.getItem(KEY_PENDING_AUTH_ACTION)
      if (pending) {
        const reason = JSON.parse(pending)?.reason
        if (reason === 'apply') dest = '/scholarship/apply'
        else if (reason === 'quiz') dest = '/quiz'
      }
    } catch { /* ignore malformed pending action */ }

    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }
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
