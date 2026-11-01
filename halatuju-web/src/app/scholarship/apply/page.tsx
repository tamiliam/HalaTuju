'use client'

import '@/lib/messagesScholarship'   // TD-416: this page's scholarship.* words (their own slice)
import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
// The School field's suggesting component loads on mount (Mobile M4: the route's budget paid for the draft).
import SchoolSelect from '@/components/scholarship/LazySchoolSelect'
import InfoTip from '@/components/InfoTip'
import FieldLabel from '@/components/FieldLabel'
import Toggle from '@/components/Toggle'
import { submitScholarshipApplication, claimNric } from '@/lib/api'
import { isThirdRoute, type Qualification } from '@/lib/qualification'
import {
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  declarationNameMismatch,
  formatNric,
  formatPhone,
  formatMoney2dp,
  nricChanged,
  setApplyReturn,
  clearApplyReturn,
  CALL_LANGUAGE_OPTIONS,
  MALAYSIAN_STATES,
  HELP_OPTIONS,
  OTHER_SCHOLARSHIP_OPTIONS,
  type ApplyFormState,
  firstTooLongField,
  APPLY_FIELD_LABEL_KEYS,
} from '@/lib/scholarship'
import { applyPlanPatch } from '@/lib/planPicker'
import { applyCard } from '@/lib/applyCopy'
import { useApplyGate, applyPageExit } from '@/lib/useApplyGate'   // the SERVER's verdict; no web rule
import { useApplyGift, isProgrammeRequired, isOtherConflict, clearApplyProgramme } from '@/lib/useApplyGift'
import LazyGiftChooser from '@/components/scholarship/LazyGiftChooser'
import LazyPathwayPicker from '@/components/scholarship/LazyPathwayPicker'
import ApplyingTo from '@/components/scholarship/ApplyingTo'
import ReferralSelect, { useReferralOptions } from '@/components/scholarship/ReferralSelect'
import { isReferralNotOffered } from '@/lib/referralSources'
import GiftClosed from '@/components/scholarship/GiftClosed'
import AlreadyApplied from '@/components/scholarship/AlreadyApplied'
import { ApplyProgress, ApplyFooter } from '@/components/scholarship/ApplyStepper'
// THE DRAFT (Mobile M4, owner: this tab only) - no IC, signature or consent; bound to her id + programme.
import { readApplyDraft, writeApplyDraft, clearApplyDraft, useApplyDraft } from '@/lib/applyDraft'

type TabKey = 'personal' | 'family' | 'results' | 'plans' | 'support'
const TAB_ORDER: TabKey[] = ['personal', 'family', 'results', 'plans', 'support']

// Which tab a validation error belongs to, so submit can jump the student there.
const ERROR_TAB: Record<string, TabKey> = {
  name: 'personal', school: 'personal', nric: 'personal', nricTaken: 'personal',
  org: 'personal', state: 'personal', phone: 'personal',
  householdSize: 'family', householdSizeMax: 'family', income: 'family', parentPhone: 'family',
  pathwayCertainty: 'plans', chosenPathway: 'plans', chosenProgramme: 'plans',
  preUTrack: 'plans', preUInstitution: 'plans',
  consent: 'support', declaration: 'support',
  // A name mismatch is fixed on the About Me name (the usual culprit — a pre-filled
  // Google handle), so land the student there; an inline hint shows in both places.
  declarationMismatch: 'personal',
}

