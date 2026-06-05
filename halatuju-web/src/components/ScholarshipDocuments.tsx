'use client'

import { useState, useEffect, useCallback, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import {
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  listDocuments,
  deleteDocument,
  getConsentStatus,
  updateScholarshipDetails,
  type ApplicantDocument,
  type ScholarshipApplication,
} from '@/lib/api'
import {
  INCOME_PROOF_TYPES,
  formatFileSize,
} from '@/lib/scholarship'
import {
  incomeRequirements,
  wizardComplete,
  type IncomeRoute,
  type IncomeEarner,
  type WorkingMember,
} from '@/lib/incomeWizard'
import DocumentHelpCoach from './DocumentHelpCoach'

// Per-file size cap (mirrors the server's MAX_DOC_SIZE_BYTES default — server is
// authoritative; this gives the student instant feedback before any upload).
const MAX_DOC_SIZE_BYTES = 8 * 1024 * 1024

// Busy/filter key for a doc card. Salary-route income docs are scoped to a household
// member, so two members' salary slips don't share one busy spinner or file list.
// member '' → just the doc type (backward-compatible with every non-income card).
function docKey(docType: string, member = ''): string {
  return member ? `${docType}:${member}` : docType
}

// ── Shared sub-components ─────────────────────────────────────────────────

function UploadedFileRow({
  doc,
  onDelete,
  t,
}: {
  doc: ApplicantDocument
  onDelete: (id: number) => void
  t: (key: string) => string
}) {
  return (
    <li className="flex items-center justify-between text-sm text-gray-600">
      <span className="truncate">
        {doc.download_url ? (
          <a
            href={doc.download_url}
            target="_blank"
            rel="noreferrer"
            className="text-primary-600 hover:underline"
          >
            {doc.original_filename || doc.doc_type}
          </a>
        ) : (
          doc.original_filename || doc.doc_type
        )}
        {doc.size ? (
          <span className="text-gray-400"> · {formatFileSize(doc.size)}</span>
        ) : null}
      </span>
      <button
        onClick={() => onDelete(doc.id)}
        className="text-red-500 hover:underline ml-2 shrink-0"
      >
        {t('scholarship.docs.remove')}
      </button>
    </li>
  )
}

// Accept images + PDF only (mirrors the API allowlist; the file picker's `accept`
// is just a hint, so re-check here). Rejects video/other junk (TD-080).
const _ACCEPTED_UPLOAD_EXT = /\.(pdf|jpe?g|png|gif|bmp|webp|tiff?|heic|heif)$/i
function isAcceptedUpload(file: File): boolean {
  const mime = (file.type || '').toLowerCase()
  if (mime.startsWith('image/') || mime === 'application/pdf') return true
  return _ACCEPTED_UPLOAD_EXT.test(file.name || '')
}

function UploadTrigger({
  docType,
  busy,
  onUpload,
  label,
}: {
  docType: string
  busy: boolean
  onUpload: (docType: string, file: File) => void
  label: string
}) {
  return (
    <label className="text-sm text-primary-600 cursor-pointer hover:underline shrink-0">
      {label}
      <input
        type="file"
        // Accept photos + PDFs (scan-to-PDF, EPF/payslip downloads). A hint only —
        // the backend allowlist is the real guard (TD-080). Excludes video/junk.
        accept="image/*,application/pdf,.pdf"
        className="hidden"
        disabled={busy}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onUpload(docType, f)
          e.target.value = ''
        }}
      />
    </label>
  )
}

// ── Vision OCR chip (S13 — soft signal under the IC upload) ──────────────

type ICCheckKind = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'none'

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
function ICChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  if (!doc.vision_run_at) return null

  const badge = (kind: ICCheckKind) => {
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-green-50 text-green-700 ring-green-200',
      partial: 'bg-amber-50 text-amber-700 ring-amber-200',
      mismatch: 'bg-red-50 text-red-700 ring-red-200',
      unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
      none: 'bg-gray-50 text-gray-500 ring-gray-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.icCheck.${kind}`)}
      </span>
    )
  }

  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {row(t('scholarship.docs.icCheck.icNo'), doc.vision_nric, badge(icVerdictKind(doc.vision_nric_verdict)))}
      {row(t('scholarship.docs.icCheck.name'), doc.vision_name, badge(icVerdictKind(doc.vision_name_verdict)))}
      {doc.vision_address
        ? row(
            t('scholarship.docs.icCheck.address'),
            doc.vision_address,
            <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
              {t('scholarship.docs.icCheck.fromIc')}
            </span>,
          )
        : null}
    </div>
  )
}

/** Income earner IC checklist (Check-1 Income) — the SAME standard as the Identity IC
 *  card (IC No / Name / Address, each with the value Vision READ), but the verdict is the
 *  RELATIONSHIP, not an identity match against the student: the NRIC is the EARNER's, so it
 *  is shown for reference only; the Name carries a "links to your family" / "doesn't match"
 *  badge (father/brother/sister via the shared patronymic, mother via birth cert, guardian
 *  via letter). Cikgu Gopal (below) gives the "what to do" only on a real mismatch. */
function IncomeIcChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.income_ic_check
  if (!chk || !doc.vision_run_at) return null

  const nameKind: ICCheckKind =
    chk.name_status === 'match' ? 'match' : chk.name_status === 'mismatch' ? 'mismatch' : 'none'
  const cls: Record<ICCheckKind, string> = {
    match: 'bg-green-50 text-green-700 ring-green-200',
    partial: 'bg-amber-50 text-amber-700 ring-amber-200',
    mismatch: 'bg-red-50 text-red-700 ring-red-200',
    unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
    none: 'bg-gray-50 text-gray-500 ring-gray-200',
  }
  const nameLabel =
    chk.name_status === 'match'
      ? t('scholarship.docs.incomeIcCheck.linked')
      : chk.name_status === 'mismatch'
        ? t('scholarship.docs.incomeIcCheck.nameMismatch')
        : t('scholarship.docs.incomeIcCheck.reviewing')

  const neutralTag = (
    <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
      {t('scholarship.docs.icCheck.fromIc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {chk.nric ? row(t('scholarship.docs.icCheck.icNo'), chk.nric, neutralTag) : null}
      {row(
        t('scholarship.docs.icCheck.name'),
        chk.name,
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[nameKind]}`}>
          {nameLabel}
        </span>,
      )}
      {chk.address ? row(t('scholarship.docs.icCheck.address'), chk.address, neutralTag) : null}
    </div>
  )
}

/** Member-tagged salary slip / EPF checklist (Check-1 Income). Reads the EARNER's facts
 *  (Name · IC No · Amount · Period) and verifies the Name + IC No against the IC the
 *  student uploaded for that SAME member — never against the student. So a father's
 *  payslip is checked against the father's IC, and Gopal (below) never tells the student
 *  to edit their own name. Amount + period are soft data points shown for reference. */
function IncomeProofChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.income_proof_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-green-50 text-green-700 ring-green-200',
    partial: 'bg-amber-50 text-amber-700 ring-amber-200',
    mismatch: 'bg-red-50 text-red-700 ring-red-200',
    unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
    none: 'bg-gray-50 text-gray-500 ring-gray-200',
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
    <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
      {t('scholarship.docs.incomeProofCheck.fromDoc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {row(t('scholarship.docs.incomeProofCheck.name'), chk.name, vsIc(chk.name_status))}
      {chk.nric ? row(t('scholarship.docs.incomeProofCheck.icNo'), chk.nric, vsIc(chk.nric_status)) : null}
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
function UtilityChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.utility_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-green-50 text-green-700 ring-green-200',
    partial: 'bg-amber-50 text-amber-700 ring-amber-200',
    mismatch: 'bg-red-50 text-red-700 ring-red-200',
    unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
    none: 'bg-gray-50 text-gray-500 ring-gray-200',
  }
  const addrPill =
    chk.address_status === 'found'
      ? <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls.match}`}>{t('scholarship.docs.utilityCheck.addressOk')}</span>
      : chk.address_status === 'not_found'
        ? <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls.mismatch}`}>{t('scholarship.docs.utilityCheck.addressMismatch')}</span>
        : <span className={`shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200`}>{t('scholarship.docs.incomeProofCheck.fromDoc')}</span>
  const fromDoc = (
    <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
      {t('scholarship.docs.incomeProofCheck.fromDoc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
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
function StrChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.str_check
  if (!chk) return null

  const cls: Record<ICCheckKind, string> = {
    match: 'bg-green-50 text-green-700 ring-green-200',
    partial: 'bg-amber-50 text-amber-700 ring-amber-200',
    mismatch: 'bg-red-50 text-red-700 ring-red-200',
    unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
    none: 'bg-gray-50 text-gray-500 ring-gray-200',
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
  // Currency: current → green; unknown (nothing read) → neutral; stale/rejected → red.
  const currentPill =
    chk.current_status === 'current'
      ? pill('match', t('scholarship.docs.strCheck.current'))
      : chk.current_status === 'unknown'
        ? pill('none', t('scholarship.docs.strCheck.unknown'))
        : pill('mismatch', t(`scholarship.docs.strCheck.${chk.current_status}`))
  const fromDoc = (
    <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
      {t('scholarship.docs.incomeProofCheck.fromDoc')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {row(t('scholarship.docs.strCheck.recipient'), chk.name, vsIc(chk.name_status))}
      {chk.nric ? row(t('scholarship.docs.strCheck.icNo'), chk.nric, vsIc(chk.nric_status)) : null}
      {row(t('scholarship.docs.strCheck.statusYear'),
           [chk.status, chk.year].filter(Boolean).join(' · '), currentPill)}
      {chk.amount ? row(t('scholarship.docs.strCheck.amount'), chk.amount, fromDoc) : null}
    </div>
  )
}

// ── Relationship-proof checklists (Check-1 Income): birth cert + guardianship ──

const REL_PILL: Record<ICCheckKind, string> = {
  match: 'bg-green-50 text-green-700 ring-green-200',
  partial: 'bg-amber-50 text-amber-700 ring-amber-200',
  mismatch: 'bg-red-50 text-red-700 ring-red-200',
  unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
  none: 'bg-gray-50 text-gray-500 ring-gray-200',
}

function relPill(status: string, t: (k: string) => string): ReactNode {
  const kind: ICCheckKind = status === 'match' ? 'match' : status === 'mismatch' ? 'mismatch' : 'none'
  const label =
    status === 'match' ? t('scholarship.docs.relCheck.confirmed')
      : status === 'mismatch' ? t('scholarship.docs.relCheck.mismatch')
        : t('scholarship.docs.relCheck.reviewing')
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${REL_PILL[kind]}`}>{label}</span>
}

