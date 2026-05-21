'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import {
  submitScholarshipApplication,
  getMyScholarshipApplications,
  type ScholarshipApplication,
} from '@/lib/api'
import {
  profileToApplyDefaults,
  buildApplicationPayload,
  applyFormError,
  PATHWAY_OPTIONS,
  type ApplyFormState,
} from '@/lib/scholarship'

export default function ScholarshipApplyPage() {
  const { t, locale } = useT()
  const { status, profile, token, showAuthGate } = useAuth()

  const [form, setForm] = useState<ApplyFormState>(() => profileToApplyDefaults(null))
  const [existing, setExisting] = useState<ScholarshipApplication | null>(null)
  const [loadingExisting, setLoadingExisting] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState<ScholarshipApplication | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Pre-fill from the profile once it's available
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

  const requirements = (
    <div className="bg-primary-50 rounded-xl p-5 mb-6">
      <h2 className="font-semibold text-gray-900 mb-2">{t('scholarship.apply.criteriaTitle')}</h2>
      <ul className="space-y-1.5 text-sm text-gray-700 list-disc list-inside">
        <li>{t('scholarship.apply.criteria1')}</li>
        <li>{t('scholarship.apply.criteria2')}</li>
        <li>{t('scholarship.apply.criteria3')}</li>
        <li>{t('scholarship.apply.criteria4')}</li>
      </ul>
    </div>
  )

  if (status === 'loading' || (status === 'ready' && loadingExisting)) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  if (status === 'anonymous' || status === 'needs-nric') {
    return wrap(
      <>
        {requirements}
        <div className="bg-white border rounded-xl p-6 text-center">
          <p className="text-gray-700 mb-4">{t('scholarship.apply.signInPrompt')}</p>
          <button onClick={() => showAuthGate('apply')} className="btn-primary">
            {t('scholarship.apply.signInButton')}
          </button>
        </div>
      </>
    )
  }

  if (submitted || existing) {
    const app = (submitted ?? existing)!
    const isNew = !!submitted
    return wrap(
      <div className="bg-green-50 border border-green-200 rounded-xl p-6">
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

  // status === 'ready' and no existing application → the form
  const isSpm = form.qualification === 'spm'
  return wrap(
    <>
      {requirements}
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Qualification */}
        <fieldset>
          <legend className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.apply.qualification')}
          </legend>
          <div className="flex gap-3">
            {(['spm', 'stpm'] as const).map((q) => (
              <label key={q} className={`flex-1 border rounded-lg px-4 py-2 cursor-pointer text-center text-sm ${
                form.qualification === q ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-300 text-gray-700'
              }`}>
                <input
                  type="radio" name="qualification" value={q} className="sr-only"
                  checked={form.qualification === q}
                  onChange={() => update('qualification', q)}
                />
                {t(`scholarship.apply.${q}`)}
              </label>
            ))}
          </div>
        </fieldset>

        {/* Academic — lightweight (full grades/quiz come at STEP 1A) */}
        {isSpm ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.apply.aCountLabel')}
            </label>
            <input
              type="number" min={0} max={20} className="input"
              value={form.spmACount}
              onChange={(e) => update('spmACount', e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1">{t('scholarship.apply.aCountHelp')}</p>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('scholarship.apply.pngkLabel')}
            </label>
            <input
              type="number" min={0} max={4} step={0.01} className="input"
              value={form.stpmPngk}
              onChange={(e) => update('stpmPngk', e.target.value)}
            />
          </div>
        )}

        {/* Household income */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.apply.incomeLabel')}
          </label>
          <input
            type="number" min={0} className="input"
            value={form.householdIncome}
            onChange={(e) => update('householdIncome', e.target.value)}
          />
        </div>

        {/* Household size */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.apply.householdSizeLabel')}
          </label>
          <input
            type="number" min={1} className="input"
            value={form.householdSize}
            onChange={(e) => update('householdSize', e.target.value)}
          />
        </div>

        {/* Aid flags */}
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.receivesStr} onChange={(e) => update('receivesStr', e.target.checked)} />
          {t('scholarship.apply.strLabel')}
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.receivesJkm} onChange={(e) => update('receivesJkm', e.target.checked)} />
          {t('scholarship.apply.jkmLabel')}
        </label>

        {/* Intended pathway */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.apply.pathwayLabel')}
          </label>
          <select
            className="input"
            value={form.intendedPathway}
            onChange={(e) => update('intendedPathway', e.target.value as ApplyFormState['intendedPathway'])}
          >
            <option value="">{t('scholarship.apply.pathwayPlaceholder')}</option>
            {PATHWAY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{t(`scholarship.apply.pathway.${opt}`)}</option>
            ))}
          </select>
        </div>

        {/* Intent */}
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.intendsTertiary2026} onChange={(e) => update('intendsTertiary2026', e.target.checked)} />
          {t('scholarship.apply.intendLabel')}
        </label>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('scholarship.apply.notesLabel')}
          </label>
          <textarea
            className="input" rows={3}
            value={form.notes}
            placeholder={t('scholarship.apply.notesPlaceholder')}
            onChange={(e) => update('notes', e.target.value)}
          />
        </div>

        {/* Consent (required) */}
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input
            type="checkbox" className="mt-1"
            checked={form.consentToContact}
            onChange={(e) => update('consentToContact', e.target.checked)}
          />
          {t('scholarship.apply.consentLabel')}
        </label>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-50">
          {submitting ? t('scholarship.apply.submitting') : t('scholarship.apply.submit')}
        </button>
      </form>
    </>
  )
}
