'use client'

/**
 * THE PER-DOCUMENT CHECKLISTS a student reads under an upload card — identity, the income
 * evidence, the utility bill, the STR, the relationship documents and the results slip.
 *
 * ⚠ MOVED OUT OF `ScholarshipDocuments.tsx` WHOLE at code health H14, and nothing else happened
 * to them. Every one is `(doc, t) => JSX` with no state of its own, which is why they were the
 * first thing to leave a 1,914-line file. The component that draws the card around them is
 * `./cards.tsx`; the tab itself is still `../ScholarshipDocuments.tsx`.
 */
import type { ReactNode } from 'react'
import type { ApplicantDocument } from '@/lib/api'
import { formatNric } from '@/lib/scholarship'

// ── Vision OCR chip (S13 — soft signal under the IC upload) ──────────────

export type ICCheckKind = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'none'

function icVerdictKind(verdict: string): ICCheckKind {
  if (verdict === 'match') return 'match'
  if (verdict === 'partial') return 'partial'
  if (verdict === 'mismatch') return 'mismatch'
  if (verdict === 'unreadable') return 'unreadable'
  return 'none'
}

/** Per-item IC checklist (replaces the old single chip): IC No / Name / Address, each
 *  with the value Vision READ and its status — so the student sees what PASSED too.
 *  Address is a SOFT data point: the MyKad address is often outdated and there are other
 *  sources, so it is NEVER a hard "mismatch"/blocker — just shown for reference. Cikgu
 *  Gopal (rendered below) gives the detailed "what to do" only when there's a real problem. */
export function ICChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  if (!doc.vision_run_at) return null

  const badge = (kind: ICCheckKind) => {
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-positive-50 text-positive-700 ring-positive-200',
      partial: 'bg-caution-50 text-caution-700 ring-caution-200',
      mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
      unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
      none: 'bg-ground-50 text-ground-500 ring-ground-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.icCheck.${kind}`)}
      </span>
    )
  }

  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  // Genuineness fingerprint (verification-assurance): when the card doesn't look like a
  // real MyKad photo, an honest amber note — the matched name/IC stay green (they DID
  // match what was typed), but we don't pretend the document is verified. Never blocks;
  // the existing "Replace" link is the re-upload path.
  const suspect = !!doc.authenticity?.status && doc.authenticity.status !== 'genuine'  // canonical: suspect / not_<type>

  return (
    <>
      <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
        {row(t('scholarship.docs.icCheck.icNo'), formatNric(doc.vision_nric || ''), badge(icVerdictKind(doc.vision_nric_verdict)))}
        {row(t('scholarship.docs.icCheck.name'), doc.vision_name, badge(icVerdictKind(doc.vision_name_verdict)))}
        {doc.vision_address
          ? row(
              t('scholarship.docs.icCheck.address'),
              doc.vision_address,
              <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
                {t('scholarship.docs.icCheck.fromIc')}
              </span>,
            )
          : null}
      </div>
      {suspect && (
        <div className="mt-2 flex items-start gap-2 rounded-xl border border-caution-200 bg-caution-50 px-3 py-2.5">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-caution-700" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <p className="text-xs text-caution-800">{t('scholarship.docs.icCheck.notGenuine')}</p>
        </div>
      )}
    </>
  )
}

/** Income earner IC checklist (Check-1 Income) — the SAME standard as the Identity IC
 *  card (IC No / Name / Address, each with the value Vision READ), but the verdict is the
 *  RELATIONSHIP, not an identity match against the student: the NRIC is the EARNER's, so it
 *  is shown for reference only; the Name carries a "links to your family" / "doesn't match"
 *  badge (father/brother/sister via the shared patronymic, mother via birth cert, guardian
 *  via letter). Cikgu Gopal (below) gives the "what to do" only on a real mismatch. */
