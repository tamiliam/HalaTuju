'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import FieldLabel from '@/components/FieldLabel'
import InfoBox from '@/components/InfoBox'
import AwardComprehensionQuiz from '@/components/AwardComprehensionQuiz'
import {
  getStudentAward, respondToAward, recordComprehensionPass,
  sendGuarantorPin, checkGuarantorPin,
  type StudentAward, type BursaryPreview, type BursaryAgreement,
} from '@/lib/api'
import { formatNric, formatMoney2dp } from '@/lib/scholarship'

/** Guardian relationship codes — must match Consent.GUARDIAN_RELATIONSHIPS on
 *  the backend (mirrors ScholarshipConsent's list). */
const GUARDIAN_RELATIONSHIPS = [
  'father', 'mother', 'legal_guardian', 'grandparent', 'brother', 'sister', 'relative',
] as const
type GuardianRelationship = typeof GUARDIAN_RELATIONSHIPS[number]

/** The student's award-acceptance screen (F8b).
 *
 *  Plain accept/decline when the bursary flag is OFF (no `bursary_preview`).
 *  When an agreement is in play (`bursary_preview` present, not yet signed), the
 *  page becomes the SIGNING page: the full agreement body + a student typed-name
 *  signature (adult) + a parent/guardian surety (guarantor) block, all on the
 *  same device, same session. The donor is never named. */
