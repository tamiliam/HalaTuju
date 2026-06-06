'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { updateScholarshipDetails, confirmScholarshipApplication, getScholarshipApplication, type ScholarshipApplication, type StudentProfile } from '@/lib/api'
import {
  applicationToDetailsForm,
  buildDetailsPayload,
  NEXT_STEP_ORDER,
  defaultNextTab,
  type NextStepKey,
  type DetailsFormState,
} from '@/lib/scholarship'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import ScholarshipConsent from '@/components/ScholarshipConsent'
import ScholarshipReview from '@/components/ScholarshipReview'
import ActionCentre from '@/components/ActionCentre'
import InfoBox from '@/components/InfoBox'
import FieldLabel from '@/components/FieldLabel'
import Toggle from '@/components/Toggle'
import type { ConfirmTarget } from '@/lib/actionCentre'

/** Small collapsible "Need ideas?" tips panel rendered below an open-ended
 *  textarea. Native <details> for accessibility + zero JS. Three tip bullets
 *  by convention — keeps the cheat-sheet short and encouraging. */
function Tips({ title, tips }: { title: string; tips: string[] }) {
  return (
    <details className="mt-1 text-xs text-gray-500">
      <summary className="cursor-pointer select-none text-primary-600 hover:underline">{title}</summary>
      <ul className="mt-1.5 ml-4 list-disc space-y-0.5">
        {tips.map((tip) => <li key={tip}>{tip}</li>)}
      </ul>
    </details>
  )
}

// Category keys and their i18n keys for the funding tab (S3 redesign)
const FUNDING_CATEGORIES = [
  'living',
  'transport',
  'accommodation',
  'books',
  'device',
  'tuition',
  'other',
] as const
type FundingCategory = typeof FUNDING_CATEGORIES[number]

// Programme-length options: display key → months value. Five-year covers PISMP
// and 5-year degrees (medicine, dentistry, pharmacy). Labels are year-only by
// design — the same year-count maps to different programme levels (e.g. 1y =
// matric OR foundation; 3y = diploma OR most degrees; 5y = PISMP OR med-degree),
// so labelling a row "1 year (Matriculation / Foundation)" was misleading.
const PROGRAMME_LENGTH_OPTIONS: { key: string; months: number }[] = [
  { key: 'length12', months: 12 },
  { key: 'length24', months: 24 },
  { key: 'length36', months: 36 },
  { key: 'length48', months: 48 },
  { key: 'length60', months: 60 },
]

// SVG icon for each tab — mirrors the style in /apply's TabIcon.
function StepIcon({ step, active }: { step: NextStepKey; active: boolean }) {
  const cls = `w-6 h-6 ${active ? 'text-primary-600' : 'text-gray-400'}`
  const paths: Record<NextStepKey, string> = {
    quiz: 'M9 12l2 2 4-4m1-7H8a2 2 0 00-2 2v14a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2z',
    story: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    funding: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    documents: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
    consent: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    review: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01',
  }
  return (
    <svg className={cls} fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d={paths[step]} />
    </svg>
  )
}

/** Render the tech-support text with the email address as a mailto: link. */
function renderTechSupport(text: string): React.ReactNode {
  const email = 'tamiliam@gmail.com'
  const i = text.indexOf(email)
  if (i === -1) return text
  return (
    <>
      {text.slice(0, i)}
      <a href={`mailto:${email}`} className="font-medium underline hover:no-underline">{email}</a>
      {text.slice(i + email.length)}
    </>
  )
}