export function IncomeIcChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string, vars?: Record<string, string>) => string }) {
  const chk = doc.income_ic_check
  if (!chk || !doc.vision_run_at) return null

  // The point of the earner IC is to MATCH the cluster's income proof (STR / salary slip).
  // Show that cross-check: green "Matches the STR document", red on a clash, neutral "from
  // their IC" before any proof exists. (The relationship to the student lives on the birth
  // certificate now, voiced by Cikgu Gopal — not on this card.)
  const proofDoc = chk.proof_kind ? t(`scholarship.docs.type.${chk.proof_kind}`) : ''
  const ring: Record<'match' | 'mismatch' | 'none', string> = {
    match: 'bg-positive-50 text-positive-700 ring-positive-200',
    mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
    none: 'bg-ground-50 text-ground-500 ring-ground-200',
  }
  const matchTag = (status?: string) => {
    const kind = status === 'match' ? 'match' : status === 'mismatch' ? 'mismatch' : 'none'
    const label =
      status === 'match' && proofDoc
        ? t('scholarship.docs.incomeIcCheck.matchesProof', { doc: proofDoc })
        : status === 'mismatch' && proofDoc
          ? t('scholarship.docs.incomeIcCheck.proofMismatch', { doc: proofDoc })
          : t('scholarship.docs.icCheck.fromTheirIc')
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${ring[kind]}`}>
        {label}
      </span>
    )
  }
  const neutralTag = (
    <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
      {t('scholarship.docs.icCheck.fromTheirIc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {chk.nric ? row(t('scholarship.docs.icCheck.icNo'), formatNric(chk.nric), matchTag(chk.proof_nric_status)) : null}
      {row(t('scholarship.docs.icCheck.name'), chk.name, matchTag(chk.proof_name_status))}
      {chk.address ? row(t('scholarship.docs.icCheck.address'), chk.address, neutralTag) : null}
    </div>
  )
}

/** Member-tagged salary slip / EPF checklist (Check-1 Income). Reads the EARNER's facts
 *  (Name · IC No · Amount · Period) and verifies the Name + IC No against the IC the
 *  student uploaded for that SAME member — never against the student. So a father's
 *  payslip is checked against the father's IC, and Gopal (below) never tells the student
 *  to edit their own name. Amount + period are soft data points shown for reference. */
export function IncomeProofChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.income_proof_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-positive-50 text-positive-700 ring-positive-200',
    partial: 'bg-caution-50 text-caution-700 ring-caution-200',
    mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
    unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
    none: 'bg-ground-50 text-ground-500 ring-ground-200',
  }
  // A status pill vs the member's IC. 'no_ref' (that IC not uploaded / not read) is a
  // neutral nudge, never a problem.
  const vsIc = (status: string) => {
    const kind: ICCheckKind = status === 'match' ? 'match' : status === 'mismatch' ? 'mismatch' : 'none'
    const label =
      status === 'match'
        ? t('scholarship.docs.incomeProofCheck.matchesIc')
        : status === 'mismatch'
          ? t('scholarship.docs.incomeProofCheck.mismatchIc')
          : t('scholarship.docs.incomeProofCheck.addIc')
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {label}
      </span>
    )
  }
  const fromDoc = (
    <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
      {t('scholarship.docs.incomeProofCheck.fromDoc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {row(t('scholarship.docs.incomeProofCheck.name'), chk.name, vsIc(chk.name_status))}
      {chk.nric ? row(t('scholarship.docs.incomeProofCheck.icNo'), formatNric(chk.nric), vsIc(chk.nric_status)) : null}
      {chk.points.map((p) => (
        <div key={p.key}>{row(t(`scholarship.docs.incomeProofCheck.${p.key}`), p.value, fromDoc)}</div>
      ))}
    </div>
  )
}

/** Utility bill checklist (Check-1 Income). The meaningful check is the home ADDRESS (these
 *  confirm where the family lives) — the bill is in a parent's name, so the name is a data
 *  point, never matched to the student. Monthly charge + any unpaid balance are shown (a high
 *  arrears is a soft hardship signal the coordinator weighs). */
export function UtilityChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.utility_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-positive-50 text-positive-700 ring-positive-200',
    partial: 'bg-caution-50 text-caution-700 ring-caution-200',
    mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
    unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
    none: 'bg-ground-50 text-ground-500 ring-ground-200',
  }
  const addrPill =
    chk.address_status === 'found'
      ? <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls.match}`}>{t('scholarship.docs.utilityCheck.addressOk')}</span>
      : chk.address_status === 'not_found'
        ? <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls.mismatch}`}>{t('scholarship.docs.utilityCheck.addressMismatch')}</span>
        : <span className={`shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200`}>{t('scholarship.docs.incomeProofCheck.fromDoc')}</span>
  const fromDoc = (
    <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
      {t('scholarship.docs.incomeProofCheck.fromDoc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {row(t('scholarship.docs.utilityCheck.address'), chk.address, addrPill)}
      {chk.monthly_bill ? row(t('scholarship.docs.utilityCheck.monthlyBill'), chk.monthly_bill, fromDoc) : null}
      {chk.unpaid_balance ? row(t('scholarship.docs.utilityCheck.unpaidBalance'), chk.unpaid_balance, fromDoc) : null}
    </div>
  )
}

/** STR document checklist (Check-1 Income). Reads the recipient (Name · IC No) and the
 *  currency facts (Status · Year) and verifies Name + IC against the STR EARNER's IC —
 *  the STR is the household benefit in the earner's name. A stale/rejected STR is
 *  flagged (STR is annual — an out-of-date one no longer proves B40). */
/** Shared honest genuineness note for the standardised supporting documents (STR / results
 *  slip / BC / EPF) — verification-assurance Sprint 2. Shows an amber "this doesn't look like
 *  a genuine document" note when the fingerprint is low-confidence or wrong-type. Never blocks;
 *  re-upload via the card's existing controls. (The IC has its own note in ICChecklist.) */
export function GenuinenessNote({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const s = doc.authenticity?.status
  if (!s || s === 'genuine') return null   // show for any non-genuine canonical status (suspect / not_<type>)
  return (
    <div className="mt-2 flex items-start gap-2 rounded-xl border border-caution-200 bg-caution-50 px-3 py-2.5">
      <svg className="mt-0.5 h-4 w-4 shrink-0 text-caution-700" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p className="text-xs text-caution-800">{t('scholarship.docs.genuineness.note')}</p>
    </div>
  )
}

export function StrChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.str_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-positive-50 text-positive-700 ring-positive-200',
    partial: 'bg-caution-50 text-caution-700 ring-caution-200',
    mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
    unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
    none: 'bg-ground-50 text-ground-500 ring-ground-200',
  }
  const pill = (kind: ICCheckKind, label: string) => (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>{label}</span>
  )
  const vsIc = (status: string) =>
    status === 'match'
      ? pill('match', t('scholarship.docs.incomeProofCheck.matchesIc'))
      : status === 'mismatch'
        ? pill('mismatch', t('scholarship.docs.incomeProofCheck.mismatchIc'))
        : pill('none', t('scholarship.docs.incomeProofCheck.addIc'))
  // The STR model is exactly four variables — Name · IC · Status · Year (owner 2026-07-07).
  // STATUS answers "is it approved?" (Lulus/diluluskan); YEAR answers "is it for this cycle?"
  // (a date, never an amount). The single currency ladder decomposes onto the two axes.
  const APPROVED_STATES = ['current', 'unconfirmed', 'stale']   // a "Lulus" was read/inferred
  const statusPill =
    APPROVED_STATES.includes(chk.current_status)
      ? pill('match', t('scholarship.docs.strCheck.approved'))
      : chk.current_status === 'unknown'
        ? pill('none', t('scholarship.docs.strCheck.unknown'))
        : pill('mismatch', t(`scholarship.docs.strCheck.${chk.current_status}`))
  // Year: current (dated this cycle) → green; unconfirmed (approved, no date) → amber; stale
  // (prior year) → red; anything not approved → neutral (the Status row carries that story).
  const yearPill =
    chk.current_status === 'current'
      ? pill('match', t('scholarship.docs.strCheck.current'))
      : chk.current_status === 'unconfirmed'
        ? pill('partial', t('scholarship.docs.strCheck.unconfirmed'))
        : chk.current_status === 'stale'
          ? pill('mismatch', t('scholarship.docs.strCheck.stale'))
          : pill('none', t('scholarship.docs.strCheck.unknown'))
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {row(t('scholarship.docs.strCheck.recipient'), chk.name, vsIc(chk.name_status))}
      {chk.nric ? row(t('scholarship.docs.strCheck.icNo'), formatNric(chk.nric), vsIc(chk.nric_status)) : null}
      {row(t('scholarship.docs.strCheck.status'), chk.status, statusPill)}
      {row(t('scholarship.docs.strCheck.year'), chk.year, yearPill)}
    </div>
  )
}

// ── Relationship-proof checklists (Check-1 Income): birth cert + guardianship ──

const REL_PILL: Record<ICCheckKind, string> = {
  match: 'bg-positive-50 text-positive-700 ring-positive-200',
  partial: 'bg-caution-50 text-caution-700 ring-caution-200',
  mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
  unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
  none: 'bg-ground-50 text-ground-500 ring-ground-200',
}

function relPill(status: string, t: (k: string) => string): ReactNode {
  const kind: ICCheckKind =
    status === 'match' ? 'match'
      : status === 'mismatch' ? 'mismatch'
        : status === 'check' || status === 'check_near' || status === 'check_name' ? 'partial'
          : 'none'
  const label =
    status === 'match' ? t('scholarship.docs.relCheck.confirmed')
      : status === 'mismatch' ? t('scholarship.docs.relCheck.mismatch')
        : status === 'check_near' ? t('scholarship.docs.relCheck.checkNumberOneDigit')
          : status === 'check' ? t('scholarship.docs.relCheck.checkNumber')
            // #19: spelt differently, same IC number. The student must NOT be told to correct a
            // certificate — the document is right and the spelling difference is real.
            : status === 'check_name' ? t('scholarship.docs.relCheck.checkName')
              : t('scholarship.docs.relCheck.reviewing')
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${REL_PILL[kind]}`}>{label}</span>
}

