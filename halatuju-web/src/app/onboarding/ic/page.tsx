'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { syncProfile } from '@/lib/api'
import { useT } from '@/lib/i18n'
import IcInput from '@/components/IcInput'
import { validateIc } from '@/lib/ic-utils'
import { KEY_REFERRAL_SOURCE } from '@/lib/storage'

export default function IcOnboardingPage() {
  const router = useRouter()
  const { t } = useT()
  const { token, session, isAnonymous, status, profile: authProfile } = useAuth()

  // Guard: anonymous users shouldn't be here; users with NRIC skip to dashboard
  useEffect(() => {
    if (status === 'loading') return
    if (status === 'anonymous') { router.replace('/'); return }
    if (status === 'ready') {
      // Already has NRIC — check if they have grades too
      const hasGrades = authProfile?.grades && Object.keys(authProfile.grades).length > 0
      router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
      return
    }
    // status === 'needs-nric' — stay on this page
  }, [status, authProfile, router])
  const [ic, setIc] = useState('')
  const [icValid, setIcValid] = useState(false)
  const [name, setName] = useState(
    session?.user?.user_metadata?.full_name ||
    session?.user?.user_metadata?.name ||
    ''
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [existingName, setExistingName] = useState<string | null>(null)
  const [referral, setReferral] = useState<string | null>(() =>
    typeof window !== 'undefined' ? localStorage.getItem(KEY_REFERRAL_SOURCE) : null
  )

  const REFERRAL_OPTIONS = [
    { value: 'whatsapp', label: 'WhatsApp' },
    { value: 'google', label: 'Google' },
    { value: 'fbig', label: 'FB/IG' },
    { value: 'cumig', label: 'CUMIG' },
    { value: 'other', label: '' },
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationErr = validateIc(ic)
    if (validationErr) {
      setError(validationErr)
      return
    }
    if (!token) {
      setError(t('errors.notSignedIn'))
      return
    }

    setLoading(true)
    setError(null)

    try {
      const { claimNric } = await import('@/lib/api')
      const result = await claimNric(ic, false, { token: token! })

      if (result.status === 'created' || result.status === 'linked') {
        // New NRIC or already own it — sync name & referral then proceed
        const ref = localStorage.getItem(KEY_REFERRAL_SOURCE)
        await syncProfile(
          { ...(name.trim() && { name: name.trim() }), ...(ref && { referral_source: ref }) },
          { token }
        )
        router.replace('/onboarding/exam-type')
      } else if (result.status === 'exists') {
        // Someone else has this NRIC — ask confirmation
        setExistingName(result.name || null)
        setShowConfirm(true)
        setLoading(false)
      }
    } catch {
      setError(t('errors.saveFailed'))
      setLoading(false)
    }
  }

  const handleConfirmClaim = async () => {
    setLoading(true)
    setError(null)
    try {
      const { claimNric } = await import('@/lib/api')
      await claimNric(ic, true, { token: token! })
      router.replace('/onboarding/exam-type')
    } catch {
      setError(t('errors.claimFailed'))
      setLoading(false)
    }
  }

  const handleDenyClaim = () => {
    setShowConfirm(false)
    setExistingName(null)
    setIc('')
  }

  return (
    <main className="min-h-screen bg-[#f8fafc]">
      {/* Header */}
      <div className="bg-white border-b border-gray-100">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={90} height={40} />
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8 max-w-md">
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h1 className="text-xl font-bold text-gray-900 text-center mb-2">
            {t('authGate.icTitle') || 'Verify Your Identity'}
          </h1>
          <p className="text-gray-600 text-center text-sm mb-6">
            {t('authGate.icSubtitle')}
          </p>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <IcInput
              value={ic}
              onChange={setIc}
              onValidChange={setIcValid}
              label={t('authGate.icLabel')}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('authGate.nameLabel')}
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('authGate.namePlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
              />
            </div>

            {!referral && (
              <div className="mt-6 pt-4 border-t border-gray-100">
                <p className="text-sm text-gray-500 mb-3">
                  {t('onboarding.referralQuestion')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {REFERRAL_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => {
                        setReferral(opt.value)
                        localStorage.setItem(KEY_REFERRAL_SOURCE, opt.value)
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        referral === opt.value
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                      }`}
                    >
                      {opt.label || t('onboarding.referralOther')}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {showConfirm && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-amber-800 mb-3">
                  {existingName
                    ? t('onboarding.nricExistsNamed', { name: existingName })
                    : t('onboarding.nricExists')}
                </p>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleConfirmClaim}
                    disabled={loading}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
                  >
                    {t('onboarding.yesThisIsMe')}
                  </button>
                  <button
                    type="button"
                    onClick={handleDenyClaim}
                    className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50"
                  >
                    {t('onboarding.noReenter')}
                  </button>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={!icValid || loading}
              className="btn-primary w-full disabled:opacity-50"
            >
              {loading ? '...' : t('common.continue')}
            </button>

            <p className="text-xs text-gray-400 text-center">
              {t('authGate.icPrivacy')}
            </p>
          </form>
        </div>
      </div>
    </main>
  )
}
