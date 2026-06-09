'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import {
  getMyScholarshipApplications,
  submitOnboarding,
  type ScholarshipApplication,
} from '@/lib/api'

type Step = 'welcome' | 'questions' | 'finish'
const STEP_ORDER: Step[] = ['welcome', 'questions', 'finish']
// Progress labels (Award is the prior page; shown for context only).
const PROGRESS_STEPS = ['award', 'welcome', 'questions', 'finish'] as const

const WELCOME_CARDS = ['stages', 'checkin', 'anonymous'] as const

const CheckIcon = () => (
  <svg className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

/** Post-award onboarding wizard (F8b). A single page with a 3-step state:
 *  Welcome (acknowledgements) → Questions → Finish (submit + confirmation). */
export default function ScholarshipOnboardingPage() {
  const { t } = useT()
  const { status, token } = useAuth()
  const router = useRouter()

  const [app, setApp] = useState<ScholarshipApplication | null>(null)
  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState<Step>('welcome')

  // Question answers
  const [lookingForward, setLookingForward] = useState('')
  const [living, setLiving] = useState<'campus' | 'home' | ''>('')
  const [wantsMentor, setWantsMentor] = useState<boolean | null>(null)

  // Finish-step submission
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [notAwarded, setNotAwarded] = useState(false)
  const [done, setDone] = useState(false)

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
    return () => { active = false }
  }, [status, token, router])

  // On entering the Finish step, submit once.
  useEffect(() => {
    if (step !== 'finish' || !token || !app || submitting || done || notAwarded) return
    let active = true
    setSubmitting(true)
    setSubmitError(null)
    const answers = {
      looking_forward: lookingForward,
      living,
      wants_mentor: wantsMentor,
    }
    submitOnboarding(app.id, answers, { token })
      .then(() => { if (active) setDone(true) })
      .catch((e) => {
        if (!active) return
        const code = (e as Error & { code?: string }).code || ''
        if (code === 'not_awarded') setNotAwarded(true)
        else setSubmitError(t('scholarship.onboarding.finish.error'))
      })
      .finally(() => { if (active) setSubmitting(false) })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

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

  if (status === 'loading' || loading) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  if (!app) {
    return wrap(
      <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
        <p className="mb-5 text-gray-700">{t('scholarship.onboarding.noApp')}</p>
        <Link href="/scholarship/application" className="btn-primary inline-block">
          {t('scholarship.award.empty.cta')}
        </Link>
      </div>
    )
  }

  const activeProgressIndex =
    step === 'finish' ? 3 : step === 'questions' ? 2 : 1

  function ProgressNav() {
    return (
      <ol className="mb-8 flex items-center justify-between gap-1 text-xs">
        {PROGRESS_STEPS.map((s, i) => {
          const active = i <= activeProgressIndex
          return (
            <li key={s} className="flex flex-1 flex-col items-center gap-1">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
                }`}
              >
                {i + 1}
              </span>
              <span className={active ? 'text-blue-700' : 'text-gray-400'}>
                {t(`scholarship.onboarding.progress.${s}`)}
              </span>
            </li>
          )
        })}
      </ol>
    )
  }

  // ── Finish / confirmation ──────────────────────────────────────────────
  if (step === 'finish') {
    if (notAwarded) {
      return wrap(
        <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
          <p className="mb-5 text-gray-700">{t('scholarship.onboarding.finish.notAwarded')}</p>
          <Link href="/scholarship/award" className="btn-primary inline-block">
            {t('scholarship.onboarding.finish.notAwardedCta')}
          </Link>
        </div>
      )
    }
    if (submitting || (!done && !submitError)) {
      return wrap(
        <>
          <ProgressNav />
          <p className="text-center text-gray-500">{t('scholarship.onboarding.finish.saving')}</p>
        </>
      )
    }
    if (submitError) {
      return wrap(
        <>
          <ProgressNav />
          <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
            <p className="mb-5 text-red-600">{submitError}</p>
            <button
              type="button"
              onClick={() => { setSubmitError(null); setStep('questions') }}
              className="btn-primary inline-block"
            >
              {t('scholarship.onboarding.finish.retry')}
            </button>
          </div>
        </>
      )
    }
    return wrap(
      <>
        <ProgressNav />
        <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.onboarding.finish.title')}</h1>
          <p className="mx-auto mt-3 max-w-md text-gray-600">{t('scholarship.onboarding.finish.body')}</p>

          <div className="mx-auto mt-6 max-w-sm rounded-xl bg-gray-50 p-5 text-left">
            <h2 className="mb-3 font-semibold text-gray-900">{t('scholarship.onboarding.finish.whatNext.title')}</h2>
            <ul className="space-y-3">
              {(['email', 'dashboard'] as const).map((row) => (
                <li key={row} className="flex gap-3">
                  <CheckIcon />
                  <span className="text-sm">
                    <span className="block font-medium text-gray-900">{t(`scholarship.onboarding.finish.whatNext.${row}.title`)}</span>
                    <span className="block text-gray-600">{t(`scholarship.onboarding.finish.whatNext.${row}.line`)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <Link href="/scholarship/application" className="btn-primary mt-6 inline-block w-full">
            {t('scholarship.onboarding.finish.dashboardCta')}
          </Link>
          {/* Anonymous thank-you relay — a later sprint; rendered as coming-soon. */}
          <p className="mt-3 text-sm text-gray-400">{t('scholarship.onboarding.finish.thankYouSoon')}</p>
        </div>
      </>
    )
  }

  // ── Questions ──────────────────────────────────────────────────────────
  if (step === 'questions') {
    return wrap(
      <>
        <ProgressNav />
        <div className="rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.onboarding.questions.heading')}</h1>

          <div className="mt-6 space-y-6">
            {/* Looking forward */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">
                {t('scholarship.onboarding.questions.lookingForward')}
              </label>
              <textarea
                className="input min-h-[6rem]"
                value={lookingForward}
                onChange={(e) => setLookingForward(e.target.value)}
                maxLength={5000}
              />
            </div>

            {/* Living arrangement */}
            <div>
              <span className="mb-1.5 block text-sm font-medium text-gray-700">
                {t('scholarship.onboarding.questions.living')}
              </span>
              <div className="flex gap-3">
                {(['campus', 'home'] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setLiving(opt)}
                    className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium ${
                      living === opt
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {t(`scholarship.onboarding.questions.living_${opt}`)}
                  </button>
                ))}
              </div>
            </div>

            {/* Mentor */}
            <div>
              <span className="mb-1.5 block text-sm font-medium text-gray-700">
                {t('scholarship.onboarding.questions.mentor')}
              </span>
              <div className="flex gap-3">
                {([['yes', true], ['no', false]] as const).map(([key, val]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setWantsMentor(val)}
                    className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium ${
                      wantsMentor === val
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {t(`scholarship.onboarding.questions.mentor_${key}`)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button type="button" onClick={() => setStep('finish')} className="btn-primary">
              {t('scholarship.onboarding.questions.continue')}
            </button>
            <button
              type="button"
              onClick={() => setStep('welcome')}
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              {t('scholarship.onboarding.back')}
            </button>
          </div>
        </div>
      </>
    )
  }

  // ── Welcome (default) ──────────────────────────────────────────────────
  return wrap(
    <>
      <ProgressNav />
      <div className="rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.onboarding.welcome.heading')}</h1>

        <div className="mt-6 space-y-4">
          {WELCOME_CARDS.map((card) => (
            <div key={card} className="flex gap-3 rounded-xl bg-gray-50 p-4">
              <CheckIcon />
              <div>
                <p className="font-semibold text-gray-900">{t(`scholarship.onboarding.welcome.${card}.title`)}</p>
                <p className="text-sm text-gray-600">{t(`scholarship.onboarding.welcome.${card}.line`)}</p>
              </div>
            </div>
          ))}
        </div>

        <button type="button" onClick={() => setStep('questions')} className="btn-primary mt-8">
          {t('scholarship.onboarding.welcome.understand')}
        </button>
      </div>
    </>
  )
}
