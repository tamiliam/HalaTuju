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

// The post-consent read-back. Builds a one-glance recap of everything the student
// entered, from data already in the client (the application + profile) plus the
// uploaded documents and the consent record. Read-only; per-section Edit links jump
// back to the relevant step (the parent owns the actual tab switch). The single
// "Submit application" button is the ONLY commit (lock-at-Continue).
export default function ScholarshipReview({
  app, profile, token, onEdit, onBack, onSubmit, submitting, submitError, canSubmit, confirmed, t, lang,
}: {
  app: ScholarshipApplication
  profile: StudentProfile | null
  token: string | null
  onEdit: (step: NextStepKey) => void
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

  // ── small primitives (mirror the existing ScholarshipDocuments row/card system) ──
  const Section = ({ title, editStep, locked, children }: {
    title: string; editStep?: NextStepKey; locked?: boolean; children: ReactNode
  }) => (
    <div className="rounded-2xl bg-white border p-5 shadow-sm mb-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {locked ? (
          <span className="text-[10px] font-semibold rounded-full bg-gray-100 text-gray-500 px-2 py-0.5">{s('locked')}</span>
        ) : editStep ? (
          <button type="button" onClick={() => onEdit(editStep)} className="text-xs font-semibold text-primary-600 hover:underline">
            {s('edit')}
          </button>
        ) : null}
      </div>
      {children}
    </div>
  )
  const Rows = ({ children }: { children: ReactNode }) => (
    <div className="rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">{children}</div>
  )
  const Row = ({ label, value }: { label: string; value: ReactNode }) => (
    <p className="text-xs text-gray-700 py-1.5">
      <span className="font-medium text-gray-500">{label}: </span>
      <span className="break-words">{value || dash}</span>
    </p>
  )
  const Chip = ({ children }: { children: ReactNode }) => (
    <span className="text-[11px] rounded-full bg-gray-50 ring-1 ring-gray-200 text-gray-700 px-2 py-0.5">{children}</span>
  )

  // ── derived values ──
  const addr = [profile?.address, [profile?.postal_code, profile?.city].filter(Boolean).join(' '), profile?.preferred_state]
    .filter(Boolean).join(', ')
  const subjectLabel = (code: string) => SUBJECT_NAMES[code]?.[lang === 'en' ? 'en' : 'bm'] || SUBJECT_NAMES[code]?.en || code
  const spmGrades = Object.entries(profile?.grades || {})
  const stpmGrades = Object.entries(profile?.stpm_grades || {})
  const fn = app.funding_need
  const plansLabel = app.chosen_programme?.course_name
    || [app.chosen_pathway, app.pre_u_track, app.pre_u_institution].filter(Boolean).join(' · ')
  const activeConsent = consent?.consents?.find((c) => c.is_active)

  return (
    <div className="space-y-1">
      <p className="text-sm text-gray-500 mb-3">{s('subtitle')}</p>

      {/* 1. About you (locked) */}
      <Section title={s('section.about')} locked>
        <Rows>
          <Row label={s('field.fullName')} value={profile?.name} />
          <Row label={s('field.ic')} value={formatNricDisplay(profile?.nric)} />
          <Row label={s('field.email')} value={profile?.contact_email || profile?.email} />
          <Row label={s('field.phone')} value={profile?.contact_phone} />
          <Row label={s('field.address')} value={addr} />
        </Rows>
      </Section>

      {/* 2. Your results (locked) */}
      <Section title={s('section.results')} locked>
        <p className="text-xs text-gray-500 mb-2">
          {(profile?.exam_type || 'spm').toUpperCase()}
          {app.exam_type === 'stpm' && app.stpm_pngk != null ? ` · PNGK ${app.stpm_pngk}` : ''}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {(app.exam_type === 'stpm' ? stpmGrades : spmGrades).map(([code, g]) => (
            <Chip key={code}>{subjectLabel(code)} {g}</Chip>
          ))}
          {spmGrades.length === 0 && stpmGrades.length === 0 && <span className="text-xs text-gray-400">{dash}</span>}
        </div>
      </Section>

      {/* 3. Your family (narrative editable via Story) */}
      <Section title={s('section.family')} editStep="story">
        <Rows>
          <Row label={s('field.householdIncome')} value={app.household_income != null ? `RM ${app.household_income.toLocaleString()}` : ''} />
          <Row label={s('field.householdSize')} value={app.household_size != null ? String(app.household_size) : ''} />
          <Row label={s('field.receivesStr')} value={yn(app.receives_str)} />
          <Row label={s('field.receivesJkm')} value={yn(app.receives_jkm)} />
          <Row label={s('field.parentsWork')} value={app.parents_occupation} />
          {app.family_context ? <Row label={s('field.familyContext')} value={app.family_context} /> : null}
        </Rows>
      </Section>

      {/* 4. Your plans (read-only — set at apply) */}
      <Section title={s('section.plans')}>
        <Rows>
          <Row label={app.pathway_certainty === 'sure' ? s('field.decided') : s('field.deciding')}
               value={app.pathway_certainty === 'sure' ? plansLabel : (app.uncertainty_note || s('field.stillDeciding'))} />
        </Rows>
      </Section>

      {/* 5. Your story (editable via Story) */}
      <Section title={s('section.story')} editStep="story">
        <Rows>
          <Row label={s('field.aspirations')} value={app.aspirations} />
          <Row label={s('field.studyPlans')} value={app.plans} />
          <Row label={s('field.dailyLife')} value={app.daily_life} />
          <Row label={s('field.concerns')} value={app.fears} />
        </Rows>
      </Section>

      {/* 6. Support you need (editable via Funding) */}
      <Section title={s('section.support')} editStep="funding">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {(fn?.categories || []).map((cat) => (
            <span key={cat} className="text-[11px] rounded-full bg-primary-50 text-primary-700 px-2.5 py-0.5">
              {t(`scholarship.nextSteps.funding.cat_${cat}`)}
            </span>
          ))}
          {(!fn || fn.categories.length === 0) && <span className="text-xs text-gray-400">{dash}</span>}
        </div>
        {fn?.programme_months ? <p className="text-xs text-gray-500">{s('field.programmeLength', { n: String(fn.programme_months) })}</p> : null}
        {fn?.funding_note ? <p className="text-xs text-gray-700 mt-1"><span className="font-medium text-gray-500">{s('field.fundingNote')}: </span>{fn.funding_note}</p> : null}
      </Section>

      {/* 7. Income evidence (editable via Documents) */}
      <Section title={s('section.income')} editStep="documents">
        <Rows>
          <Row label={s('field.incomeRoute')} value={app.income_route ? s(`value.route_${app.income_route}`) : ''} />
          {app.income_route === 'str'
            ? <Row label={s('field.incomeEarner')} value={app.income_earner ? t(`scholarship.docs.income.wizard.earner.${app.income_earner}`) : ''} />
            : app.income_route === 'salary'
              ? <Row label={s('field.workingMembers')} value={(app.income_working_members || []).map((m) => t(`scholarship.docs.income.wizard.member.${m}`)).join(', ')} />
              : null}
        </Rows>
      </Section>

      {/* 8. Documents — simple uploaded list */}
      <Section title={s('section.documents')} editStep="documents">
        <Rows>
          {docs.length === 0 && <p className="text-xs text-gray-400 py-1.5">{dash}</p>}
          {docs.map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-2 py-2">
              <span className="text-xs text-gray-700 min-w-0 break-words">
                {t(`scholarship.docs.type.${d.doc_type}`)}
                {d.original_filename ? <span className="text-gray-400"> · {d.original_filename}</span> : null}
              </span>
              <span className="shrink-0 text-[10px] font-semibold rounded-full bg-green-50 text-green-700 ring-1 ring-green-200 px-2 py-0.5">
                {s('uploaded')}
              </span>
            </div>
          ))}
        </Rows>
      </Section>

      {/* 9. Consent (editable via Consent) */}
      <Section title={s('section.consent')} editStep="consent">
        {activeConsent ? (
          <Rows>
            <Row label={s('field.consentGiven')}
                 value={activeConsent.granted_by === 'guardian' ? s('value.byGuardian') : s('value.bySelf')} />
            {activeConsent.granted_by === 'guardian' ? (
              <Row label={s('field.guardian')} value={`${activeConsent.guardian_name || dash}${activeConsent.guardian_nric ? ` · ${formatNricDisplay(activeConsent.guardian_nric)}` : ''}`} />
            ) : null}
          </Rows>
        ) : (
          <p className="text-xs text-gray-400">{dash}</p>
        )}
      </Section>

      {/* info note + actions */}
      <div className="rounded-xl bg-blue-50 ring-1 ring-blue-100 p-3 my-4 flex gap-2">
        <span className="text-primary-600 text-sm shrink-0" aria-hidden>ⓘ</span>
        <p className="text-xs text-blue-900/90 leading-relaxed">{s('lockNote')}</p>
      </div>

      {!canSubmit && !confirmed && (
        <p className="text-xs text-amber-700 mb-2">{s('incompleteNote')}</p>
      )}
      {submitError && <p className="text-sm text-red-600 mb-2">{submitError}</p>}

      <div className="flex gap-3">
        <button type="button" onClick={onBack}
          className="rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">
          {s('back')}
        </button>
        {!confirmed && (
          <button type="button" onClick={onSubmit} disabled={submitting || !canSubmit}
            className="flex-1 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm disabled:opacity-50">
            {submitting ? s('submitting') : s('submit')}
          </button>
        )}
      </div>
    </div>
  )
}
