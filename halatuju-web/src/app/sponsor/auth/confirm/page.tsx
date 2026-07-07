'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSponsorSupabase } from '@/lib/sponsor-supabase'
import { enforceSingleScope } from '@/lib/sessionPolicy'
import { useT } from '@/lib/i18n'

/**
 * Landing target for the sponsor email-confirmation link (emailRedirectTo).
 *
 * The confirmation click is verified by Supabase server-side FIRST — so the email is
 * confirmed by the time we get here, regardless of what happens next. The only variable
 * is whether we can also establish a session in THIS browser:
 *  - same browser that signed up → the PKCE code exchanges → session → straight into /sponsor;
 *  - a different device/browser (no stored code-verifier), or an already-used/expired link →
 *    no session here, but the email is confirmed, so we send them to sign in normally with a
 *    reassuring notice instead of a raw error.
 */
export default function SponsorAuthConfirmPage() {
  const router = useRouter()
  const { t } = useT()

  useEffect(() => {
    const sb = getSponsorSupabase()
    let done = false
    const finish = (path: string) => { if (!done) { done = true; router.replace(path) } }

    // A bad / expired / already-used link comes back with error params (query or hash).
    const params = new URLSearchParams(
      (window.location.hash.replace(/^#/, '') || window.location.search.replace(/^\?/, '')),
    )
    if (params.get('error') || params.get('error_code')) {
      finish('/sponsor/login?notice=confirm')
      return
    }

    const enter = async (token: string) => {
      await enforceSingleScope('sponsor', { token })
      finish('/sponsor')
    }
    // detectSessionInUrl exchanges the code asynchronously → SIGNED_IN.
    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => {
      if (session) enter(session.access_token)
    })
    sb.auth.getSession().then(({ data: { session } }) => { if (session) enter(session.access_token) })
    // Cross-device / no-verifier: the exchange can't complete here — the email is confirmed,
    // so fall back to a normal sign-in rather than leaving them stuck.
    const timer = setTimeout(() => finish('/sponsor/login?notice=confirm'), 2500)

    return () => { sub.subscription.unsubscribe(); clearTimeout(timer) }
  }, [router])

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-600">{t('login.completingSignIn')}</p>
    </main>
  )
}
