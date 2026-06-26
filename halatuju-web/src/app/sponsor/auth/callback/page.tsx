'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getSponsorSupabase } from '@/lib/sponsor-supabase'
import { enforceSingleScope } from '@/lib/sessionPolicy'
import { useT } from '@/lib/i18n'

export default function SponsorAuthCallbackPage() {
  const router = useRouter()
  const { t } = useT()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getSponsorSupabase().auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        setError(t('errors.authFailed'))
        return
      }
      // One privileged scope per identity (super exempt): ends an active partner session.
      await enforceSingleScope('sponsor', { token: session.access_token })
      // The portal decides registered/not + whether details still need completing.
      router.replace('/sponsor')
    })
  }, [router, t])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <a href="/sponsor/login" className="text-blue-600 hover:underline">{t('login.backToLogin')}</a>
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
