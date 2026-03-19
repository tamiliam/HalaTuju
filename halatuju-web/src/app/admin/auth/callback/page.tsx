'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminSupabase } from '@/lib/admin-supabase'
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
          await supabase.auth.signOut()
          setError(t('errors.noAdminAccess'))
          return
        }
      } catch {
        setError(t('errors.adminVerifyFailed'))
        return
      }

      router.replace('/admin')
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