export default function ScholarshipNextSteps({
  initialApp,
  token,
  studentName,
  profile,
}: {
  initialApp: ScholarshipApplication
  token: string | null
  studentName?: string
  profile?: StudentProfile | null
}) {
  const { t, locale } = useT()
  const [app, setApp] = useState<ScholarshipApplication>(initialApp)
  const [form, setForm] = useState<DetailsFormState>(() => applicationToDetailsForm(initialApp))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [tab, setTab] = useState<NextStepKey>(() => defaultNextTab(initialApp.completeness))

  const update = <K extends keyof DetailsFormState>(key: K, value: DetailsFormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  // Refresh status + completeness after a document/consent change (which can flip
  // status, e.g. deleting a compulsory doc un-confirms a profile_complete app).
  // Only updates `app` — NOT `form` — so in-progress story/funding edits are kept.
  const refreshApp = async () => {
    if (!token) return
    try { setApp(await getScholarshipApplication(app.id, { token })) } catch { /* ignore */ }
  }

  // Action Centre "Review" → switch to the section that resolves a `confirm`
  // ticket and scroll the step card into view. The grades/results live in the
  // Documents tab (results_slip), identity & income also in Documents, and the
  // pathway narrative in "Your story".
  const handleConfirmNav = (target: ConfirmTarget) => {
    const tabFor: Record<ConfirmTarget, NextStepKey> = {
      results: 'documents',
      documents: 'documents',
      story: 'story',
    }
    setTab(tabFor[target])
    // Defer the scroll until the tab content has rendered.
    setTimeout(() => {
      document.getElementById('next-steps-active')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }

  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await updateScholarshipDetails(app.id, buildDetailsPayload(form), { token })
      setApp(updated)
      setForm(applicationToDetailsForm(updated))
      setSaved(true)
    } catch {
      setError(t('scholarship.nextSteps.saveError'))
    } finally {
      setSaving(false)
    }
  }

  // Phase C: the explicit "Confirm & submit" action (shortlisted → profile_complete).
  const handleConfirm = async () => {
    if (!token) return
    setConfirming(true)
    setConfirmError(null)
    try {
      const updated = await confirmScholarshipApplication(app.id, { token })
      setApp(updated)
    } catch {
      setConfirmError(t('scholarship.nextSteps.confirmError'))
    } finally {
      setConfirming(false)
    }
  }

  const c = app.completeness
  const confirmed = app.status !== 'shortlisted'  // profile_complete or further along
  const tabIndex = NEXT_STEP_ORDER.indexOf(tab)

  // Completeness mapping — every step now has a backend signal (S5).
  // S14: story tick requires the narrative AND the address sub-section (both
  // captured in the same tab; users see one consolidated done state).
  const stepDone: Record<NextStepKey, boolean> = {
    quiz: c.quiz_done,
    story: c.details_done && c.address_done,
    funding: c.funding_done,
    documents: c.documents_done,
    consent: c.consent_done,
    review: confirmed,   // ticked once submitted
  }

  // Jump to a step's tab and scroll its card into view — used by the review page's
  // per-section Edit links (and Back).
  const goToStep = (k: NextStepKey) => {
    setTab(k)
    setTimeout(() => {
      document.getElementById('next-steps-active')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }

  // The shared save feedback — rendered inside whichever tab has the Save button.
  const saveFeedback = (
    <>
      {error && <InfoBox kind="block">{error}</InfoBox>}
      {saved && <p className="text-sm text-green-800">{t('scholarship.nextSteps.saved')}</p>}
    </>
  )

  // ── Tab content ──
  const sections: Record<NextStepKey, React.ReactNode> = {
    quiz: (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${c.quiz_done ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'}`} aria-hidden>
            {c.quiz_done ? '✓' : '○'}
          </span>
          <p className="font-medium text-gray-900">{t('scholarship.nextSteps.step1Title')}</p>
        </div>
        <p className="text-sm text-gray-600">{t('scholarship.nextSteps.step1Body')}</p>
        {!c.quiz_done && (
          <Link href="/quiz?return=application" className="btn-primary inline-block text-sm">
            {t('scholarship.nextSteps.step1Cta')}
          </Link>
        )}
        {c.quiz_done && (
          <p className="text-sm text-green-700">{t('scholarship.nextSteps.allDone').split('—')[0].trim()}</p>
        )}
      </div>
    ),

    story: (
      <form onSubmit={handleSave} className="space-y-5">
        {/* Language note (the card title "2. Your story" already heads the section) */}
        <InfoBox kind="info">{t('scholarship.nextSteps.story.langNote')}</InfoBox>

        {/* Card A — About your family */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
          <h3 className="font-medium text-gray-900">{t('scholarship.nextSteps.story.cardA.title')}</h3>

          {/* first_in_family — slide toggle (S15) for consistency with /apply */}
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-gray-700">{t('scholarship.nextSteps.story.cardA.firstInFamily')}</span>
            <Toggle
              on={form.firstInFamily}
              onChange={(v) => update('firstInFamily', v)}
              label={t('scholarship.nextSteps.story.cardA.firstInFamily')}
            />
          </div>

          {/* parents_occupation */}
          <div>
            <FieldLabel>{t('scholarship.nextSteps.story.cardA.parentsOccupation')}</FieldLabel>
            <input
              type="text"
              className="input"
              placeholder={t('scholarship.nextSteps.story.cardA.parentsOccupationPlaceholder')}
              value={form.parentsOccupation}
              onChange={(e) => update('parentsOccupation', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardA.parentsOccupationTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardA.parentsOccupationTip1'),
                t('scholarship.nextSteps.story.cardA.parentsOccupationTip2'),
                t('scholarship.nextSteps.story.cardA.parentsOccupationTip3'),
              ]}
            />
          </div>

          {/* siblings_studying_count — open numeric (S15 replaces the boolean tick) */}
          <div>
            <FieldLabel>{t('scholarship.nextSteps.story.cardA.siblingsCountLabel')}</FieldLabel>
            <input
              type="text"
              inputMode="numeric"
              maxLength={2}
              placeholder="0"
              className="input w-24"
              value={form.siblingsStudyingCount}
              onChange={(e) => update('siblingsStudyingCount', e.target.value.replace(/\D/g, '').slice(0, 2))}
            />
          </div>

          {/* family_context */}
          <div>
            <FieldLabel>{t('scholarship.nextSteps.story.cardA.familyContext')}</FieldLabel>
            <textarea
              className="input" rows={3}
              placeholder={t('scholarship.nextSteps.story.cardA.familyContextPlaceholder')}
              value={form.familyContext}
              onChange={(e) => update('familyContext', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardA.familyContextTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardA.familyContextTip1'),
                t('scholarship.nextSteps.story.cardA.familyContextTip2'),
                t('scholarship.nextSteps.story.cardA.familyContextTip3'),
              ]}
            />
          </div>
        </div>

        {/* Card A.5 — Where you live (S14). State is read-only from /apply. */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
          <h3 className="font-medium text-gray-900">{t('scholarship.nextSteps.story.cardAddress.title')}</h3>
          <p className="text-xs text-gray-500">{t('scholarship.nextSteps.story.cardAddress.intro')}</p>

          {/* address (street) — required */}
          <div>
            <FieldLabel required>{t('scholarship.nextSteps.story.cardAddress.street')}</FieldLabel>
            <textarea
              className="input" rows={2}
              placeholder={t('scholarship.nextSteps.story.cardAddress.streetPlaceholder')}
              value={form.address}
              onChange={(e) => update('address', e.target.value)}
            />
          </div>

          {/* postal + city — two-column on wider screens, both required */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <FieldLabel required>{t('scholarship.nextSteps.story.cardAddress.postal')}</FieldLabel>
              <input
                type="text"
                inputMode="numeric"
                maxLength={5}
                placeholder="62100"
                className="input"
                value={form.postalCode}
                onChange={(e) => update('postalCode', e.target.value.replace(/\D/g, '').slice(0, 5))}
              />
            </div>
            <div>
              <FieldLabel required>{t('scholarship.nextSteps.story.cardAddress.city')}</FieldLabel>
              <input
                type="text"
                className="input"
                placeholder={t('scholarship.nextSteps.story.cardAddress.cityPlaceholder')}
                value={form.city}
                onChange={(e) => update('city', e.target.value)}
              />
            </div>
          </div>

          {/* state — read-only, sourced from /apply */}
          <div>
            <FieldLabel>{t('scholarship.nextSteps.story.cardAddress.state')}</FieldLabel>
            <div className="input flex items-center justify-between bg-gray-100 text-gray-600">
              <span>{app.preferred_state || '—'}</span>
              <span className="text-xs text-gray-400">{t('scholarship.nextSteps.story.cardAddress.fromApply')}</span>
            </div>
          </div>
        </div>

        {/* Card B — About you */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
          <h3 className="font-medium text-gray-900">{t('scholarship.nextSteps.story.cardB.title')}</h3>

          {/* aspirations — required */}
          <div>
            <FieldLabel required>{t('scholarship.nextSteps.story.cardB.aspirations')}</FieldLabel>
            <textarea
              className="input" rows={3}
              placeholder={t('scholarship.nextSteps.story.cardB.aspirationsPlaceholder')}
              value={form.aspirations}
              onChange={(e) => update('aspirations', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardB.aspirationsTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardB.aspirationsTip1'),
                t('scholarship.nextSteps.story.cardB.aspirationsTip2'),
                t('scholarship.nextSteps.story.cardB.aspirationsTip3'),
              ]}
            />
          </div>

          {/* plans — required */}
          <div>
            <FieldLabel required>{t('scholarship.nextSteps.story.cardB.plans')}</FieldLabel>
            <textarea
              className="input" rows={3}
              placeholder={t('scholarship.nextSteps.story.cardB.plansPlaceholder')}
              value={form.plans}
              onChange={(e) => update('plans', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardB.plansTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardB.plansTip1'),
                t('scholarship.nextSteps.story.cardB.plansTip2'),
                t('scholarship.nextSteps.story.cardB.plansTip3'),
              ]}
            />
          </div>

          {/* daily_life — required (S: compulsory narrative) */}
          <div>
            <FieldLabel required>{t('scholarship.nextSteps.story.cardB.dailyLife')}</FieldLabel>
            <textarea
              className="input" rows={3}
              placeholder={t('scholarship.nextSteps.story.cardB.dailyLifePlaceholder')}
              value={form.dailyLife}
              onChange={(e) => update('dailyLife', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardB.dailyLifeTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardB.dailyLifeTip1'),
                t('scholarship.nextSteps.story.cardB.dailyLifeTip2'),
                t('scholarship.nextSteps.story.cardB.dailyLifeTip3'),
              ]}
            />
          </div>

          {/* fears (worries / support needed) — required */}
          <div>
            <FieldLabel required>{t('scholarship.nextSteps.story.cardB.fears')}</FieldLabel>
            <textarea
              className="input" rows={3}
              placeholder={t('scholarship.nextSteps.story.cardB.fearsPlaceholder')}
              value={form.fears}
              onChange={(e) => update('fears', e.target.value)}
            />
            <Tips
              title={t('scholarship.nextSteps.story.cardB.fearsTipsTitle')}
              tips={[
                t('scholarship.nextSteps.story.cardB.fearsTip1'),
                t('scholarship.nextSteps.story.cardB.fearsTip2'),
                t('scholarship.nextSteps.story.cardB.fearsTip3'),
              ]}
            />
          </div>
        </div>

        {/* Statement-of-intent note */}
        <p className="text-xs text-gray-500">{t('scholarship.nextSteps.story.soiNote')}</p>

        {saveFeedback}
        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? t('scholarship.nextSteps.saving') : t('scholarship.nextSteps.save')}
        </button>
      </form>
    ),

    funding: (
      <form onSubmit={handleSave} className="space-y-5">
        {/* Instruction-led info box (merged S20 — old `infoBox` framing now
            folded into the single `intro` string so the student sees one
            clear instruction + context rather than two stacked paragraphs). */}
        <InfoBox kind="info">{t('scholarship.nextSteps.funding.intro')}</InfoBox>

        {/* Decided study (from /apply) — read-only, so the student sees what they
            are funding. Only when they committed to a choice; uncertain students
            (still exploring) see nothing here. */}
        {app.pathway_certainty === 'sure' && (() => {
          const pathway = app.chosen_pathway
            ? t(`scholarship.apply.plan.pathway.${app.chosen_pathway}`) : ''
          const label = app.chosen_programme?.course_name
            || [pathway, app.pre_u_track, app.pre_u_institution].filter(Boolean).join(' · ')
            || pathway
          return label ? (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="text-xs uppercase tracking-wide text-gray-400">
                {t('scholarship.nextSteps.funding.chosenStudyLabel')}
              </p>
              <p className="mt-0.5 text-sm font-medium text-gray-800">{label}</p>
            </div>
          ) : null
        })()}

        {/* Programme length — horizontal pill row, just the number; "in years"
            moved into the question label (avoids repeating "year(s)" five times).
            Pills are radios under the hood (sr-only input wrapped in the label)
            so keyboard / screen-reader behaviour matches a native radio group.
            Compulsory: funding_done requires programme_months to be set. */}
        <div>
          <FieldLabel required>{t('scholarship.nextSteps.funding.lengthLabel')}</FieldLabel>
          <div className="mt-2 flex flex-wrap gap-2">
            {PROGRAMME_LENGTH_OPTIONS.map(({ key, months }) => {
              const selected = form.programmeMonths === String(months)
              return (
                <label
                  key={key}
                  className={`cursor-pointer rounded-lg border px-4 py-2 text-sm font-medium min-w-[3.5rem] text-center transition-colors ${
                    selected
                      ? 'border-primary-600 bg-primary-600 text-white'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="programmeMonths"
                    className="sr-only"
                    value={String(months)}
                    checked={selected}
                    onChange={(e) => update('programmeMonths', e.target.value)}
                  />
                  {t(`scholarship.nextSteps.funding.${key}`)}
                </label>
              )
            })}
          </div>
        </div>

        {/* Category checklist — at least one tick required (funding_done rule). */}
        <div>
          <FieldLabel required>{t('scholarship.nextSteps.funding.categoriesLabel')}</FieldLabel>
          <div className="space-y-2">
            {FUNDING_CATEGORIES.map((cat) => {
              const checked = form.fundingCategories.includes(cat)
              const toggle = () => {
                const next = checked
                  ? form.fundingCategories.filter((c) => c !== cat)
                  : [...form.fundingCategories, cat]
                update('fundingCategories', next)
              }
              return (
                <div key={cat}>
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      checked={checked}
                      onChange={toggle}
                    />
                    <span className="text-sm text-gray-700">
                      {t(`scholarship.nextSteps.funding.cat_${cat}`)}
                    </span>
                  </label>
                  {/* Tuition helper text */}
                  {cat === 'tuition' && (
                    <p className="ml-7 mt-0.5 text-xs text-gray-500">
                      {t('scholarship.nextSteps.funding.cat_tuition_helper')}
                    </p>
                  )}
                  {/* "Something else" — the open free-text box below the categories
                      (form.fundingNote) is where the student elaborates. */}
                </div>
              )
            })}
          </div>
        </div>

        {/* Open note — optional, but no "(optional)" suffix per convention. */}
        <div>
          <FieldLabel>{t('scholarship.nextSteps.funding.noteLabel')}</FieldLabel>
          <textarea
            className="input"
            rows={3}
            placeholder={t('scholarship.nextSteps.funding.notePlaceholder')}
            value={form.fundingNote}
            onChange={(e) => update('fundingNote', e.target.value)}
          />
          <Tips
            title={t('scholarship.nextSteps.funding.noteTipsTitle')}
            tips={[
              t('scholarship.nextSteps.funding.noteTip1'),
              t('scholarship.nextSteps.funding.noteTip2'),
              t('scholarship.nextSteps.funding.noteTip3'),
            ]}
          />
        </div>

        {saveFeedback}
        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? t('scholarship.nextSteps.saving') : t('scholarship.nextSteps.save')}
        </button>
      </form>
    ),

    documents: (
      <div className="space-y-3">
        <InfoBox kind="info">{t('scholarship.nextSteps.step4Body')}</InfoBox>
        <ScholarshipDocuments token={token} onChange={refreshApp} app={app} />
      </div>
    ),

    consent: (
      <div className="space-y-3">
        {/* step6Body intro removed — the Consent component carries its own
            student-directed info notice (for minors) + the consent body
            itself, so a stacked "Allow us to share…" line was redundant. */}
        <ScholarshipConsent token={token} locale={locale} onChange={refreshApp} />
      </div>
    ),

    // The final read-back. Submit here is the ONLY commit (lock-at-Continue).
    review: (
      <ScholarshipReview
        app={app}
        profile={profile ?? null}
        token={token}
        onEdit={goToStep}
        onBack={() => goToStep('consent')}
        onSubmit={handleConfirm}
        submitting={confirming}
        submitError={confirmError}
        canSubmit={c.complete}
        confirmed={confirmed}
        t={t}
        lang={locale}
      />
    ),
  }

  return (
    <div>
      {/* Student Action Centre — the self-service "things to finish" queue, shown
          ABOVE the step tabs. Additive: it renders nothing when there are no
          tickets. "Review" on a confirm ticket switches to the relevant tab. */}
      <ActionCentre token={token} studentName={studentName} onConfirm={handleConfirmNav} />

      {/* Admin "please send more documentation" request — shown until resolved by the admin */}
      {app.info_request_note && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
          <p className="text-sm font-medium text-amber-900">{t('scholarship.nextSteps.infoRequestTitle')}</p>
          <p className="text-sm text-amber-800 mt-1 whitespace-pre-line">{app.info_request_note}</p>
        </div>
      )}

      {/* Intro banner — switches to a success state once everything is done */}
      <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-6">
        {c.complete ? (
          <>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-green-600 text-white text-sm">✓</span>
              <h2 className="font-semibold text-gray-900">
                {confirmed ? t('scholarship.nextSteps.confirmedTitle') : t('scholarship.nextSteps.allSetTitle')}
              </h2>
            </div>
            <p className="text-sm text-gray-700 mt-1">
              {confirmed ? t('scholarship.nextSteps.confirmedIntro') : t('scholarship.nextSteps.allSetIntro')}
            </p>
            {/* The commit now lives on the Review step ("lock at Continue"): this
                button takes the student to the final read-back, where they submit. */}
            {!confirmed && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => goToStep('review')}
                  className="btn-primary"
                >
                  {t('scholarship.nextSteps.reviewCta')}
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <h2 className="font-semibold text-gray-900">{t('scholarship.nextSteps.title')}</h2>
            <p className="text-sm text-gray-700 mt-1">{t('scholarship.nextSteps.intro')}</p>
          </>
        )}
      </div>

      {/* What happens next — shown once the application is complete */}
      {c.complete && (
        <div className="bg-white border rounded-2xl p-5 shadow-sm mb-6">
          <h3 className="font-semibold text-gray-900 mb-3">{t('scholarship.nextSteps.whatNext.title')}</h3>
          <ol className="space-y-3">
            {['step1', 'step2', 'step3'].map((s, i) => (
              <li key={s} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700 text-xs font-semibold">
                  {i + 1}
                </span>
                <span className="text-sm text-gray-700">{t(`scholarship.nextSteps.whatNext.${s}`)}</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-primary-50 p-3">
            <span className="text-primary-600 shrink-0" aria-hidden>✉️</span>
            <p className="text-sm text-gray-700">
              {t('scholarship.nextSteps.whatNext.emailNote', {
                email: app.notify_email || t('scholarship.nextSteps.whatNext.yourEmail'),
              })}
            </p>
          </div>
        </div>
      )}

      {/* On desktop: left step-rail beside the active section. On mobile: bottom tab bar. */}
      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8 lg:items-start">
        {/* Desktop left rail */}
        <aside className="hidden lg:block">
          <nav className="sticky top-6 space-y-1">
            {NEXT_STEP_ORDER.map((k, i) => {
              const active = k === tab
              const done = stepDone[k]
              return (
                <button key={k} type="button" onClick={() => setTab(k)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${active ? 'bg-primary-50 font-medium text-primary-700' : 'text-gray-600 hover:bg-gray-50'}`}>
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${active ? 'bg-primary-500 text-white' : done ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-400'}`}>
                    {done ? '✓' : i + 1}
                  </span>
                  {t(`scholarship.nextSteps.tab.${k}`)}
                </button>
              )
            })}
            {/* TEMP (testing only — remove when testing is done): tech-support help
                placed in the menu so it's reachable on every step during testing. */}
            <div className="pt-3">
              <InfoBox kind="info">{renderTechSupport(t('scholarship.nextSteps.techSupport'))}</InfoBox>
            </div>
          </nav>
        </aside>

        {/* Main content area */}
        <div>
          {/* Progress bar + step indicator */}
          <div className="mb-1 flex gap-1.5">
            {NEXT_STEP_ORDER.map((k, i) => (
              <span key={k} className={`h-1.5 flex-1 rounded-full ${i <= tabIndex ? 'bg-primary-500' : 'bg-gray-200'}`} />
            ))}
          </div>
          <p className="text-xs text-gray-500 mb-4">
            {t('scholarship.nextSteps.stepOf', { n: String(tabIndex + 1) })} · {t(`scholarship.nextSteps.tab.${tab}`)}
          </p>

          {/* Active section card */}
          <div id="next-steps-active" className="bg-white border rounded-2xl p-5 shadow-sm scroll-mt-6">
            <h2 className="font-semibold text-gray-900 mb-4">
              {tabIndex + 1}. {t(`scholarship.nextSteps.tab.${tab}`)}
            </h2>
            {sections[tab]}
          </div>
        </div>
      </div>

      {/* TEMP (testing only — remove when done): tech-support on mobile, where the
          left menu is hidden. */}
      <div className="lg:hidden mt-4">
        <InfoBox kind="info">{renderTechSupport(t('scholarship.nextSteps.techSupport'))}</InfoBox>
      </div>

      {/* Bottom tab bar (mobile only) */}
      <nav className="sticky bottom-0 bg-white border-t flex justify-around py-2 -mx-6 px-2 lg:hidden mt-4">
        {NEXT_STEP_ORDER.map((k) => (
          <button key={k} type="button" onClick={() => setTab(k)}
            className="flex flex-col items-center gap-0.5 px-2 py-1 min-w-[56px]">
            <StepIcon step={k} active={k === tab} />
            <span className={`text-[10px] ${k === tab ? 'text-primary-600 font-medium' : 'text-gray-400'}`}>
              {t(`scholarship.nextSteps.tab.${k}`)}
            </span>
          </button>
        ))}
      </nav>
    </div>
  )
}
