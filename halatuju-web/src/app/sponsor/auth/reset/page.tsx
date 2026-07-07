'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { getSponsorSupabase } from '@/lib/sponsor-supabase'
import { checkPassword } from '@/lib/sponsorAuth'
import { enforceSingleScope } from '@/lib/sessionPolicy'
import { useT } from '@/lib/i18n'

type Phase = 'verifying' | 'form' | 'error'

/**
 * Where a sponsor's "reset password" email lands. The link carries a recovery grant;
 * once it opens a session here we show a set-a-new-password form and call updateUser.
 * Supports a token_hash link (cross-device) and the same-browser PKCE code exchange.
 */
export default function SponsorResetPasswordPage() {
  const router = useRouter()
  const { t } = useT()
  const [phase, setPhase] = useState<Phase>('verifying')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const sb = getSponsorSupabase()
    let settled = false
    const toForm = () => { if (!settled) { settled = true; setPhase('form') } }

    const params = new URLSearchParams(
      (window.location.hash.replace(/^#/, '') || window.location.search.replace(/^\?/, '')),
    )
    if (params.get('error') || params.get('error_code')) { setPhase('error'); return }

    // Cross-device: a token_hash recovery link needs no stored code-verifier.
    const tokenHash = params.get('token_hash')
    if (tokenHash) {
      sb.auth.verifyOtp({ type: 'recovery', token_hash: tokenHash })
        .then(({ error }) => { if (error) setPhase('error'); else toForm() })
      return
    }
    // Same browser: detectSessionInUrl exchanges the PKCE code → recovery session.
    const { data: sub } = sb.auth.onAuthStateChange((_e, session) => { if (session) toForm() })
    sb.auth.getSession().then(({ data: { session } }) => { if (session) toForm() })
    const timer = setTimeout(() => { if (!settled) setPhase('error') }, 2500)
    return () => { sub.subscription.unsubscribe(); clearTimeout(timer) }
  }, [])

  const pw = checkPassword(password)
  const pwMatch = password.length > 0 && password === password2
  const canSave = pw.allPass && pwMatch && !saving

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSave) return
    setSaving(true)
    setError(null)
    const sb = getSponsorSupabase()
    const { error } = await sb.auth.updateUser({ password })
    if (error) { setError(error.message); setSaving(false); return }
    const { data: { session } } = await sb.auth.getSession()
    if (session) await enforceSingleScope('sponsor', { token: session.access_token })
    router.replace('/sponsor')
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center py-12">
      <div className="w-full max-w-md px-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Image src="/logo-icon.png" alt="HalaTuju" width={90} height={48} />
          <span className="text-lg font-bold text-blue-600">{t('sponsorAuth.badge')}</span>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          {phase === 'verifying' && (
            <p className="text-center text-gray-600">{t('sponsorAuth.resetVerifying')}</p>
          )}

          {phase === 'error' && (
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900 mb-2">{t('sponsorAuth.resetPassword')}</h1>
              <p className="text-red-600 text-sm mb-6">{t('sponsorAuth.resetLinkError')}</p>
              <Link href="/sponsor/login" className="inline-block text-blue-600 font-semibold hover:underline">
                {t('sponsorAuth.requestNewLink')}
              </Link>
            </div>
          )}

          {phase === 'form' && (
            <>
              <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">{t('sponsorAuth.resetNewTitle')}</h1>
              <p className="text-gray-600 text-center mb-6">{t('sponsorAuth.resetNewSubtitle')}</p>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6"><p className="text-red-600 text-sm">{error}</p></div>
              )}

              <form onSubmit={handleSave} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.newPassword')} <span className="text-red-500">*</span></label>
                  <div className="rounded-lg bg-blue-50/70 border border-blue-100 px-3 py-2 mb-2 text-xs text-gray-600">
                    <p className="font-medium text-gray-700 mb-1">{t('sponsorAuth.pwRulesTitle')}</p>
                    <ul className="space-y-0.5">
                      <li className={pw.minLength ? 'text-green-600' : ''}>{pw.minLength ? '✓' : '•'} {t('sponsorAuth.pwMinLength')}</li>
                      <li className={pw.mixedCase ? 'text-green-600' : ''}>{pw.mixedCase ? '✓' : '•'} {t('sponsorAuth.pwMixedCase')}</li>
                      <li className={pw.hasNumber ? 'text-green-600' : ''}>{pw.hasNumber ? '✓' : '•'} {t('sponsorAuth.pwNumber')}</li>
                    </ul>
                  </div>
                  <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} autoComplete="new-password" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.reenterPassword')} <span className="text-red-500">*</span></label>
                  <input type="password" value={password2} onChange={(e) => setPassword2(e.target.value)} className={inputCls} autoComplete="new-password" />
                  {password2.length > 0 && !pwMatch && (
                    <p className="text-xs text-red-600 mt-1">{t('sponsorAuth.pwMismatch')}</p>
                  )}
                </div>
                <button type="submit" disabled={!canSave}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
                  {saving ? t('sponsorAuth.resetSaving') : t('sponsorAuth.resetSave')}
                </button>
              </form>
            </>
          )}
        </div>

        <div className="text-center mt-6">
          <Link href="/sponsor/login" className="text-sm text-gray-500 hover:text-blue-600 transition-colors">{t('login.backToLogin')}</Link>
        </div>
      </div>
    </main>
  )
}