function relRow(label: string, value: string, right: ReactNode): ReactNode {
  return (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )
}

/** Birth-certificate checklist — links the student to their mother (the income earner):
 *  Child (vs you) · Mother (vs Mother's IC) · Father (vs your IC's family name). */
export function BcChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.bc_check
  if (!chk) return null
  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {relRow(t('scholarship.docs.relCheck.child'), chk.child_name, relPill(chk.child_status, t))}
      {relRow(t('scholarship.docs.relCheck.mother'),
              [chk.mother_name, chk.mother_nric].filter(Boolean).join(' · '), relPill(chk.mother_status, t))}
      {chk.father_name ? relRow(t('scholarship.docs.relCheck.father'), chk.father_name, relPill(chk.father_status, t)) : null}
    </div>
  )
}

/** Guardianship-letter checklist — ties the guardian to the student (the ward):
 *  Guardian (vs Guardian's IC) · Ward (vs you). */
export function GuardianshipChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.guardianship_check
  if (!chk) return null
  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {relRow(t('scholarship.docs.relCheck.guardian'),
              [chk.guardian_name, chk.guardian_nric].filter(Boolean).join(' · '), relPill(chk.guardian_status, t))}
      {relRow(t('scholarship.docs.relCheck.ward'), chk.ward_name, relPill(chk.ward_status, t))}
    </div>
  )
}

