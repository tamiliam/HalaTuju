'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { getAdminSupabase, adminUpdatePassword } from '@/lib/admin-supabase'
import { useT } from '@/lib/i18n'

const MIN_LEN = 8

// Reached from an INVITE or a PASSWORD-RESET email link. The Supabase client processes the
// link on load and establishes a (recovery/invite) session; this page then lets the user
// choose a password (auth.updateUser), which is the missing piece for non-Google reviewers.
export default function AdminSetPasswordPage() {
  const router = useRouter()
  const { t } = useT()
  const [ready, setReady] = useState(false)      // a valid session from the email link exists
  const [checking, setChecking] = useState(true) // still waiting for the link session
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const supabase = getAdminSupabase()
    let settled = false
    const markReady = () => { settled = true; setReady(true); setChecking(false) }

    // The session may already be established by the time we subscribe…
    supabase.auth.getSession().then(({ data }) => { if (data.session) markReady() })
    // …or it arrives via the auth event (PASSWORD_RECOVERY / SIGNED_IN) as the link is processed.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) markReady()
    })
    // If no session shows up shortly, the link was missing/expired/invalid.
    const timer = setTimeout(() => { if (!settled) setChecking(false) }, 4000)

    return () => { sub.subscription.unsubscribe(); clearTimeout(timer) }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < MIN_LEN) { setError(t('admin.passwordTooShort')); return }
    if (password !== password2) { setError(t('admin.passwordMismatch')); return }

    setLoading(true)
    const { error: updErr } = await adminUpdatePassword(password)
    if (updErr) { setError(updErr.message); setLoading(false); return }

    // They now have a password of their own, so stop forcing them through this page on every
    // sign-in. Best-effort: a failure here would only mean one redundant visit.
    await getAdminSupabase().auth.updateUser({ data: { must_change_password: false } }).catch(() => {})

    // Password set → route the user in by role (reviewers → their workspace).
    try {
      const { data } = await getAdminSupabase().auth.getSession()
      const token = data.session?.access_token
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/admin/role/`,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } }
      )
      const role = await res.json()
      router.replace(role.role === 'reviewer' || role.role === 'viewer' ? '/admin/scholarship' : '/admin')
    } catch {
      router.replace('/admin/login')
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center">
      <div className="w-full max-w-md px-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Image src="/logo-icon.png" alt="HalaTuju" width={90} height={48} />
          <span className="text-lg font-bold text-blue-600">Partner</span>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">{t('admin.setPasswordTitle')}</h1>
          <p className="text-gray-600 text-center mb-8">{t('admin.setPasswordSubtitle')}</p>

          {checking ? (
            <p className="text-center text-gray-500">{t('login.completingSignIn')}</p>
          ) : !ready ? (
            <div className="text-center">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                <p className="text-amber-700 text-sm">{t('admin.setPasswordNoLink')}</p>
              </div>
              <a href="/admin/login" className="text-blue-600 hover:underline text-sm">
                {t('login.backToLogin')}
              </a>
            </div>
          ) : (
            <>
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                  <p className="text-red-600 text-sm">{error}</p>
                </div>
              )}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.newPassword')}</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t('admin.newPasswordHint')}
                    autoComplete="new-password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.confirmPassword')}</label>
                  <input
                    type="password"
                    value={password2}
                    onChange={(e) => setPassword2(e.target.value)}
                    autoComplete="new-password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || !password || !password2}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {loading ? t('admin.settingPassword') : t('admin.setPasswordCta')}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