function relRow(label: string, value: string, right: ReactNode): ReactNode {
  return (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )
}

/** Birth-certificate checklist — links the student to their mother (the income earner):
 *  Child (vs you) · Mother (vs Mother's IC) · Father (vs your IC's family name). */
function BcChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.bc_check
  if (!chk) return null
  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {relRow(t('scholarship.docs.relCheck.child'), chk.child_name, relPill(chk.child_status, t))}
      {relRow(t('scholarship.docs.relCheck.mother'),
              [chk.mother_name, chk.mother_nric].filter(Boolean).join(' · '), relPill(chk.mother_status, t))}
      {chk.father_name ? relRow(t('scholarship.docs.relCheck.father'), chk.father_name, relPill(chk.father_status, t)) : null}
    </div>
  )
}

/** Guardianship-letter checklist — ties the guardian to the student (the ward):
 *  Guardian (vs Guardian's IC) · Ward (vs you). */
function GuardianshipChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.guardianship_check
  if (!chk) return null
  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
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

function ResultsSlipChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.academic_check
  if (!chk) return null

  const badge = (s: SlipStatus) => {
    const kind = slipBadgeKind(s)
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-green-50 text-green-700 ring-green-200',
      partial: 'bg-amber-50 text-amber-700 ring-amber-200',
      mismatch: 'bg-red-50 text-red-700 ring-red-200',
      unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
      none: 'bg-gray-50 text-gray-500 ring-gray-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.slipCheck.status.${s}`)}
      </span>
    )
  }

  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
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
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
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
            <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
              {t('scholarship.docs.slipCheck.fromSlip')}
            </span>,
          )
        : null}
    </div>
  )
}

// ── Offer-letter clinical facts (Check-1 Pathway) ────────────────────────
// Mirrors the IC / slip checklists. Two real identity checks — Name and IC (the
// IC is the strong one) — then the offer's facts as soft data points: programme,
// institution, who issued it (tells the pathway type), the date, and address.

type PathStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'uncertain' | 'pending'

function pathBadgeKind(s: PathStatus): ICCheckKind {
  if (s === 'match') return 'match'
  if (s === 'partial' || s === 'uncertain') return 'partial'
  if (s === 'mismatch') return 'mismatch'
  if (s === 'unreadable') return 'unreadable'
  return 'none' // pending
}

function OfferLetterChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.pathway_check
  if (!chk) return null

  const badge = (s: PathStatus) => {
    const kind = pathBadgeKind(s)
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-green-50 text-green-700 ring-green-200',
      partial: 'bg-amber-50 text-amber-700 ring-amber-200',
      mismatch: 'bg-red-50 text-red-700 ring-red-200',
      unreadable: 'bg-gray-50 text-gray-600 ring-gray-200',
      none: 'bg-gray-50 text-gray-500 ring-gray-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.pathwayCheck.status.${s}`)}
      </span>
    )
  }
  const fromLetter = (
    <span className="shrink-0 rounded-full bg-gray-50 px-2 py-0.5 text-[10px] text-gray-500 ring-1 ring-gray-200">
      {t('scholarship.docs.pathwayCheck.fromLetter')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-gray-700">
        <span className="font-medium text-gray-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )
  // Soft data point — only shown when the field was actually read.
  const dataRow = (labelKey: string, value: string) =>
    value ? row(t(`scholarship.docs.pathwayCheck.${labelKey}`), value, fromLetter) : null

  // The offer is for a genuinely different college/programme than declared. We mark
  // the two rows red (Check 1) — but it is NEVER a block: Cikgu Gopal reassures, and
  // the student confirms which is final when they submit (Check 2).
  const isMismatch = chk.pathway === 'mismatch'
  const pathRow = (labelKey: string, value: string) =>
    value
      ? row(
          t(`scholarship.docs.pathwayCheck.${labelKey}`),
          value,
          isMismatch ? badge('mismatch') : fromLetter,
        )
      : null

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {row(t('scholarship.docs.pathwayCheck.name'), chk.candidate_name, badge(chk.name))}
      {row(t('scholarship.docs.pathwayCheck.ic'), chk.candidate_nric, badge(chk.ic))}
      {pathRow('programme', chk.programme)}
      {pathRow('institution', chk.institution)}
      {dataRow('issuer', chk.issuer)}
      {dataRow('date', chk.offer_date || chk.intake)}
      {dataRow('address', chk.address)}
      {isMismatch && (chk.declared_programme || chk.declared_institution) ? (
        <p className="py-1.5 text-xs text-amber-700">
          {t('scholarship.docs.pathwayCheck.declaredNote')}{' '}
          <span className="font-medium">
            {[chk.declared_programme, chk.declared_institution].filter(Boolean).join(' · ')}
          </span>
        </p>
      ) : null}
    </div>
  )
}

