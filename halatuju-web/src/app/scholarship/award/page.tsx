'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import FieldLabel from '@/components/FieldLabel'
import { getStudentAward, respondToAward, type StudentAward } from '@/lib/api'
import { formatNric, formatMoney2dp } from '@/lib/scholarship'

/** Guardian relationship codes — must match Consent.GUARDIAN_RELATIONSHIPS on
 *  the backend (mirrors ScholarshipConsent's list). */
const GUARDIAN_RELATIONSHIPS = [
  'father', 'mother', 'legal_guardian', 'grandparent', 'brother', 'sister', 'relative',
] as const
type GuardianRelationship = typeof GUARDIAN_RELATIONSHIPS[number]

/** The student's award-acceptance screen (F8b). Shows the confirmed-funding
 *  offer; an adult accepts in one tap, a minor accepts via a guardian modal.
 *  Wrapped in AppHeader/AppFooter so it never reads as a dead-end page. */
export default function ScholarshipAwardPage() {
  const { t, locale } = useT()
  const { status, token } = useAuth()
  const router = useRouter()

  const [offer, setOffer] = useState<StudentAward | null>(null)
  const [isMinor, setIsMinor] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Guardian modal (minors only)
  const [showGuardian, setShowGuardian] = useState(false)
  const [guardianName, setGuardianName] = useState('')
  const [guardianNric, setGuardianNric] = useState('')
  const [relationship, setRelationship] = useState<GuardianRelationship | ''>('')

  useEffect(() => {
    let active = true
    if (status === 'loading') return
    if (status === 'anonymous' || status === 'needs-nric' || !token) {
      router.replace('/scholarship/apply')
      return
    }
    getStudentAward({ token })
      .then((res) => { if (active) { setOffer(res.offer); setIsMinor(res.is_minor) } })
      .catch(() => { if (active) setOffer(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [status, token, router])

  function wrap(children: React.ReactNode) {
    return (
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className="container mx-auto w-full max-w-2xl flex-1 px-6 py-10">
          {children}
        </main>
        <AppFooter />
      </div>
    )
  }

  /** Friendly message for a backend error code; falls back to a generic line. */
  function messageForCode(code: string): string {
    const known = ['no_offer', 'guardian_required', 'bad_action']
    return known.includes(code)
      ? t(`scholarship.award.error.${code}`)
      : t('scholarship.award.error.generic')
  }

  async function accept(guardian?: { name: string; relationship: string; nric: string }) {
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      await respondToAward(
        guardian
          ? {
              action: 'accept', locale, granted_by: 'guardian',
              guardian_name: guardian.name, guardian_relationship: guardian.relationship,
              guardian_nric: guardian.nric,
            }
          : { action: 'accept', locale },
        { token },
      )
      router.push('/scholarship/onboarding')
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      setError(messageForCode(code))
    } finally {
      setSubmitting(false)
    }
  }

  function handleAcceptClick() {
    if (isMinor) { setShowGuardian(true); return }
    void accept()
  }

  function handleGuardianSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!guardianName.trim() || !relationship || !guardianNric.trim()) return
    void accept({ name: guardianName.trim(), relationship, nric: guardianNric.trim() })
  }

  async function decline() {
    if (!token) return
    if (!window.confirm(t('scholarship.award.declineConfirm'))) return
    setSubmitting(true)
    setError(null)
    try {
      await respondToAward({ action: 'decline', locale }, { token })
      router.push('/scholarship/application')
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      setError(messageForCode(code))
    } finally {
      setSubmitting(false)
    }
  }

  if (status === 'loading' || loading) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  // Gentle empty state — no offer waiting.
  if (!offer) {
    return wrap(
      <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
        <p className="mb-5 text-gray-700">{t('scholarship.award.empty.body')}</p>
        <Link href="/scholarship/application" className="btn-primary inline-block">
          {t('scholarship.award.empty.cta')}
        </Link>
      </div>
    )
  }

  const localeTag = ({ en: 'en-GB', ms: 'ms-MY', ta: 'ta-IN' } as Record<string, string>)[locale] || 'en-GB'
  const deadline = offer.accept_deadline
    ? new Date(offer.accept_deadline).toLocaleDateString(localeTag, { day: 'numeric', month: 'long', year: 'numeric' })
    : ''

  return wrap(
    <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
      {/* Award badge */}
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
        <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 002.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.492a46.32 46.32 0 012.916.52 6.003 6.003 0 01-5.395 4.972m0 0a6.726 6.726 0 01-2.749 1.35m0 0a6.772 6.772 0 01-3.044 0" />
        </svg>
      </div>

      <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.award.confirmed.heading')}</h1>
      <p className="mx-auto mt-3 max-w-md text-gray-600">{t('scholarship.award.confirmed.body')}</p>

      {/* Amount + deadline */}
      <div className="mx-auto mt-6 max-w-xs rounded-xl bg-gray-50 p-4">
        <p className="text-sm text-gray-500">{t('scholarship.award.confirmed.amountLabel')}</p>
        <p className="text-3xl font-bold text-gray-900">RM {formatMoney2dp(offer.amount)}</p>
        {deadline && (
          <p className="mt-2 text-sm text-gray-500">
            {t('scholarship.award.confirmed.acceptBy', { date: deadline })}
          </p>
        )}
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <button
        type="button"
        onClick={handleAcceptClick}
        disabled={submitting}
        className="btn-primary mt-6 w-full disabled:opacity-50"
      >
        {submitting ? t('scholarship.award.confirmed.accepting') : t('scholarship.award.confirmed.accept')}
      </button>
      <button
        type="button"
        onClick={decline}
        disabled={submitting}
        className="mt-3 block w-full text-sm font-medium text-gray-500 hover:text-gray-700 disabled:opacity-50"
      >
        {t('scholarship.award.confirmed.decline')}
      </button>

      <p className="mt-6 text-xs text-gray-400">{t('scholarship.award.confirmed.heldNote')}</p>

      {/* Guardian modal — minor acceptance */}
      {showGuardian && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form
            onSubmit={handleGuardianSubmit}
            className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 text-left shadow-xl"
          >
            <div>
              <h2 className="text-lg font-bold text-gray-900">{t('scholarship.award.guardian.title')}</h2>
              <p className="mt-1 text-sm text-gray-600">{t('scholarship.award.guardian.intro')}</p>
            </div>

            <div>
              <FieldLabel required>{t('scholarship.award.guardian.name')}</FieldLabel>
              <input
                className="input"
                placeholder={t('scholarship.award.guardian.namePlaceholder')}
                value={guardianName}
                onChange={(e) => setGuardianName(e.target.value)}
              />
            </div>

            <div>
              <FieldLabel required>{t('scholarship.award.guardian.relationship')}</FieldLabel>
              <select
                className="input"
                value={relationship}
                onChange={(e) => setRelationship(e.target.value as GuardianRelationship | '')}
              >
                <option value="">{t('scholarship.award.guardian.relationshipPlaceholder')}</option>
                {GUARDIAN_RELATIONSHIPS.map((r) => (
                  <option key={r} value={r}>
                    {t(`scholarship.consent.relationship.${r}`)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <FieldLabel required>{t('scholarship.award.guardian.nric')}</FieldLabel>
              <input
                className="input font-mono"
                placeholder="XXXXXX-XX-XXXX"
                inputMode="numeric"
                autoComplete="off"
                value={guardianNric}
                onChange={(e) => setGuardianNric(formatNric(e.target.value))}
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex flex-wrap gap-3 pt-1">
              <button
                type="submit"
                disabled={submitting || !guardianName.trim() || !relationship || !guardianNric.trim()}
                className="btn-primary disabled:opacity-50"
              >
                {submitting ? t('scholarship.award.confirmed.accepting') : t('scholarship.award.guardian.submit')}
              </button>
              <button
                type="button"
                onClick={() => { setShowGuardian(false); setError(null) }}
                disabled={submitting}
                className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                {t('scholarship.award.guardian.cancel')}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