export default function ScholarshipApplyPage() {
  const { t, locale } = useT()
  const { status, profile, token, showAuthGate, session } = useAuth()
  const uid = session?.user?.id
  const router = useRouter()

  const [form, setForm] = useState<ApplyFormState>(() => profileToApplyDefaults(null))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A SERVER refusal at submit, kept apart from the field error the live-revalidate effect below
  // manages — that effect used to wipe it at once when the form itself was valid (TD-340).
  const [serverError, setServerError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabKey>('personal')
  // Which gift this form is for: its code (sent at submit), its own copy, the chooser's options
  // when several are open and nothing named one, and its name for the form. See `useApplyGift`.
  const gift = useApplyGift(router)
  // May she apply to it? The server's verdict (TD-337), re-asked with the gift; never signed out.
  const gate = useApplyGate(status === 'ready' ? token : null, gift.named)
  // Where she goes, decided in ONE place once intake and gate have both answered (no racing redirects).
  const exit = applyPageExit({ settled: gift.settled, noneOpen: gift.noneOpen, authLoading: status === 'loading', gate: gate.state })
  useEffect(() => { if (exit) router.replace(exit) }, [exit, router])
  // Income field shows raw digits while focused (easy to edit) and a formatted
  // "3,000.00" when blurred. The stored value (form.householdIncome) stays raw.
  const [incomeFocused, setIncomeFocused] = useState(false)
  // Once the form is populated (from a stash on return, or from the profile),
  // don't let the profile effect overwrite the student's in-progress edits.
  const populatedRef = useRef(false)
  // Which Plans branch applies (an SPM leaver names a pathway; an STPM or third-route holder a
  // degree) reads the RESULTS we hold, not the declared exam (TD-325; owner ruling TD-324):
  // `profileAcademicSummary` reads the served `results_held` — the same rule as the Results step.
  const examType: Qualification = profileAcademicSummary(profile).examType
  // Where the Plans step draws "Eligible only": the card header, beside the step's title.
  const [switchSlot, setSwitchSlot] = useState<HTMLElement | null>(null)
  // ⚠ THE RESULTS STEP NAMES NO EXAM. It used to read "My SPM Results" / "My STPM Results" off
  // the DECLARED exam — which is a claim we cannot back: the declaration moves on a card tap and
  // needs no results behind it, so a Form Six student holding ten SPM grades was shown "My STPM
  // Results" above "We don't have your results yet". A fresh student got "My SPM Results" before
  // choosing anything, because the declaration falls back to spm. Every step now maps to its own
  // key; the card below names the exam only where it has the results to name it from.
  const sectionKey = (k: string) => k

  // On the form, the "edit my results" detour is over (or never began): clear its return marker, so a
  // later ordinary onboarding does not route back here. Her typing comes back from THE DRAFT below.
  useEffect(() => { clearApplyReturn() }, [])

  // Pre-fill from the profile once it carries its NRIC - then lay HER DRAFT for THIS programme over it
  // (Mobile M4: an iOS tab kill, the results detour, a trip to Home). The draft holds no IC, signature
  // or consent, so those always come from the profile / a fresh answer. Wait for the NRIC specifically:
  // a brand-new user claims it at the auth gate *after* this page mounts, so the first profile snapshot
  // has no NRIC; seeding (and locking populatedRef) on it would leave the box blank. And wait for the
  // programme: a draft is only ever restored onto the form for the programme it was typed for.
  const baseFormRef = useRef<ApplyFormState | null>(null)
  useEffect(() => {
    // Not while the chooser is up (several open, none picked): no programme yet to read a draft for.
    if (!profile?.nric || populatedRef.current || !gift.settled || gift.choices.length > 1 || !uid) return
    const draft = readApplyDraft({ uid, programme: gift.code })
    const seeded = draft ? { ...profileToApplyDefaults(profile), ...draft.form } : profileToApplyDefaults(profile)
    setForm(seeded)
    baseFormRef.current = seeded
    if (draft && (TAB_ORDER as string[]).includes(draft.step)) setTab(draft.step as TabKey)
    populatedRef.current = true
  }, [profile, gift.settled, gift.choices.length, gift.code, uid])
  // Kept as she types - only once she has changed something, and never once the form is sent.
  const [sent, setSent] = useState(false)
  useApplyDraft(form, uid, gift.code, tab, populatedRef.current && !sent && baseFormRef.current !== form)
  // A form that will not be sent from here - already applied, programme closed, sent away - keeps no draft.
  useEffect(() => {
    if (gate.state === 'already_applied' || gift.closed || exit) clearApplyDraft()
  }, [gate.state, gift.closed, exit])
  // "Who referred you?" is pre-filled ONCE, only from her own earlier answer to THIS organisation
  // (the gate's `referral`) — never a `?ref=` code (sources Sprint C) — and never over a choice made.
  const referralSeeded = useRef(false)
  useEffect(() => {
    if (referralSeeded.current || !gate.referral || !populatedRef.current) return
    referralSeeded.current = true
    setForm((p) => (p.referringOrg ? p : { ...p, referringOrg: gate.referral }))
  }, [gate.referral, profile])

  // A server refusal stays on screen until she changes something (or submits again) — TD-340.
  useEffect(() => { setServerError(null) }, [form])

  const update = useCallback(
    <K extends keyof ApplyFormState>(key: K, value: ApplyFormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    []
  )
  // "Who referred you?": THIS gift's sources + the fixed choices it offers; a value not among them is cleared.
  const referralOpts = useReferralOptions(gift.settled, gift.sources, gift.code, form.referringOrg, () => update('referringOrg', ''), gift.fixedSources)

  // Live-revalidate ONLY while an error is already showing (i.e. after a Continue/
  // Submit attempt). As the student fixes fields, keep the red box in sync: update
  // it to the current first outstanding field in this-or-an-earlier step, or clear
  // it the moment the blocking error is resolved. We never surface a NEW error for a
  // step they haven't tried to pass — same gate as goNext. The functional
  // setError(prev===next?prev:next) bails on an unchanged value, so this can't loop.
  // MUST stay above the early returns below (loading / sign-in gate) so the hook is
  // unconditional — Rules of Hooks. (Computes the tab index from `tab` directly.)
  useEffect(() => {
    if (!error) return
    const errKey = applyFormError(form, examType)
    const next = errKey && TAB_ORDER.indexOf(ERROR_TAB[errKey] ?? 'personal') <= TAB_ORDER.indexOf(tab)
      ? t(`scholarship.apply.error.${errKey}`)
      : null
    setError((prev) => (prev === next ? prev : next))
  }, [form, examType, tab, error, t])

  // Edit/add results → run the full onboarding (grades, electives, co-curricular,
  // "a few more details"), then return here. Save THE DRAFT first (landing back on Results) so her
  // edits survive the detour (the form only commits on submit).
  const goEditResults = () => {
    writeApplyDraft(form, { uid, programme: gift.code }, 'results')
    setApplyReturn()
    router.push('/onboarding/exam-type')
  }

  // ── My Plans: the picker (`PathwayPicker`, shared with /profile) reports a patch; the form's two
  // derived answers (upu_status, field of study) follow it (`applyPlanPatch`).
  const updatePlan = useCallback(
    (patch: Partial<ApplyFormState>) => setForm((p) => applyPlanPatch(p, patch)), [])
  const toggleScholarship = (key: string) => setForm((p) => ({
    ...p,
    otherScholarships: p.otherScholarships.includes(key)
      ? p.otherScholarships.filter((k) => k !== key)
      : [...p.otherScholarships, key],
  }))

  // Validate on Continue: block advancing while an error sits in the current (or an earlier) step, and
  // surface it there. Errors that belong only to a later step don't block - fixed when she gets there.
  const goNext = () => {
    const at = TAB_ORDER.indexOf(tab)
    const errKey = applyFormError(form, examType)
    if (errKey && TAB_ORDER.indexOf(ERROR_TAB[errKey] ?? 'personal') <= at) {
      setError(t(`scholarship.apply.error.${errKey}`))
      setTab(ERROR_TAB[errKey] ?? 'personal')
      return
    }
    setError(null)
    setTab(TAB_ORDER[Math.min(at + 1, TAB_ORDER.length - 1)])
  }
  const goBack = () => { setError(null); setTab(TAB_ORDER[Math.max(TAB_ORDER.indexOf(tab) - 1, 0)]) }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // A press while a submit is in flight (Enter in a field, a second tap) sends nothing (Mobile M4).
    if (submitting) return
    // Enter / "Go" on a phone keyboard before the last step means NEXT - never "submit the whole form".
    if (tab !== TAB_ORDER[TAB_ORDER.length - 1]) { goNext(); return }
    const errKey = applyFormError(form, examType)
    if (errKey) {
      setError(t(`scholarship.apply.error.${errKey}`))
      setTab(ERROR_TAB[errKey] ?? 'personal')
      return
    }
    if (!token) return
    setSubmitting(true)
    setError(null); setServerError(null)

    // Commit-on-submit. The NRIC commits through the validated claim path (never
    // the application payload); the other About Me + My Family fields are synced
    // to the profile by the submit. Nothing persists until this succeeds.
    if (nricChanged(form, profile) && !profile?.nric_verified) {
      try {
        const res = await claimNric(form.nric.trim(), false, { token })
        if (res.status === 'exists') {
          setServerError(t('scholarship.apply.error.nricTaken'))
          setTab('personal'); setSubmitting(false); return
        }
      } catch {
        // 400 (age/state) or 403 (locked) from the claim endpoint
        setServerError(t('scholarship.apply.error.nric'))
        setTab('personal'); setSubmitting(false); return
      }
    }

    try {
      const payload = buildApplicationPayload(form) as unknown as Record<string, unknown>
      // PF-1: the code the "You are applying to" line was resolved from (`useApplyGift`).
      if (gift.code) payload.programme_code = gift.code
      await submitScholarshipApplication(payload, locale, { token })
      setSent(true); clearApplyDraft()   // sent: nothing of it stays on this phone
      clearApplyProgramme()
      router.replace('/scholarship/application')
    } catch (err) {
      // Which gift? → ask again, typed answers kept. The gate's own refusals → her application, or
      // the already-applied card. Another 409 → closed mid-form? → the closed card.
      if (isProgrammeRequired(err)) { gift.change(); return }
      // Who-referred-you code no longer offered → re-read the list, ask again by the field; nothing else lost.
      if (isReferralNotOffered(err)) { update('referringOrg', ''); setTab('personal'); await gift.refuseReferral(); return }
      if (gate.adopt(err) || (isOtherConflict(err) && await gift.recheck())) return
      // If a field was rejected for length, name the exact question to shorten.
      const key = firstTooLongField((err as { fieldErrors?: unknown }).fieldErrors)
      const labelKey = key ? APPLY_FIELD_LABEL_KEYS[key] : null
      if (labelKey) {
        setServerError(t('scholarship.apply.error.tooLong', { field: t(labelKey) }))
      } else {
        setServerError(t('scholarship.apply.error.generic'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render (all hooks are above this line — Rules of Hooks) ──
  // ⚠ THE GIFT'S OWN WORDS IF IT WROTE ANY, ELSE THE PLATFORM'S. The platform default is resolved
  // HERE, from the message files — its one home. The server never carries a copy of it.
  const card = applyCard(gift.copy, locale, {
    title: t('scholarship.apply.title'),
    intro: t('scholarship.apply.intro'),
    criteria: ['criteria1', 'criteria2', 'criteria3', 'criteria4']
      .map(k => t(`scholarship.apply.${k}`)),
  })

  // `headed` false: no heading/intro — before the intake answers, and on the chooser (no gift chosen).
  function wrap(children: React.ReactNode, headed = true) {
    return (
      <main className="container mx-auto px-6 py-10 max-w-2xl lg:max-w-4xl">
        {headed && <><h1 className="text-2xl font-bold text-ground-900 mb-2">{card.title}</h1>
          {/* pre-line: the gift's own line breaks and blank lines show (request #34). Text, never HTML. */}
          <p className="text-ground-600 mb-6 whitespace-pre-line" data-testid="apply-intro">{card.intro}</p></>}
        {children}
      </main>
    )
  }

  const criteria = (
    <div className="bg-primary-50 rounded-2xl p-5 mb-5">
      {/* ⚠ "Who can apply" STAYS A PLATFORM STRING — it is generic, works for any gift, and a
          fourth box on the editor would be friction with no gain (owner, 2026-09-09). */}
      <h2 className="font-semibold text-ground-900 mb-3 text-sm uppercase tracking-wide">{t('scholarship.apply.criteriaTitle')}</h2>
      <ul className="space-y-2.5 text-sm text-ground-700">
        {card.criteria.map((line, i) => (
          <li key={i} className="flex items-start gap-2">
            <svg className="w-5 h-5 text-primary-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {line}
          </li>
        ))}
      </ul>
    </div>
  )

  // Loading also while the gate is unanswered for a signed-in student, and while she is being sent
  // away (`exit`: her application, or the landing) — never a flash of the closed card on the way.
  if (!gift.settled || status === 'loading' || gate.state === 'pending' || exit) {
    return wrap(<p className="text-ground-500">{t('scholarship.apply.loading')}</p>, gift.settled && !gift.closed && gift.choices.length < 2)
  }

  // A NAMED gift that has closed says so on its own page (after the bounce above, before all else).
  if (gift.closed) return wrap(<GiftClosed onSeeOpen={gift.othersOpen ? gift.change : undefined} />, card.fromGift)
  // ── Which programme? Several open, none named — asked BEFORE the sign-in gate, for everyone ──
  // (owner's live test, 2026-10-05: signed out, a bare link showed one gift's criteria unasked).
  if (gift.choices.length > 1) {
    return wrap(<LazyGiftChooser choices={gift.choices} onPick={gift.pick} />, false)
  }

  // ── Soft sign-in gate (read freely; sign in to apply) ──
  if (status === 'anonymous' || status === 'needs-nric') {
    return wrap(
      <>
        {criteria}
        <div className="bg-ground-0 border rounded-2xl p-6 shadow-sm">
          <p className="text-ground-600 text-sm mb-4">{t('scholarship.apply.gate.readFreely')}</p>
          <button onClick={() => showAuthGate('apply')} className="btn-primary w-full flex items-center justify-center gap-2">
            <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="currentColor" d="M21.35 11.1h-9.18v2.92h5.27c-.23 1.46-1.64 4.28-5.27 4.28-3.17 0-5.76-2.62-5.76-5.85s2.59-5.85 5.76-5.85c1.81 0 3.02.77 3.71 1.43l2.53-2.44C16.46 3.6 14.43 2.7 12.17 2.7 6.91 2.7 2.7 6.91 2.7 12.45s4.21 9.75 9.47 9.75c5.47 0 9.09-3.84 9.09-9.26 0-.62-.07-1.1-.16-1.84z"/></svg>
            {t('scholarship.apply.signInButton')}
          </button>
          <p className="text-xs text-ground-400 mt-3 text-center">{t('scholarship.apply.gate.helper')}</p>
        </div>
      </>
    )
  }

  // A finished application in THIS round: say so, here (the gate's `already_applied`; never a bounce).
  if (gate.state === 'already_applied') return wrap(<AlreadyApplied onSeeOpen={gift.canChange ? gift.change : undefined} />)
  // ── status === 'ready', allowed by the gate (or it could not answer) → the tabbed form ──
  const academic = profileAcademicSummary(profile)
  const tabIndex = TAB_ORDER.indexOf(tab)
  const isLast = tabIndex === TAB_ORDER.length - 1

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
        <p className="text-xs text-ground-500">{t('scholarship.apply.aboutMeHint')}</p>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.name')}>{t('scholarship.apply.field.name')}</FieldLabel>
          <input className="input" maxLength={255} value={form.name} onChange={(e) => update('name', e.target.value)} />
          {/* Mismatch with the declaration signature blocks submit — flag it here too,
              since the About Me name (often a pre-filled handle) is the usual fix. */}
          {declarationNameMismatch(form) && (
            <p className="mt-1 text-sm text-critical-600">{t('scholarship.apply.declaration.mismatch')}</p>
          )}
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.school')}>{t('scholarship.apply.field.school')}</FieldLabel>
          <SchoolSelect value={form.school} onChange={(v) => update('school', v)} />
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.ic')}>{t('scholarship.apply.field.ic')}</FieldLabel>
          {nricLocked ? (
            <div className="input flex items-center justify-between bg-ground-50 text-ground-600">
              <span>{form.nric || '—'}</span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-positive-700">
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 10.7a1 1 0 011.4-1.4l3 3 6.8-6.8a1 1 0 011.2 0z" clipRule="evenodd"/></svg>
                {t('scholarship.apply.verified')}
              </span>
            </div>
          ) : (
            <input className="input" value={form.nric} placeholder="XXXXXX-XX-XXXX"
              inputMode="numeric" autoComplete="off"
              onChange={(e) => update('nric', formatNric(e.target.value))} />
          )}
        </div>
        <div>
          <FieldLabel>{t('scholarship.apply.field.email')}</FieldLabel>
          <div className="input flex items-center justify-between bg-ground-50 text-ground-500">
            <span className="truncate">{lockedEmail || '—'}</span>
            <span className="ml-2 shrink-0 text-xs text-ground-400">{t('scholarship.apply.locked')}</span>
          </div>
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.org')}>{t('scholarship.apply.field.org')}</FieldLabel>
          <ReferralSelect options={referralOpts} value={form.referringOrg} refused={gift.referralRefused}
            onChange={(code) => update('referringOrg', code)} />
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
            onChange={(e) => update('phone', formatPhone(e.target.value))} />
        </div>
      </div>
    ),
    family: (
      <div className="space-y-4">
        {/* Household size first — the student counts who's in the home, then totals
            that group's income (which the income tip refers back to). Both feed the
            per-capita need calc, so both are required. */}
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.household')}>{t('scholarship.apply.householdSizeLabel')}</FieldLabel>
          <input type="number" inputMode="numeric" min={1} max={20} className="input" value={form.householdSize}
            onChange={(e) => update('householdSize', e.target.value)} />
        </div>
        <div>
          <FieldLabel required tip={t('scholarship.apply.tip.income')}>{t('scholarship.apply.incomeLabel')}</FieldLabel>
          {/* Text (not number) input so it can show grouped digits + two decimals
              ("3,000.00"); raw digits only are stored. Formatted on blur, raw on focus. */}
          <input type="text" inputMode="numeric" className="input"
            value={incomeFocused ? form.householdIncome : formatMoney2dp(form.householdIncome)}
            onFocus={() => setIncomeFocused(true)}
            onBlur={() => setIncomeFocused(false)}
            onChange={(e) => update('householdIncome', e.target.value.replace(/[^\d]/g, ''))} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center text-sm text-ground-700">{t('scholarship.apply.strLabel')}<InfoTip text={t('scholarship.apply.tip.str')} /></span>
          <Toggle on={form.receivesStr} onChange={(v) => update('receivesStr', v)} label={t('scholarship.apply.strLabel')} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center text-sm text-ground-700">{t('scholarship.apply.jkmLabel')}<InfoTip text={t('scholarship.apply.tip.jkm')} /></span>
          <Toggle on={form.receivesJkm} onChange={(v) => update('receivesJkm', v)} label={t('scholarship.apply.jkmLabel')} />
        </div>
        <hr className="border-ground-100" />
        <p className="text-xs font-medium uppercase tracking-wide text-ground-400">{t('scholarship.apply.parentHeading')}</p>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.parentName')}>{t('scholarship.apply.field.parentName')}</FieldLabel>
          <input className="input" maxLength={255} value={form.parentName} onChange={(e) => update('parentName', e.target.value)} />
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.parentPhone')}>{t('scholarship.apply.field.parentPhone')}</FieldLabel>
          <input className="input" inputMode="tel" placeholder="01X-XXX XXXX" value={form.parentPhone}
            onChange={(e) => update('parentPhone', formatPhone(e.target.value))} />
        </div>
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.callLang')}>{t('scholarship.apply.field.callLang')}</FieldLabel>
          <select className="input" value={form.callLanguage}
            onChange={(e) => update('callLanguage', e.target.value as ApplyFormState['callLanguage'])}>
            {/* No empty placeholder — "Any (no preference)" (mixed) is the neutral default. */}
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
                <p className="text-sm text-ground-600 mt-1">{t('scholarship.apply.pngkLabel')}</p>
              </>
            ) : isThirdRoute(academic.examType) ? (
              <>{/* Third results route S2b: the qualification and the SERVER's overall CGPA */}
                <p className="text-3xl font-bold text-primary-700">{academic.overallCgpa?.toFixed(2) ?? '—'}</p>
                <p className="text-sm text-ground-600 mt-1">{t(`onboarding.higherKind.${academic.examType}`)} · {t('onboarding.cgpaLabel')}</p>
              </>
            ) : (
              <>
                <p className="text-3xl font-bold text-primary-700">{academic.aCount} {t('scholarship.apply.aGradesWord')}</p>
                {academic.aPlusCount > 0 && (
                  <p className="text-sm text-ground-600 mt-1">{t('scholarship.apply.including')} {academic.aPlusCount} A+</p>
                )}
              </>
            )}
            <p className="text-xs text-ground-400 mt-2">{t('scholarship.apply.resultsFromProfile')}</p>
            <button type="button" onClick={goEditResults} className="mt-3 inline-block text-sm font-medium text-primary-600 hover:underline">
              {t('scholarship.apply.resultsWrong')}
            </button>
          </div>
        ) : (
          <div className="bg-caution-50 border border-caution-200 rounded-xl p-5 text-center">
            <p className="font-medium text-ground-900 mb-1">{t('scholarship.apply.noResultsTitle')}</p>
            <p className="text-sm text-ground-600 mb-3">{t('scholarship.apply.noResultsBody')}</p>
            <button type="button" onClick={goEditResults} className="btn-primary inline-block">{t('scholarship.apply.noResultsCta')}</button>
          </div>
        )}
      </div>
    ),
    plans: (
      <div className="space-y-5">
        {/* The question, the offer branch (institution first, then course) and the waiting branch. */}
        <LazyPathwayPicker value={form} onChange={updatePlan} profile={profile} token={token} apply
          switchSlot={switchSlot} topChoices={form.topChoices} onTopChoices={(slots) => update('topChoices', slots)} />

        {/* Free text — shown for BOTH branches once answered. A student who cannot find her
            course or campus in the list tells us here. */}
        {form.pathwayCertainty !== '' && (
          <div>
            <FieldLabel>{t('scholarship.apply.plan.uncertainNoteLabel')}</FieldLabel>
            <textarea className="input" rows={3} maxLength={5000} value={form.uncertaintyNote}
              placeholder={t('scholarship.apply.plan.uncertainNotePlaceholder')}
              onChange={(e) => update('uncertaintyNote', e.target.value)} />
          </div>
        )}

        {/* Other scholarships — independent funding-overlap signal, shown once answered. */}
        {form.pathwayCertainty !== '' && (
        <div>
          <FieldLabel tip={t('scholarship.apply.tip.otherScholarships')}>{t('scholarship.apply.otherScholarshipsLabel')}</FieldLabel>
          <div className="mb-2 flex flex-wrap gap-2">
            {OTHER_SCHOLARSHIP_OPTIONS.map((opt) => {
              const on = form.otherScholarships.includes(opt)
              return (
                <button key={opt} type="button" onClick={() => toggleScholarship(opt)}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-brand-shape bg-primary-50 font-medium text-primary-700' : 'border-ground-300 text-ground-600'}`}>
                  {t(`scholarship.apply.scholarship.${opt}`)}
                </button>
              )
            })}
          </div>
          <input className="input" maxLength={300} value={form.otherScholarshipsText}
            placeholder={t('scholarship.apply.otherScholarshipsPlaceholder')}
            onChange={(e) => update('otherScholarshipsText', e.target.value)} />
        </div>
        )}
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
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-brand-shape bg-primary-50 font-medium text-primary-700' : 'border-ground-300 text-ground-600'}`}>
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
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? 'border-brand-shape bg-primary-50 font-medium text-primary-700' : 'border-ground-300 text-ground-600'}`}>
                  {t(`scholarship.apply.help.${opt}`)}
                </button>
              )
            })}
          </div>
        </div>
        <div>
          <FieldLabel>{t('scholarship.apply.anythingElseLabel')}</FieldLabel>
          <textarea className="input" rows={4} maxLength={5000} value={form.anythingElse}
            placeholder={t('scholarship.apply.anythingElsePlaceholder')}
            onChange={(e) => update('anythingElse', e.target.value)} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-ground-700">
            {t('scholarship.apply.consentLabel')}<span className="ml-0.5 text-critical-600" aria-hidden>*</span>
          </span>
          <Toggle on={form.consentToContact} onChange={(v) => update('consentToContact', v)} label={t('scholarship.apply.consentLabel')} />
        </div>

        {/* Truthfulness declaration + typed-name signature — the final, weightiest step
            before submit. Typing your IC name + submitting IS the agreement. The signature
            must match the About Me name (declarationNameMismatch) — a hard block on submit. */}
        <div className="rounded-xl border border-caution-200 bg-caution-50 p-4">
          <h3 className="mb-1 font-semibold text-ground-900">{t('scholarship.apply.declaration.title')}</h3>
          <p className="text-sm text-ground-700">{t('scholarship.apply.declaration.body')}</p>
          <div className="mt-3">
            <FieldLabel required>{t('scholarship.apply.declaration.signLabel')}</FieldLabel>
            <input
              className="input"
              maxLength={200}
              value={form.declarationName}
              placeholder={t('scholarship.apply.declaration.signPlaceholder')}
              autoComplete="off"
              onChange={(e) => update('declarationName', e.target.value)}
            />
            {declarationNameMismatch(form) && (
              <p className="mt-1 text-sm text-critical-600">{t('scholarship.apply.declaration.mismatch')}</p>
            )}
            <p className="mt-1 text-xs text-ground-500">{t('scholarship.apply.declaration.signHelp')}</p>
          </div>
        </div>
      </div>
    ),
  }

  return wrap(
    <form onSubmit={handleSubmit}>
      {/* Which gift this is for; "Change" (back to the chooser, edits kept) only when another is open */}
      <ApplyingTo name={gift.name} onChange={gift.canChange ? gift.change : undefined} />
      {/* Context bar — profile is the source of truth */}
      <div className="flex items-center gap-3 bg-ground-0 border rounded-2xl px-4 py-3 mb-4 shadow-sm">
        <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-semibold">
          {(profile?.name || '?').trim().charAt(0).toUpperCase()}
        </div>
        <div className="leading-tight">
          <p className="text-sm font-medium text-ground-900">{t('scholarship.apply.signedInAs')} {profile?.name || ''}</p>
          <p className="text-xs text-ground-400">{t('scholarship.apply.usingProfile')}</p>
        </div>
      </div>

      {/* On desktop: a left step-nav rail beside the active step (uses the horizontal
          space the mobile single column left empty). On mobile: the bottom tab bar below. */}
      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8 lg:items-start">
        <aside className="hidden lg:block">
          <nav className="sticky top-6 space-y-1">
            <Link href="/scholarship"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-ground-500 hover:bg-ground-50 hover:text-ground-700">
              <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10" />
              </svg>
              {t('scholarship.apply.tab.home')}
            </Link>
            <div className="my-1 border-t border-ground-100" />
            {TAB_ORDER.map((k, i) => {
              const active = k === tab
              const done = i < tabIndex
              return (
                <button key={k} type="button" onClick={() => setTab(k)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${active ? 'bg-primary-50 font-medium text-primary-700' : 'text-ground-600 hover:bg-ground-50'}`}>
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${active ? 'bg-brand-fill text-brand-fill-ink' : done ? 'bg-primary-100 text-primary-700' : 'bg-ground-100 text-ground-400'}`}>
                    {done ? '✓' : i + 1}
                  </span>
                  {t(`scholarship.apply.section.${sectionKey(k)}`)}
                </button>
              )
            })}
          </nav>
        </aside>

        <div>
          {/* Phone + desktop: "Step n/5 · section", the bars, and "Saved on this device only" (Mobile M4) */}
          <ApplyProgress index={tabIndex} total={TAB_ORDER.length} label={t(`scholarship.apply.section.${sectionKey(tab)}`)} />

          {/* Active section card */}
          <div className="bg-ground-0 border rounded-2xl p-5 shadow-sm mb-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <h2 className="font-semibold text-ground-900">{tabIndex + 1}. {t(`scholarship.apply.section.${sectionKey(tab)}`)}</h2>
              {tab === 'plans' && <div ref={setSwitchSlot} />}
            </div>
            {sections[tab]}
          </div>

          {/* Validation / submit error — shown on whichever tab the error sent the user to */}
          {(error || serverError) && (
            <div role="alert" aria-live="assertive" className="mb-4 rounded-lg border border-critical-200 bg-critical-50 p-3">
              <p className="text-sm text-critical-600">{error || serverError}</p>
            </div>
          )}

          {/* Back / Continue (Submit on the last step): a sticky bar on a phone, clear of the home bar */}
          <ApplyFooter first={tabIndex === 0} last={isLast} submitting={submitting} onBack={goBack} onNext={goNext} />
        </div>
      </div>
    </form>
  )
}
