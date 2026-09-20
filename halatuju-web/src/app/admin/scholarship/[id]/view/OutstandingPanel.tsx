'use client'

/**
 * CHECK 2 — OUTSTANDING: the student-facing tasks (queries + document requests), what they
 * answered, and the two controls that raise more work for them.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import { showsCheck2Box } from '@/lib/officerCockpit'
import { localiseParams, titleSourceFor } from '@/lib/actionCentre'
import type { AdminScholarshipDetail, AdminResolutionItem } from '@/lib/admin-api'

import { REQUEST_CATEGORIES, REQ_CAT, type T } from './shared'

export function OutstandingPanel({
  app, t, busy, canWrite, decisionReopened, queryingLocked, lockReason,
  infoNote, setInfoNote, doRaiseQuery, doActionResolution,
  reqCategory, reqQualifier, reqDocNote, setReqDocNote, reqResolved,
  onReqCategory, onReqQualifier, doRequestDoc,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  canWrite: boolean
  decisionReopened: boolean
  queryingLocked: boolean
  lockReason: 'interview' | 'closed' | null
  infoNote: string
  setInfoNote: Dispatch<SetStateAction<string>>
  doRaiseQuery: () => void
  doActionResolution: (itemId: number, action: 'waive' | 'resolve' | 'reopen') => void
  reqCategory: string
  reqQualifier: string
  reqDocNote: string
  setReqDocNote: Dispatch<SetStateAction<string>>
  reqResolved: { docType: string; member: string } | null
  onReqCategory: (key: string) => void
  onReqQualifier: (q: string) => void
  doRequestDoc: () => void
}) {
  return (<>

      {/* ── Check 2 — Outstanding: student-facing tasks only (queries + doc requests).
           Interview flags + AI gaps now live in the Interview Stage box below.
           Hidden on a CLOSED case with nothing in it — "all student tasks are clear" reads as an
           achievement, and on 43 records nothing was ever asked of the student at all. ─────── */}
      {showsCheck2Box({
        status: app.status, decisionReopened, hasItems: (app.resolution_items?.length ?? 0) > 0,
      }) && (
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.outstanding.title')}</h2>
            <p className="text-xs text-ground-500">{t('admin.scholarship.outstanding.subtitle')}</p>
          </div>
          {(() => {
            const n = app.resolution_items?.length ?? 0
            return n > 0 ? (
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-caution-100 text-caution-700">
                {n} {n === 1 ? t('admin.scholarship.outstanding.itemOne') : t('admin.scholarship.outstanding.itemMany')}
              </span>
            ) : null
          })()}
        </div>
        {/* The REASON, not just the fact: this line used to assert "the interview is concluded"
            on cases that never held one (the lock also fires on a terminal status). */}
        {queryingLocked && lockReason && (
          <p className="rounded-md bg-ground-100 px-3 py-2 text-xs text-ground-500">
            {t(lockReason === 'interview'
              ? 'admin.scholarship.outstanding.locked'
              : 'admin.scholarship.outstanding.lockedClosed')}
          </p>
        )}
        {/* V3 (#7): a higher-priority query crowded out by the clarify cap stays visible here,
            so a capped-out gap isn't silently dropped. */}
        {(app.query_sla?.clarify_overflow ?? 0) > 0 && (
          <p className="rounded-md bg-caution-50 px-3 py-2 text-xs text-caution-700">
            {t('admin.scholarship.outstanding.overflow', { n: String(app.query_sla.clarify_overflow) })}
          </p>
        )}
        {(() => {
          const caveats: AdminResolutionItem[] = app.resolution_items ?? []
          if (caveats.length === 0) {
            return <p className="text-sm text-ground-400 italic">{t('admin.scholarship.outstanding.empty')}</p>
          }
          return (
                  <ul className="space-y-2">
                    {caveats.map((item) => {
                      const answered = item.status === 'resolved'  // student answered; awaiting officer review
                      // Show the ACTUAL question the student was asked (same source as their
                      // Action Centre), not the internal caveat description.
                      const src = titleSourceFor(item)
                      const question = src.kind === 'raw'
                        ? (src.text || item.code)
                        : t(src.titleKey, localiseParams(item.params, t))
                      // The FULL instruction the STUDENT actually saw (auto items carry a detailed
                      // description; a manual request's raw `text` above already IS the full ask). Show
                      // it so the reviewer sees EXACTLY what was asked, next to the student's answer.
                      // Strip markdown emphasis (*…*) for a clean plain-text read; hide when there's no
                      // desc key (t() echoes the key path) or it just repeats the title.
                      let detail = ''
                      if (src.kind === 'i18n') {
                        const d = t(src.descKey, localiseParams(item.params, t))
                        if (d && d !== src.descKey && d !== question) {
                          detail = d.replace(/\*([^*]+)\*/g, '$1')
                        }
                      }
                      return (
                        <li key={item.id} className="flex items-start gap-2.5 rounded-lg border border-ground-100 bg-ground-50 p-3">
                          {answered ? (
                            <svg className="mt-0.5 h-5 w-5 shrink-0 text-positive-700" viewBox="0 0 20 20" fill="currentColor" aria-label="Answered">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                            </svg>
                          ) : (
                            <svg className="mt-0.5 h-5 w-5 shrink-0 text-caution-700" viewBox="0 0 20 20" fill="currentColor" aria-label="Awaiting student">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z" clipRule="evenodd" />
                            </svg>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-ground-800 break-words">
                              {/* A document request is a task ("Upload"), not a "Question" — label by kind. */}
                              <span className="font-semibold">{item.kind === 'doc' ? t('admin.scholarship.outstanding.uploadLabel') : t('admin.scholarship.outstanding.questionLabel')}:</span> {question}
                              {' '}
                              <span className="ml-0.5 rounded bg-ground-200 px-1.5 py-0.5 text-[11px] text-ground-500 align-middle">{item.fact}</span>
                              {' '}
                              <span className="rounded bg-ground-200 px-1.5 py-0.5 text-[11px] text-ground-500 align-middle">{item.kind}</span>
                              {/* Circuit-breaker (Phase 2/4): the student re-uploaded past the limit
                                  without a usable doc — the loop was stopped and their best copy kept
                                  live. A HOLD for a human, not an auto-resolve. */}
                              {item.params?.needs_officer_eye === true && (
                                <>
                                  {' '}
                                  <span
                                    title={t('admin.scholarship.outstanding.holdTip')}
                                    // A HOLD, filled — the same treatment `suspended` got in F4.
                                    // It is caution at weight, not a fifth hue: the loop was
                                    // stopped and a human has to look, so it should not read as a
                                    // quiet neighbour of the grey `kind` chip beside it.
                                    className="rounded bg-caution-fill px-1.5 py-0.5 text-[11px] font-semibold text-caution-fill-ink align-middle"
                                  >
                                    {t('admin.scholarship.outstanding.hold')}
                                  </span>
                                </>
                              )}
                            </p>
                            {detail && (
                              <p className="mt-1 text-xs text-ground-500 break-words">{detail}</p>
                            )}
                            {answered && item.resolution_text && (
                              <div className="mt-2 rounded-md border border-primary-100 bg-primary-50 p-2">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-700">
                                  {t('admin.scholarship.caveats.studentAnswer')}
                                </p>
                                <p className="mt-0.5 text-sm text-ground-800 break-words">{item.resolution_text}</p>
                              </div>
                            )}
                          </div>
                          {/* Answered items are auto-accepted (the Q&A is the record — no
                              officer action). Only an unanswered item offers Delete, for
                              the reviewer to drop an irrelevant / poorly-worded query so
                              they can raise a better one. */}
                          {canWrite && !queryingLocked && !answered && (
                            <div className="flex shrink-0">
                              <button
                                onClick={() => doActionResolution(item.id, 'waive')}
                                disabled={!!busy}
                                className="rounded border border-ground-300 px-2 py-1 text-xs text-ground-600 hover:border-critical-300 hover:bg-critical-50 hover:text-critical-700 disabled:opacity-50"
                              >
                                {t('admin.scholarship.caveats.delete')}
                              </button>
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
          )
        })()}
        {/* Raise work for the student — merged into the Check-2 box with a clear divider.
            Two roles: (1) raise a query, (2) request a document. Each adds a to-do to the
            student's Action Centre (they're notified there — no separate per-item email). */}
        {canWrite && !queryingLocked && (
          <div className="border-t border-ground-200 pt-3 mt-1 space-y-3">
            <p className="text-xs text-ground-500">{t('admin.scholarship.raiseSectionHint')}</p>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-ground-600">{t('admin.scholarship.raiseQueryTitle')}</p>
              <textarea name="infoNote" value={infoNote} rows={2} onChange={(e) => setInfoNote(e.target.value)}
                placeholder={t('admin.scholarship.raiseQueryPlaceholder')}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
              <button onClick={doRaiseQuery} disabled={!!busy || !infoNote.trim()}
                className="px-3 py-1.5 border border-primary-300 text-primary-700 rounded-lg text-sm disabled:opacity-50">
                {busy === 'raise' ? t('common.loading') : t('admin.scholarship.raiseQuerySend')}
              </button>
            </div>
            <div className="space-y-1.5 border-t border-ground-100 pt-3">
              <p className="text-xs font-medium text-ground-600">{t('admin.scholarship.requestDocTitle')}</p>
              {(() => {
                const cat = REQ_CAT.get(reqCategory)
                return (
              <div className="flex flex-wrap items-center gap-2">
                <select value={reqCategory} onChange={(e) => onReqCategory(e.target.value)}
                  className="border rounded-lg px-2 py-1.5 text-sm">
                  <option value="">{t('admin.scholarship.requestDocAny')}</option>
                  {REQUEST_CATEGORIES.map((c) => (
                    <option key={c.key} value={c.key}>{t(`admin.scholarship.requestCat.${c.key}`)}</option>
                  ))}
                </select>
                {/* Context-aware qualifier: "Whose?" (person) or "Which?" (sub-type). Required. */}
                {cat?.qualifier === 'whose' && (
                  <select value={reqQualifier} onChange={(e) => onReqQualifier(e.target.value)}
                    className="border rounded-lg px-2 py-1.5 text-sm">
                    <option value="">{t('admin.scholarship.requestDocWhose')}</option>
                    {cat.members!.map((m) => (
                      <option key={m} value={m}>{t(`scholarship.docs.income.wizard.member.${m}`)}</option>
                    ))}
                  </select>
                )}
                {cat?.qualifier === 'which' && (
                  <select value={reqQualifier} onChange={(e) => onReqQualifier(e.target.value)}
                    className="border rounded-lg px-2 py-1.5 text-sm">
                    <option value="">{t('admin.scholarship.requestDocWhich')}</option>
                    {cat.options!.map((o) => (
                      <option key={o.value} value={o.value}>{t(`admin.scholarship.requestWhich.${o.value}`)}</option>
                    ))}
                  </select>
                )}
              </div>
                )
              })()}
              {reqCategory && (
                <>
                  <textarea value={reqDocNote} rows={2} onChange={(e) => setReqDocNote(e.target.value)}
                    placeholder={t('admin.scholarship.requestDocNotePlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                  {/* Enabled ONLY once the request resolves (qualifier chosen where required); a
                      generic "Other" still needs a note describing exactly what's wanted. */}
                  <button onClick={doRequestDoc}
                    disabled={!!busy || !reqResolved || (reqResolved.docType === 'other' && !reqDocNote.trim())}
                    className="px-3 py-1.5 border border-primary-300 text-primary-700 rounded-lg text-sm disabled:opacity-50">
                    {busy === 'reqdoc' ? t('common.loading') : t('admin.scholarship.requestDocSend')}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
      )}

  </>)
}
