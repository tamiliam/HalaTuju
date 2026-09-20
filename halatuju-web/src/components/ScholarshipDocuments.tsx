'use client'

/**
 * THE STUDENT'S DOCUMENTS TAB.
 *
 * ⚠ MOST OF THIS FILE MOVED TO `./ScholarshipDocuments/` AT CODE HEALTH H14, AND NOTHING ELSE
 * HAPPENED TO IT. It was 1,914 lines; the per-document checklists and the card furniture are
 * three modules beside it and every moved line is the line it was. The FILE stayed at its own
 * path deliberately (H13's rule): every `@/components/ScholarshipDocuments` import in the
 * product still resolves here, and the oversize ledger's key still names a real file.
 *
 * ⚠ `IncomeWizard` MOVED OUT TOO (TD-272, 2026-09-20) — see `./ScholarshipDocuments/IncomeWizard`.
 * It could not move at H14: its two reasonless `react-hooks/exhaustive-deps` disables were
 * recorded in `code-standards.json` under THIS file's path, and a frozen ledger keyed on a path
 * has nowhere to put a suppression that lives INSIDE a moved body. The standard now lets a ledger
 * key follow its code — a DECLARED move, in the `_moved` array of `code-standards.json` — so the
 * two entries travelled with the wizard and bought nothing on the way.
 */
import { useState, useEffect, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  listDocuments,
  deleteDocument,
  getConsentStatus,
  type ApplicantDocument,
  type ScholarshipApplication,
} from '@/lib/api'
import { asksForDocument, documentRequirement } from '@/lib/scholarship'
import { limitsFrom, type ResolvedDocumentLimits } from '@/lib/documentLimits'

import {
  docKey,
  isAcceptedUpload,
  CollapsibleSection,
  SingleDocCard,
  IncomeProofCard,
} from './ScholarshipDocuments/cards'
import IncomeWizard from './ScholarshipDocuments/IncomeWizard'

// ── Main component ────────────────────────────────────────────────────────

