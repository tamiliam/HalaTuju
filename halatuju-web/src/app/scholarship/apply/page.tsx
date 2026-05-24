'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import {
  submitScholarshipApplication,
  getMyScholarshipApplications,
  claimNric,
  getSavedCourses,
  fetchFieldTaxonomy,
  type SavedCourseWithStatus,
  type FieldTaxonomyEntry,
} from '@/lib/api'
import {
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  nricChanged,
  stashApplyForm,
  popApplyStash,
  clearApplyReturn,
  PATHWAY_OPTIONS,
  REFERRING_ORG_OPTIONS,
  CALL_LANGUAGE_OPTIONS,
  MALAYSIAN_STATES,
  UPU_OPTIONS,
  HELP_OPTIONS,
  OTHER_SCHOLARSHIP_OPTIONS,
  type ApplyFormState,
  type TopChoice,
} from '@/lib/scholarship'

type TabKey = 'personal' | 'family' | 'results' | 'plans' | 'support'
const TAB_ORDER: TabKey[] = ['personal', 'family', 'results', 'plans', 'support']

// Which tab a validation error belongs to, so submit can jump the student there.
const ERROR_TAB: Record<string, TabKey> = {
  name: 'personal', school: 'personal', nric: 'personal', nricTaken: 'personal',
  org: 'personal', state: 'personal', phone: 'personal',
  income: 'family',
  consent: 'support',
}

/** An `i` info bubble — tap/click toggles a small popover (works on mobile + desktop). */
function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button" aria-label={text} title={text}
        onClick={() => setOpen((v) => !v)} onBlur={() => setOpen(false)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-gray-200 text-[10px] font-semibold leading-none text-gray-600 hover:bg-gray-300"
      >
        i
      </button>
      {open && (
        <span role="tooltip" className="absolute left-1/2 top-6 z-20 w-56 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-xs font-normal leading-snug text-white shadow-lg">
          {text}
        </span>
      )}
    </span>
  )
}

