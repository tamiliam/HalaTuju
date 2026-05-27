'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { updateScholarshipDetails, type ScholarshipApplication } from '@/lib/api'
import {
  applicationToDetailsForm,
  buildDetailsPayload,
  fundingTotal,
  NEXT_STEP_ORDER,
  defaultNextTab,
  type NextStepKey,
  type DetailsFormState,
} from '@/lib/scholarship'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import ScholarshipConsent from '@/components/ScholarshipConsent'

const TEXT_FIELDS = ['aspirations', 'justification', 'plans', 'fears'] as const
const MONEY_FIELDS = ['tuitionGap', 'laptop', 'hostel', 'transport', 'books', 'other'] as const

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
  const total = fundingTotal(form)
  const tabIndex = NEXT_STEP_ORDER.indexOf(tab)

  // Completeness mapping: quiz and details/funding have backend signals.
  // Documents + Consent have no completeness field yet (S4/S5) — show as neutral.
  const stepDone: Record<NextStepKey, boolean> = {
    quiz: c.quiz_done,
    story: c.details_done,
    funding: c.funding_done,
    documents: false,
    consent: false,
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
      <form onSubmit={handleSave} className="space-y-4">
        <div className="flex items-center gap-3 mb-1">
          <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${c.details_done ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'}`} aria-hidden>
            {c.details_done ? '✓' : '○'}
          </span>
          <p className="font-medium text-gray-900">{t('scholarship.nextSteps.step2Title')}</p>
        </div>
        {TEXT_FIELDS.map((field) => (
          <div key={field}>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t(`scholarship.nextSteps.${field}`)}
            </label>
            <textarea
              className="input" rows={2} value={form[field]}
              onChange={(e) => update(field, e.target.value)}
            />
          </div>
        ))}
        {saveFeedback}
        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? t('scholarship.nextSteps.saving') : t('scholarship.nextSteps.save')}
        </button>
      </form>
    ),

    funding: (
      <form onSubmit={handleSave} className="space-y-4">
        <div className="flex items-center gap-3 mb-1">
          <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${c.funding_done ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'}`} aria-hidden>
            {c.funding_done ? '✓' : '○'}
          </span>
          <p className="font-medium text-gray-900">{t('scholarship.nextSteps.step3Title')}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {MONEY_FIELDS.map((item) => (
            <div key={item}>
              <label className="block text-sm text-gray-700 mb-1">
                {t(`scholarship.nextSteps.${item}`)}
              </label>
              <input
                type="number" min={0} className="input" value={form[item]}
                onChange={(e) => update(item, e.target.value)}
              />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-700 mb-1">
              {t('scholarship.nextSteps.monthlyAllowance')}
            </label>
            <input
              type="number" min={0} className="input" value={form.monthlyAllowance}
              onChange={(e) => update('monthlyAllowance', e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">
              {t('scholarship.nextSteps.allowanceMonths')}
            </label>
            <input
              type="number" min={0} className="input" value={form.allowanceMonths}
              onChange={(e) => update('allowanceMonths', e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm text-gray-700 mb-1">
            {t('scholarship.nextSteps.otherDesc')}
          </label>
          <input
            type="text" className="input" value={form.otherDesc}
            onChange={(e) => update('otherDesc', e.target.value)}
          />
        </div>
        <p className="text-right font-semibold text-gray-900">
          {t('scholarship.nextSteps.total')}: RM{total.toLocaleString()}
        </p>
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
      {/* Intro banner */}
      <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-6">
        <h2 className="font-semibold text-gray-900">{t('scholarship.nextSteps.title')}</h2>
        <p className="text-sm text-gray-700 mt-1">{t('scholarship.nextSteps.intro')}</p>
        {c.complete && (
          <p className="text-sm font-medium text-green-700 mt-2">{t('scholarship.nextSteps.allDone')}</p>
        )}
      </div>

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
