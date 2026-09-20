'use client'

/**
 * THE REFEREES PANEL (behind `SHOW_REFEREES`) and THE INTERVIEW STAGE — the agenda, the
 * reviewer's findings, and the read-only record once the interview is submitted.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was. The
 * two are one module because the interview-scheduling card sits BETWEEN them on screen and
 * stays in the cockpit, so neither range could swallow the other.
 */
import type { Dispatch, SetStateAction } from 'react'
import { formatPhone } from '@/lib/scholarship'
import { showsInterviewStage } from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import { SHOW_REFEREES, type T, type AgendaItem, type Findings, type RefereeForm } from './shared'

export function RefereesPanel({
  app, t, busy, refForm, setRefForm, doAddReferee, doDeleteReferee,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  refForm: RefereeForm
  setRefForm: Dispatch<SetStateAction<RefereeForm>>
  doAddReferee: () => void
  doDeleteReferee: (refId: number) => void
}) {
  return (<>

      {/* ── Referees (consent panel removed — the consent RECORD + sponsor-share gating
           stay untouched; only the cockpit status line is gone). Behind SHOW_REFEREES. ── */}
      {SHOW_REFEREES && (
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
        <h3 className="font-semibold text-sm mb-1">{t('admin.scholarship.referees')}</h3>
        <p className="text-xs text-ground-400 mb-2">{t('admin.scholarship.refHint')}</p>
        <ul className="text-sm text-ground-600 space-y-1">
          {app.referees.map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-2">
              <span>
                {r.name}{r.role ? ` (${r.role})` : ''}{r.relationship ? ` · ${r.relationship}` : ''}
                {r.phone ? ` — ${r.phone}` : ''}{r.email ? ` · ${r.email}` : ''}
              </span>
              <button onClick={() => doDeleteReferee(r.id)} disabled={!!busy}
                className="text-critical-600 hover:underline text-xs shrink-0 disabled:opacity-50">
                {t('admin.scholarship.refRemove')}
              </button>
            </li>
          ))}
          {app.referees.length === 0 && <li className="text-ground-400">{t('admin.scholarship.none')}</li>}
        </ul>
        {/* Add referee (coordinator records it at verify-&-accept) */}
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input value={refForm.name} onChange={(e) => setRefForm((f) => ({ ...f, name: e.target.value }))}
            placeholder={t('admin.scholarship.refName')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.role} onChange={(e) => setRefForm((f) => ({ ...f, role: e.target.value }))}
            placeholder={t('admin.scholarship.refRole')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.relationship} onChange={(e) => setRefForm((f) => ({ ...f, relationship: e.target.value }))}
            placeholder={t('admin.scholarship.refRelationship')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.phone} onChange={(e) => setRefForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))}
            placeholder={t('admin.scholarship.refPhone')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.email} onChange={(e) => setRefForm((f) => ({ ...f, email: e.target.value }))}
            placeholder={t('admin.scholarship.refEmail')} className="border rounded-lg px-2 py-1 text-sm sm:col-span-2" />
        </div>
        <button onClick={doAddReferee} disabled={!!busy || !refForm.name.trim()}
          className="mt-2 px-3 py-1.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm disabled:opacity-50">
          {busy === 'ref' ? t('admin.scholarship.refAdding') : t('admin.scholarship.refAdd')}
        </button>
      </div>
      )}

  </>)
}


