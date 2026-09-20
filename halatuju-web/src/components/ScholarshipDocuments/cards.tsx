'use client'

/**
 * THE DOCUMENT CARD AND ITS FURNITURE — the upload trigger, the file chip, the "done" collapse,
 * the single-document card and the income-proof card.
 *
 * ⚠ MOVED OUT OF `ScholarshipDocuments.tsx` WHOLE at code health H14. These draw the card; the
 * checklists that go inside it are `./checklists.tsx` and `./checklistsPathway.tsx`.
 */
import { useState, type ReactNode } from 'react'
import type { ApplicantDocument } from '@/lib/api'
import { INCOME_PROOF_TYPES, docFileLayout, formatFileSize } from '@/lib/scholarship'
import DocumentHelpCoach from '../DocumentHelpCoach'

import {
  ICChecklist,
  IncomeIcChecklist,
  IncomeProofChecklist,
  UtilityChecklist,
  GenuinenessNote,
  StrChecklist,
  BcChecklist,
  GuardianshipChecklist,
  ResultsSlipChecklist,
} from './checklists'
import { OfferLetterChecklist, SupportingDocChip } from './checklistsPathway'

// Busy/filter key for a doc card. Salary-route income docs are scoped to a household
// member, so two members' salary slips don't share one busy spinner or file list.
// member '' → just the doc type (backward-compatible with every non-income card).
export function docKey(docType: string, member = ''): string {
  return member ? `${docType}:${member}` : docType
}

// ── Shared sub-components ─────────────────────────────────────────────────