export default function ScholarshipAwardPage() {
  const { t, locale } = useT()
  const { status, token } = useAuth()
  const router = useRouter()

  const [offer, setOffer] = useState<StudentAward | null>(null)
  const [finalising, setFinalising] = useState(false)
  const [isMinor, setIsMinor] = useState(false)
  const [preview, setPreview] = useState<BursaryPreview | null>(null)
  const [signed, setSigned] = useState<BursaryAgreement | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [justSigned, setJustSigned] = useState(false)
  // The student must pass the comprehension quiz ("Understand" step) before the signing form.
  const [comprehensionPassed, setComprehensionPassed] = useState(false)

  // Guardian modal (minors, plain flow only — used when there's no agreement)
  const [showGuardian, setShowGuardian] = useState(false)
  const [guardianName, setGuardianName] = useState('')
  const [guardianNric, setGuardianNric] = useState('')
  const [relationship, setRelationship] = useState<GuardianRelationship | ''>('')

  // ── Bursary signing fields ──
  // Student typed-name signature (adult: required; minor: optional) + the read-&-agree toggle.
  const [studentName, setStudentName] = useState('')
  const [studentNric, setStudentNric] = useState('')
  const [studentAgreed, setStudentAgreed] = useState(false)
  // Parent / guardian surety (the guarantor) block + their own stand-as-guarantor toggle.
  const [guarantorName, setGuarantorName] = useState('')
  const [guarantorNric, setGuarantorNric] = useState('')
  const [guarantorRel, setGuarantorRel] = useState<GuardianRelationship | ''>('')
  const [guarantorAgreed, setGuarantorAgreed] = useState(false)
  // Parent PIN (same-session gate): a one-time SMS code to the guarantor's PRE-DECLARED,
  // LOCKED phone must be confirmed before the surety signature is accepted. The student
  // never sees or edits the number — that's what makes the parent check meaningful.
  const [phoneVerified, setPhoneVerified] = useState(false)
  const [pinSent, setPinSent] = useState(false)
  const [pinCode, setPinCode] = useState('')
  const [phoneHint, setPhoneHint] = useState('')
  const [pinBusy, setPinBusy] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (status === 'loading') return
    if (status === 'anonymous' || status === 'needs-nric' || !token) {
      router.replace('/scholarship/apply')
      return
    }
    getStudentAward({ token })
      .then((res) => {
        if (!active) return
        setOffer(res.offer)
        setIsMinor(res.is_minor)
        setFinalising(!!res.finalising)
        setPreview(res.bursary_preview ?? null)
        setSigned(res.bursary_agreement ?? null)
      })
      .catch(() => { if (active) setOffer(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [status, token, router])

  function wrap(children: React.ReactNode) {
    return (
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className="container mx-auto w-full max-w-3xl flex-1 px-6 py-10">
          {children}
        </main>
        <AppFooter />
      </div>
    )
  }

  /** Friendly message for a backend error code; falls back to a generic line. The
   *  parent_ic_* mismatches map to one clear "doesn't match the IC on file" line. */
  function messageForCode(code: string): string {
    const known = [
      'no_offer', 'guardian_required', 'bad_action',
      'student_signature_required', 'guarantor_required',
      'parent_ic_missing', 'parent_ic_required',
      'parent_ic_nric_mismatch', 'parent_ic_name_mismatch',
      'guarantor_phone_missing', 'guarantor_phone_unverified',
    ]
    return known.includes(code)
      ? t(`scholarship.award.error.${code}`)
      : t('scholarship.award.error.generic')
  }

  /** Friendly message for a parent-PIN error code; falls back to a generic line. */
  function pinMessage(code: string): string {
    const known = [
      'guarantor_phone_missing', 'rate_limited', 'invalid_number',
      'unconfigured', 'incorrect', 'code_required', 'bursary_disabled', 'no_offer',
    ]
    return known.includes(code)
      ? t(`scholarship.award.bursary.guarantor.pin.error.${code}`)
      : t('scholarship.award.bursary.guarantor.pin.error.generic')
  }

  async function sendPin() {
    if (!token) return
    setPinBusy(true)
    setPinError(null)
    try {
      const res = await sendGuarantorPin({ token })
      setPhoneHint(res.phone_hint || '')
      setPinSent(true)
    } catch (e) {
      setPinError(pinMessage((e as Error & { code?: string }).code || ''))
    } finally {
      setPinBusy(false)
    }
  }

  async function verifyPin() {
    if (!token || !pinCode.trim()) return
    setPinBusy(true)
    setPinError(null)
    try {
      const res = await checkGuarantorPin(pinCode.trim(), { token })
      if (res.verified) setPhoneVerified(true)
      else setPinError(pinMessage('incorrect'))
    } catch (e) {
      setPinError(pinMessage((e as Error & { code?: string }).code || 'incorrect'))
    } finally {
      setPinBusy(false)
    }
  }

  // The plain (flag-off) acceptance — unchanged behaviour.
  async function acceptPlain(guardian?: { name: string; relationship: string; nric: string }) {
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
      const res = await getStudentAward({ token })
      if (res.finalising) { setFinalising(true); setOffer(null) }
      else router.push('/scholarship/onboarding')
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      setError(messageForCode(code))
    } finally {
      setSubmitting(false)
    }
  }

  function handleAcceptClick() {
    if (isMinor) { setShowGuardian(true); return }
    void acceptPlain()
  }

  function handleGuardianSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!guardianName.trim() || !relationship || !guardianNric.trim()) return
    void acceptPlain({ name: guardianName.trim(), relationship, nric: guardianNric.trim() })
  }

  // The bursary SIGNING acceptance — student typed-name (adult) + the guarantor surety.
  async function signAndAccept(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      await respondToAward(
        {
          action: 'accept', locale,
          granted_by: 'guardian',
          // For a minor the guardian IS the guarantor: send the guardian_* fields too
          // so the share-consent guardian gate is satisfied in the same step.
          guardian_name: guarantorName.trim(),
          guardian_relationship: guarantorRel || '',
          guardian_nric: guarantorNric.trim(),
          student_signed_name: studentName.trim(),
          student_signed_nric: studentNric.trim(),
          guarantor_name: guarantorName.trim(),
          guarantor_nric: guarantorNric.trim(),
          guarantor_relationship: guarantorRel || '',
        },
        { token },
      )
      const res = await getStudentAward({ token })
      setOffer(res.offer)
      setPreview(res.bursary_preview ?? null)
      setSigned(res.bursary_agreement ?? null)
      setFinalising(!!res.finalising)
      setJustSigned(true)
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      setError(messageForCode(code))
    } finally {
      setSubmitting(false)
    }
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

  // Just signed (or already signed) the bursary agreement → confirmation + the PDF.
  if (justSigned || signed) {
    const pdfUrl = signed?.pdf_url || null
    return wrap(
      <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.award.bursary.signed.heading')}</h1>
        <p className="mx-auto mt-3 max-w-md text-gray-600">{t('scholarship.award.bursary.signed.body')}</p>
        {pdfUrl && (
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="btn-primary mt-6 inline-block">
            {t('scholarship.award.bursary.signed.download')}
          </a>
        )}
        <Link href="/scholarship/application" className="mt-3 block text-sm font-medium text-gray-500 hover:text-gray-700">
          {t('scholarship.award.empty.cta')}
        </Link>
      </div>
    )
  }

  // Award cool-off: accepted, being finalised — confirmation + onboarding open in a couple of days.
  if (finalising) {
    return wrap(
      <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
          <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.award.finalising.heading')}</h1>
        <p className="mx-auto mt-3 max-w-md text-gray-600">{t('scholarship.award.finalising.body')}</p>
        <Link href="/scholarship/application" className="btn-primary mt-6 inline-block">
          {t('scholarship.award.empty.cta')}
        </Link>
      </div>
    )
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

  // ── The bursary SIGNING page (agreement in play, not yet signed) ──
  if (preview) {
    // STEP 1 — "Understand": the comprehension quiz gates the signing form. The student
    // works through the 8 checkpoints; on completion we record the pass (best-effort) and
    // reveal the signing form below.
    if (!comprehensionPassed) {
      return wrap(
        <AwardComprehensionQuiz
          onComplete={() => {
            setComprehensionPassed(true)
            if (token) recordComprehensionPass({ token }).catch(() => {})
            window.scrollTo(0, 0)
          }}
        />,
      )
    }

    // STEP 2 — "Read & sign".
    // Both toggles required; an adult must type their name; the guarantor block is
    // always required (the guardian is the surety for a minor too).
    const studentNameOk = isMinor || studentName.trim().length > 0
    const guarantorOk = guarantorName.trim().length > 0 && guarantorNric.trim().length > 0 && !!guarantorRel
    const canSubmit = studentAgreed && guarantorAgreed && studentNameOk && guarantorOk && phoneVerified && !submitting

    return wrap(
      <form onSubmit={signAndAccept} className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.award.bursary.heading')}</h1>
          <p className="mt-2 text-gray-600">{t('scholarship.award.bursary.intro')}</p>
        </div>

        {/* Particulars summary */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-500">
            {t('scholarship.award.bursary.particulars')}
          </h2>
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wider text-gray-400">{t('scholarship.award.bursary.amount')}</dt>
              <dd className="text-lg font-bold text-gray-900">RM {formatMoney2dp(preview.award_amount ?? offer.amount)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-gray-400">{t('scholarship.award.bursary.schedule')}</dt>
              <dd className="text-sm text-gray-800">{preview.payment_schedule || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-gray-400">{t('scholarship.award.bursary.institution')}</dt>
              <dd className="text-sm text-gray-800">{preview.institution_name || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-gray-400">{t('scholarship.award.bursary.course')}</dt>
              <dd className="text-sm text-gray-800">{preview.course_name || '—'}</dd>
            </div>
          </dl>
        </div>

        {/* The full agreement body — server-rendered HTML (inline CSS, no donor data).
            Rendered inside a SANDBOXED iframe (sandbox="" → no allow-scripts): the
            document is isolated from the host page and cannot run scripts, so even
            though the HTML is trusted (our own backend, server-side-escaped, inline
            CSS only) there is no XSS path into the app. Constrained + scrollable. */}
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-500">
            {t('scholarship.award.bursary.documentTitle')}
          </h2>
          <iframe
            title={t('scholarship.award.bursary.documentTitle')}
            sandbox=""
            srcDoc={preview.rendered_html}
            className="h-[28rem] w-full rounded-2xl border bg-white shadow-inner"
          />
        </div>

        {error && <InfoBox kind="block">{error}</InfoBox>}

        {/* STUDENT signature */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">{t('scholarship.award.bursary.student.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('scholarship.award.bursary.student.intro')}</p>

          {!isMinor && (
            <div className="mt-4 space-y-4">
              <div>
                <FieldLabel required>{t('scholarship.award.bursary.student.signLabel')}</FieldLabel>
                <input
                  className="input"
                  placeholder={t('scholarship.award.bursary.student.signPlaceholder')}
                  value={studentName}
                  onChange={(e) => setStudentName(e.target.value)}
                />
              </div>
              <div>
                <FieldLabel>{t('scholarship.award.bursary.student.nricLabel')}</FieldLabel>
                <input
                  className="input font-mono"
                  placeholder="XXXXXX-XX-XXXX"
                  inputMode="numeric"
                  autoComplete="off"
                  value={studentNric}
                  onChange={(e) => setStudentNric(formatNric(e.target.value))}
                />
              </div>
            </div>
          )}

          <label className="mt-4 flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4"
              checked={studentAgreed}
              onChange={(e) => setStudentAgreed(e.target.checked)}
            />
            <span className="text-sm text-gray-800">{t('scholarship.award.bursary.student.agree')}</span>
          </label>
        </div>

        {/* PARENT / GUARANTOR (surety) — signs in-session, same device */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">{t('scholarship.award.bursary.guarantor.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('scholarship.award.bursary.guarantor.intro')}</p>

          <div className="mt-4 space-y-4">
            <div>
              <FieldLabel required>{t('scholarship.award.bursary.guarantor.name')}</FieldLabel>
              <input
                className="input"
                placeholder={t('scholarship.award.bursary.guarantor.namePlaceholder')}
                value={guarantorName}
                onChange={(e) => setGuarantorName(e.target.value)}
              />
            </div>
            <div>
              <FieldLabel required>{t('scholarship.award.bursary.guarantor.relationship')}</FieldLabel>
              <select
                className="input"
                value={guarantorRel}
                onChange={(e) => setGuarantorRel(e.target.value as GuardianRelationship | '')}
              >
                <option value="">{t('scholarship.award.guardian.relationshipPlaceholder')}</option>
                {GUARDIAN_RELATIONSHIPS.map((r) => (
                  <option key={r} value={r}>{t(`scholarship.consent.relationship.${r}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel required>{t('scholarship.award.bursary.guarantor.nric')}</FieldLabel>
              <input
                className="input font-mono"
                placeholder="XXXXXX-XX-XXXX"
                inputMode="numeric"
                autoComplete="off"
                value={guarantorNric}
                onChange={(e) => setGuarantorNric(formatNric(e.target.value))}
              />
            </div>
          </div>

          {/* Same-session parent verification — a one-time PIN to the parent's phone on
              file (read server-side, never editable here). Required before signing. */}
          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4">
            <p className="text-sm font-semibold text-gray-800">
              {t('scholarship.award.bursary.guarantor.pin.title')}
            </p>
            <p className="mt-1 text-sm text-gray-600">
              {t('scholarship.award.bursary.guarantor.pin.intro')}
            </p>

            {phoneVerified ? (
              <p className="mt-3 flex items-center gap-2 text-sm font-medium text-green-700">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {t('scholarship.award.bursary.guarantor.pin.verified')}
              </p>
            ) : !pinSent ? (
              <button
                type="button"
                onClick={sendPin}
                disabled={pinBusy}
                className="btn-primary mt-3 disabled:opacity-50"
              >
                {pinBusy ? t('scholarship.award.bursary.guarantor.pin.sending') : t('scholarship.award.bursary.guarantor.pin.send')}
              </button>
            ) : (
              <div className="mt-3 space-y-3">
                <p className="text-sm text-gray-700">
                  {t('scholarship.award.bursary.guarantor.pin.sentTo', { phone: phoneHint })}
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <div className="min-w-[10rem] flex-1">
                    <FieldLabel>{t('scholarship.award.bursary.guarantor.pin.codeLabel')}</FieldLabel>
                    <input
                      className="input font-mono tracking-widest"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      placeholder="••••••"
                      value={pinCode}
                      onChange={(e) => setPinCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={verifyPin}
                    disabled={pinBusy || !pinCode.trim()}
                    className="btn-primary disabled:opacity-50"
                  >
                    {pinBusy ? t('scholarship.award.bursary.guarantor.pin.verifying') : t('scholarship.award.bursary.guarantor.pin.verify')}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={sendPin}
                  disabled={pinBusy}
                  className="text-sm font-medium text-gray-500 hover:text-gray-700 disabled:opacity-50"
                >
                  {t('scholarship.award.bursary.guarantor.pin.resend')}
                </button>
              </div>
            )}

            {pinError && <p className="mt-2 text-sm text-red-600">{pinError}</p>}
          </div>

          <label className="mt-4 flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4"
              checked={guarantorAgreed}
              onChange={(e) => setGuarantorAgreed(e.target.checked)}
            />
            <span className="text-sm text-gray-800">{t('scholarship.award.bursary.guarantor.agree')}</span>
          </label>
        </div>

        {deadline && (
          <p className="text-sm text-gray-500">{t('scholarship.award.confirmed.acceptBy', { date: deadline })}</p>
        )}

        <div className="space-y-3">
          <button type="submit" disabled={!canSubmit} className="btn-primary w-full disabled:opacity-50">
            {submitting ? t('scholarship.award.bursary.signing') : t('scholarship.award.bursary.signSubmit')}
          </button>
          <button
            type="button"
            onClick={decline}
            disabled={submitting}
            className="block w-full text-sm font-medium text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            {t('scholarship.award.confirmed.decline')}
          </button>
        </div>

        <p className="text-xs text-gray-400">{t('scholarship.award.confirmed.heldNote')}</p>
      </form>
    )
  }

  // ── The plain (flag-off) accept/decline page — unchanged ──
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

      {/* Guardian modal — minor acceptance (plain flow) */}
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
