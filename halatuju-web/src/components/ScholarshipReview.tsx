'use client'

import { useEffect, useState, type ReactNode } from 'react'
import {
  listDocuments, getConsentStatus,
  type ScholarshipApplication, type StudentProfile,
  type ApplicantDocument, type ConsentStatus,
} from '@/lib/api'
import { formatNricDisplay } from '@/lib/scholarship'
import { SUBJECT_NAMES } from '@/lib/subjects'
import type { NextStepKey } from '@/lib/scholarship'

// Documents grouped + ordered like the rest of the pipeline: Identity → Results →
// Pathway → Income (many) → Other (optional, many).
const DOC_GROUP_ORDER = ['identity', 'academic', 'pathway', 'income', 'other'] as const
const DOC_CATEGORY: Record<string, string> = {
  ic: 'identity', results_slip: 'academic', offer_letter: 'pathway',
  parent_ic: 'income', str: 'income', salary_slip: 'income', epf: 'income',
  birth_certificate: 'income', guardianship_letter: 'income',
  water_bill: 'income', electricity_bill: 'income',
}

// The post-consent read-back. Builds a one-glance recap of everything the student
// entered, from data already in the client (the application + profile) plus the
// uploaded documents and the consent record. Read-only; per-section Edit links jump
// back to the relevant step. The single "Submit application" button is the ONLY
// commit (lock-at-Continue).
export default function ScholarshipReview({
  app, profile, token, onEdit, onBack, onSubmit, submitting, submitError, canSubmit, confirmed, t, lang,
}: {
  app: ScholarshipApplication
  profile: StudentProfile | null
  token: string | null
  onEdit: (step: NextStepKey, anchor?: string) => void
  onBack: () => void
  onSubmit: () => void
  submitting: boolean
  submitError: string | null
  canSubmit: boolean
  confirmed: boolean
  t: (key: string, vars?: Record<string, string>) => string
  lang: string
}) {
  const [docs, setDocs] = useState<ApplicantDocument[]>([])
  const [consent, setConsent] = useState<ConsentStatus | null>(null)

  useEffect(() => {
    if (!token) return
    let live = true
    listDocuments({ token }).then((r) => { if (live) setDocs(r.documents) }).catch(() => {})
    getConsentStatus({ token }).then((c) => { if (live) setConsent(c) }).catch(() => {})
    return () => { live = false }
  }, [token])

  const s = (k: string, vars?: Record<string, string>) => t(`scholarship.summary.${k}`, vars)
  const dash = '—'
  const yn = (v: boolean | null | undefined) => (v ? s('yes') : s('no'))

  // ── primitives (matched to the approved Stitch design: white soft-shadow cards,
  //    uppercase muted section labels, stacked label-above-value with large dark
  //    values, a blue left-accent on editable cards) ──
  const Card = ({ title, editStep, editAnchor, locked, children }: {
    title: string; editStep?: NextStepKey; editAnchor?: string; locked?: boolean; children: ReactNode
  }) => (
    <section className={`rounded-2xl bg-white p-5 shadow-sm mb-4 ${
      editStep ? 'border-l-4 border-primary-500' : 'border border-gray-100'}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">{title}</h3>
        {locked ? (
          <span className="text-[10px] font-semibold rounded-full bg-gray-100 text-gray-500 px-2 py-0.5">{s('locked')}</span>
        ) : editStep ? (
          <button type="button" onClick={() => onEdit(editStep, editAnchor)} className="text-xs font-semibold text-primary-600 hover:underline">
            {s('edit')}
          </button>
        ) : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  )
  // Stacked field: small label, then a large, dark, readable value.
  const Field = ({ label, value, strong }: { label: string; value: ReactNode; strong?: boolean }) => (
    <div>
      <p className={`text-xs ${strong ? 'font-semibold text-gray-600' : 'font-medium text-gray-400'}`}>{label}</p>
      <p className="text-[15px] leading-relaxed text-gray-900 mt-0.5 break-words">{value || dash}</p>
    </div>
  )

  // ── derived values ──
  const addr = [profile?.address, [profile?.postal_code, profile?.city].filter(Boolean).join(' '), profile?.preferred_state]
    .filter(Boolean).join(', ')
  const subjectLabel = (code: string) => SUBJECT_NAMES[code]?.[lang === 'en' ? 'en' : 'bm'] || SUBJECT_NAMES[code]?.en || code
  const spmGrades = Object.entries(profile?.grades || {})
  const stpmGrades = Object.entries(profile?.stpm_grades || {})
  const grades = app.exam_type === 'stpm' ? stpmGrades : spmGrades
  const fn = app.funding_need
  const plansLabel = app.chosen_programme?.course_name
    || [app.chosen_pathway, app.pre_u_track, app.pre_u_institution].filter(Boolean).join(' · ')
  const activeConsent = consent?.consents?.find((c) => c.is_active)

  // Documents grouped + ordered.
  const grouped = DOC_GROUP_ORDER
    .map((cat) => ({ cat, items: docs.filter((d) => (DOC_CATEGORY[d.doc_type] || 'other') === cat) }))
    .filter((g) => g.items.length > 0)

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-gray-900">{t('scholarship.application.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-5">{s('subtitle')}</p>

      {/* 1. About you (locked) — identity + the non-editable household facts */}
      <Card title={s('section.about')} locked>
        <Field label={s('field.fullName')} value={profile?.name} />
        <Field label={s('field.ic')} value={formatNricDisplay(profile?.nric)} />
        <Field label={s('field.email')} value={profile?.contact_email || profile?.email} />
        <Field label={s('field.phone')} value={profile?.contact_phone} />
        <Field label={s('field.householdIncome')} value={app.household_income != null ? `RM ${app.household_income.toLocaleString()}` : ''} />
        <Field label={s('field.householdSize')} value={app.household_size != null ? String(app.household_size) : ''} />
        <Field label={s('field.receivesStr')} value={yn(app.receives_str)} />
        <Field label={s('field.receivesJkm')} value={yn(app.receives_jkm)} />
      </Card>

      {/* 2. Your results (locked) */}
      <Card title={s('section.results')} locked>
        <p className="text-xs font-medium text-gray-400">
          {(profile?.exam_type || 'spm').toUpperCase()}
          {app.exam_type === 'stpm' && app.stpm_pngk != null ? ` · PNGK ${app.stpm_pngk}` : ''}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {grades.map(([code, g]) => (
            <span key={code} className="text-[13px] rounded-full bg-gray-50 ring-1 ring-gray-200 text-gray-800 px-2.5 py-1">
              {subjectLabel(code)} {g}
            </span>
          ))}
          {grades.length === 0 && <span className="text-sm text-gray-400">{dash}</span>}
        </div>
      </Card>

      {/* 3. Your story (family narrative + address + the story narrative) */}
      <Card title={s('section.story')} editStep="story">
        <Field label={s('field.parentsWork')} value={app.parents_occupation} />
        <Field label={s('field.firstInFamily')} value={yn(app.first_in_family)} />
        <Field label={s('field.siblings')} value={app.siblings_studying_count != null ? String(app.siblings_studying_count) : ''} />
        {app.family_context ? <Field label={s('field.familyContext')} value={app.family_context} /> : null}
        <Field label={s('field.address')} value={addr} />
        <Field label={s('field.aspirations')} value={app.aspirations} />
        <Field label={s('field.studyPlans')} value={app.plans} />
        <Field label={s('field.dailyLife')} value={app.daily_life} />
        <Field label={s('field.concerns')} value={app.fears} />
      </Card>

      {/* 4. Funding — chosen study (read-only) → programme length (bold) → support → note */}
      <Card title={s('section.funding')} editStep="funding">
        <Field label={s('field.chosenStudy')}
               value={app.pathway_certainty === 'sure' ? plansLabel : (app.uncertainty_note || s('field.stillDeciding'))} />
        <Field strong label={s('field.programmeLengthLabel')}
               value={fn?.programme_months ? s('value.months', { n: String(fn.programme_months) }) : ''} />
        <div>
          <p className="text-xs font-medium text-gray-400 mb-1.5">{s('field.support')}</p>
          <div className="flex flex-wrap gap-1.5">
            {(fn?.categories || []).map((cat) => (
              <span key={cat} className="text-[13px] rounded-full bg-primary-50 text-primary-700 px-3 py-1">
                {t(`scholarship.nextSteps.funding.cat_${cat}`)}
              </span>
            ))}
            {(!fn || fn.categories.length === 0) && <span className="text-sm text-gray-400">{dash}</span>}
          </div>
        </div>
        {fn?.funding_note ? <Field label={s('field.fundingNote')} value={fn.funding_note} /> : null}
      </Card>

      {/* 5. Household income (the income wizard answers). Edit jumps to the income wizard. */}
      <Card title={s('section.income')} editStep="documents" editAnchor="income-wizard">
        <Field label={s('field.incomeRoute')} value={app.income_route ? s(`value.route_${app.income_route}`) : ''} />
        {app.income_route === 'str'
          ? <Field label={s('field.incomeEarner')} value={app.income_earner ? t(`scholarship.docs.income.wizard.earner.${app.income_earner}`) : ''} />
          : app.income_route === 'salary'
            ? <Field label={s('field.workingMembers')} value={(app.income_working_members || []).map((m) => t(`scholarship.docs.income.wizard.member.${m}`)).join(', ')} />
            : null}
      </Card>

      {/* 6. Documents — grouped Identity / Results / Pathway / Income / Other */}
      <Card title={s('section.documents')} editStep="documents">
        {docs.length === 0 && <p className="text-sm text-gray-400">{dash}</p>}
        <div className="space-y-4">
          {grouped.map(({ cat, items }) => (
            <div key={cat}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
                {t(`scholarship.docs.section.${cat}.title`)}
              </p>
              <div className="space-y-1.5">
                {items.map((d) => (
                  <div key={d.id} className="flex items-center justify-between gap-2">
                    <span className="text-sm text-gray-800 min-w-0 break-words">
                      {t(`scholarship.docs.type.${d.doc_type}`)}
                      {d.original_filename ? <span className="text-gray-400"> · {d.original_filename}</span> : null}
                    </span>
                    <span className="shrink-0 text-[10px] font-semibold rounded-full bg-green-50 text-green-700 ring-1 ring-green-200 px-2 py-0.5">
                      {s('uploaded')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 7. Consent — read-only: once given it can't be re-edited (no dead-end Edit link). */}
      <Card title={s('section.consent')} locked>
        {activeConsent ? (
          <>
            <Field label={s('field.consentGiven')}
                   value={activeConsent.granted_by === 'guardian' ? s('value.byGuardian') : s('value.bySelf')} />
            {activeConsent.granted_by === 'guardian' ? (
              <Field label={s('field.guardian')} value={`${activeConsent.guardian_name || dash}${activeConsent.guardian_nric ? ` · ${formatNricDisplay(activeConsent.guardian_nric)}` : ''}`} />
            ) : null}
          </>
        ) : (
          <p className="text-sm text-gray-400">{dash}</p>
        )}
      </Card>

      {/* info note + actions */}
      <div className="rounded-xl bg-blue-50 ring-1 ring-blue-100 p-3.5 mb-4 flex gap-2">
        <span className="text-primary-600 text-sm shrink-0" aria-hidden>ⓘ</span>
        <p className="text-sm text-blue-900/90 leading-relaxed">{s('lockNote')}</p>
      </div>

      {!canSubmit && !confirmed && (
        <p className="text-sm text-amber-700 mb-2">{s('incompleteNote')}</p>
      )}
      {submitError && <p className="text-sm text-red-600 mb-2">{submitError}</p>}

      <div className="flex gap-3">
        <button type="button" onClick={onBack}
          className="rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">
          {s('back')}
        </button>
        {!confirmed && (
          <button type="button" onClick={onSubmit} disabled={submitting || !canSubmit}
            className="flex-1 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50">
            {submitting ? s('submitting') : s('submit')}
          </button>
        )}
      </div>
    </div>
  )
}