// Accept images + PDF only (mirrors the API allowlist; the file picker's `accept`
// is just a hint, so re-check here). Rejects video/other junk (TD-080).
const _ACCEPTED_UPLOAD_EXT = /\.(pdf|jpe?g|png|gif|bmp|webp|tiff?|heic|heif)$/i
export function isAcceptedUpload(file: File): boolean {
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
        // `sr-only`, NOT `hidden`: several Android browsers refuse to open the
        // native file picker for a display:none input triggered via its label.
        // sr-only keeps the input rendered (just visually hidden) so the picker
        // reliably opens — matching the Funding step's sr-only radio pills.
        className="sr-only"
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

// An uploaded file as one tidy bordered row: icon + name + size on the left, the actions
// grouped on the right so they line up instead of stacking on separate lines. THE one file
// presentation for every document card — `onUpload` omitted (a card holding more than one
// file) simply drops Replace, so the rows still look the same.
function FileChip({
  doc,
  docType,
  busy,
  onUpload,
  onDelete,
  t,
}: {
  doc: ApplicantDocument
  docType: string
  busy: boolean
  onUpload?: (docType: string, file: File) => void
  onDelete: (id: number) => void
  t: (key: string) => string
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-ground-200 bg-ground-50/60 px-3 py-2.5">
      <span className="flex min-w-0 items-center gap-2 text-sm text-ground-600">
        <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-primary-600" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 3h7l5 5v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M14 3v5h5" />
        </svg>
        <span className="truncate">
          {doc.download_url ? (
            <a href={doc.download_url} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">
              {doc.original_filename || doc.doc_type}
            </a>
          ) : (
            doc.original_filename || doc.doc_type
          )}
          {doc.size ? <span className="text-ground-400"> · {formatFileSize(doc.size)}</span> : null}
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-4">
        {onUpload && (
          <UploadTrigger docType={docType} busy={busy} onUpload={onUpload}
            label={busy ? t('scholarship.docs.uploading') : t('scholarship.docs.replace')} />
        )}
        <button onClick={() => onDelete(doc.id)} className="text-sm text-critical-600 hover:underline">
          {t('scholarship.docs.remove')}
        </button>
      </span>
    </div>
  )
}
// ── "Done" collapse ───────────────────────────────────────────────────────
// A finished document folds to a calm green summary (title + a word of reassurance),
// re-openable on tap. It collapses ONLY when genuinely finished: a verified doc reads
// all-green, or an unverifiable optional (photo / statement of intent) is simply
// uploaded. Anything amber / red / pending / suspect stays OPEN so the student still
// sees what needs doing. Income-cluster docs are excluded at the call site (the shared
// cluster coach speaks across them) via `suppressCoach`.

function docIsGenuine(doc: ApplicantDocument): boolean {
  const s = doc.authenticity?.status
  return !s || s === 'genuine'   // canonical: '' / 'genuine' vs suspect / not_<type>
}

function docDone(docType: string, doc: ApplicantDocument | undefined): boolean {
  if (!doc) return false
  switch (docType) {
    case 'ic':
      return !!doc.vision_run_at
        && doc.vision_name_verdict === 'match'
        && doc.vision_nric_verdict === 'match'
        && docIsGenuine(doc)
    case 'results_slip': {
      const c = doc.academic_check
      return !!c && c.name === 'match' && c.subjects === 'match' && c.results === 'match'
        && docIsGenuine(doc)
    }
    // Nothing to verify — uploaded IS finished.
    case 'photo':
    case 'statement_of_intent':
      return true
    default:
      return false   // everything else keeps today's always-open card
  }
}

// ── Collapsible section ───────────────────────────────────────────────────
// Folds a whole stage behind a summary so the Documents tab never reads as a wall of
// uploads. `tone='done'` = a green, reassuring header (a finished stage); `tone='optional'`
// = a quiet dashed shell the student opens only if they have more to add. Nothing REQUIRED
// and unmet is ever put behind one — only finished or genuinely-optional stages.

export function CollapsibleSection({
  tone,
  title,
  summary,
  defaultOpen = false,
  openLabel,
  hideLabel,
  children,
}: {
  tone: 'done' | 'optional'
  title: ReactNode
  summary: string
  defaultOpen?: boolean
  openLabel: string
  hideLabel: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const done = tone === 'done'
  return (
    <div className={`rounded-lg border overflow-hidden ${done ? 'border-positive-200' : 'border-dashed border-ground-200'}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`flex w-full items-center gap-3 px-3 py-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-positive-500 ${
          done ? (open ? 'bg-positive-50' : 'bg-positive-50/70') : 'bg-ground-50/60'}`}
      >
        <span aria-hidden className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${
          done ? 'bg-positive-fill text-positive-fill-ink' : 'border border-ground-200 bg-ground-100 text-ground-400'}`}>
          {done ? (
            <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
            </svg>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ground-800">{title}</span>
          <span className={`mt-0.5 block text-xs ${done ? 'text-positive-700' : 'text-ground-500'}`}>{summary}</span>
        </span>
        <span className="shrink-0 text-xs font-medium text-ground-400">{open ? hideLabel : openLabel}</span>
        <svg aria-hidden viewBox="0 0 24 24" className={`h-4 w-4 shrink-0 text-ground-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && <div className={`border-t p-3 ${done ? 'border-positive-100' : 'border-ground-100'}`}>{children}</div>}
    </div>
  )
}

// ── Single-type upload card ───────────────────────────────────────────────

export function SingleDocCard({
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
  legacyBlank = false,
  suppressCoach = false,
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
  // Slot model (TD-115): an STR earner's income doc may carry the legacy blank tag during the
  // backfill — show it under the earner's card too (uploads still tag the earner).
  legacyBlank?: boolean
  // Income cluster docs suppress their per-file coach — one cluster coach speaks for them.
  suppressCoach?: boolean
}) {
  const [open, setOpen] = useState(false)
  const busy = busyType === docKey(docType, member)
  // Member-scoped income docs match on the (type, member) pair so each earner's card shows only
  // their file; STR cards also accept the legacy untagged copy during the slot backfill.
  const existing = docs.filter((d) => d.doc_type === docType
    && ((d.household_member || '') === member || (legacyBlank && !(d.household_member || ''))))
  const visionDoc = showVisionChip ? existing.find((d) => d.vision_run_at) : null
  const onPick = (dt: string, f: File) => onUpload(dt, f, member)

  // Collapse to a green "done" summary once finished — but never mid-upload (show the
  // full card so the "Uploading…" state is visible), and never for income-cluster docs.
  const doneDoc = docType === 'ic' ? (visionDoc ?? existing[0]) : existing[0]
  const done = !suppressCoach && existing.length > 0 && !busy && docDone(docType, doneDoc)
  // One file → the tidy chip with Replace + Remove inside it; more than one (an STR earner's
  // legacy untagged copy beside the tagged one) → the list, Replace back in the header. No doc
  // type is exempt — see `docFileLayout`.
  const layout = docFileLayout(existing.length)

  const title = (
    <>
      {titleOverride ?? t(`scholarship.docs.type.${docType}`)}
      {required && <span className="text-critical-600"> *</span>}
    </>
  )

  // The uploaded file(s) — the same bordered row either way; only Replace's home differs.
  const fileBlock = layout === 'chip' ? (
    <div className="mt-2">
      <FileChip doc={existing[0]} docType={docType} busy={busy} onUpload={onPick} onDelete={onDelete} t={t} />
    </div>
  ) : layout === 'list' ? (
    <ul className="mt-2 space-y-1">
      {existing.map((d) => (
        <li key={d.id}>
          <FileChip doc={d} docType={docType} busy={busy} onDelete={onDelete} t={t} />
        </li>
      ))}
    </ul>
  ) : null

  // The per-type fact checklists + coach — everything below the file row. Shared by both
  // the normal and the collapsed-"done" layouts.
  const checks = (
    <>
      {visionDoc && (
        <>
          <ICChecklist doc={visionDoc} t={t} />
          {!suppressCoach && <DocumentHelpCoach doc={visionDoc} token={token} t={t} lang={lang} />}
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
          <GenuinenessNote doc={d} t={t} />
          {!suppressCoach && <DocumentHelpCoach doc={d} token={token} t={t} lang={lang} />}
        </div>
      ))}
    </>
  )

  // ── Collapsed "done" card: green summary, tap to reveal the detail. ──
  if (done) {
    return (
      <div className="rounded-lg border border-positive-200 overflow-hidden">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className={`flex w-full items-center gap-3 px-3 py-2.5 text-left ${open ? 'bg-positive-50' : 'bg-positive-50/70'} focus:outline-none focus-visible:ring-2 focus-visible:ring-positive-500`}
        >
          <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-positive-fill text-positive-fill-ink">
            <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-ground-800">{title}</span>
            <span className="mt-0.5 block text-xs text-positive-700">{t(`scholarship.docs.done.${docType}`)}</span>
          </span>
          <span className="shrink-0 text-xs font-medium text-ground-400">
            {open ? t('scholarship.docs.hide') : t('scholarship.docs.view')}
          </span>
          <svg aria-hidden viewBox="0 0 24 24" className={`h-4 w-4 shrink-0 text-ground-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
          </svg>
        </button>
        {open && (
          <div className="border-t border-positive-100 p-3">
            <p className="text-xs text-ground-500">{helpOverride ?? t(`scholarship.docs.help.${docType}`)}</p>
            {fileBlock}
            {checks}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-ground-800">{title}</span>
          <p className="text-xs text-ground-500 mt-0.5">
            {helpOverride ?? t(`scholarship.docs.help.${docType}`)}
          </p>
        </div>
        {/* With one file, Replace lives in the chip below (beside the file it replaces); the
            header trigger shows only to CHOOSE a first file, or to replace when the card
            happens to hold more than one and no single row owns the action. */}
        {layout !== 'chip' && (
          <UploadTrigger
            docType={docType}
            busy={busy}
            onUpload={onPick}
            label={
              busy
                ? t('scholarship.docs.uploading')
                : existing.length > 0
                ? t('scholarship.docs.replace')
                : t('scholarship.docs.choose')
            }
          />
        )}
      </div>
      {fileBlock}
      {checks}
    </div>
  )
}

// ── Combined income-proof card ────────────────────────────────────────────

export function IncomeProofCard({
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
          <span className="text-sm font-medium text-ground-800">
            {t('scholarship.docs.income.title')}
          </span>
          <p className="text-xs text-ground-500 mt-0.5">
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
                    ? 'bg-brand-fill text-brand-fill-ink border-primary-600'
                    : 'text-ground-600 border-ground-300 hover:border-primary-400'
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
              <div className="flex items-center justify-between text-sm text-ground-600">
                <span className="truncate">
                  <span className="text-ground-400 text-xs mr-1">
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
                    <span className="text-ground-400"> · {formatFileSize(d.size)}</span>
                  ) : null}
                </span>
                <button
                  onClick={() => onDelete(d.id)}
                  className="text-critical-600 hover:underline ml-2 shrink-0"
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