export function InterviewStage({
  app, t, busy, canWrite, decisionReopened, decisionRecorded, interviewLocked, interviewMsg,
  agendaItems, editableAgenda, findings, setFindings, note, setNote,
  doSuggestGaps, doReopenInterview, doDeleteAgendaItem, doSaveInterview, doSubmitInterview,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  canWrite: boolean
  decisionReopened: boolean
  decisionRecorded: boolean
  interviewLocked: boolean
  interviewMsg: string
  agendaItems: AgendaItem[]
  editableAgenda: AgendaItem[]
  findings: Findings
  setFindings: Dispatch<SetStateAction<Findings>>
  note: string
  setNote: Dispatch<SetStateAction<string>>
  doSuggestGaps: () => void
  doReopenInterview: () => void
  doDeleteAgendaItem: (code: string) => void
  doSaveInterview: () => void
  doSubmitInterview: () => void
}) {
  return (<>

      {/* Phase C: interview capture */}
      {/* Hidden at shortlisted (pre-submission): no interview can exist pre-submission.
          Hidden on a CLOSED case that never held one: the controls here (gap suggestion — a
          billable call — Save draft, Submit findings) would write into a file nobody can act on. */}
      {showsInterviewStage({
        status: app.status, decisionReopened, hasInterviewSession: !!app.interview_session,
      }) && (
      <div id="interview-section" className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.interview.title')}</h2>
          </div>
          {interviewLocked
            ? (canWrite && !decisionRecorded && (
                /* Reviewer reopens a submitted interview to add a forgotten finding — un-submits
                   (reopens this box AND Check 2; Approve/Decline switch off until re-submitted).
                   Post-decision, the Decision panel's Reopen is used instead. */
                <button onClick={doReopenInterview} disabled={!!busy}
                  className="rounded-lg border border-ground-300 px-2.5 py-1 text-xs text-ground-600 hover:bg-ground-100 disabled:opacity-50">
                  {busy === 'ivreopen' ? t('common.loading') : t('admin.scholarship.interview.reopen')}
                </button>
              ))
            : (canWrite && (
                <button onClick={doSuggestGaps} disabled={!!busy}
                  className="px-2.5 py-1 rounded-lg text-xs bg-brand-fill text-brand-fill-ink disabled:opacity-50">
                  {busy === 'gaps' ? t('admin.scholarship.gaps.running')
                    : (app.interview_gaps?.length ?? 0) > 0 ? t('admin.scholarship.gaps.more')
                    : t('admin.scholarship.gaps.button')}
                </button>
              ))}
        </div>

        {/* S4: the sponsor's interviewer guide — the three "what we need to know" buckets +
            their key probes, as a collapsible reference. The AI gaps above target whichever
            buckets the record leaves unanswered; this is the human checklist behind them. */}
        {canWrite && !interviewLocked && (
          <details className="rounded-lg border border-ground-100 bg-ground-50/60 p-3">
            <summary className="cursor-pointer text-xs font-medium text-ground-600">
              {t('admin.scholarship.interviewGuide.title')}
            </summary>
            <div className="mt-2 space-y-2">
              {(['academic', 'financial', 'pathway'] as const).map((b) => (
                <div key={b}>
                  <p className="text-xs font-semibold text-ground-700">{t(`admin.scholarship.interviewGuide.${b}.title`)}</p>
                  <ul className="ml-4 list-disc text-[11px] text-ground-500">
                    {[0, 1, 2].map((i) => {
                      const key = `admin.scholarship.interviewGuide.${b}.q${i}`
                      const txt = t(key)
                      return txt === key ? null : <li key={i}>{txt}</li>
                    })}
                  </ul>
                </div>
              ))}
              <p className="text-[11px] text-ground-400">{t('admin.scholarship.interviewGuide.note')}</p>
            </div>
          </details>
        )}

        {interviewLocked ? (
          /* Submitted → read-only record (Check-2 style blue boxes). Questions with no
             answer are dropped; the open-ended findings show in their own box. */
          (() => {
            const answered = agendaItems.filter((it) => {
              const f = findings[it.code]
              return f && f.verdict !== 'deleted' && ((f.rationale || '').trim() || f.verdict === 'resolved')
            })
            const hasNote = (note || '').trim().length > 0
            if (answered.length === 0 && !hasNote) {
              return <p className="text-sm text-ground-400 italic">{t('admin.scholarship.interview.noneRecorded')}</p>
            }
            return (
              <div className="space-y-3">
                {/* Q&A organised like Check 2: ✓ tick · bold "Question:" · the finding under
                    a "Reviewer's finding" header (the label sits ABOVE the box, not inside). */}
                {answered.map((it) => {
                  const f = findings[it.code]
                  return (
                    <div key={it.code} className="flex items-start gap-2.5 rounded-lg border border-ground-100 bg-ground-50 p-3">
                      <svg className="mt-0.5 h-5 w-5 shrink-0 text-positive-700" viewBox="0 0 20 20" fill="currentColor" aria-label="Answered">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                      </svg>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-ground-800 break-words">
                          <span className="font-semibold">{t('admin.scholarship.outstanding.questionLabel')}:</span> {it.label}
                          {it.ai && <span className="ml-1 rounded bg-brand-fill px-1.5 py-0.5 text-[10px] font-semibold text-brand-fill-ink align-middle">{t('admin.scholarship.gaps.aiBadge')}</span>}
                        </p>
                        <p className="mt-1.5 text-xs font-medium text-ground-600">{t('admin.scholarship.interview.answerLabel')}</p>
                        <div className="mt-0.5 rounded-md border border-info-100 bg-info-50/50 p-2">
                          <p className="text-sm text-ground-800 break-words">
                            {(f.rationale || '').trim() || `${t('admin.scholarship.interview.verdict.resolved')} ✓`}
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                })}
                {hasNote && (
                  <div>
                    <p className="text-xs font-medium text-ground-600 mb-1">{t('admin.scholarship.interview.findingsLabel')}</p>
                    <div className="rounded-lg border border-info-100 bg-info-50/50 p-3">
                      <p className="whitespace-pre-line text-sm text-ground-800">{note}</p>
                    </div>
                  </div>
                )}
                {/* ⚠ WHO conducted it, not only when it was sent (TD-216). The name has always
                    been on the payload and was rendered nowhere, so an interview credited to the
                    wrong person looked exactly like one credited to the right person. */}
                {app.interview_session?.interviewer_name && (
                  <p className="text-[11px] text-ground-400">
                    {t('admin.scholarship.interview.interviewedBy')}{' '}
                    {app.interview_session.interviewer_name}
                  </p>
                )}
                {app.interview_session?.submitted_at && (
                  <p className="text-[11px] text-ground-400">
                    {t('admin.scholarship.interview.submittedOn')} {formatDate(app.interview_session.submitted_at)}
                  </p>
                )}
              </div>
            )
          })()
        ) : (
          <>
            <p className="text-xs text-ground-500">{t('admin.scholarship.interview.intro')}</p>
            {editableAgenda.length === 0 ? (
              <p className="text-sm text-ground-400 italic">{t('admin.scholarship.interview.noFlags')}</p>
            ) : (
              <ul className="space-y-3">
                {editableAgenda.map((it) => {
                  const f = findings[it.code] ?? { verdict: '', rationale: '' }
                  const setF = (patch: Partial<{ verdict: string; rationale: string }>) =>
                    setFindings((prev) => ({ ...prev, [it.code]: { ...f, ...patch } }))
                  const resolved = f.verdict === 'resolved'
                  return (
                    <li key={it.code} className="border rounded-lg p-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm text-ground-800 min-w-0">
                          {it.ai && <span className="mr-1 rounded bg-brand-fill px-1.5 py-0.5 text-[10px] font-semibold text-brand-fill-ink align-middle">{t('admin.scholarship.gaps.aiBadge')}</span>}
                          {it.label}
                        </p>
                        {canWrite && (
                          <div className="flex shrink-0 gap-1.5">
                            <button onClick={() => doDeleteAgendaItem(it.code)} disabled={!!busy}
                              className="rounded border border-ground-300 px-2 py-1 text-xs text-ground-600 hover:border-critical-300 hover:bg-critical-50 hover:text-critical-700 disabled:opacity-50">
                              {t('admin.scholarship.caveats.delete')}
                            </button>
                            <button onClick={() => setF({ verdict: resolved ? '' : 'resolved' })}
                              className={`rounded px-2 py-1 text-xs font-medium ${resolved ? 'bg-positive-fill text-positive-fill-ink hover:bg-positive-fill-hover' : 'border border-ground-300 text-ground-700 hover:bg-ground-100'}`}>
                              {t('admin.scholarship.interview.verdict.resolved')}
                            </button>
                          </div>
                        )}
                      </div>
                      <input
                        value={f.rationale} maxLength={140} disabled={!canWrite}
                        onChange={(e) => setF({ rationale: e.target.value })}
                        placeholder={t('admin.scholarship.interview.rationalePlaceholder')}
                        className="mt-2 w-full border rounded-lg px-3 py-1.5 text-sm"
                      />
                    </li>
                  )
                })}
              </ul>
            )}
            <textarea value={note} disabled={!canWrite} rows={2}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('admin.scholarship.interview.notePlaceholder')}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
            {canWrite && (
              <div className="flex items-center gap-2">
                <button onClick={doSaveInterview} disabled={!!busy}
                  className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50">
                  {busy === 'iv' ? t('common.loading') : t('admin.scholarship.interview.saveDraft')}
                </button>
                <button onClick={doSubmitInterview} disabled={!!busy}
                  className="px-4 py-2 bg-brand-fill text-brand-fill-ink rounded-lg text-sm disabled:opacity-50">
                  {busy === 'ivs' ? t('common.loading') : t('admin.scholarship.interview.submit')}
                </button>
                {interviewMsg && <span className="text-sm font-medium text-positive-700">{interviewMsg}</span>}
              </div>
            )}
          </>
        )}
      </div>
      )}

  </>)
}
