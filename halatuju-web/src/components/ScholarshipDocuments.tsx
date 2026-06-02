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
  type ApplicantDocument,
} from '@/lib/api'
import {
  INCOME_PROOF_TYPES,
  formatFileSize,
} from '@/lib/scholarship'
import DocumentHelpCoach from './DocumentHelpCoach'

// Per-file size cap (mirrors the server's MAX_DOC_SIZE_BYTES default — server is
// authoritative; this gives the student instant feedback before any upload).
const MAX_DOC_SIZE_BYTES = 8 * 1024 * 1024

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

// ── Results-slip clinical 3-check (Check-1 Academic) ─────────────────────
// Mirrors the IC checklist: three rows the student can read at a glance —
// Name · Subjects · Results — each with what we read + a pass/fail badge, plus
// the exam (year) as a soft data point. Cikgu Gopal (below) gives the specific
// "what to do" only when there's a real problem.

type SlipStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'pending'

function slipBadgeKind(s: SlipStatus): ICCheckKind {
  if (s === 'match') return 'match'
  if (s === 'partial') return 'partial'
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

type PathStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'pending'

function pathBadgeKind(s: PathStatus): ICCheckKind {
  if (s === 'match') return 'match'
  if (s === 'partial') return 'partial'
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

  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50/60 px-3 divide-y divide-gray-100">
      {row(t('scholarship.docs.pathwayCheck.name'), chk.candidate_name, badge(chk.name))}
      {row(t('scholarship.docs.pathwayCheck.ic'), chk.candidate_nric, badge(chk.ic))}
      {dataRow('programme', chk.programme)}
      {dataRow('institution', chk.institution)}
      {dataRow('issuer', chk.issuer)}
      {dataRow('date', chk.offer_date || chk.intake)}
      {dataRow('address', chk.address)}
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
}: {
  docType: string
  docs: ApplicantDocument[]
  busyType: string | null
  onUpload: (docType: string, file: File) => void
  onDelete: (id: number) => void
  t: (key: string) => string
  token: string | null
  lang: string
  showVisionChip?: boolean
}) {
  const busy = busyType === docType
  const existing = docs.filter((d) => d.doc_type === docType)
  const visionDoc = showVisionChip ? existing.find((d) => d.vision_run_at) : null

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-gray-800">
            {t(`scholarship.docs.type.${docType}`)}
          </span>
          <p className="text-xs text-gray-500 mt-0.5">
            {t(`scholarship.docs.help.${docType}`)}
          </p>
        </div>
        <UploadTrigger
          docType={docType}
          busy={busy}
          onUpload={onUpload}
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

export default function ScholarshipDocuments({ token, onChange }: { token: string | null; onChange?: () => void }) {
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

  const handleUpload = async (docType: string, file: File) => {
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
    setBusyType(docType)
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(docType, { token })
      await uploadFileToSignedUrl(upload_url, file)
      await recordDocument(
        { doc_type: docType, storage_path, original_filename: file.name, content_type: file.type, size: file.size },
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
  const card = (docType: string, extra: { showVisionChip?: boolean } = {}) => (
    <SingleDocCard
      key={docType}
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
  const sectionHead = (key: string, pill: SectionPill) => (
    <div className="mb-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-800">
          {t(`scholarship.docs.section.${key}.title`)}
        </h3>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${pillClass[pill]}`}>
          {t(`scholarship.docs.pill.${pill}`)}
        </span>
      </div>
      <p className="text-xs text-gray-500 mt-0.5">{t(`scholarship.docs.section.${key}.note`)}</p>
    </div>
  )

  // Documents are grouped by the four verification facts (matching the officer's
  // verdict + Documents drawer) + an Other bucket:
  //   Identity (IC) · Academic (results slip) · Pathway (offer letter) ·
  //   Income (income proof + parent IC + utility bills) · Other (intent, photo).
  return (
    <div className="space-y-6">
      <section>
        {sectionHead('identity', 'compulsory')}
        <div className="space-y-3">{card('ic', { showVisionChip: true })}</div>
      </section>

      <section>
        {sectionHead('academic', 'compulsory')}
        <div className="space-y-3">{card('results_slip')}</div>
      </section>

      <section>
        {sectionHead('pathway', 'important')}
        <div className="space-y-3">{card('offer_letter')}</div>
      </section>

      <section>
        {sectionHead('income', 'compulsory')}
        <div className="space-y-3">
          {/* Any one of STR / salary slip / EPF satisfies the income requirement. */}
          <IncomeProofCard
            docs={docs}
            busyType={busyType}
            onUpload={handleUpload}
            onDelete={handleDelete}
            t={t}
            token={token}
            lang={locale}
          />
          {/* Parent/guardian IC — confirms the earner the income docs are issued to. */}
          {card('parent_ic', { showVisionChip: false })}
          {/* Utility bills — optional; they lend credibility to the income claim. */}
          {card('water_bill')}
          {card('electricity_bill')}
        </div>
      </section>

      <section>
        {sectionHead('other', 'optional')}
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