/** Field label with an optional required `*` and an optional `i` tooltip. */
function FieldLabel({ children, required, tip }: { children: React.ReactNode; required?: boolean; tip?: string }) {
  return (
    <span className="mb-1 flex items-center text-sm font-medium text-gray-700">
      {children}
      {required && <span className="ml-0.5 text-red-500" aria-hidden>*</span>}
      {tip && <InfoTip text={tip} />}
    </span>
  )
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
  const router = useRouter()

  const [form, setForm] = useState<ApplyFormState>(() => profileToApplyDefaults(null))
  const [loadingExisting, setLoadingExisting] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabKey>('personal')
  // My Plans data: the student's saved courses (top-3 source) + field taxonomy.
  const [savedCourses, setSavedCourses] = useState<SavedCourseWithStatus[]>([])
  const [fieldGroups, setFieldGroups] = useState<FieldTaxonomyEntry[]>([])
  // Once the form is populated (from a stash on return, or from the profile),
  // don't let the profile effect overwrite the student's in-progress edits.
  const populatedRef = useRef(false)

  // Returning from the My Results → onboarding detour: restore the stashed
  // in-progress edits and land back on the Results tab. Runs once on mount,
  // before the profile prefill below (which then skips, seeing populatedRef).
  useEffect(() => {
    const stashed = popApplyStash()
    if (stashed) {
      setForm(stashed)
      setTab('results')
      populatedRef.current = true
    } else {
      // No stash on a normal apply visit → clear any orphan return marker left by
      // an abandoned results-edit detour, so a later normal onboarding doesn't
      // wrongly route back here.
      clearApplyReturn()
    }
  }, [])

  // Pre-fill from the profile once it's available (skipped if we restored a stash).
  useEffect(() => {
    if (profile && !populatedRef.current) {
      setForm(profileToApplyDefaults(profile))
      populatedRef.current = true
    }
  }, [profile])

  // My Plans data: saved courses (top-3 picker, exam-type aware) + field taxonomy.
  useEffect(() => {
    if (status !== 'ready' || !token) return
    const qualification = profile?.exam_type === 'stpm' ? 'STPM' : 'SPM'
    getSavedCourses({ token, qualification })
      .then((res) => setSavedCourses(res.saved_courses || []))
      .catch(() => setSavedCourses([]))
    fetchFieldTaxonomy({ token })
      .then((res) => setFieldGroups(res.groups || []))
      .catch(() => setFieldGroups([]))
  }, [status, token, profile?.exam_type])

  // A returning applicant has nothing to fill in here — send them to their
  // application page (which shows status / the follow-up steps). Keeps the
  // form for first-time applicants only and avoids a 409 on resubmit.
  useEffect(() => {
    let active = true
    if (status !== 'ready' || !token) {
      setLoadingExisting(false)
      return
    }
    setLoadingExisting(true)
    getMyScholarshipApplications({ token })
      .then((res) => {
        if (!active) return
        if (res.applications[0]) { router.replace('/scholarship/application'); return }
        setLoadingExisting(false)
      })
      .catch(() => { if (active) setLoadingExisting(false) })
    return () => { active = false }
  }, [status, token, router])

  const update = useCallback(
    <K extends keyof ApplyFormState>(key: K, value: ApplyFormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  // Edit/add results → run the full onboarding (grades, electives, co-curricular,
  // "a few more details"), then return here. Stash the in-progress edits first so
  // they survive the detour (the form only commits on submit).
  const goEditResults = () => {
    stashApplyForm(form)
    router.push('/onboarding/exam-type')
  }

  // ── My Plans helpers ──
  const togglePathway = (key: string) => setForm((p) => ({
    ...p,
    pathwaysConsidered: p.pathwaysConsidered.includes(key)
      ? p.pathwaysConsidered.filter((k) => k !== key)
      : [...p.pathwaysConsidered, key],
  }))
  const toggleScholarship = (key: string) => setForm((p) => ({
    ...p,
    otherScholarships: p.otherScholarships.includes(key)
      ? p.otherScholarships.filter((k) => k !== key)
      : [...p.otherScholarships, key],
  }))
  // Pick top-3 from saved courses; rank = selection order, capped at 3.
  const toggleTopChoice = (sc: SavedCourseWithStatus) => setForm((p) => {
    if (p.topChoices.some((c) => c.courseId === sc.course_id)) {
      return { ...p, topChoices: p.topChoices.filter((c) => c.courseId !== sc.course_id) }
    }
    if (p.topChoices.length >= 3) return p
    return { ...p, topChoices: [...p.topChoices, { courseId: sc.course_id, courseName: sc.course, institution: sc.institution_name || '' }] }
  })
  const topChoiceRank = (id: string) => form.topChoices.findIndex((c) => c.courseId === id) + 1
  const fieldName = (g: FieldTaxonomyEntry) => (locale === 'ms' ? g.name_ms : locale === 'ta' ? g.name_ta : g.name_en)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errKey = applyFormError(form)
    if (errKey) {
      setError(t(`scholarship.apply.error.${errKey}`))
      setTab(ERROR_TAB[errKey] ?? 'personal')
      return
    }
    if (!token) return
    setSubmitting(true)
    setError(null)

    // Commit-on-submit. The NRIC commits through the validated claim path (never
    // the application payload); the other About Me + My Family fields are synced
    // to the profile by the submit. Nothing persists until this succeeds.
    if (nricChanged(form, profile) && !profile?.nric_verified) {
      try {
        const res = await claimNric(form.nric.trim(), false, { token })
        if (res.status === 'exists') {
          setError(t('scholarship.apply.error.nricTaken'))
          setTab('personal'); setSubmitting(false); return
        }
      } catch {
        // 400 (age/state) or 403 (locked) from the claim endpoint
        setError(t('scholarship.apply.error.nric'))
        setTab('personal'); setSubmitting(false); return
      }
    }

    try {
      const payload = buildApplicationPayload(form) as unknown as Record<string, unknown>
      await submitScholarshipApplication(payload, locale, { token })
      router.replace('/scholarship/application')
    } catch {
      setError(t('scholarship.apply.error.generic'))
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render (all hooks are above this line — Rules of Hooks) ──

  function wrap(children: React.ReactNode) {
    return (
      <main className="container mx-auto px-6 py-10 max-w-2xl lg:max-w-4xl">
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

  // ── status === 'ready', no existing application → the tabbed form ──
  // (returning applicants were redirected to /scholarship/application above)
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

  const lockedEmail = profile?.contact_email || profile?.email || ''
  const nricLocked = !!profile?.nric_verified

  const sections: Record<TabKey, React.ReactNode> = {
    personal: (
      <div className="space-y-4">
        <p className="text-xs text-gray-500">{t('scholarship.apply.aboutMeHint')}</p>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.name')}>{t('scholarship.apply.field.name')}</FieldLabel>
          <input className="input" value={form.name} onChange={(e) => update('name', e.target.value)} />
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.school')}>{t('scholarship.apply.field.school')}</FieldLabel>
          <input className="input" value={form.school} onChange={(e) => update('school', e.target.value)} />
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.ic')}>{t('scholarship.apply.field.ic')}</FieldLabel>
          {nricLocked ? (
            <div className="input flex items-center justify-between bg-gray-50 text-gray-600">
              <span>{form.nric || '—'}</span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600">
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 10.7a1 1 0 011.4-1.4l3 3 6.8-6.8a1 1 0 011.2 0z" clipRule="evenodd"/></svg>
                {t('scholarship.apply.verified')}
              </span>
            </div>
          ) : (
            <input className="input" value={form.nric} placeholder="XXXXXX-XX-XXXX"
              onChange={(e) => update('nric', e.target.value)} />
          )}
        </div>
        <div>
          <FieldLabel>{t('scholarship.apply.field.email')}</FieldLabel>
          <div className="input flex items-center justify-between bg-gray-50 text-gray-500">
            <span className="truncate">{lockedEmail || '—'}</span>
            <span className="ml-2 shrink-0 text-xs text-gray-400">{t('scholarship.apply.locked')}</span>
          </div>
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.org')}>{t('scholarship.apply.field.org')}</FieldLabel>
          <select className="input" value={form.referringOrg}
            onChange={(e) => update('referringOrg', e.target.value as ApplyFormState['referringOrg'])}>
            <option value="">{t('scholarship.apply.orgPlaceholder')}</option>
            {REFERRING_ORG_OPTIONS.map((code) => (
              <option key={code} value={code}>{t(`scholarship.apply.org.${code}`)}</option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.state')}>{t('scholarship.apply.field.state')}</FieldLabel>
          <select className="input" value={form.homeState} onChange={(e) => update('homeState', e.target.value)}>
            <option value="">{t('scholarship.apply.statePlaceholder')}</option>
            {MALAYSIAN_STATES.map((s) => (<option key={s} value={s}>{s}</option>))}
          </select>
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.phone')}>{t('scholarship.apply.field.phone')}</FieldLabel>
          <input className="input" inputMode="tel" placeholder="01X-XXX XXXX" value={form.phone}
            onChange={(e) => update('phone', e.target.value)} />
        </div>
      </div>
    ),
    family: (
      <div className="space-y-4">
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.income')}>{t('scholarship.apply.incomeLabel')}</FieldLabel>
          <input type="number" min={0} className="input" value={form.householdIncome}
            onChange={(e) => update('householdIncome', e.target.value)} />
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.household')}>{t('scholarship.apply.householdSizeLabel')}</FieldLabel>
          <input type="number" min={1} className="input" value={form.householdSize}
            onChange={(e) => update('householdSize', e.target.value)} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center text-sm text-gray-700">{t('scholarship.apply.strLabel')}<InfoTip text={t('scholarship.apply.tip.str')} /></span>
          <Toggle on={form.receivesStr} onChange={(v) => update('receivesStr', v)} label={t('scholarship.apply.strLabel')} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center text-sm text-gray-700">{t('scholarship.apply.jkmLabel')}<InfoTip text={t('scholarship.apply.tip.jkm')} /></span>
          <Toggle on={form.receivesJkm} onChange={(v) => update('receivesJkm', v)} label={t('scholarship.apply.jkmLabel')} />
        </div>
        <hr className="border-gray-100" />
        <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{t('scholarship.apply.parentHeading')}</p>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.parentName')}>{t('scholarship.apply.field.parentName')}</FieldLabel>
          <input className="input" value={form.parentName} onChange={(e) => update('parentName', e.target.value)} />
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.parentPhone')}>{t('scholarship.apply.field.parentPhone')}</FieldLabel>
          <input className="input" inputMode="tel" placeholder="01X-XXX XXXX" value={form.parentPhone}
            onChange={(e) => update('parentPhone', e.target.value)} />
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.callLang')}>{t('scholarship.apply.field.callLang')}</FieldLabel>
          <select className="input" value={form.callLanguage}
            onChange={(e) => update('callLanguage', e.target.value as ApplyFormState['callLanguage'])}>
            <option value="">{t('scholarship.apply.callLangPlaceholder')}</option>
            {CALL_LANGUAGE_OPTIONS.map((c) => (
              <option key={c} value={c}>{t(`scholarship.apply.callLang.${c}`)}</option>
            ))}
          </select>
        </div>
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
            <button type="button" onClick={goEditResults} className="mt-3 inline-block text-sm font-medium text-primary-600 hover:underline">
              {t('scholarship.apply.resultsWrong')}
            </button>
          </div>
        ) : (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-center">
            <p className="font-medium text-gray-900 mb-1">{t('scholarship.apply.noResultsTitle')}</p>
            <p className="text-sm text-gray-600 mb-3">{t('scholarship.apply.noResultsBody')}</p>
            <button type="button" onClick={goEditResults} className="btn-primary inline-block">{t('scholarship.apply.noResultsCta')}</button>
          </div>
        )}
      </div>
    ),
    plans: (
      <div className="space-y-5">
        {/* Continuing to tertiary study — engine hard gate */}
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input type="checkbox" className="mt-1" checked={form.intendsTertiary2026}
            onChange={(e) => update('intendsTertiary2026', e.target.checked)} />
          {t('scholarship.apply.intendLabel')}
        </label>

        {/* Pathways considering (non-exclusive multi-select) */}
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.pathways')}>{t('scholarship.apply.pathwaysLabel')}</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {PATHWAY_OPTIONS.map((opt) => {
              const on = form.pathwaysConsidered.includes(opt)
              return (
                <button key={opt} type="button" onClick={() => togglePathway(opt)}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-primary-500 bg-primary-50 font-medium text-primary-700' : 'border-gray-300 text-gray-600'}`}>
                  {t(`scholarship.apply.pathway.${opt}`)}
                </button>
              )
            })}
          </div>
        </div>

        {/* UPU / destination intent (IPTS-only is out of scope) */}
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.upu')}>{t('scholarship.apply.upuLabel')}</FieldLabel>
          <div className="space-y-2">
            {UPU_OPTIONS.map((opt) => (
              <label key={opt} className="flex items-start gap-2 text-sm text-gray-700">
                <input type="radio" name="upu" className="mt-1" checked={form.upuStatus === opt}
                  onChange={() => update('upuStatus', opt)} />
                {t(`scholarship.apply.upu.${opt}`)}
              </label>
            ))}
          </div>
          {form.upuStatus === 'ipts' && (
            <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              {t('scholarship.apply.iptsNote')}
            </p>
          )}
        </div>

        {/* Field of study */}
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.field')}>{t('scholarship.apply.fieldLabel')}</FieldLabel>
          <select className="input" value={form.fieldOfStudy} onChange={(e) => update('fieldOfStudy', e.target.value)}>
            <option value="">{t('scholarship.apply.fieldPlaceholder')}</option>
            {fieldGroups.map((g) => (<option key={g.key} value={g.key}>{fieldName(g)}</option>))}
          </select>
        </div>

        {/* Top-3 course choices — from the student's saved courses */}
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.topChoices')}>{t('scholarship.apply.topChoicesLabel')}</FieldLabel>
          {savedCourses.length === 0 ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
              <p className="mb-2 text-sm text-gray-600">{t('scholarship.apply.noSavedCourses')}</p>
              <Link href="/dashboard" className="text-sm font-medium text-primary-600 hover:underline">
                {t('scholarship.apply.browseCourses')}
              </Link>
            </div>
          ) : (
            <>
              <p className="mb-2 text-xs text-gray-400">{t('scholarship.apply.topChoicesHint')}</p>
              <div className="space-y-2">
                {savedCourses.map((sc) => {
                  const rank = topChoiceRank(sc.course_id)
                  const on = rank > 0
                  const full = form.topChoices.length >= 3 && !on
                  return (
                    <button key={sc.course_id} type="button" disabled={full} onClick={() => toggleTopChoice(sc)}
                      className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left ${on ? 'border-primary-500 bg-primary-50' : full ? 'border-gray-200 opacity-50' : 'border-gray-300'}`}>
                      <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${on ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-400'}`}>
                        {on ? rank : '+'}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-gray-900">{sc.course}</span>
                        {sc.institution_name && <span className="block truncate text-xs text-gray-400">{sc.institution_name}</span>}
                      </span>
                    </button>
                  )
                })}
              </div>
            </>
          )}
        </div>

        {/* Other scholarships applied/held → funding-overlap signal */}
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.otherScholarships')}>{t('scholarship.apply.otherScholarshipsLabel')}</FieldLabel>
          <div className="mb-2 flex flex-wrap gap-2">
            {OTHER_SCHOLARSHIP_OPTIONS.map((opt) => {
              const on = form.otherScholarships.includes(opt)
              return (
                <button key={opt} type="button" onClick={() => toggleScholarship(opt)}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-primary-500 bg-primary-50 font-medium text-primary-700' : 'border-gray-300 text-gray-600'}`}>
                  {t(`scholarship.apply.scholarship.${opt}`)}
                </button>
              )
            })}
          </div>
          <input className="input" value={form.otherScholarshipsText}
            placeholder={t('scholarship.apply.otherScholarshipsPlaceholder')}
            onChange={(e) => update('otherScholarshipsText', e.target.value)} />
        </div>
      </div>
    ),
    support: (
      <div className="space-y-5">
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.helpUniversity')}>{t('scholarship.apply.helpUniversityLabel')}</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {HELP_OPTIONS.map((opt) => {
              const on = form.helpUniversity === opt
              return (
                <button key={opt} type="button" onClick={() => update('helpUniversity', opt)}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-primary-500 bg-primary-50 font-medium text-primary-700' : 'border-gray-300 text-gray-600'}`}>
                  {t(`scholarship.apply.help.${opt}`)}
                </button>
              )
            })}
          </div>
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.helpScholarship')}>{t('scholarship.apply.helpScholarshipLabel')}</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {HELP_OPTIONS.map((opt) => {
              const on = form.helpScholarship === opt
              return (
                <button key={opt} type="button" onClick={() => update('helpScholarship', opt)}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-primary-500 bg-primary-50 font-medium text-primary-700' : 'border-gray-300 text-gray-600'}`}>
                  {t(`scholarship.apply.help.${opt}`)}
                </button>
              )
            })}
          </div>
        </div>
        <div>
          <FieldLabel>{t('scholarship.apply.anythingElseLabel')}</FieldLabel>
          <textarea className="input" rows={4} value={form.anythingElse}
            placeholder={t('scholarship.apply.anythingElsePlaceholder')}
            onChange={(e) => update('anythingElse', e.target.value)} />
        </div>
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input type="checkbox" className="mt-1" checked={form.consentToContact}
            onChange={(e) => update('consentToContact', e.target.checked)} />
          <span>{t('scholarship.apply.consentLabel')}<span className="ml-0.5 text-red-500" aria-hidden>*</span></span>
        </label>
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

      {/* On desktop: a left step-nav rail beside the active step (uses the horizontal
          space the mobile single column left empty). On mobile: the bottom tab bar below. */}
      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8 lg:items-start">
        <aside className="hidden lg:block">
          <nav className="sticky top-6 space-y-1">
            {TAB_ORDER.map((k, i) => {
              const active = k === tab
              const done = i < tabIndex
              return (
                <button key={k} type="button" onClick={() => setTab(k)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${active ? 'bg-primary-50 font-medium text-primary-700' : 'text-gray-600 hover:bg-gray-50'}`}>
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${active ? 'bg-primary-500 text-white' : done ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-400'}`}>
                    {done ? '✓' : i + 1}
                  </span>
                  {t(`scholarship.apply.section.${k}`)}
                </button>
              )
            })}
          </nav>
        </aside>

        <div>
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

          {/* Validation / submit error — shown on whichever tab the error sent the user to */}
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Commit-on-submit: nothing is saved until the application is submitted */}
          {isLast && (
            <p className="mb-3 text-center text-xs text-gray-400">{t('scholarship.apply.commitNote')}</p>
          )}

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
        </div>
      </div>

      {/* Bottom tab bar (mobile only — replaced by the left rail on desktop) */}
      <nav className="sticky bottom-0 bg-white border-t flex justify-around py-2 -mx-6 px-2 lg:hidden">
        <Link href="/scholarship" className="flex flex-col items-center gap-0.5 px-2 py-1 min-w-[56px]">
          <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10" />
          </svg>
          <span className="text-[10px] text-gray-400">{t('scholarship.apply.tab.home')}</span>
        </Link>
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
