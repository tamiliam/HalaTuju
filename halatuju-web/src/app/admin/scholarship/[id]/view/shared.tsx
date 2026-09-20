'use client'

/**
 * THE COCKPIT'S SHARED FURNITURE — the small presentational atoms every panel draws with, the
 * officer's doc-request vocabulary, and the type aliases the panels take as props.
 *
 * ⚠ LIFTED OUT OF `view.tsx` WHOLE at code health H14, and nothing else happened to it. The
 * screen itself is still `../view.tsx`; the panels are the files beside this one.
 *
 * ⚠ THE PROP TYPES ARE DERIVED, NEVER RE-DECLARED. `T` and `AdminRole` are read off the hooks
 * that produce them (`ReturnType<typeof useT>['t']`), so a panel's props cannot drift from the
 * thing the cockpit actually passes it — and no file outside this folder had to export anything
 * new for the split.
 */
import type { ReactNode } from 'react'
import type { useT } from '@/lib/i18n'
import type { useAdminAuth } from '@/lib/admin-auth-context'
import type { VerifiableField } from '@/lib/fieldVerification'
import VerifiedTick from '@/components/VerifiedTick'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

/** The translate function, exactly as `useT()` hands it out. */
export type T = ReturnType<typeof useT>['t']
/** The signed-in admin, exactly as `useAdminAuth()` hands it out. */
export type AdminRole = ReturnType<typeof useAdminAuth>['role']
/** The field-level "verified" tooltip, built once in the cockpit and passed down. */
export type Vtip = (field: VerifiableField) => string | undefined
/** One talking point on the interview agenda (a flag, a carried-over query, or an AI gap). */
export type AgendaItem = { code: string; ai: boolean; label: string }
/** The reviewer's typed interview findings, keyed by agenda code. */
export type Findings = Record<string, { verdict: string; rationale: string }>
/** The referee capture form (behind `SHOW_REFEREES`). */
export type RefereeForm = typeof EMPTY_REFEREE

// Officer doc-request control: a friendly CATEGORY + a mandatory QUALIFIER that resolves to a
// concrete (doc_type, household_member). Every request is tagged at source — a "Whose?" category
// (STR / IC / salary / EPF) requires a person; a "Which?" category (results slip / utility / other)
// requires a sub-type. The Request button stays disabled until the qualifier is chosen.
type ReqCategory = {
  key: string
  qualifier: 'whose' | 'which' | null
  docType?: string                                          // 'whose' | null → fixed doc_type
  members?: readonly string[]                               // 'whose' → the person options
  options?: readonly { value: string; docType: string }[]  // 'which' → sub-type options
}
export const REQUEST_CATEGORIES: readonly ReqCategory[] = [
  { key: 'ic', qualifier: null, docType: 'ic' },                                   // Applicant's IC
  { key: 'results_slip', qualifier: 'which', options: [
      { value: 'spm', docType: 'results_slip' },
      { value: 'cgpa', docType: 'semester_result' } ] },                            // SPM / current CGPA
  { key: 'offer_letter', qualifier: null, docType: 'offer_letter' },
  { key: 'str', qualifier: 'whose', docType: 'str', members: ['father', 'mother', 'guardian'] },
  { key: 'parent_ic', qualifier: 'whose', docType: 'parent_ic',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },              // Family member's IC
  { key: 'salary_slip', qualifier: 'whose', docType: 'salary_slip',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },
  { key: 'epf', qualifier: 'whose', docType: 'epf',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },
  { key: 'birth_certificate', qualifier: null, docType: 'birth_certificate' },
  { key: 'utility', qualifier: 'which', options: [
      { value: 'water_bill', docType: 'water_bill' },
      { value: 'electricity_bill', docType: 'electricity_bill' } ] },
  { key: 'other', qualifier: 'which', options: [
      { value: 'school_leaving_cert', docType: 'school_leaving_cert' },
      { value: 'guardianship_letter', docType: 'guardianship_letter' },
      { value: 'statement_of_intent', docType: 'statement_of_intent' },
      { value: 'photo', docType: 'photo' },
      { value: 'other', docType: 'other' } ] },
]
export const REQ_CAT = new Map(REQUEST_CATEGORIES.map((c) => [c.key, c]))
// Resolve a (category, qualifier) pick to a concrete request, or null when the qualifier is
// required but not yet chosen (→ keeps the Request button disabled).
export function resolveReq(catKey: string, qual: string): { docType: string; member: string } | null {
  const c = REQ_CAT.get(catKey)
  if (!c) return null
  if (c.qualifier === null) return { docType: c.docType!, member: '' }
  if (c.qualifier === 'whose') return qual ? { docType: c.docType!, member: qual } : null
  const opt = c.options!.find((o) => o.value === qual)
  return opt ? { docType: opt.docType, member: '' } : null
}
// The fact a requested document belongs to comes from `@/lib/docCategory` — see
// `docTypeToRequestFact`. A private `DOC_FACT` literal lived here until TD-262 chunk 1 and had
// never gained `income_support_doc`, so a request for the one document that proves an informal
// earner's wage would have been stamped 'other'. Latent only: `REQUEST_CATEGORIES` above offers
// no such request today.

