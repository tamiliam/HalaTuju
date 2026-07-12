'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { getMyScholarshipApplications, getStudentAward, getBursaryAgreement, type ScholarshipApplication, type StudentAward, type BursaryAgreement } from '@/lib/api'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'
import ActionCentre from '@/components/ActionCentre'
import { showsActionCentre, isFundedStatus } from '@/lib/scholarship'
import InterviewBookingPanel from '@/components/scholarship/InterviewBookingPanel'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'

/**
 * The post-submission home for an applicant. A shortlisted student completes
 * their follow-up (quiz, deeper info, documents, consent) here; anyone else
 * sees a neutral "received" status. Unauthenticated visitors are sent to apply.
 *
 * Wrapped in the standard AppHeader/AppFooter so it never looks like a dead-end
 * page — the student keeps full site navigation after submitting.
 */
export default function ScholarshipApplicationPage() {
  const { t } = useT()
  const { status, token, profile } = useAuth()
  const router = useRouter()
  const [app, setApp] = useState<ScholarshipApplication | null>(null)
  const [award, setAward] = useState<StudentAward | null>(null)
  // Gates the award/onboarding panel. Default false: the accept→onboarding flow
  // isn't exposed yet (students are invited by a later email), so the panel stays
  // hidden until the backend flag AWARD_ACCEPTANCE_ENABLED is turned on.
  const [acceptanceEnabled, setAcceptanceEnabled] = useState(false)
  const [bursary, setBursary] = useState<BursaryAgreement | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    if (status === 'loading') return
    if (status === 'anonymous' || status === 'needs-nric' || !token) {
      router.replace('/scholarship/apply')
      return
    }
    getMyScholarshipApplications({ token })
      .then((res) => { if (active) setApp(res.applications[0] ?? null) })
      .catch(() => { if (active) setApp(null) })
      .finally(() => { if (active) setLoading(false) })
    // The award offer is fetched alongside the application so the "accept your
    // award / complete onboarding" panel can show. No offer → endpoint returns
    // { offer: null }; on any error we simply hide the panel.
    getStudentAward({ token })
      .then((res) => {
        if (!active) return
        setAward(res.offer)
        setAcceptanceEnabled(!!res.acceptance_enabled)
      })
      .catch(() => { if (active) setAward(null) })
    // Bursary agreement (flag-gated): a signed student gets a small "your agreement"
    // panel with a PDF download. 404s while the flag is off / unsigned → hide it.
    getBursaryAgreement({ token })
      .then((res) => { if (active) setBursary(res) })
      .catch(() => { if (active) setBursary(null) })
    return () => { active = false }
  }, [status, token, router])

  // Where our communications will go — the verified account email (the profile's
  // contact email if set, otherwise the Google sign-in address).
  const commsEmail = profile?.contact_email || profile?.email || ''

  // The shortlisted view needs the extra width for the desktop step-rail.
  // Other status cards (received/accepted/none) keep the narrower max-w-2xl.
  const isShortlisted = app?.status === 'shortlisted'

  function wrap(children: React.ReactNode) {
    return (
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className={`container mx-auto w-full flex-1 px-6 py-10 ${isShortlisted ? 'max-w-2xl lg:max-w-4xl' : 'max-w-2xl'}`}>
          <h1 className="mb-6 text-2xl font-bold text-gray-900">{t('scholarship.application.title')}</h1>
          {awardPanel()}
          {bursaryPanel()}
          {children}
        </main>
        <AppFooter />
      </div>
    )
  }

  // "Next: accept your award / complete onboarding" — shown only when the
  // student has an award offer. An un-accepted offer (status 'offered') points
  // to the award page; an accepted-but-not-yet-onboarded award points to
  // onboarding. Once onboarded (onboarded_at set) the panel disappears.
  function awardPanel() {
    // Embargoed for now: the accept→onboarding flow isn't tested end-to-end, so we
    // keep the panel hidden until AWARD_ACCEPTANCE_ENABLED is turned on (no deploy).
    if (!award || !acceptanceEnabled) return null

    // Bursary flow: once the student has SIGNED (a bursary agreement exists) but the
    // agreement isn't yet fully executed — the application only reaches a funded state
    // (active/maintenance) when the Foundation has counter-signed — we do NOT route them
    // to the portal yet. "We do not land them in the portal until everyone has signed."
    const signedAgreement = !!bursary
    const fullyExecuted = isFundedStatus(app?.status || '')
    if (signedAgreement && !fullyExecuted) {
      return (
        <div className="mb-6 rounded-2xl border border-blue-200 bg-blue-50 p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <span className="shrink-0 text-blue-600" aria-hidden>✅</span>
            <div className="flex-1">
              <h2 className="font-semibold text-gray-900">{t('scholarship.application.awardPanel.awaitingTitle')}</h2>
              <p className="mt-1 text-sm text-gray-700">{t('scholarship.application.awardPanel.awaitingBody')}</p>
            </div>
          </div>
        </div>
      )
    }

    const accepted = award.status !== 'offered'   // active / sponsored / etc.
    if (accepted && app?.onboarded_at) return null
    const href = accepted ? '/scholarship/onboarding' : '/scholarship/award'
    const cta = accepted
      ? t('scholarship.application.awardPanel.onboardingCta')
      : t('scholarship.application.awardPanel.acceptCta')
    const body = accepted
      ? t('scholarship.application.awardPanel.onboardingBody')
      : t('scholarship.application.awardPanel.acceptBody')
    return (
      <div className="mb-6 rounded-2xl border border-blue-200 bg-blue-50 p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="shrink-0 text-blue-600" aria-hidden>🎉</span>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900">{t('scholarship.application.awardPanel.title')}</h2>
            <p className="mt-1 text-sm text-gray-700">{body}</p>
            <Link href={href} className="btn-primary mt-3 inline-block">{cta}</Link>
          </div>
        </div>
      </div>
    )
  }

  // "Your bursary agreement" — a minimal panel with a PDF download, shown only once
  // the student has signed (getBursaryAgreement returned an agreement). Flag-gated:
  // null while the feature is off or unsigned. No donor identity anywhere.
  function bursaryPanel() {
    if (!bursary || !bursary.pdf_url) return null
    return (
      <div className="mb-6 rounded-2xl border border-green-200 bg-green-50 p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="shrink-0 text-green-600" aria-hidden>📄</span>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900">{t('scholarship.application.bursaryPanel.title')}</h2>
            <p className="mt-1 text-sm text-gray-700">{t('scholarship.application.bursaryPanel.body')}</p>
            <a
              href={bursary.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary mt-3 inline-block"
            >
              {t('scholarship.application.bursaryPanel.download')}
            </a>
          </div>
        </div>
      </div>
    )
  }

  // Email note + onward navigation, shown under the status card so the page is
  // never a dead end. `email` defaults on; pass false where an email note is
  // already shown nearby (the received screen's "What happens next" box) to
  // avoid repeating it.
  function nav({ email = true }: { email?: boolean } = {}) {
    return (
      <>
        {email && commsEmail && (
          <p className="mt-4 text-sm text-gray-500">
            {t('scholarship.application.emailNote', { email: commsEmail })}
          </p>
        )}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/search" className="btn-primary inline-block">
            {t('scholarship.application.browseCta')}
          </Link>
          <Link href="/" className="inline-block rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            {t('scholarship.application.homeCta')}
          </Link>
        </div>
      </>
    )
  }

  if (status === 'loading' || loading) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  if (!app) {
    return wrap(
      <div className="rounded-2xl border bg-white p-6 text-center shadow-sm">
        <p className="mb-4 text-gray-700">{t('scholarship.application.none')}</p>
        <Link href="/scholarship/apply" className="btn-primary inline-block">
          {t('scholarship.application.applyCta')}
        </Link>
      </div>
    )
  }

  if (app.status === 'shortlisted') {
    return wrap(<ScholarshipNextSteps initialApp={app} token={token} studentName={profile?.name} profile={profile} onSubmitted={setApp} />)
  }

  // Post-submit (profile_complete and beyond): the application is LOCKED — having
  // consented, reviewed the final values and submitted, the student can no longer
  // see or edit the 5-step form. Their only surface is the Action Centre, where
  // they respond to queries and upload requested documents (in place). When nothing
  // is pending it shows a calm "all set — we'll be in touch" message.
  //
  // This MUST include the funded post-award states (awarded/active/maintenance) — a
  // funded student still uses the Action Centre, e.g. to upload their bank details
  // (the bank-details task is created + served for them by the backend). Gating this on
  // a hand-listed subset previously left awarded students with the task in the API but
  // no surface to act on it. `showsActionCentre` is the single tested source of truth.
  if (showsActionCentre(app.status)) {
    const funded = isFundedStatus(app.status)
    return wrap(
      <>
        {/* The interview booking panel is for the pre-award review states only. */}
        {!funded && <InterviewBookingPanel applicationId={app.id} token={token} />}
        <ActionCentre
          token={token}
          studentName={profile?.name}
          email={commsEmail || app.notify_email || ''}
          applicationId={app.id}
          incomeRoute={app.income_route || ''}
          incomeEarner={app.income_earner || ''}
          contactPhone={app.contact_phone || profile?.contact_phone || ''}
          formLocked
          funded={funded}
        />
      </>,
    )
  }

  // NB: 'accepted' is masked to 'interviewed' by ApplicationReadSerializer.get_status
  // (an internal decision the super-admin can still reverse — the student must not
  // perceive it), so it renders the Action Centre above, never a celebratory card.
  // Real good news reaches the student only via a concrete award offer (awardPanel).

  // submitted / profile_complete / rejected / withdrawn — keep it neutral (the
  // decision email is sent separately; we don't expose a raw "rejected" status here).
  // "What happens next" lives HERE (post-submit), where it actually applies.
  return wrap(
    <>
      <div className="rounded-2xl border border-green-200 bg-green-50 p-6">
        <h2 className="mb-2 font-semibold text-gray-900">{t('scholarship.application.receivedTitle')}</h2>
        <p className="text-gray-700">{t('scholarship.application.receivedBody')}</p>
      </div>
      <div className="mt-6 rounded-2xl border bg-white p-5 shadow-sm">
        <h3 className="mb-3 font-semibold text-gray-900">{t('scholarship.nextSteps.whatNext.title')}</h3>
        <ol className="space-y-3">
          {['step1', 'step2', 'step3', 'step4'].map((s, i) => (
            <li key={s} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700 text-xs font-semibold">
                {i + 1}
              </span>
              <span className="text-sm text-gray-700">{t(`scholarship.nextSteps.whatNext.${s}`)}</span>
            </li>
          ))}
        </ol>
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-primary-50 p-3">
          <span className="shrink-0 text-primary-600" aria-hidden>✉️</span>
          <p className="text-sm text-gray-700">
            {t('scholarship.nextSteps.whatNext.emailNote', {
              email: app.notify_email || t('scholarship.nextSteps.whatNext.yourEmail'),
            })}
          </p>
        </div>
      </div>
      {/* email note suppressed here — the box above already states the address + spam */}
      {nav({ email: false })}
    </>
  )
}
