'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { signInWithPhone, verifyOTP, signInWithGoogle } from '@/lib/supabase'
import { syncProfile, claimNric, type SyncProfileData } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { KEY_PENDING_AUTH_ACTION, KEY_RESUME_ACTION, KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS, KEY_REFERRAL_SOURCE } from '@/lib/storage'
import IcInput from './IcInput'
import { validateIc } from '@/lib/ic-utils'

type ModalStep = 'login' | 'otp' | 'ic'

export default function AuthGateModal() {
  const router = useRouter()
  const { t } = useT()
  const {
    authGateReason,
    authGateCourseId,
    hideAuthGate,
    isAuthenticated,
    isAnonymous,
    token,
    session,
    status,
    profile,
  } = useAuth()

  const [step, setStep] = useState<ModalStep>('login')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [name, setName] = useState('')
  const [ic, setIc] = useState('')
  const [icValid, setIcValid] = useState(false)
  const [loading, setLoading] = useState(false)
  const [pendingProfileRedirect, setPendingProfileRedirect] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [existingName, setExistingName] = useState<string | null>(null)

  // Reset when modal opens; if already authenticated (has NRIC), sync and resume
  useEffect(() => {
    if (authGateReason) {
      setPhone('')
      setOtp('')
      setName('')
      setIc('')
      setIcValid(false)
      setError(null)
      setLoading(false)
      setShowConfirm(false)
      setExistingName(null)

      if (isAuthenticated) {
        // Already has identity — sync localStorage to backend and resume action
        handleReturningUser()
        return
      }
      setStep('login')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authGateReason])

  // Advance when user authenticates mid-modal
  useEffect(() => {
    if (!authGateReason || status === 'loading' || status === 'anonymous') return
    if (step === 'ic') return

    if (status === 'ready') {
      // RETURNING USER — has NRIC, sync and close
      handleReturningUser()
    } else if (status === 'needs-nric') {
      // NEW USER — needs NRIC verification
      const googleName = session?.user?.user_metadata?.full_name
        || session?.user?.user_metadata?.name
      if (googleName && !name) setName(googleName)
      setStep('ic')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, authGateReason])

  // Redirect after profile-reason auth completes — reads fresh status, not stale closure
  useEffect(() => {
    if (!pendingProfileRedirect || status === 'loading') return
    setPendingProfileRedirect(false)
    if (status === 'ready') {
      const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
      router.push(hasGrades ? '/dashboard' : '/onboarding/exam-type')
    } else {
      router.push('/onboarding/exam-type')
    }
  }, [pendingProfileRedirect, status, profile, router])

  if (!authGateReason) return null

  const reasonKey =
    authGateReason === 'quiz'
      ? 'quizReason'
      : authGateReason === 'save'
        ? 'saveReason'
        : authGateReason === 'eligible'
          ? 'eligibleReason'
          : authGateReason === 'profile'
            ? 'profileReason'
            : authGateReason === 'loadmore'
              ? 'loadmoreReason'
              : 'reportReason'

  const formatPhone = (raw: string) => {
    let formatted = raw.trim()
    if (!formatted.startsWith('+')) {
      formatted = formatted.startsWith('0')
        ? '+6' + formatted
        : '+60' + formatted
    }
    return formatted
  }

  const syncLocalStorageToBackend = async (tkn: string) => {
    const syncData: SyncProfileData = {}
    try {
      const grades = localStorage.getItem(KEY_GRADES)
      if (grades) syncData.grades = JSON.parse(grades)
      const prof = localStorage.getItem(KEY_PROFILE)
      if (prof) {
        const p = JSON.parse(prof)
        if (p.gender) syncData.gender = p.gender
        if (p.nationality) syncData.nationality = p.nationality
        if (p.state) syncData.preferred_state = p.state
        if (p.colorblind) syncData.colorblind = p.colorblind
        if (p.disability) syncData.disability = p.disability
      }
      const signals = localStorage.getItem(KEY_QUIZ_SIGNALS)
      if (signals) syncData.student_signals = JSON.parse(signals)
    } catch { /* ignore */ }
    if (name.trim()) syncData.name = name.trim()
    const ref = localStorage.getItem(KEY_REFERRAL_SOURCE)
    if (ref) syncData.referral_source = ref
    try {
      await syncProfile(syncData, { token: tkn })
    } catch { /* non-critical */ }
  }

  const finishAndClose = () => {
    const reason = authGateReason
    const courseId = authGateCourseId
    if (reason === 'save' && courseId) {
      localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'save', courseId }))
    } else if (reason === 'report') {
      localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'report' }))
    } else if (reason === 'eligible') {
      localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'eligible' }))
    } else if (reason === 'loadmore') {
      localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'loadmore' }))
    }
    localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
    hideAuthGate()
    setLoading(false)
    if (reason === 'quiz') {
      router.push('/quiz')
    } else if (reason === 'profile') {
      setPendingProfileRedirect(true)
    }
  }

  const handleReturningUser = async () => {
    if (!token) return
    await syncLocalStorageToBackend(token)
    finishAndClose()
  }

  const handlePhoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { error } = await signInWithPhone(formatPhone(phone))
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }
    setStep('otp')
    setLoading(false)
  }

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { error } = await verifyOTP(formatPhone(phone), otp)
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }
    // Session set by onAuthStateChange → useEffect advances
    setLoading(false)
  }

  const handleGoogleLogin = async () => {
    localStorage.setItem(
      KEY_PENDING_AUTH_ACTION,
      JSON.stringify({ reason: authGateReason, courseId: authGateCourseId })
    )
    setLoading(true)
    setError(null)

    // Always use signInWithGoogle — not linkIdentity.
    // linkIdentity redirects to Google before errors can be caught locally.
    // For returning users whose Google identity is already claimed,
    // linkIdentity silently fails at the Supabase callback, leaving the
    // anonymous session active. signInWithGoogle works for both new and
    // returning users. Anonymous users have no data to preserve (NRIC gate
    // blocks all writes), so orphaning the anonymous session is harmless.
    const { error } = await signInWithGoogle()
    if (error) {
      setError(error.message)
      setLoading(false)
    }
  }

  const handleIcSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const err = validateIc(ic)
    if (err) { setError(err); return }
    if (!token) return

    setLoading(true)
    setError(null)

    try {
      const result = await claimNric(ic, false, { token })

      if (result.status === 'created' || result.status === 'linked') {
        await syncLocalStorageToBackend(token)
        finishAndClose()
      } else if (result.status === 'exists') {
        setExistingName(result.name || null)
        setShowConfirm(true)
        setLoading(false)
      }
    } catch {
      setError(t('authGate.icError') || 'Failed to verify NRIC')
      setLoading(false)
    }
  }

  const handleConfirmClaim = async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      await claimNric(ic, true, { token })
      await syncLocalStorageToBackend(token)
      finishAndClose()
    } catch {
      setError(t('authGate.claimError') || 'Failed to claim NRIC')
      setLoading(false)
    }
  }

  const handleDismiss = () => {
    localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
    hideAuthGate()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleDismiss()
      }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <h2 className="text-xl font-bold text-gray-900 text-center mb-2">
            {t('authGate.title')}
          </h2>
          <p className="text-gray-600 text-center mb-6">
            {t(`authGate.${reasonKey}`)}
          </p>

          {/* Benefits (login step only) */}
          {step === 'login' && (
            <div className="bg-primary-50 rounded-xl p-4 mb-6">
              <ul className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <svg className="w-5 h-5 text-primary-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    {t(`authGate.benefit${i}`)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          {/* Login Step */}
          {step === 'login' && (
            <>
              <form onSubmit={handlePhoneSubmit} className="space-y-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('authGate.phoneNumber')}
                  </label>
                  <div className="flex">
                    <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                      +60
                    </span>
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="12 345 6789"
                      className="input rounded-l-none"
                      required
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={loading || !phone}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {loading ? t('authGate.sending') : t('authGate.sendCode')}
                </button>
              </form>

              <div className="relative mb-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-gray-500">{t('authGate.or')}</span>
                </div>
              </div>

              <button
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 px-6 py-3 border-2 border-gray-200 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                {t('authGate.googleLogin')}
              </button>
            </>
          )}

          {/* OTP Step */}
          {step === 'otp' && (
            <form onSubmit={handleOtpSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('authGate.enterOTP')}
                </label>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  maxLength={6}
                  className="input text-center text-2xl tracking-widest"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="btn-primary w-full disabled:opacity-50"
              >
                {loading ? t('authGate.verifying') : t('authGate.verifyCode')}
              </button>
              <button
                type="button"
                onClick={() => { setStep('login'); setOtp(''); setError(null) }}
                className="w-full text-gray-600 hover:text-gray-900 text-sm"
              >
                {t('authGate.differentPhone')}
              </button>
            </form>
          )}

          {/* IC Step */}
          {step === 'ic' && (
            <>
              {showConfirm ? (
                <div className="space-y-4">
                  <p className="text-gray-600 text-center">
                    {t('authGate.icExistsMessage') || `This NRIC is already registered${existingName ? ` to ${existingName}` : ''}. Is this you?`}
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setShowConfirm(false); setIc(''); setError(null) }}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                    >
                      {t('authGate.icNotMe') || 'No, not me'}
                    </button>
                    <button
                      onClick={handleConfirmClaim}
                      disabled={loading}
                      className="flex-1 btn-primary disabled:opacity-50"
                    >
                      {loading ? '...' : (t('authGate.icYesMe') || "Yes, that's me")}
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleIcSubmit} className="space-y-4">
                  <p className="text-gray-600 text-center mb-2">
                    {t('authGate.icSubtitle')}
                  </p>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('authGate.nameLabel')}
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder={t('authGate.namePlaceholder')}
                      className="input"
                    />
                  </div>
                  <IcInput
                    value={ic}
                    onChange={setIc}
                    onValidChange={setIcValid}
                    label={t('authGate.icLabel')}
                  />
                  <button
                    type="submit"
                    disabled={!icValid || loading}
                    className="btn-primary w-full disabled:opacity-50"
                  >
                    {loading ? '...' : t('authGate.icContinue')}
                  </button>
                  <p className="text-xs text-gray-400 text-center">
                    {t('authGate.icPrivacy')}
                  </p>
                </form>
              )}
            </>
          )}

          {/* Dismiss */}
          <button
            onClick={handleDismiss}
            className="w-full text-gray-500 hover:text-gray-700 text-sm mt-4 text-center"
          >
            {t('authGate.continueBrowsing')}
          </button>
        </div>
      </div>
    </div>
  )
}
