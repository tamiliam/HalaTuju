'use client'

/**
 * THE DOCUMENTS DRAWER — every document on file, grouped by the FACT it carries, with the
 * income route's compulsory slots drawn as Missing placeholders when nothing fills them.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import {
  groupDocumentsByFact,
  documentPill,
  documentFacts,
  utilityBillValues,
  schoolLeavingValues,
  incomeSubSections,
  docIconFor,
  earnerMemberFor,
  viewerKind,
  type FactStatus,
  type IncomeSlot,
} from '@/lib/officerCockpit'
import type { AdminScholarshipDetail, AdminApplicantDocument } from '@/lib/admin-api'
import type { ViewerDoc } from '@/components/DocViewer'

import type { T } from './shared'

export function DocumentsDrawer({ app, t, busy, setViewerDoc, doReRunVision }: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  setViewerDoc: (doc: ViewerDoc | null) => void
  doReRunVision: (docId: number) => void
}) {
  return (<>

      {/* ── Documents drawer — grouped by fact ────────────────────────────────── */}
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
        <div className="mb-3">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.docsDrawer.title')} ({app.documents.length})</h2>
          <p className="text-xs text-ground-400">{t('admin.scholarship.docsDrawer.subtitle')}</p>
        </div>
        {(() => {
          const groups = groupDocumentsByFact(app.documents)
          const sectionKeys = ['identity', 'academic', 'pathway', 'income', 'additional', 'other'] as const
          const pillClass = (p: 'verified' | 'check' | 'unread') => {
            if (p === 'verified') return 'bg-positive-100 text-positive-700'
            if (p === 'check') return 'bg-caution-100 text-caution-700'
            return 'bg-ground-100 text-ground-500'
          }
          // The doc-type icon sits in a badge tinted by the SAME verdict as the pill.
          const iconBadge = (p: 'verified' | 'check' | 'unread') =>
            p === 'verified' ? 'bg-positive-50' : p === 'check' ? 'bg-caution-50' : 'bg-ground-100'
          const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
          // Standard, student-independent label per doc type (the actual filename is shown
          // muted in brackets below). parent_ic → "Mother's IC" etc. when the earner is known.
          const TYPE_KEYS = new Set(['ic', 'parent_ic', 'results_slip', 'offer_letter', 'str',
            'salary_slip', 'epf', 'income_support_doc', 'school_leaving_cert', 'semester_result',
            'water_bill', 'electricity_bill', 'birth_certificate', 'guardianship_letter',
            'statement_of_intent', 'photo', 'bank_statement', 'other'])
          // Income-earner docs are person-qualified from their slot ("Mother's STR proof",
          // "Father's salary slip"); the IC keeps its own possessive ("Mother's IC").
          // `income_support_doc` is here because it is that earner's INCOME EVIDENCE (2026-07-25's
          // fourth way), so it must read "Mother's income letter" like her payslip would — not a
          // bare type name that gives no clue whose income it proves.
          const INCOME_MEMBER_DOCS = new Set(['parent_ic', 'str', 'salary_slip', 'epf',
                                              'income_support_doc'])
          const docLabel = (d: AdminApplicantDocument) => {
            if (INCOME_MEMBER_DOCS.has(d.doc_type)) {
              const m = earnerMemberFor(d.doc_type, d.household_member || '',
                app.income_route || '', app.income_earner || '')
              const base = t(`admin.scholarship.docsDrawer.type.${d.doc_type}`)
              if (!m) return base
              const member = t(`scholarship.docs.income.wizard.member.${m}`)
              return d.doc_type === 'parent_ic'
                ? t('admin.scholarship.docsDrawer.parentIcOf', { member })
                : t('admin.scholarship.docsDrawer.ofMember', { member, doc: base })
            }
            return TYPE_KEYS.has(d.doc_type)
              ? t(`admin.scholarship.docsDrawer.type.${d.doc_type}`)
              : (d.original_filename || d.doc_type)
          }
          // Open the document in the in-cockpit viewer (embedded, never a download).
          const openViewer = (d: AdminApplicantDocument) => {
            if (!d.download_url) return
            setViewerDoc({
              label: docLabel(d), filename: d.original_filename || '', url: d.download_url,
              kind: viewerKind(d.content_type || '', d.original_filename || ''),
            })
          }
          const factClass = (s: FactStatus) =>
            s === 'verified' ? 'text-positive-700' : s === 'partial' ? 'text-caution-700'
              : s === 'not' ? 'text-critical-600' : 'text-ground-400'
          const subLabel = 'text-[10px] font-semibold uppercase tracking-widest text-ground-400 mb-1.5'
          // Line 2: the coloured fact-labels — only the facts THIS document provides. A results slip
          // also surfaces the SPM exam YEAR, an offer letter its intake (course-start) YEAR — coloured
          // by currency vs the cohort (green = current, amber = off), so the officer sees at a glance
          // whether the slip/offer belongs to this round.
          const yearChip = (d: AdminApplicantDocument): { text: string; status: string } | null => {
            if (d.doc_type === 'results_slip' && d.academic_check?.exam_year)
              return { text: t('admin.scholarship.docsDrawer.examYear', { year: d.academic_check.exam_year }),
                       status: d.academic_check.exam_year_status || '' }
            if (d.doc_type === 'offer_letter' && d.pathway_check?.intake_year)
              return { text: t('admin.scholarship.docsDrawer.intakeYear', { year: d.pathway_check.intake_year }),
                       status: d.pathway_check.intake_year_status || '' }
            return null
          }
          const yearClass = (s: string) =>
            s === 'current' ? 'text-positive-700' : s === 'off' ? 'text-caution-700' : 'text-ground-500'
          const factLine = (d: AdminApplicantDocument) => {
            const facts = documentFacts(d)
            const yc = yearChip(d)
            if (facts.length === 0 && !yc) return null
            return (
              <p className="mt-0.5 flex flex-wrap items-center text-[11px]">
                {facts.map((f, i) => (
                  <span key={`${f.key}-${i}`} className="flex items-center">
                    {i > 0 && <span className="text-ground-300 mx-1.5">·</span>}
                    <span className={`font-medium ${factClass(f.status)}`}>
                      {t(`admin.scholarship.docsDrawer.fact.${f.key}`)}
                    </span>
                  </span>
                ))}
                {yc && (
                  <span className="flex items-center">
                    {facts.length > 0 && <span className="text-ground-300 mx-1.5">·</span>}
                    <span className={`font-medium ${yearClass(yc.status)}`}>{yc.text}</span>
                  </span>
                )}
              </p>
            )
          }
          // Placeholder label for a missing compulsory income doc (+ the member, salary route).
          const slotLabel = (docType: string, member: string) => {
            const base = t(`admin.scholarship.docsDrawer.type.${docType}`)
            if (!member) return base
            const m = t(`scholarship.docs.income.wizard.member.${member}`)
            return docType === 'parent_ic'
              ? t('admin.scholarship.docsDrawer.parentIcOf', { member: m })
              : t('admin.scholarship.docsDrawer.ofMember', { member: m, doc: base })
          }
          // `unusable` (TD-262) is a SERVED reason code: this document was offered as an earner's
          // income evidence and cannot carry it. The row still shows — the officer must see what
          // the family sent — with a red "not usable" line naming why, and the Missing row beside.
          const docRow = (d: AdminApplicantDocument, unusable = '') => {
            const p = documentPill(d)
            return (
              <li key={d.id} className="flex items-start gap-2 rounded-lg border border-ground-100 p-2.5 hover:bg-ground-50">
                <span className={`shrink-0 mt-0.5 flex h-7 w-7 items-center justify-center rounded-md text-sm ${iconBadge(p)}`} aria-hidden>
                  {docIconFor(d.doc_type)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {d.download_url ? (
                      <button type="button" onClick={() => openViewer(d)}
                        title={t('admin.scholarship.docsDrawer.view')}
                        className="text-left text-sm font-medium text-ground-800 hover:text-primary-600 hover:underline truncate max-w-[200px]">
                        {docLabel(d)} <span aria-hidden className="text-[10px] text-ground-400">↗</span>
                      </button>
                    ) : (
                      <span className="text-sm font-medium text-ground-800 truncate max-w-[200px]">
                        {docLabel(d)}
                      </span>
                    )}
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${pillClass(p)}`}>
                      {t(`admin.scholarship.docsDrawer.pill.${p}`)}
                    </span>
                    {/* Capture confidence: read deterministically (fixed labels) or by AI? Shown on
                        every read doc — field-extracted docs AND the identity ICs (read via the MyKad
                        OCR path). The stored `capture` tag wins; when absent (older extractions) the
                        default is doc-type-aware: an IC/parent_ic is deterministic Vision OCR → 'Exact',
                        everything else → 'AI' (the safe "please verify" label). So no read doc is ever
                        unlabelled, and a later Re-run stamps the precise tag. */}
                    {(d.vision_fields?.fields || d.doc_type === 'ic' || d.doc_type === 'parent_ic') && (() => {
                      const stored = d.vision_fields?.capture
                      // The stored tag always wins. When absent (older extractions), default by the
                      // doc type's PRIMARY read method: the deterministic-first types (a label/positional
                      // parser runs before any Gemini fallback) default to 'Exact'; the rest — read by
                      // Gemini — default to 'AI'. A Re-run stamps the precise tag either way.
                      const DETERMINISTIC_FIRST = ['ic', 'parent_ic', 'results_slip', 'birth_certificate', 'str', 'epf', 'school_leaving_cert']
                      const cap = stored === 'deterministic' ? 'deterministic'
                        : stored === 'ai' ? 'ai'
                        : DETERMINISTIC_FIRST.includes(d.doc_type) ? 'deterministic' : 'ai'
                      return (
                        <span
                          title={t(`admin.scholarship.docsDrawer.capture.${cap}.hint`)}
                          className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                            cap === 'deterministic'
                              // A CATEGORY: how the value was produced — read deterministically, or
                              // derived by a model. Two kinds, so the neutral one keeps the ground
                              // and the other takes one swatch. Not a tone: "a model read this" is
                              // neither good news nor a warning, it is a provenance.
                              ? 'bg-ground-100 text-ground-500'
                              : 'bg-category-1-surface text-category-1-ink'}`}>
                          {t(`admin.scholarship.docsDrawer.capture.${cap}.label`)}
                        </span>
                      )
                    })()}
                  </div>
                  {d.original_filename && (
                    <p className="text-[11px] text-ground-400 truncate max-w-[230px]" title={d.original_filename}>
                      ({trunc(d.original_filename, 30)})
                    </p>
                  )}
                  {factLine(d)}
                  {unusable && (
                    <p className="text-[11px] font-medium text-critical-600 mt-0.5">
                      {t('admin.scholarship.docsDrawer.notUsable.label')}
                      {' — '}
                      {t(`admin.scholarship.docsDrawer.notUsable.reason.${unusable}`)}
                    </p>
                  )}
                  {/* Key values FIRST (directly under the facts), so every note falls below them —
                      consistent for both water and electricity. */}
                  {(() => {
                    const vals = utilityBillValues(d)
                    return vals.length > 0 ? (
                      <p className="text-[11px] text-ground-500 mt-0.5">
                        {vals.map((v, i) => (
                          <span key={v.labelKey}>
                            {i > 0 && <span className="text-ground-300"> · </span>}
                            <span className="text-ground-400">{t(`admin.scholarship.docsDrawer.billValue.${v.labelKey}`)} </span>
                            {v.value ?? t(`admin.scholarship.docsDrawer.billValue.${v.valueKey}`)}
                          </span>
                        ))}
                      </p>
                    ) : null
                  })()}
                  {/* School-leaving cert values (owner 2026-07-15): the school name, the conduct
                      rating, and the co-curricular / leadership notes — under the School/Name/IC/
                      Behaviour chips. */}
                  {(() => {
                    const vals = schoolLeavingValues(d)
                    return vals.length > 0 ? (
                      <p className="text-[11px] text-ground-500 mt-0.5">
                        {vals.map((v, i) => (
                          <span key={v.labelKey}>
                            {i > 0 && <span className="text-ground-300"> · </span>}
                            <span className="text-ground-400">{t(`admin.scholarship.docsDrawer.certValue.${v.labelKey}`)} </span>
                            {v.value}
                          </span>
                        ))}
                      </p>
                    ) : null
                  })()}
                  {/* CRITICAL, not caution. The generic vision warnings two blocks below are
                      `caution-600`; "this bill is in an unrelated person's name" is a different
                      order of thing — it is evidence the document may not belong to this household
                      at all. Orange used to hold them apart; sharing `caution` would have
                      flattened the distinction an officer most needs to see. */}
                  {d.utility_check?.name_note === 'unrelated' && (
                    <p className="text-[11px] text-critical-600 mt-0.5">
                      {t('admin.scholarship.docsDrawer.utilityNote.unrelated', { name: d.utility_check.name })}
                    </p>
                  )}
                  {(d.utility_check?.reasonable_detail === 'water_only'
                    || d.utility_check?.reasonable_detail === 'electricity_only') && (
                    <p className="text-[11px] text-ground-400 mt-0.5">
                      {t(`admin.scholarship.docsDrawer.utilityNote.${d.utility_check.reasonable_detail}`)}
                    </p>
                  )}
                  {d.vision_fields?.warnings && d.vision_fields.warnings.length > 0 && (
                    <p className="text-[11px] text-caution-700 mt-0.5">{d.vision_fields.warnings.join('; ')}</p>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-0.5 mt-0.5">
                  <button onClick={() => doReRunVision(d.id)} disabled={busy === 'vision'}
                    className="text-[11px] text-ground-500 hover:text-ground-700 hover:underline disabled:opacity-50">
                    {busy === 'vision' ? t('common.loading') : t('admin.scholarship.docsDrawer.rerun')}
                  </button>
                </div>
              </li>
            )
          }
          const placeholderRow = (s: IncomeSlot) => (
            <li key={`ph-${s.docType}-${s.member}`}
              className="flex items-center gap-2 rounded-lg border border-dashed border-ground-200 p-2.5">
              <span className="shrink-0 text-ground-300 text-base" aria-hidden>
                {s.docType === 'parent_ic' ? '🪪' : '📄'}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-ground-500">{slotLabel(s.docType, s.member)}</span>
                <span className="text-[11px] text-ground-400"> — {t('admin.scholarship.docsDrawer.notUploaded')}</span>
              </div>
              <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold bg-critical-100 text-critical-600">
                {t('admin.scholarship.docsDrawer.pill.missing')}
              </span>
            </li>
          )
          return (
            // Fixed-height, scrollable: a long document list (11+) no longer pushes the
            // rest of the cockpit down — the header stays put and the groups scroll.
            <div className="space-y-4 max-h-[28rem] overflow-y-auto pr-1">
              {sectionKeys.map((key) => {
                const docs = groups[key]
                if (key === 'income') {
                  // Income splits into STR ROUTE / SALARY ROUTE / UTILITY sub-sections. STR is
                  // shown only on the STR route with an STR doc; SALARY + UTILITY always (when
                  // they have content). A missing compulsory slot renders a "Missing" placeholder.
                  const sub = incomeSubSections(app, docs)
                  const subHead = 'text-[9px] font-semibold uppercase tracking-wider text-ground-300 mb-1 mt-2'
                  const subSection = (headKey: string, slots: IncomeSlot[]) => (
                    slots.length === 0 ? null : (
                      <div key={headKey}>
                        <p className={subHead}>{t(`admin.scholarship.docsDrawer.group.${headKey}`)}</p>
                        <ul className="space-y-1.5">
                          {slots.map((s) => (s.doc ? docRow(s.doc, s.unusable) : placeholderRow(s)))}
                        </ul>
                      </div>
                    )
                  )
                  if (docs.length === 0 && !sub.str && sub.salary.length === 0 && sub.utility.length === 0) return null
                  return (
                    <div key={key}>
                      <p className={subLabel}>{t('admin.scholarship.docsDrawer.group.income')}</p>
                      {sub.str && subSection('incomeStr', sub.str)}
                      {subSection('incomeSalary', sub.salary)}
                      {subSection('incomeUtility', sub.utility)}
                    </div>
                  )
                }
                if (docs.length === 0) return null
                return (
                  <div key={key}>
                    <p className={subLabel}>{t(`admin.scholarship.docsDrawer.group.${key}`)}</p>
                    <ul className="space-y-1.5">{docs.map((d) => docRow(d))}</ul>
                  </div>
                )
              })}
              {/* Phase 2: replaced documents — version history, muted, kept out of every fact
                  group so a superseded doc never reads as a live verification input. */}
              {groups.superseded.length > 0 && (
                <div key="superseded" className="pt-2 mt-2 border-t border-ground-100">
                  <p className={subLabel}>{t('admin.scholarship.docsDrawer.group.superseded')}</p>
                  <ul className="space-y-1.5 opacity-60">{groups.superseded.map((d) => docRow(d))}</ul>
                </div>
              )}
              {app.documents.length === 0 && (
                <p className="text-sm text-ground-400">{t('admin.scholarship.none')}</p>
              )}
            </div>
          )
        })()}
      </div>

  </>)
}