// ── Supporting-doc soft chip (name/address presence, S) ──────────────────

function supportingChipVariant(doc: ApplicantDocument): 'good' | 'name-missing' | 'address-missing' | 'unreadable' | null {
  const nm = doc.vision_name_match
  if (!nm) return null   // not a checked supporting doc, or Vision hasn't run
  const am = doc.vision_address_match
  if (nm === 'unreadable' || am === 'unreadable') return 'unreadable'
  if (nm === 'not_found') return 'name-missing'
  if (am === 'not_found') return 'address-missing'
  return 'good'   // name found; address found or not applicable
}

// Document-assist verdict (Gemini extraction) takes precedence over the
// deterministic presence chip when it has run — it's richer + more specific.
function assistTone(verdict: string): 'good' | 'warn' | 'info' {
  if (verdict === 'ok') return 'good'
  if (verdict === 'unreadable' || verdict === 'review_manually') return 'info'
  return 'warn'   // name_mismatch / address_mismatch / wrong_doc
}

function SupportingDocChip({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const palette: Record<string, string> = {
    good: 'bg-green-50 text-green-800 ring-green-200',
    warn: 'bg-amber-50 text-amber-800 ring-amber-200',
    info: 'bg-gray-50 text-gray-700 ring-gray-200',
    'name-missing': 'bg-amber-50 text-amber-800 ring-amber-200',
    'address-missing': 'bg-amber-50 text-amber-800 ring-amber-200',
    unreadable: 'bg-gray-50 text-gray-700 ring-gray-200',
  }
  const chip = (tone: string, icon: string, text: string) => (
    <div className="mt-2">
      <span className={`inline-flex items-start gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 ${palette[tone]}`}>
        <span aria-hidden>{icon}</span>
        <span>{text}</span>
      </span>
      <p className="mt-1 text-xs text-gray-400">{t('scholarship.docs.vision.note')}</p>
    </div>
  )
  // Prefer the Gemini doc-assist verdict when it ran.
  const av = doc.vision_fields?.student_verdict
  if (av) {
    const tone = assistTone(av)
    return chip(tone, tone === 'good' ? '✓' : tone === 'info' ? 'ⓘ' : '⚠', t(`scholarship.docs.assist.${av}`))
  }
  // Fallback: the deterministic name/address presence chip.
  const variant = supportingChipVariant(doc)
  if (!variant) return null
  return chip(variant, variant === 'good' ? '✓' : variant === 'unreadable' ? 'ⓘ' : '⚠',
    t(`scholarship.docs.match.${variant}`))
}

// ── Single-type upload card ───────────────────────────────────────────────

function SingleDocCard({
  docType,
  docs,
  busyType,
  onUpload,
  onDelete,
  t,
  token,
  lang,
  showVisionChip = false,
  required = false,
  helpOverride,
  titleOverride,
  member = '',
}: {
  docType: string
  docs: ApplicantDocument[]
  busyType: string | null
  onUpload: (docType: string, file: File, member?: string) => void
  onDelete: (id: number) => void
  t: (key: string) => string
  token: string | null
  lang: string
  showVisionChip?: boolean
  required?: boolean
  helpOverride?: string
  titleOverride?: string
  member?: string
}) {
  const busy = busyType === docKey(docType, member)
  // Salary-route income docs are scoped to a household member; everything else is
  // member ''. Match on the pair so father's payslip card shows only father's file.
  const existing = docs.filter((d) => d.doc_type === docType && (d.household_member || '') === member)
  const visionDoc = showVisionChip ? existing.find((d) => d.vision_run_at) : null
  const onPick = (dt: string, f: File) => onUpload(dt, f, member)

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-gray-800">
            {titleOverride ?? t(`scholarship.docs.type.${docType}`)}
            {required && <span className="text-red-500"> *</span>}
          </span>
          <p className="text-xs text-gray-500 mt-0.5">
            {helpOverride ?? t(`scholarship.docs.help.${docType}`)}
          </p>
        </div>
        <UploadTrigger
          docType={docType}
          busy={busy}
          onUpload={onPick}
          label={
            busy
              ? t('scholarship.docs.uploading')
              : existing.length > 0
              // Single-instance doc types replace on re-upload (backend
              // sweeps the old file + Storage blob). Be honest about it.
              ? t('scholarship.docs.replace')
              : t('scholarship.docs.choose')
          }
        />
      </div>
      {existing.length > 0 && (
        <ul className="mt-2 space-y-1">
          {existing.map((d) => (
            <UploadedFileRow key={d.id} doc={d} onDelete={onDelete} t={t} />
          ))}
        </ul>
      )}
      {visionDoc && (
        <>
          <ICChecklist doc={visionDoc} t={t} />
          <DocumentHelpCoach doc={visionDoc} token={token} t={t} lang={lang} />
        </>
      )}
      {existing.filter((d) => d !== visionDoc).map((d) => (
        <div key={`m${d.id}`}>
          {/* The results slip + offer letter get clinical fact-checklists; every
              other supporting doc keeps the single soft chip. */}
          {d.doc_type === 'results_slip' && d.academic_check ? (
            <ResultsSlipChecklist doc={d} t={t} />
          ) : d.doc_type === 'offer_letter' && d.pathway_check ? (
            <OfferLetterChecklist doc={d} t={t} />
          ) : d.doc_type === 'parent_ic' && d.income_ic_check ? (
            <IncomeIcChecklist doc={d} t={t} />
          ) : (d.doc_type === 'salary_slip' || d.doc_type === 'epf') && d.income_proof_check ? (
            <IncomeProofChecklist doc={d} t={t} />
          ) : d.doc_type === 'str' && d.str_check ? (
            <StrChecklist doc={d} t={t} />
          ) : (d.doc_type === 'water_bill' || d.doc_type === 'electricity_bill') && d.utility_check ? (
            <UtilityChecklist doc={d} t={t} />
          ) : d.doc_type === 'birth_certificate' && d.bc_check ? (
            <BcChecklist doc={d} t={t} />
          ) : d.doc_type === 'guardianship_letter' && d.guardianship_check ? (
            <GuardianshipChecklist doc={d} t={t} />
          ) : (
            <SupportingDocChip doc={d} t={t} />
          )}
          <DocumentHelpCoach doc={d} token={token} t={t} lang={lang} />
        </div>
      ))}
    </div>
  )
}

