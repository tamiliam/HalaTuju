'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminSupabase } from '@/lib/admin-supabase'
import { enforceSingleScope } from '@/lib/sessionPolicy'
import { adminLanding } from '@/lib/adminLanding'
import { effectiveRole } from '@/lib/navigation'
import { useT } from '@/lib/i18n'

export default function AdminAuthCallbackPage() {
  const router = useRouter()
  const { t } = useT()
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<string>('')

  useEffect(() => {
    const supabase = getAdminSupabase()

    /**
     * Get the session, exchanging the PKCE `?code=` ourselves if the client's own
     * `detectSessionInUrl` has not already done it.
     *
     * Relying on auto-detect alone is a race we do not control: another supabase client on the
     * page can reach the URL first, and supabase-js consumes the single-use code on the attempt
     * whether or not it holds the matching verifier. Claiming it explicitly is idempotent — if
     * auto-detect already succeeded there is a session and we never call exchange at all.
     *
     * The REASON is surfaced rather than swallowed. "Authentication failed. Please try again."
     * told nobody anything, including me: it cost several rounds of guessing at a failure the
     * page already knew the cause of. A code like `invalid_grant` is diagnostic, not sensitive.
     */
    const resolveSession = async () => {
      const { data: { session: existing } } = await supabase.auth.getSession()
      if (existing) return { session: existing, reason: '' }

      const code = new URLSearchParams(window.location.search).get('code')
      if (!code) return { session: null, reason: 'no code in callback URL' }

      const { data, error: exErr } = await supabase.auth.exchangeCodeForSession(code)
      return { session: data?.session ?? null, reason: exErr?.message ?? 'exchange returned no session' }
    }

    resolveSession().then(async ({ session, reason }) => {
      if (!session) {
        setError(t('errors.authFailed'))
        setDetail(reason)
        return
      }

      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/admin/role/`,
          {
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              'Content-Type': 'application/json',
            },
          }
        )
        const role = await res.json()
        if (!role.is_admin) {
          // Clear ONLY this admin-scope session. `scope: 'local'` matters: the default
          // (global) revokes EVERY session for this Supabase user — so a person who is
          // also a signed-in sponsor (same Google identity, other tab) would be kicked
          // out of the sponsor portal just for landing here. Mirror the other signOuts.
          await supabase.auth.signOut({ scope: 'local' })
          setError(t('errors.noAdminAccess'))
          return
        }
        // One privileged scope per identity (super exempt): ends an active sponsor session.
        await enforceSingleScope('admin', {
          token: session.access_token,
          isSuper: effectiveRole(role) === 'super',
        })
        // Reviewers/viewers have no partner-org dashboard — send them to their workspace
        // (B40 Applications); org admins/super keep the dashboard; a reviewer with an
        // incomplete profile is held on /admin/profile until they finish onboarding.
        router.replace(adminLanding(role))
        return
      } catch {
        setError(t('errors.adminVerifyFailed'))
        return
      }
    })
  }, [router])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          {detail && (
            <p className="mb-4 font-mono text-xs text-gray-400">{detail}</p>
          )}
          <a href="/admin/login" className="text-blue-600 hover:underline">
            {t('login.backToLogin')}
          </a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-600">{t('login.completingSignIn')}</p>
    </main>
  )
}