// #9 sync: an interview anomaly is SUPPRESSED from the agenda when the same concern is
// already a Check-2 query the student is being asked (Check-2 fires first; no repeat).
// Maps anomaly code → the owning Check-2 clarify code.
export const ANOMALY_CHECK2_OWNER: Record<string, string> = {
  utility_holder_unknown: 'utility_holder_unknown',
  utility_address_mismatch: 'utility_address_mismatch',
  device_in_funding: 'device_status_unknown',
  first_in_family_with_siblings_studying: 'sibling_level_unknown',
}

export const EMPTY_REFEREE = { name: '', role: '', relationship: '', phone: '', email: '' }

// Non-parent guardian relationships — drive the dynamic "Parent" vs "Guardian" label (#5).
export const NON_PARENT_RELATIONSHIPS = new Set([
  'legal_guardian', 'grandparent', 'older_sibling', 'brother', 'sister', 'relative', 'other_relative',
])
// Referees aren't in play yet — hide the capture UI (the handlers stay wired so this
// is a one-line re-enable, and so they don't become unused). Flip to true to restore.
export const SHOW_REFEREES = false


export function Field({ label, value, verifiedLabel, note, noteTone = 'amber' }: { label: string; value: ReactNode; verifiedLabel?: string; note?: string; noteTone?: 'amber' | 'muted' }) {
  return (
    <div>
      <dt className="text-xs text-ground-400 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-ground-800 break-words">
        {value === null || value === undefined || value === '' ? '—' : value}
        {verifiedLabel && <VerifiedTick label={verifiedLabel} />}
      </dd>
      {note && <p className={`mt-0.5 text-xs ${noteTone === 'muted' ? 'text-ground-400' : 'text-caution-700'}`}>{note}</p>}
    </div>
  )
}

/**
 * The QC floor override — who accepted this case over a RED fact, when, and why.
 *
 * The V5 gate refuses a QC-Accept while any of the four facts is red; a super may override with a
 * written reason. Those three columns have been written since the gate shipped and displayed
 * NOWHERE — not on this payload, not in this app. A reason nobody can read provides none of the
 * accountability that demanding one was for. Amber rather than green: this is an exception to a
 * control, and it should not look like routine sign-off.
 *
 * At MODULE scope deliberately (lessons.md, the Administration hub): a component declared inside
 * the page body is a new type on every keystroke, remounts its subtree and steals focus.
 */
export function QcOverrideNote({ app, t }: { app: AdminScholarshipDetail; t: (k: string) => string }) {
  if (!app.qc_override_at && !app.qc_override_reason) return null
  const who = app.qc_override_by_name || app.qc_override_by || '—'
  const when = app.qc_override_at ? ` · ${formatDate(app.qc_override_at)}` : ''
  return (
    <div className="rounded-lg border border-caution-200 bg-caution-50 px-3 py-2">
      <p className="text-xs font-medium text-caution-900">
        {t('admin.scholarship.qcOverride.title')} {who}{when}
      </p>
      {(app.qc_override_reason || '').trim() && (
        <p className="mt-1 whitespace-pre-line text-xs text-caution-800">{app.qc_override_reason}</p>
      )}
    </div>
  )
}

export function Card({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm ${className}`}>
      <h2 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-400">{title}</h2>
      {children}
    </div>
  )
}

/** Section heading for a group of panels (e.g. "Review & actions"). */
export function GroupLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-2 mt-2 text-xs font-semibold uppercase tracking-wider text-ground-500">{children}</h2>
}

export const yn = (v: boolean | null | undefined) => (v === true ? 'Yes' : v === false ? 'No' : '—')
export const joinOr = (a?: string[] | null) => (a && a.length ? a.join(', ') : '—')

/** Grade dict → readable chips (subject key uppercased · grade). */
export function Grades({ grades, trailing }: { grades?: Record<string, string> | null; trailing?: ReactNode }) {
  const entries = Object.entries(grades || {}).filter(([, g]) => g)
  if (!entries.length) return <span className="text-ground-400 text-sm">—</span>
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {entries.map(([k, g]) => (
        <span key={k} className="inline-flex items-center gap-1 rounded-md bg-ground-100 px-2 py-0.5 text-xs">
          <span className="text-ground-500 uppercase">{k.replace(/_/g, ' ')}</span>
          <span className="font-semibold text-ground-800">{g}</span>
        </span>
      ))}
      {trailing}
    </div>
  )
}