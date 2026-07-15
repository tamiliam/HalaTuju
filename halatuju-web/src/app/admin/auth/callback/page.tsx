'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminSupabase } from '@/lib/admin-supabase'
import { enforceSingleScope } from '@/lib/sessionPolicy'
import { adminLanding } from '@/lib/adminLanding'
import { useT } from '@/lib/i18n'

export default function AdminAuthCallbackPage() {
  const router = useRouter()
  const { t } = useT()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const supabase = getAdminSupabase()

    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        setError(t('errors.authFailed'))
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
          isSuper: !!(role.is_super_admin || role.role === 'super'),
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