export default function ScholarshipDocuments({ token, onChange, app }: { token: string | null; onChange?: () => void; app?: ScholarshipApplication | null }) {
  const { t, locale } = useT()
  const [docs, setDocs] = useState<ApplicantDocument[]>([])
  const [busyType, setBusyType] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // S17: minors get an additional Required card (parent_ic). is_minor is derived
  // backend-side from the profile's NRIC year and surfaced on the consent status
  // endpoint. The guardianship letter is now gated on the CONSENT relationship being a
  // NON-parent guardian (a father/mother consenting needs only their IC) and shown under
  // Income, not "Other" — see the income section below (#61: a father's family no longer
  // sees a needless guardian-letter slot).
  const [isMinor, setIsMinor] = useState(false)
  const [guardianRel, setGuardianRel] = useState('')
  // The organisation's upload limits, as SERVED with the document list — never a copy held
  // here (Org Config Sprint E). Starts at the platform default so the very first render, before
  // the list lands, still refuses an absurd file rather than letting it upload unchecked.
  const [limits, setLimits] = useState<ResolvedDocumentLimits>(() => limitsFrom(null))

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const r = await listDocuments({ token })
      setDocs(r.documents)
      setLimits(limitsFrom(r.limits))
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!token) return
    getConsentStatus({ token }).then((s) => {
      setIsMinor(!!s.is_minor)
      setGuardianRel(s.consents?.find((c) => c.is_active)?.guardian_relationship || '')
    }).catch(() => { /* ignore */ })
  }, [token])

  const handleUpload = async (docType: string, file: File, member = '') => {
    if (!token) return
    // Guardrail: per-file size cap — instant feedback, no wasted upload.
    if (file.size > limits.maxDocSizeBytes) {
      setError(t('scholarship.docs.file_too_large', { mb: String(limits.maxDocSizeMb) }))
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
        : code === 'file_too_large' ? t('scholarship.docs.file_too_large',
          // The server's OWN number on the refusal (a 400 body lands on `fieldErrors`),
          // so a stale served limit cannot make the message contradict the rejection.
          { mb: String((e as { fieldErrors?: { max_mb?: number } })?.fieldErrors?.max_mb
                       ?? limits.maxDocSizeMb) })
        : code === 'unsupported_format' ? t('scholarship.docs.unsupportedFormat')
        : code === 'upload_incomplete' ? t('scholarship.docs.uploadIncomplete')
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
  const card = (docType: string, extra: { showVisionChip?: boolean; required?: boolean; helpOverride?: string; titleOverride?: string; member?: string; legacyBlank?: boolean } = {}) => (
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
    compulsory: 'bg-caution-100 text-caution-800',
    important: 'bg-info-100 text-info-800',
    optional: 'bg-ground-100 text-ground-600',
  }
  // pill null → a bare section title (no badge, no note); the compulsory status is
  // shown on the cards themselves (a red * after the title).
  const sectionHead = (key: string, pill: SectionPill | null, showNote = false) => (
    <div className="mb-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-ground-800">
          {t(`scholarship.docs.section.${key}.title`)}
        </h3>
        {pill && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${pillClass[pill]}`}>
            {t(`scholarship.docs.pill.${pill}`)}
          </span>
        )}
      </div>
      {(pill || showNote) && <p className="text-xs text-ground-500 mt-0.5">{t(`scholarship.docs.section.${key}.note`)}</p>}
    </div>
  )

  // The guardianship letter belongs to the INCOME cluster (it proves a guardian earner's
  // link to the student). A minor whose consenting guardian is a NON-parent also needs it
  // for consent — surfaced here under Income, gated on that relationship, so a father's /
  // mother's family never sees a needless slot (#61). When the income earner already IS a
  // guardian, the wizard renders the letter itself — don't double it.
  const PARENT_RELATIONSHIPS = new Set(['father', 'mother'])
  const incomeUsesGuardian = app?.income_earner === 'guardian'
    || !!app?.income_working_members?.includes('guardian')
  const needsConsentGuardianLetter = isMinor && !!guardianRel
    && !PARENT_RELATIONSHIPS.has(guardianRel) && !incomeUsesGuardian

  // Documents are grouped by the four verification facts (matching the officer's
  // verdict + Documents drawer) + an Other bucket:
  //   Identity (IC) · Academic (results slip) · Pathway (offer letter) ·
  //   Income (income proof + parent IC + utility bills) · Other (cert, intent, photo).
  //
  // ⚠ WHICH of these appear, and which carry the compulsory marker, is the PROGRAMME'S answer —
  // read from the payload, never decided here (Layer 0, Sprint 3b). Until then this JSX was the
  // real source of truth for "what we ask for", spelling out `required: true` inline while a
  // separate constant in lib/scholarship.ts claimed a different, shorter list. Adding a literal
  // `required` back to any card below re-opens that gap.
  //
  // A section whose only document is switched off collapses out entirely: a heading over nothing
  // reads as a page that failed to load.
  const req = app?.requirements
  const docState = (dt: string) => documentRequirement(req, dt)
  const section = (key: string, dt: string, extra: Record<string, unknown> = {}) => {
    const state = docState(dt)
    if (state === 'off') return null
    return (
      <section>
        {sectionHead(key, null)}
        <div className="space-y-3">{card(dt, { ...extra, required: state === 'required' })}</div>
      </section>
    )
  }
  // The Other bucket is a plain list, so it thins rather than disappears — unless every one of
  // its documents is off, in which case the collapsible would open onto nothing.
  const otherDocs = ['school_leaving_cert', 'statement_of_intent', 'photo']
    .filter((dt) => docState(dt) !== 'off')

  return (
    <div className="space-y-6">
      {section('identity', 'ic', { showVisionChip: true })}
      {section('academic', 'results_slip')}
      {section('pathway', 'offer_letter')}

      {/* `income_proof` is ONE switch over the whole household-income route engine — see
          requirements.DOCUMENT_AGGREGATES. Off means this programme does not means-test at all,
          so the wizard, its per-member clusters and the utility bills all go together. Letting an
          organisation keep "the father's IC" while dropping "his payslip" would produce an
          assessment nobody designed. */}
      {asksForDocument(req, 'income_proof') && (
      <section id="income-wizard" className="scroll-mt-6">
        {sectionHead('income', null)}
        {app ? (
          /* Guided wizard → dynamic checklist (Check-1 item 3). */
          <IncomeWizard app={app} token={token} t={t} onChange={onChange}
            docs={docs} lang={locale}
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
        {/* A minor with a NON-parent consenting guardian: the guardianship letter is an
            income-cluster relationship doc, shown here (not under "Other") and gated on
            that relationship. A father's/mother's family doesn't see it (#61). */}
        {needsConsentGuardianLetter && (
          <div className="space-y-3 mt-3">{card('guardianship_letter')}</div>
        )}
      </section>
      )}

      {otherDocs.length > 0 && (
      <section>
        {/* Additional documents are all optional — folded by default so they never read as a
            wall of extra tasks; the student opens it only if they have more to add. A programme
            MAY promote one to required; the card then carries the marker inside the fold. */}
        <CollapsibleSection
          tone="optional"
          title={t('scholarship.docs.section.other.title')}
          summary={t('scholarship.docs.section.other.note')}
          openLabel={t('scholarship.docs.add')}
          hideLabel={t('scholarship.docs.hide')}
        >
          <div className="space-y-3">
            {otherDocs.map((dt) => (
              <div key={dt}>{card(dt, { required: docState(dt) === 'required' })}</div>
            ))}
          </div>
        </CollapsibleSection>
      </section>
      )}

      {error && <p className="text-critical-600 text-sm">{error}</p>}
    </div>
  )
}