// ── Combined income-proof card ────────────────────────────────────────────

function IncomeProofCard({
  docs,
  busyType,
  onUpload,
  onDelete,
  t,
  token,
  lang,
}: {
  docs: ApplicantDocument[]
  busyType: string | null
  onUpload: (docType: string, file: File) => void
  onDelete: (id: number) => void
  t: (key: string) => string
  token: string | null
  lang: string
}) {
  const incomeTypes = [...INCOME_PROOF_TYPES] as string[]
  const existing = docs.filter((d) => incomeTypes.includes(d.doc_type))
  const [activeType, setActiveType] = useState<string>(INCOME_PROOF_TYPES[0])
  const busy = busyType === activeType

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <span className="text-sm font-medium text-gray-800">
            {t('scholarship.docs.income.title')}
          </span>
          <p className="text-xs text-gray-500 mt-0.5">
            {t('scholarship.docs.help.income')}
          </p>
          {/* Type selector */}
          <div className="flex flex-wrap gap-2 mt-2">
            {INCOME_PROOF_TYPES.map((dt) => (
              <button
                key={dt}
                onClick={() => setActiveType(dt)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  activeType === dt
                    ? 'bg-primary-600 text-white border-primary-600'
                    : 'text-gray-600 border-gray-300 hover:border-primary-400'
                }`}
              >
                {t(`scholarship.docs.type.${dt}`)}
              </button>
            ))}
          </div>
        </div>
        <UploadTrigger
          docType={activeType}
          busy={busy}
          onUpload={onUpload}
          label={
            busy ? t('scholarship.docs.uploading') : t('scholarship.docs.choose')
          }
        />
      </div>
      {existing.length > 0 && (
        <ul className="mt-2 space-y-1">
          {existing.map((d) => (
            <li key={d.id}>
              <div className="flex items-center justify-between text-sm text-gray-600">
                <span className="truncate">
                  <span className="text-gray-400 text-xs mr-1">
                    [{t(`scholarship.docs.type.${d.doc_type}`)}]
                  </span>
                  {d.download_url ? (
                    <a
                      href={d.download_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary-600 hover:underline"
                    >
                      {d.original_filename || d.doc_type}
                    </a>
                  ) : (
                    d.original_filename || d.doc_type
                  )}
                  {d.size ? (
                    <span className="text-gray-400"> · {formatFileSize(d.size)}</span>
                  ) : null}
                </span>
                <button
                  onClick={() => onDelete(d.id)}
                  className="text-red-500 hover:underline ml-2 shrink-0"
                >
                  {t('scholarship.docs.remove')}
                </button>
              </div>
              <SupportingDocChip doc={d} t={t} />
              <DocumentHelpCoach doc={d} token={token} t={t} lang={lang} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

// ── Income wizard (Check-1 item 3) ────────────────────────────────────────
// A few questions → the dynamic document checklist (compulsory + optional),
// mirroring income_engine.income_requirements so the student's list matches the
// officer verdict exactly. Encouraging, never-punitive; nothing here blocks.

function IncomeWizard({
  app,
  token,
  t,
  renderCard,
  onChange,
}: {
  app: ScholarshipApplication
  token: string | null
  t: (key: string) => string
  renderCard: (docType: string, opts?: { required?: boolean; helpOverride?: string; titleOverride?: string; member?: string }) => ReactNode
  onChange?: () => void
}) {
  // Q1 prefills from the Apply-stage STR declaration (receives_str): had STR → 'str' (Yes),
  // else 'salary' (No). The student can change it.
  const prefillRoute = app.income_route || (app.receives_str ? 'str' : 'salary')
  const [ans, setAns] = useState({
    income_route: prefillRoute,
    income_earner: app.income_earner || '',
    income_working_members: (app.income_working_members || []) as WorkingMember[],
    siblings_in_school: app.siblings_in_school,
    siblings_in_tertiary: app.siblings_in_tertiary,
  })

  const save = async (patch: Record<string, unknown>) => {
    setAns((a) => ({ ...a, ...patch }))
    if (!token) return
    try {
      await updateScholarshipDetails(app.id, patch, { token })
      onChange?.()
    } catch {
      /* soft — local state already updated, save retries on the next change */
    }
  }

  // Persist the prefilled route once (so the verdict reflects the declaration), only if
  // the student hasn't already set a route.
  useEffect(() => {
    if (!app.income_route && token) {
      updateScholarshipDetails(app.id, { income_route: prefillRoute }, { token })
        .then(() => onChange?.())
        .catch(() => { /* soft */ })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const iq = (k: string) => t(`scholarship.docs.income.wizard.${k}`)

  const Pills = ({
    options,
    selected,
    onPick,
  }: {
    options: { value: string; label: string }[]
    selected: string
    onPick: (v: string) => void
  }) => (
    <div className="flex flex-wrap gap-2 mt-1.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onPick(o.value)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
            selected === o.value
              ? 'bg-primary-600 text-white border-primary-600'
              : 'text-gray-600 border-gray-300 hover:border-primary-400'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )

  const Stepper = ({ field, value }: { field: string; value: number | null | undefined }) => {
    const n = value ?? 0
    return (
      <div className="flex items-center gap-2 mt-1.5">
        <button type="button" aria-label="decrease" onClick={() => save({ [field]: Math.max(0, n - 1) })}
          className="h-7 w-7 rounded-full border border-gray-300 text-gray-600 hover:border-primary-400">−</button>
        <span className="w-6 text-center text-sm font-medium">{n}</span>
        <button type="button" aria-label="increase" onClick={() => save({ [field]: Math.min(20, n + 1) })}
          className="h-7 w-7 rounded-full border border-gray-300 text-gray-600 hover:border-primary-400">+</button>
      </div>
    )
  }

  const Question = ({ label, children }: { label: string; children: ReactNode }) => (
    <div>
      <p className="text-sm font-medium text-gray-800">{label}</p>
      {children}
    </div>
  )


  const answers = {
    income_route: ans.income_route as IncomeRoute,
    income_earner: ans.income_earner as IncomeEarner,
    income_working_members: ans.income_working_members,
  }
  const reqs = incomeRequirements(answers)
  const ready = wizardComplete(answers)

  // Salary route — toggle a working household member in/out of the multi-select.
  const MEMBER_OPTIONS: WorkingMember[] = ['father', 'mother', 'guardian', 'brother', 'sister']
  const members = ans.income_working_members
  const toggleMember = (m: WorkingMember) => {
    const next = members.includes(m) ? members.filter((x) => x !== m) : [...members, m]
    save({ income_working_members: next })
  }

  // STR-route checklist display order: income evidence first, then the earner IC,
  // then the relationship doc.
  const DISPLAY_ORDER = ['str', 'salary_slip', 'epf', 'water_bill', 'electricity_bill',
                         'parent_ic', 'birth_certificate', 'guardianship_letter']
  const ordered = (docs: string[]) =>
    [...docs].sort((a, b) => DISPLAY_ORDER.indexOf(a) - DISPLAY_ORDER.indexOf(b))
  // STR route: income-doc help + IC card title name the single chosen earner.
  const e = ans.income_earner
  const helpFor = (dt: string): string | undefined => {
    if (!e) return undefined
    if (dt === 'parent_ic') return iq(`icHelp.${e}`)
    if (dt === 'salary_slip') return iq(`salaryHelp.${e}`)
    if (dt === 'epf') return iq(`epfHelp.${e}`)
    return undefined
  }
  const titleFor = (dt: string): string | undefined =>
    dt === 'parent_ic' && e ? iq(`icTitle.${e}`) : undefined
  // Salary route: the same context-aware help/title, but per household-member block.
  const memberHelp = (dt: string, m: string): string | undefined => {
    if (dt === 'parent_ic') return iq(`icHelp.${m}`)
    if (dt === 'salary_slip') return iq(`salaryHelp.${m}`)
    if (dt === 'epf') return iq(`epfHelp.${m}`)
    return undefined // birth cert / guardianship letter keep their default help
  }
  const memberTitle = (dt: string, m: string): string | undefined =>
    dt === 'parent_ic' ? iq(`icTitle.${m}`) : undefined

  return (
    <div className="space-y-4">
      {/* Encouraging, never-punitive intro (blue = info). */}
      <div className="rounded-xl bg-blue-50 ring-1 ring-blue-100 p-3 text-sm text-blue-900/90">
        {iq('intro')}
      </div>

      {/* Q1 — STR document? Yes → STR route, No → salary route */}
      <Question label={iq('q1')}>
        <Pills selected={ans.income_route}
          options={[{ value: 'str', label: iq('yes') }, { value: 'salary', label: iq('no') }]}
          onPick={(v) => save({ income_route: v })} />
      </Question>

      {/* Q2 — STR route: a single earner. Salary route: tick everyone who works. */}
      {ans.income_route === 'str' ? (
        <Question label={iq('q2Str')}>
          <Pills selected={ans.income_earner}
            options={['father', 'mother', 'guardian'].map((v) => ({ value: v, label: iq(`earner.${v}`) }))}
            onPick={(v) => save({ income_earner: v })} />
        </Question>
      ) : (
        <Question label={iq('q2Multi')}>
          <div className="flex flex-wrap gap-2 mt-1.5">
            {MEMBER_OPTIONS.map((m) => {
              const on = members.includes(m)
              return (
                <button key={m} type="button" onClick={() => toggleMember(m)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    on ? 'bg-primary-600 text-white border-primary-600'
                       : 'text-gray-600 border-gray-300 hover:border-primary-400'}`}>
                  {on ? '✓ ' : ''}{iq(`member.${m}`)}
                </button>
              )
            })}
          </div>
        </Question>
      )}

      {/* Family burden */}
      <div className="grid grid-cols-2 gap-3">
        <Question label={iq('school')}><Stepper field="siblings_in_school" value={ans.siblings_in_school} /></Question>
        <Question label={iq('tertiary')}><Stepper field="siblings_in_tertiary" value={ans.siblings_in_tertiary} /></Question>
      </div>

      {/* Dynamic checklist — appears once the wizard is answered. Compulsory docs carry a
          red * on the card title; optional docs carry no marker (the * is what distinguishes). */}
      {ready && ans.income_route === 'str' && (
        <div className="space-y-3 pt-1">
          {ordered(reqs.compulsory).map((dt) => (
            <div key={dt}>{renderCard(dt, { required: true, helpOverride: helpFor(dt), titleOverride: titleFor(dt) })}</div>
          ))}
          {ordered(reqs.optional).map((dt) => (
            <div key={dt}>
              {renderCard(dt, { required: false, helpOverride: helpFor(dt), titleOverride: titleFor(dt) })}
            </div>
          ))}
          <p className="text-xs text-gray-400">{iq('footer')}</p>
        </div>
      )}

      {/* Salary route — one document block per ticked working member. */}
      {ready && ans.income_route === 'salary' && (
        <div className="space-y-3 pt-1">
          {reqs.members.map((block) => (
            <div key={block.member} className="rounded-lg border border-gray-100 bg-gray-50/60 p-2.5 space-y-2">
              <p className="text-xs font-semibold text-gray-700">{iq(`member.${block.member}`)}</p>
              {block.compulsory.map(({ docType, member }) => (
                <div key={docKey(docType, member)}>
                  {renderCard(docType, { required: true, member,
                    helpOverride: memberHelp(docType, block.member),
                    titleOverride: memberTitle(docType, block.member) })}
                </div>
              ))}
              {block.optional.map(({ docType, member }) => (
                <div key={docKey(docType, member)}>
                  {renderCard(docType, { required: false, member,
                    helpOverride: memberHelp(docType, block.member) })}
                </div>
              ))}
            </div>
          ))}
          {/* Household-level optional credibility docs (utility bills). */}
          {reqs.optional.map((dt) => (
            <div key={dt}>
              {renderCard(dt, { required: false })}
            </div>
          ))}
          <p className="text-xs text-gray-400">{iq('footer')}</p>
        </div>
      )}
    </div>
  )
}


