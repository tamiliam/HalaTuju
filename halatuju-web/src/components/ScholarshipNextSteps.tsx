'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { updateScholarshipDetails, type ScholarshipApplication } from '@/lib/api'
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

// Programme-length options: display key → months value
const PROGRAMME_LENGTH_OPTIONS: { key: string; months: number }[] = [
  { key: 'length12', months: 12 },
  { key: 'length24', months: 24 },
  { key: 'length36', months: 36 },
  { key: 'length48', months: 48 },
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
  }
  return (
    <svg className={cls} fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d={paths[step]} />
    </svg>
  )
}

export default function ScholarshipNextSteps({
  initialApp,
  token,
}: {
  initialApp: ScholarshipApplication
  token: string | null
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

  const c = app.completeness
  const tabIndex = NEXT_STEP_ORDER.indexOf(tab)

  // Completeness mapping — every step now has a backend signal (S5).
  const stepDone: Record<NextStepKey, boolean> = {
    quiz: c.quiz_done,
    story: c.details_done,
    funding: c.funding_done,
    documents: c.documents_done,
    consent: c.consent_done,
  }

  // The shared save feedback — rendered inside whichever tab has the Save button.
  const saveFeedback = (
    <>
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
      {saved && <p className="text-green-700 text-sm">{t('scholarship.nextSteps.saved')}</p>}
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
          <Link href="/quiz" className="btn-primary inline-block text-sm">
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
        <p className="text-sm text-gray-600 italic">{t('scholarship.nextSteps.story.langNote')}</p>

        {/* Card A — About your family */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
          <h3 className="font-medium text-gray-900">{t('scholarship.nextSteps.story.cardA.title')}</h3>

          {/* first_in_family */}
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              checked={form.firstInFamily}
              onChange={(e) => update('firstInFamily', e.target.checked)}
            />
            <span className="text-sm text-gray-700">{t('scholarship.nextSteps.story.cardA.firstInFamily')}</span>
          </label>

          {/* parents_occupation */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardA.parentsOccupation')}
            </label>
            <input
              type="text"
              className="input"
              value={form.parentsOccupation}
              onChange={(e) => update('parentsOccupation', e.target.value)}
            />
          </div>

          {/* siblings_studying (optional) */}
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              checked={form.siblingsStudying}
              onChange={(e) => update('siblingsStudying', e.target.checked)}
            />
            <span className="text-sm text-gray-700">
              {t('scholarship.nextSteps.story.cardA.siblingsStudying')}
              {' '}<span className="text-xs text-gray-400 font-normal">{t('scholarship.nextSteps.story.optional')}</span>
            </span>
          </label>

          {/* family_context (optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardA.familyContext')}
              {' '}<span className="text-xs text-gray-400 font-normal">{t('scholarship.nextSteps.story.optional')}</span>
            </label>
            <textarea
              className="input" rows={3}
              value={form.familyContext}
              onChange={(e) => update('familyContext', e.target.value)}
            />
          </div>
        </div>

        {/* Card B — About you */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
          <h3 className="font-medium text-gray-900">{t('scholarship.nextSteps.story.cardB.title')}</h3>

          {/* aspirations */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardB.aspirations')}
            </label>
            <textarea
              className="input" rows={3}
              value={form.aspirations}
              onChange={(e) => update('aspirations', e.target.value)}
            />
          </div>

          {/* plans */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardB.plans')}
            </label>
            <textarea
              className="input" rows={3}
              value={form.plans}
              onChange={(e) => update('plans', e.target.value)}
            />
          </div>

          {/* daily_life (optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardB.dailyLife')}
              {' '}<span className="text-xs text-gray-400 font-normal">{t('scholarship.nextSteps.story.optional')}</span>
            </label>
            <textarea
              className="input" rows={3}
              value={form.dailyLife}
              onChange={(e) => update('dailyLife', e.target.value)}
            />
          </div>

          {/* fears (optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.nextSteps.story.cardB.fears')}
              {' '}<span className="text-xs text-gray-400 font-normal">{t('scholarship.nextSteps.story.optional')}</span>
            </label>
            <textarea
              className="input" rows={3}
              value={form.fears}
              onChange={(e) => update('fears', e.target.value)}
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
        {/* Info box — honest framing: "a contribution, not full funding" */}
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <p className="text-sm text-blue-800">{t('scholarship.nextSteps.funding.infoBox')}</p>
        </div>

        {/* Intro */}
        <p className="text-sm text-gray-700">{t('scholarship.nextSteps.funding.intro')}</p>

        {/* Programme length dropdown */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.nextSteps.funding.lengthLabel')}
          </label>
          <select
            className="input"
            value={form.programmeMonths}
            onChange={(e) => update('programmeMonths', e.target.value)}
          >
            <option value=""></option>
            {PROGRAMME_LENGTH_OPTIONS.map(({ key, months }) => (
              <option key={key} value={String(months)}>
                {t(`scholarship.nextSteps.funding.${key}`)}
              </option>
            ))}
          </select>
        </div>

        {/* Category checklist */}
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">
            {t('scholarship.nextSteps.funding.categoriesLabel')}
          </p>
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
                  {/* "Something else" text input — revealed when ticked */}
                  {cat === 'other' && checked && (
                    <div className="ml-7 mt-1">
                      <input
                        type="text"
                        className="input text-sm"
                        placeholder={t('scholarship.nextSteps.funding.cat_other_desc')}
                        value={form.otherDesc}
                        onChange={(e) => update('otherDesc', e.target.value)}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Open optional note */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.nextSteps.funding.noteLabel')}
          </label>
          <textarea
            className="input"
            rows={3}
            value={form.fundingNote}
            onChange={(e) => update('fundingNote', e.target.value)}
          />
          <p className="mt-1 text-xs text-gray-500">
            {t('scholarship.nextSteps.funding.noteHelper')}
          </p>
        </div>

        {saveFeedback}
        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? t('scholarship.nextSteps.saving') : t('scholarship.nextSteps.save')}
        </button>
      </form>
    ),

    documents: (
      <div className="space-y-3">
        <p className="text-sm text-gray-600">{t('scholarship.nextSteps.step4Body')}</p>
        <ScholarshipDocuments token={token} />
      </div>
    ),

    consent: (
      <div className="space-y-3">
        <p className="text-sm text-gray-600">{t('scholarship.nextSteps.step6Body')}</p>
        <ScholarshipConsent token={token} locale={locale} />
      </div>
    ),
  }

  return (
    <div>
      {/* Intro banner — switches to a success state once everything is done */}
      <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-6">
        {c.complete ? (
          <>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-green-600 text-white text-sm">✓</span>
              <h2 className="font-semibold text-gray-900">{t('scholarship.nextSteps.allSetTitle')}</h2>
            </div>
            <p className="text-sm text-gray-700 mt-1">{t('scholarship.nextSteps.allSetIntro')}</p>
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
          <div className="bg-white border rounded-2xl p-5 shadow-sm">
            <h2 className="font-semibold text-gray-900 mb-4">
              {tabIndex + 1}. {t(`scholarship.nextSteps.tab.${tab}`)}
            </h2>
            {sections[tab]}
          </div>
        </div>
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
