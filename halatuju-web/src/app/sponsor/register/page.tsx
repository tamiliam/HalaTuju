'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import BrandLogo from '@/components/BrandLogo'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { sponsorSignUpWithPassword, sponsorSignInWithGoogle } from '@/lib/sponsor-supabase'
import { registerSponsor } from '@/lib/api'
import { checkPassword, SPONSOR_SOURCES, formatIntlPhone, isValidIntlPhone, toStoredPhone } from '@/lib/sponsorAuth'
import { COUNTRIES, DEFAULT_COUNTRY_ISO, countryByIso, flagOf } from '@/lib/countries'
import { KEY_SPONSOR_PENDING } from '@/lib/storage'

const EMAIL_RE = /\S+@\S+\.\S+/

export default function SponsorRegisterPage() {
  const router = useRouter()
  const { t } = useT()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [phone, setPhone] = useState('')
  const [country, setCountry] = useState(DEFAULT_COUNTRY_ISO)
  const [source, setSource] = useState('')
  const [consent, setConsent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<'form' | 'confirm'>('form')

  const pw = checkPassword(password)
  const pwMatch = password.length > 0 && password === password2
  const emailInvalid = email.length > 0 && !EMAIL_RE.test(email)
  const dial = countryByIso(country)?.dial || '60'
  const phoneInvalid = phone.length > 0 && !isValidIntlPhone(phone)
  const canSubmit =
    !!name.trim() && EMAIL_RE.test(email) && pw.allPass && pwMatch &&
    isValidIntlPhone(phone) && !!source && consent && !loading

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)

    // Stash so the portal's complete-details step can pre-fill after an email
    // confirmation gap (no session returned at sign-up).
    try {
      sessionStorage.setItem(KEY_SPONSOR_PENDING, JSON.stringify({ name: name.trim(), phone, country, source }))
    } catch { /* sessionStorage unavailable — register still works via the form */ }

    const { data, error } = await sponsorSignUpWithPassword(email.trim(), password, name.trim())
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    if (data.session) {
      // Email confirmation disabled → we have a session; create the pending account now.
      try {
        await registerSponsor(
          { name: name.trim(), phone: toStoredPhone(dial, phone), source, consent: true },
          { token: data.session.access_token },
        )
        try { sessionStorage.removeItem(KEY_SPONSOR_PENDING) } catch { /* ignore */ }
        router.push('/sponsor')
        return
      } catch {
        setError(t('sponsorAuth.registerFailed'))
        setLoading(false)
        return
      }
    }
    // No session → email confirmation required.
    setStep('confirm')
    setLoading(false)
  }

  const handleGoogle = async () => {
    setLoading(true)
    setError(null)
    const { error } = await sponsorSignInWithGoogle()
    if (error) {
      setError(error.message)
      setLoading(false)
    }
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center py-12">
      <div className="w-full max-w-md px-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          <BrandLogo width={90} height={48} />
          <span className="text-lg font-bold text-blue-600">{t('sponsorAuth.badge')}</span>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          {step === 'confirm' ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✉️</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorAuth.confirmTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorAuth.confirmBody')} <strong>{email}</strong></p>
              <Link href="/sponsor/login" className="inline-block mt-5 text-sm font-semibold text-blue-600 hover:underline">
                {t('login.backToLogin')}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">{t('sponsorAuth.registerTitle')}</h1>
              <p className="text-gray-600 text-center mb-6">{t('sponsorAuth.registerSubtitle')}</p>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6"><p className="text-red-600 text-sm">{error}</p></div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.fullName')} <span className="text-red-500">*</span></label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.email')} <span className="text-red-500">*</span></label>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} />
                  {emailInvalid && <p className="text-xs text-red-600 mt-1">{t('sponsorAuth.emailInvalid')}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.password')} <span className="text-red-500">*</span></label>
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.country')} <span className="text-red-500">*</span></label>
                  <select value={country} onChange={(e) => setCountry(e.target.value)} className={inputCls}>
                    {COUNTRIES.map((c) => (
                      <option key={c.iso2} value={c.iso2}>{flagOf(c.iso2)} {c.name} (+{c.dial})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.phone')} <span className="text-red-500">*</span></label>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm text-gray-600 whitespace-nowrap">
                      {flagOf(country)} +{dial}
                    </span>
                    <input inputMode="tel" value={phone} onChange={(e) => setPhone(formatIntlPhone(e.target.value))}
                      placeholder={t('sponsorAuth.phonePlaceholder')} className={inputCls} />
                  </div>
                  {phoneInvalid && <p className="text-xs text-red-600 mt-1">{t('sponsorAuth.phoneInvalid')}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.source')} <span className="text-red-500">*</span></label>
                  <select value={source} onChange={(e) => setSource(e.target.value)} className={inputCls}>
                    <option value="">{t('sponsorAuth.sourcePlaceholder')}</option>
                    {SPONSOR_SOURCES.map((s) => <option key={s} value={s}>{t(`sponsorAuth.sourceOption.${s}`)}</option>)}
                  </select>
                </div>

                <label className="flex items-start gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
                  <span>{t('sponsorAuth.consent')}{' '}
                    <Link href="/privacy" className="text-blue-600 hover:underline">{t('sponsorAuth.privacyNotice')}</Link>.
                  </span>
                </label>

                <button type="submit" disabled={!canSubmit}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
                  {loading ? t('sponsorAuth.creating') : t('sponsorAuth.signUp')}
                </button>
              </form>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                <div className="relative flex justify-center text-sm"><span className="px-4 bg-white text-gray-500">{t('login.or')}</span></div>
              </div>

              <button onClick={handleGoogle} disabled={loading}
                className="w-full flex items-center justify-center gap-3 px-6 py-3 border-2 border-gray-200 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50">
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                {t('sponsorAuth.signUpGoogle')}
              </button>

              <p className="text-center text-sm text-gray-500 mt-6">
                {t('sponsorAuth.haveAccount')}{' '}
                <Link href="/sponsor/login" className="font-semibold text-blue-600 hover:underline">{t('sponsorAuth.signInLink')}</Link>
              </p>
            </>
          )}
        </div>

        <div className="text-center mt-6">
          <Link href="/" className="text-sm text-gray-500 hover:text-blue-600 transition-colors">{t('sponsorAuth.backToHome')}</Link>
        </div>
      </div>
    </main>
  )
}
