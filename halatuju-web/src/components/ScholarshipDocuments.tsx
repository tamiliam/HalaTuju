'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
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
  COMPULSORY_DOC_TYPES,
  INCOME_PROOF_TYPES,
  OTHER_OPTIONAL_DOC_TYPES,
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

function visionChipVariant(doc: ApplicantDocument): 'good' | 'name-soft' | 'nric-bad' | 'unreadable' | null {
  if (!doc.vision_run_at) return null
  const nv = doc.vision_nric_verdict
  const mv = doc.vision_name_verdict
  if (nv === 'unreadable' || mv === 'unreadable') return 'unreadable'
  if (nv === 'mismatch') return 'nric-bad'
  if (mv === 'mismatch') return 'name-soft'
  if (nv === 'match') return 'good'   // mv is 'match' or 'partial' — both fine
  return null
}

/** Render text containing a single `<link>…</link>` marker as a /profile link.
 *  Falls back to plain text if the marker is absent (defensive against
 *  translations that lose the tag). */
function renderWithProfileLink(text: string) {
  const m = text.match(/^([\s\S]*?)<link>([\s\S]*?)<\/link>([\s\S]*)$/)
  if (!m) return text
  const [, before, linkText, after] = m
  return (
    <>
      {before}
      <Link href="/profile" className="font-semibold underline hover:no-underline">
        {linkText}
      </Link>
      {after}
    </>
  )
}

function VisionChip({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const variant = visionChipVariant(doc)
  if (!variant) return null
  const palette: Record<string, string> = {
    good: 'bg-green-50 text-green-800 ring-green-200',
    'name-soft': 'bg-amber-50 text-amber-800 ring-amber-200',
    'nric-bad': 'bg-amber-50 text-amber-800 ring-amber-200',
    unreadable: 'bg-gray-50 text-gray-700 ring-gray-200',
  }
  const icon = variant === 'good' ? '✓' : variant === 'unreadable' ? 'ⓘ' : '⚠'
  const text = t(`scholarship.docs.vision.${variant}`)
  return (
    <div className="mt-2">
      <span className={`inline-flex items-start gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 ${palette[variant]}`}>
        <span aria-hidden>{icon}</span>
        <span>{variant === 'name-soft' ? renderWithProfileLink(text) : text}</span>
      </span>
      <p className="mt-1 text-xs text-gray-400">{t('scholarship.docs.vision.note')}</p>
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
          <VisionChip doc={visionDoc} t={t} />
          <DocumentHelpCoach doc={visionDoc} token={token} t={t} lang={lang} />
        </>
      )}
      {existing.filter((d) => d !== visionDoc).map((d) => (
        <div key={`m${d.id}`}>
          <SupportingDocChip doc={d} t={t} />
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

  return (
    <div className="space-y-5">

      {/* ── Required ──────────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
            {t('scholarship.docs.requiredPill')}
          </span>
          <span className="text-xs text-gray-500">
            {t('scholarship.docs.requiredNote')}
          </span>
        </div>
        <div className="space-y-3">
          {COMPULSORY_DOC_TYPES.map((dt) => (
            <SingleDocCard
              key={dt}
              docType={dt}
              docs={docs}
              busyType={busyType}
              onUpload={handleUpload}
              onDelete={handleDelete}
              t={t}
              token={token}
              lang={locale}
              showVisionChip={dt === 'ic'}
            />
          ))}
          {/* S22: parent/guardian IC is now required for EVERYONE (not just
              minors). The admin uses it to cross-check supporting docs like
              STR or EPF — those are usually issued in a parent's name, and
              comparing the IC name + NRIC catches mismatches that would
              otherwise sneak past. Vision OCR runs on upload (same pipeline
              as the student's IC). */}
          <SingleDocCard
            key="parent_ic"
            docType="parent_ic"
            docs={docs}
            busyType={busyType}
            onUpload={handleUpload}
            onDelete={handleDelete}
            t={t}
            token={token}
            lang={locale}
            showVisionChip={false}
          />
          {/* S23: proof of household income is now required (any one of
              STR / salary slip / EPF satisfies it). STR families are
              encouraged in the card explainer to ALSO upload salary/EPF
              for each working household member, but one is enough to
              pass completeness. */}
          <IncomeProofCard
            docs={docs}
            busyType={busyType}
            onUpload={handleUpload}
            onDelete={handleDelete}
            t={t}
            token={token}
            lang={locale}
          />
        </div>
      </section>

      {/* ── Optional ──────────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
            {t('scholarship.docs.optionalPill')}
          </span>
          <span className="text-xs text-gray-500">
            {t('scholarship.docs.optionalNote')}
          </span>
        </div>
        <div className="space-y-3">
          {OTHER_OPTIONAL_DOC_TYPES.map((dt) => (
            <SingleDocCard
              key={dt}
              docType={dt}
              docs={docs}
              busyType={busyType}
              onUpload={handleUpload}
              onDelete={handleDelete}
              t={t}
              token={token}
              lang={locale}
            />
          ))}
          {/* S17: minors with a non-parent guardian (grandparent / legal
              guardian / older sibling / other relative) must also upload
              this. Shown as optional here because the relationship is only
              picked on the Consent step; the consent POST blocks if missing. */}
          {isMinor && (
            <SingleDocCard
              key="guardianship_letter"
              docType="guardianship_letter"
              docs={docs}
              busyType={busyType}
              onUpload={handleUpload}
              onDelete={handleDelete}
              t={t}
              token={token}
              lang={locale}
            />
          )}
        </div>
      </section>

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}
