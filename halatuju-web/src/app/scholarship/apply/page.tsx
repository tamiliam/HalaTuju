'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import {
  submitScholarshipApplication,
  getMyScholarshipApplications,
  type ScholarshipApplication,
} from '@/lib/api'
import {
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  PATHWAY_OPTIONS,
  type ApplyFormState,
} from '@/lib/scholarship'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'

type TabKey = 'personal' | 'family' | 'results' | 'plans' | 'support'
const TAB_ORDER: TabKey[] = ['personal', 'family', 'results', 'plans', 'support']

function maskNric(nric?: string): string {
  const digits = (nric || '').replace(/\D/g, '')
  if (!digits) return '—'
  return `••••••-••-${digits.slice(-4) || '----'}`
}

/** Minimal iOS-style toggle (no external dep, keyboard-accessible). */
function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button" role="switch" aria-checked={on} aria-label={label}
      onClick={() => onChange(!on)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
        on ? 'bg-primary-500' : 'bg-gray-300'
      }`}
    >
      <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${on ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function TabIcon({ tab, active }: { tab: TabKey; active: boolean }) {
  const cls = `w-6 h-6 ${active ? 'text-primary-600' : 'text-gray-400'}`
  const p: Record<TabKey, string> = {
    personal: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    family: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 10-4 0M19 8a3 3 0 11-6 0 3 3 0 016 0z',
    results: 'M9 12l2 2 4-4m1-7H8a2 2 0 00-2 2v14a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2z',
    plans: 'M13 7l5 5m0 0l-5 5m5-5H6',
    support: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 20l.8-3.6A7.9 7.9 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  }
  return (
    <svg className={cls} fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d={p[tab]} />
    </svg>
  )
}

export default function ScholarshipApplyPage() {
  const { t, locale } = useT()
  const { status, profile, token, showAuthGate } = useAuth()

  const [form, setForm] = useState<ApplyFormState>(() => profileToApplyDefaults(null))
  const [existing, setExisting] = useState<ScholarshipApplication | null>(null)
  const [loadingExisting, setLoadingExisting] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState<ScholarshipApplication | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabKey>('personal')

  // Pre-fill the financial fields from the profile once it's available
  useEffect(() => {
    if (profile) setForm(profileToApplyDefaults(profile))
  }, [profile])

  // Load any existing application so a returning applicant sees their status
  // instead of a blank form (also avoids a 409 on resubmit)
  useEffect(() => {
    let active = true
    if (status !== 'ready' || !token) {
      setLoadingExisting(false)
      return
    }
    setLoadingExisting(true)
    getMyScholarshipApplications({ token })
      .then((res) => { if (active) setExisting(res.applications[0] ?? null) })
      .catch(() => { /* ignore — treat as no application */ })
      .finally(() => { if (active) setLoadingExisting(false) })
    return () => { active = false }
  }, [status, token])

  const update = useCallback(
    <K extends keyof ApplyFormState>(key: K, value: ApplyFormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errKey = applyFormError(form)
    if (errKey) { setError(t(`scholarship.apply.error.${errKey}`)); return }
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      const payload = buildApplicationPayload(form) as unknown as Record<string, unknown>
      const app = await submitScholarshipApplication(payload, locale, { token })
      setSubmitted(app)
    } catch {
      setError(t('scholarship.apply.error.generic'))
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render (all hooks are above this line — Rules of Hooks) ──

  function wrap(children: React.ReactNode) {
    return (
      <main className="container mx-auto px-6 py-10 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('scholarship.apply.title')}</h1>
        <p className="text-gray-600 mb-6">{t('scholarship.apply.intro')}</p>
        {children}
      </main>
    )
  }

  const criteria = (
    <div className="bg-primary-50 rounded-2xl p-5 mb-5">
      <h2 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">{t('scholarship.apply.criteriaTitle')}</h2>
      <ul className="space-y-2.5 text-sm text-gray-700">
        {['criteria1', 'criteria2', 'criteria3', 'criteria4'].map((k) => (
          <li key={k} className="flex items-start gap-2">
            <svg className="w-5 h-5 text-primary-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {t(`scholarship.apply.${k}`)}
          </li>
        ))}
      </ul>
    </div>
  )

  if (status === 'loading' || (status === 'ready' && loadingExisting)) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  // ── Soft sign-in gate (read freely; sign in to apply) ──
  if (status === 'anonymous' || status === 'needs-nric') {
    return wrap(
      <>
        {criteria}
        <div className="bg-white border rounded-2xl p-6 shadow-sm">
          <p className="text-gray-600 text-sm mb-4">{t('scholarship.apply.gate.readFreely')}</p>
          <button onClick={() => showAuthGate('apply')} className="btn-primary w-full flex items-center justify-center gap-2">
            <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="currentColor" d="M21.35 11.1h-9.18v2.92h5.27c-.23 1.46-1.64 4.28-5.27 4.28-3.17 0-5.76-2.62-5.76-5.85s2.59-5.85 5.76-5.85c1.81 0 3.02.77 3.71 1.43l2.53-2.44C16.46 3.6 14.43 2.7 12.17 2.7 6.91 2.7 2.7 6.91 2.7 12.45s4.21 9.75 9.47 9.75c5.47 0 9.09-3.84 9.09-9.26 0-.62-.07-1.1-.16-1.84z"/></svg>
            {t('scholarship.apply.signInButton')}
          </button>
          <p className="text-xs text-gray-400 mt-3 text-center">{t('scholarship.apply.gate.helper')}</p>
        </div>
      </>
    )
  }

  // ── Already submitted / returning applicant ──
  if (submitted || existing) {
    const app = (submitted ?? existing)!
    if (app.status === 'shortlisted') {
      return wrap(<ScholarshipNextSteps initialApp={app} token={token} />)
    }
    const isNew = !!submitted
    return wrap(
      <div className="bg-green-50 border border-green-200 rounded-2xl p-6">
        <h2 className="font-semibold text-gray-900 mb-2">
          {isNew ? t('scholarship.apply.successTitle') : t('scholarship.apply.alreadyTitle')}
        </h2>
        <p className="text-gray-700 mb-3">
          {isNew ? t('scholarship.apply.successBody') : t('scholarship.apply.alreadyBody')}
        </p>
        <p className="text-sm text-gray-600">
          {t('scholarship.apply.statusLabel')}: <span className="font-medium">{app.status}</span>
        </p>
      </div>
    )
  }

  // ── status === 'ready', no existing application → the tabbed form ──
  const academic = profileAcademicSummary(profile)
  const tabIndex = TAB_ORDER.indexOf(tab)
  const isLast = tabIndex === TAB_ORDER.length - 1
  const goNext = () => setTab(TAB_ORDER[Math.min(tabIndex + 1, TAB_ORDER.length - 1)])
  const goBack = () => setTab(TAB_ORDER[Math.max(tabIndex - 1, 0)])

  const ProfileBadge = (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a1 1 0 01.894.553l1.382 2.8 3.09.45a1 1 0 01.554 1.706l-2.236 2.18.528 3.078a1 1 0 01-1.451 1.054L10 12.347l-2.764 1.454a1 1 0 01-1.451-1.054l.528-3.078L4.077 7.49a1 1 0 01.554-1.706l3.09-.45 1.382-2.8A1 1 0 0110 2z"/></svg>
      {t('scholarship.apply.fromProfile')}
    </span>
  )

  const ReadRow = ({ label, value }: { label: string; value: string }) => (
    <div className="py-2.5 border-b border-gray-100 last:border-0">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-medium text-gray-900 mt-0.5">{value || '—'}</p>
    </div>
  )

  const sections: Record<TabKey, React.ReactNode> = {
    personal: (
      <div>
        <div className="flex items-center justify-between mb-1">
          {ProfileBadge}
          <Link href="/profile" className="text-sm font-medium text-primary-600 hover:underline">{t('scholarship.apply.edit')}</Link>
        </div>
        <ReadRow label={t('scholarship.apply.field.name')} value={profile?.name || ''} />
        <ReadRow label={t('scholarship.apply.field.school')} value={profile?.school || ''} />
        <ReadRow label={t('scholarship.apply.field.ic')} value={maskNric(profile?.nric)} />
        <ReadRow label={t('scholarship.apply.field.email')} value={profile?.contact_email || profile?.email || ''} />
      </div>
    ),
    family: (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('scholarship.apply.incomeLabel')}</label>
          <input type="number" min={0} className="input" value={form.householdIncome}
            onChange={(e) => update('householdIncome', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('scholarship.apply.householdSizeLabel')}</label>
          <input type="number" min={1} className="input" value={form.householdSize}
            onChange={(e) => update('householdSize', e.target.value)} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-gray-700">{t('scholarship.apply.strLabel')}</span>
          <Toggle on={form.receivesStr} onChange={(v) => update('receivesStr', v)} label={t('scholarship.apply.strLabel')} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-gray-700">{t('scholarship.apply.jkmLabel')}</span>
          <Toggle on={form.receivesJkm} onChange={(v) => update('receivesJkm', v)} label={t('scholarship.apply.jkmLabel')} />
        </div>
        <p className="text-xs text-gray-400">{t('scholarship.apply.writebackNote')}</p>
      </div>
    ),
    results: (
      <div>
        <div className="mb-3">{ProfileBadge}</div>
        {academic.hasData ? (
          <div className="bg-primary-50 rounded-xl p-5 text-center">
            {academic.examType === 'stpm' ? (
              <>
                <p className="text-3xl font-bold text-primary-700">{academic.stpmCgpa?.toFixed(2)}</p>
                <p className="text-sm text-gray-600 mt-1">{t('scholarship.apply.pngkLabel')}</p>
              </>
            ) : (
              <>
                <p className="text-3xl font-bold text-primary-700">{academic.aCount} {t('scholarship.apply.aGradesWord')}</p>
                {academic.aPlusCount > 0 && (
                  <p className="text-sm text-gray-600 mt-1">{t('scholarship.apply.including')} {academic.aPlusCount} A+</p>
                )}
              </>
            )}
            <p className="text-xs text-gray-400 mt-2">{t('scholarship.apply.resultsFromProfile')}</p>
            <Link href="/profile" className="text-sm font-medium text-primary-600 hover:underline mt-3 inline-block">
              {t('scholarship.apply.resultsWrong')}
            </Link>
          </div>
        ) : (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-center">
            <p className="font-medium text-gray-900 mb-1">{t('scholarship.apply.noResultsTitle')}</p>
            <p className="text-sm text-gray-600 mb-3">{t('scholarship.apply.noResultsBody')}</p>
            <Link href="/quiz" className="btn-primary inline-block">{t('scholarship.apply.noResultsCta')}</Link>
          </div>
        )}
      </div>
    ),
    plans: (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('scholarship.apply.pathwayLabel')}</label>
          <select className="input" value={form.intendedPathway}
            onChange={(e) => update('intendedPathway', e.target.value as ApplyFormState['intendedPathway'])}>
            <option value="">{t('scholarship.apply.pathwayPlaceholder')}</option>
            {PATHWAY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{t(`scholarship.apply.pathway.${opt}`)}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-gray-700">{t('scholarship.apply.intendLabel')}</span>
          <Toggle on={form.intendsTertiary2026} onChange={(v) => update('intendsTertiary2026', v)} label={t('scholarship.apply.intendLabel')} />
        </div>
      </div>
    ),
    support: (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('scholarship.apply.notesLabel')}</label>
          <textarea className="input" rows={4} value={form.notes}
            placeholder={t('scholarship.apply.notesPlaceholder')}
            onChange={(e) => update('notes', e.target.value)} />
        </div>
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input type="checkbox" className="mt-1" checked={form.consentToContact}
            onChange={(e) => update('consentToContact', e.target.checked)} />
          {t('scholarship.apply.consentLabel')}
        </label>
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}
      </div>
    ),
  }

  return wrap(
    <form onSubmit={handleSubmit}>
      {/* Context bar — profile is the source of truth */}
      <div className="flex items-center gap-3 bg-white border rounded-2xl px-4 py-3 mb-4 shadow-sm">
        <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-semibold">
          {(profile?.name || '?').trim().charAt(0).toUpperCase()}
        </div>
        <div className="leading-tight">
          <p className="text-sm font-medium text-gray-900">{t('scholarship.apply.signedInAs')} {profile?.name || ''}</p>
          <p className="text-xs text-gray-400">{t('scholarship.apply.usingProfile')}</p>
        </div>
      </div>

      {/* Progress */}
      <div className="mb-1 flex gap-1.5">
        {TAB_ORDER.map((k, i) => (
          <span key={k} className={`h-1.5 flex-1 rounded-full ${i <= tabIndex ? 'bg-primary-500' : 'bg-gray-200'}`} />
        ))}
      </div>
      <p className="text-xs text-gray-500 mb-4">
        {t('scholarship.apply.step')} {tabIndex + 1}/5 · {t(`scholarship.apply.section.${tab}`)}
      </p>

      {/* Active section card */}
      <div className="bg-white border rounded-2xl p-5 shadow-sm mb-4">
        <h2 className="font-semibold text-gray-900 mb-3">{tabIndex + 1}. {t(`scholarship.apply.section.${tab}`)}</h2>
        {sections[tab]}
      </div>

      {/* Linear nav */}
      <div className="flex gap-3 mb-4">
        {tabIndex > 0 && (
          <button type="button" onClick={goBack} className="btn-secondary flex-1">{t('scholarship.apply.back')}</button>
        )}
        {isLast ? (
          <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
            {submitting ? t('scholarship.apply.submitting') : t('scholarship.apply.submit')}
          </button>
        ) : (
          <button type="button" onClick={goNext} className="btn-primary flex-1">{t('scholarship.apply.continue')}</button>
        )}
      </div>

      {/* Bottom tab bar */}
      <nav className="sticky bottom-0 bg-white border-t flex justify-around py-2 -mx-6 px-2">
        {TAB_ORDER.map((k) => (
          <button key={k} type="button" onClick={() => setTab(k)}
            className="flex flex-col items-center gap-0.5 px-2 py-1 min-w-[56px]">
            <TabIcon tab={k} active={k === tab} />
            <span className={`text-[10px] ${k === tab ? 'text-primary-600 font-medium' : 'text-gray-400'}`}>
              {t(`scholarship.apply.tab.${k}`)}
            </span>
          </button>
        ))}
      </nav>
    </form>
  )
}