export default function ScholarshipDocuments({ token, onChange, app }: { token: string | null; onChange?: () => void; app?: ScholarshipApplication | null }) {
  const { t, locale } = useT()
  const [docs, setDocs] = useState<ApplicantDocument[]>([])
  const [busyType, setBusyType] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // S17: minors get an additional Required card (parent_ic) and an Optional
  // card (guardianship_letter). is_minor is derived backend-side from the
  // profile's NRIC year and surfaced on the consent status endpoint.
  const [isMinor, setIsMinor] = useState(false)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const r = await listDocuments({ token })
      setDocs(r.documents)
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!token) return
    getConsentStatus({ token }).then((s) => setIsMinor(!!s.is_minor)).catch(() => { /* ignore */ })
  }, [token])

  const handleUpload = async (docType: string, file: File, member = '') => {
    if (!token) return
    // Guardrail: per-file size cap — instant feedback, no wasted upload.
    if (file.size > MAX_DOC_SIZE_BYTES) {
      setError(t('scholarship.docs.file_too_large'))
      return
    }
    // Guardrail: images + PDF only (TD-080) — instant feedback, mirrors the API allowlist.
    if (!isAcceptedUpload(file)) {
      setError(t('scholarship.docs.unsupportedFormat'))
      return
    }
    setBusyType(docKey(docType, member))
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(docType, { token })
      await uploadFileToSignedUrl(upload_url, file)
      await recordDocument(
        { doc_type: docType, storage_path, household_member: member,
          original_filename: file.name, content_type: file.type, size: file.size },
        { token },
      )
      await refresh()
      onChange?.()
    } catch (e) {
      const code = (e as { code?: string })?.code
      setError(
        code === 'doc_limit_reached' ? t('scholarship.docs.doc_limit_reached')
        : code === 'file_too_large' ? t('scholarship.docs.file_too_large')
        : code === 'unsupported_format' ? t('scholarship.docs.unsupportedFormat')
        : t('scholarship.docs.uploadError'),
      )
    } finally {
      setBusyType(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (!token) return
    try {
      await deleteDocument(id, { token })
      await refresh()
      onChange?.()
    } catch {
      setError(t('scholarship.docs.deleteError'))
    }
  }

  // A doc card with the shared handlers closed over — keeps the sections tidy.
  const card = (docType: string, extra: { showVisionChip?: boolean; required?: boolean; helpOverride?: string; titleOverride?: string; member?: string } = {}) => (
    <SingleDocCard
      key={docKey(docType, extra.member)}
      docType={docType}
      docs={docs}
      busyType={busyType}
      onUpload={handleUpload}
      onDelete={handleDelete}
      t={t}
      token={token}
      lang={locale}
      {...extra}
    />
  )

  // Section header: title + a status pill (compulsory / important / optional) + note.
  type SectionPill = 'compulsory' | 'important' | 'optional'
  const pillClass: Record<SectionPill, string> = {
    compulsory: 'bg-amber-100 text-amber-800',
    important: 'bg-blue-100 text-blue-800',
    optional: 'bg-gray-100 text-gray-600',
  }
  // pill null → a bare section title (no badge, no note); the compulsory status is
  // shown on the cards themselves (a red * after the title).
  const sectionHead = (key: string, pill: SectionPill | null, showNote = false) => (
    <div className="mb-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-800">
          {t(`scholarship.docs.section.${key}.title`)}
        </h3>
        {pill && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${pillClass[pill]}`}>
            {t(`scholarship.docs.pill.${pill}`)}
          </span>
        )}
      </div>
      {(pill || showNote) && <p className="text-xs text-gray-500 mt-0.5">{t(`scholarship.docs.section.${key}.note`)}</p>}
    </div>
  )

  // Documents are grouped by the four verification facts (matching the officer's
  // verdict + Documents drawer) + an Other bucket:
  //   Identity (IC) · Academic (results slip) · Pathway (offer letter) ·
  //   Income (income proof + parent IC + utility bills) · Other (intent, photo).
  return (
    <div className="space-y-6">
      <section>
        {sectionHead('identity', null)}
        <div className="space-y-3">{card('ic', { showVisionChip: true, required: true })}</div>
      </section>

      <section>
        {sectionHead('academic', null)}
        <div className="space-y-3">{card('results_slip', { required: true })}</div>
      </section>

      <section>
        {sectionHead('pathway', null)}
        <div className="space-y-3">{card('offer_letter', { required: true })}</div>
      </section>

      <section>
        {sectionHead('income', null)}
        {app ? (
          /* Guided wizard → dynamic checklist (Check-1 item 3). */
          <IncomeWizard app={app} token={token} t={t} onChange={onChange}
            renderCard={(dt, opts) => card(dt, opts)} />
        ) : (
          /* Fallback (no application loaded): the original static income cards. */
          <div className="space-y-3">
            <IncomeProofCard
              docs={docs}
              busyType={busyType}
              onUpload={handleUpload}
              onDelete={handleDelete}
              t={t}
              token={token}
              lang={locale}
            />
            {card('parent_ic', { showVisionChip: false })}
            {card('water_bill')}
            {card('electricity_bill')}
          </div>
        )}
      </section>

      <section>
        {sectionHead('other', null, true)}
        <div className="space-y-3">
          {card('statement_of_intent')}
          {card('photo')}
          {/* S17: a minor with a non-parent guardian uploads the guardianship letter
              here; the relationship is picked on Consent and the POST blocks if missing. */}
          {isMinor && card('guardianship_letter')}
        </div>
      </section>

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}
