'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { updateScholarshipDetails, type ScholarshipApplication } from '@/lib/api'
import {
  applicationToDetailsForm,
  buildDetailsPayload,
  fundingTotal,
  type DetailsFormState,
} from '@/lib/scholarship'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import ScholarshipReferee from '@/components/ScholarshipReferee'
import ScholarshipConsent from '@/components/ScholarshipConsent'

const TEXT_FIELDS = ['aspirations', 'justification', 'plans', 'fears'] as const
const MONEY_FIELDS = ['tuitionGap', 'laptop', 'hostel', 'transport', 'books', 'other'] as const

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

  const check = (done: boolean) => (
    <span
      className={`inline-flex w-6 h-6 rounded-full items-center justify-center text-sm flex-shrink-0 ${
        done ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
      }`}
      aria-hidden
    >
      {done ? '✓' : '○'}
    </span>
  )

  return (
    <div className="space-y-6">
      <div className="bg-green-50 border border-green-200 rounded-xl p-5">
        <h2 className="font-semibold text-gray-900">{t('scholarship.nextSteps.title')}</h2>
        <p className="text-sm text-gray-700 mt-1">{t('scholarship.nextSteps.intro')}</p>
        {c.complete && (
          <p className="text-sm font-medium text-green-700 mt-2">{t('scholarship.nextSteps.allDone')}</p>
        )}
      </div>

      {/* Step 1 — course quiz (reuses the existing /quiz) */}
      <div className="border rounded-xl p-4 flex items-start gap-3">
        {check(c.quiz_done)}
        <div className="flex-1">
          <p className="font-medium text-gray-900">{t('scholarship.nextSteps.step1Title')}</p>
          <p className="text-sm text-gray-600 mb-2">{t('scholarship.nextSteps.step1Body')}</p>
          {!c.quiz_done && (
            <Link href="/quiz" className="btn-primary inline-block text-sm">
              {t('scholarship.nextSteps.step1Cta')}
            </Link>
          )}
        </div>
      </div>

      {/* Steps 2 + 3 — about you + funding need */}
      <form onSubmit={handleSave} className="border rounded-xl p-4 space-y-4">
        <div className="flex items-center gap-3">
          {check(c.details_done)}
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

        <div className="flex items-center gap-3 pt-2">
          {check(c.funding_done)}
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

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}
        {saved && <p className="text-green-700 text-sm">{t('scholarship.nextSteps.saved')}</p>}

        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? t('scholarship.nextSteps.saving') : t('scholarship.nextSteps.save')}
        </button>
      </form>

      {/* Step 4 — supporting documents */}
      <div className="border rounded-xl p-4">
        <p className="font-medium text-gray-900 mb-1">{t('scholarship.nextSteps.step4Title')}</p>
        <p className="text-sm text-gray-600 mb-3">{t('scholarship.nextSteps.step4Body')}</p>
        <ScholarshipDocuments token={token} />
      </div>

      {/* Step 5 — referee */}
      <div className="border rounded-xl p-4">
        <p className="font-medium text-gray-900 mb-1">{t('scholarship.nextSteps.step5Title')}</p>
        <p className="text-sm text-gray-600 mb-3">{t('scholarship.nextSteps.step5Body')}</p>
        <ScholarshipReferee token={token} />
      </div>

      {/* Step 6 — consent */}
      <div className="border rounded-xl p-4">
        <p className="font-medium text-gray-900 mb-1">{t('scholarship.nextSteps.step6Title')}</p>
        <p className="text-sm text-gray-600 mb-3">{t('scholarship.nextSteps.step6Body')}</p>
        <ScholarshipConsent token={token} locale={locale} />
      </div>
    </div>
  )
}