// ── Results-slip clinical 3-check (Check-1 Academic) ─────────────────────
// Mirrors the IC checklist: three rows the student can read at a glance —
// Name · Subjects · Results — each with what we read + a pass/fail badge, plus
// the exam (year) as a soft data point. Cikgu Gopal (below) gives the specific
// "what to do" only when there's a real problem.

type SlipStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'uncertain' | 'pending'

function slipBadgeKind(s: SlipStatus): ICCheckKind {
  if (s === 'match') return 'match'
  if (s === 'partial' || s === 'uncertain') return 'partial' // amber "please check"
  if (s === 'mismatch') return 'mismatch'
  if (s === 'unreadable') return 'unreadable'
  return 'none' // pending
}

export function ResultsSlipChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.academic_check
  if (!chk) return null

  const badge = (s: SlipStatus) => {
    const kind = slipBadgeKind(s)
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-positive-50 text-positive-700 ring-positive-200',
      partial: 'bg-caution-50 text-caution-700 ring-caution-200',
      mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
      unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
      none: 'bg-ground-50 text-ground-500 ring-ground-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.slipCheck.status.${s}`)}
      </span>
    )
  }

  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  const entered = chk.slip_count - chk.missing.length
  const subjectsValue =
    chk.subjects === 'match'
      ? t('scholarship.docs.slipCheck.allEntered')
      : chk.subjects === 'mismatch'
        ? `${t('scholarship.docs.slipCheck.missing')}: ${chk.missing.join(', ')}`
        : '—'
  const resultsValue =
    chk.results === 'match'
      ? t('scholarship.docs.slipCheck.allMatch')
      : chk.results === 'mismatch'
        ? chk.mismatched
            .map((m) => `${m.subject} (${t('scholarship.docs.slipCheck.youTyped')} ${m.typed}, ${t('scholarship.docs.slipCheck.slipSays')} ${m.slip})`)
            .join('; ')
        : chk.results === 'uncertain'
          ? `${t('scholarship.docs.slipCheck.uncertainNote')}: ${(chk.uncertain || []).map((m) => m.subject).join(', ')}`
          : '—'

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {row(t('scholarship.docs.slipCheck.name'), chk.candidate_name, badge(chk.name))}
      {row(
        // Only show the "(entered/total)" count when there's a real subjects mismatch;
        // for match / couldn't-read / pending it's noise (and "(0/0)" looks broken).
        chk.subjects === 'mismatch'
          ? `${t('scholarship.docs.slipCheck.subjects')} (${entered}/${chk.slip_count})`
          : t('scholarship.docs.slipCheck.subjects'),
        subjectsValue,
        badge(chk.subjects),
      )}
      {row(t('scholarship.docs.slipCheck.results'), resultsValue, badge(chk.results))}
      {chk.exam_year || chk.exam
        ? row(
            t('scholarship.docs.slipCheck.exam'),
            chk.exam || chk.exam_year,
            <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
              {t('scholarship.docs.slipCheck.fromSlip')}
            </span>,
          )
        : null}
    </div>
  )
}