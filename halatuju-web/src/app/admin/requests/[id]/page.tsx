'use client'

import { useCallback, useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import {
  getOrgRequest, answerOrgRequest, approveOrgRequest, deferOrgRequest, modifyOrgRequest,
  declineOrgRequest, triageOrgRequest, quoteOrgRequest, requoteOrgRequest, scheduleOrgRequest,
  doneOrgRequest, aiRerunOrgRequest, type OrgRequestDetail,
} from '@/lib/admin-api'
import {
  statusLabelKey, statusTone, kindLabelKey, laneLabelKey, requestActionsFor,
  hasUnansweredQuestions, type RequestAction,
} from '@/lib/requestStatus'

// The Requests detail: the clarification thread + the org's requestee actions (accept / defer /
// modify / withdraw) and the owner's controls (triage / quote / requote / schedule / done /
// decline / AI re-run). Which controls appear is decided ENTIRELY by requestActionsFor — keep it
// in step with halatuju_api/apps/scholarship/org_requests.py (the server re-gates each one).

const KNOWN_ERR = ['bug_is_free', 'bad_hours', 'reason_required', 'triage_ai_unconfigured',
  'triage_ai_unavailable', 'ai_limit_reached']
const errText = (t: (k: string) => string, code?: string) =>
  code && KNOWN_ERR.includes(code) ? t(`admin.requests.error.${code}`) : t('admin.requests.error.generic')

export default function AdminRequestDetailPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const id = Number(params.id)

  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const reqRole: 'super' | 'org_admin' = isSuper ? 'super' : 'org_admin'

  const [req, setReq] = useState<OrgRequestDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Inputs
  const [answer, setAnswer] = useState('')
  const [modifyText, setModifyText] = useState('')
  const [declineReason, setDeclineReason] = useState('')
  const [triageKind, setTriageKind] = useState<'bug' | 'feature'>('feature')
  const [triageLane, setTriageLane] = useState<'small_change' | 'sprint'>('sprint')
  const [triageNote, setTriageNote] = useState('')
  const [quoteHours, setQuoteHours] = useState('')
  const [quoteMargin, setQuoteMargin] = useState('50')
  const [quoteNote, setQuoteNote] = useState('')
  const [scheduleDate, setScheduleDate] = useState('')

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    getOrgRequest(id, { token })
      .then(setReq)
      .catch(() => setError(t('admin.requests.error.generic')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  useEffect(() => { load() }, [load])

  const run = async (fn: () => Promise<OrgRequestDetail>) => {
    setBusy(true); setError('')
    try {
      setReq(await fn())
    } catch (err) {
      setError(errText(t, (err as { code?: string })?.code))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
  if (!req) return <p className="text-red-600">{error || t('admin.requests.error.generic')}</p>

  const triagedKind = req.triaged_kind || ''
  const unanswered = hasUnansweredQuestions(req.clarifications)
  const actions = requestActionsFor(reqRole, req.status, triagedKind, unanswered)
  const has = (a: RequestAction) => actions.includes(a)
  const opt = { token: token! }

  return (
    <div className="max-w-3xl">
      <Link href="/admin/requests" className="text-sm text-blue-600 hover:text-blue-800">← {t('admin.requests.detail.back')}</Link>

      <div className="flex items-start justify-between gap-3 mt-3 mb-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">{req.title}</h1>
          <div className="text-xs text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
            <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{t(kindLabelKey(req.kind))}</span>
            {isSuper && req.organisation_name && <span>{req.organisation_name}</span>}
            <span>{t('admin.requests.list.submittedBy', { name: req.submitted_by_name })}</span>
            <span>{formatDate(req.created_at)}</span>
          </div>
        </div>
        <span className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold ${statusTone(req.status)}`}>
          {t(statusLabelKey(req.status))}
        </span>
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-600 p-3 mb-4">{error}</div>}

      {/* Description */}
      <div className="bg-white rounded-xl border p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.detail.description')}</h2>
        <p className="text-gray-800 whitespace-pre-wrap">{req.description}</p>
      </div>

      {/* Quote (org-facing) */}
      {req.quote_hours != null && (
        <div className="bg-white rounded-xl border p-5 mb-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.detail.quote')}</h2>
          <p className="text-lg font-semibold text-gray-900">
            {t('admin.requests.detail.quoteValue', { hours: req.quote_hours, margin: String(req.quote_margin_pct ?? 0) })}
          </p>
          {req.quote_note && <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">{req.quote_note}</p>}
          {req.scheduled_for && (
            <p className="text-sm text-gray-500 mt-2">{t('admin.requests.detail.scheduledFor')}: {formatDate(req.scheduled_for)}</p>
          )}
          {req.status === 'declined' && req.decline_reason && (
            <p className="text-sm text-red-600 mt-2">{t('admin.requests.detail.declinedReason')}: {req.decline_reason}</p>
          )}
        </div>
      )}

      {/* Clarification thread */}
      <div className="bg-white rounded-xl border p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-500 mb-3">{t('admin.requests.detail.thread')}</h2>
        {(req.clarifications || []).filter((c) => c.question || c.history).length === 0 ? (
          <p className="text-sm text-gray-400">{t('admin.requests.detail.noQuestions')}</p>
        ) : (
          <ul className="space-y-3">
            {(req.clarifications || []).map((c, i) => (
              <li key={i} className="text-sm">
                {c.history ? (
                  <p className="text-gray-400 italic">{t('admin.requests.detail.historyModified')}</p>
                ) : (
                  <div>
                    <p className="text-gray-800">{c.question}</p>
                    {c.answer ? (
                      <p className="text-gray-600 mt-1 pl-3 border-l-2 border-green-300">{c.answer}</p>
                    ) : (
                      <p className="text-amber-600 text-xs mt-1">{t('admin.requests.list.answerNeeded')}</p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Answer box — org_admin, when a question is waiting */}
        {has('answer') && (
          <div className="mt-4 border-t pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.detail.answerLabel')}</label>
            <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3}
              placeholder={t('admin.requests.detail.answerPlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            <button disabled={busy || !answer.trim()}
              onClick={() => run(async () => { const r = await answerOrgRequest(id, { answer }, opt); setAnswer(''); return r })}
              className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {busy ? t('admin.requests.action.working') : t('admin.requests.detail.answerSend')}
            </button>
          </div>
        )}
      </div>

      {/* Requestee actions (org_admin) */}
      {(has('accept') || has('defer') || has('modify') || has('withdraw')) && (
        <div className="bg-white rounded-xl border p-5 mb-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            {has('accept') && (
              <button disabled={busy} onClick={() => run(() => approveOrgRequest(id, opt))}
                className="px-4 bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                {t('admin.requests.action.accept')}
              </button>
            )}
            {has('defer') && (
              <button disabled={busy} onClick={() => run(() => deferOrgRequest(id, opt))}
                className="px-4 bg-amber-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50">
                {t('admin.requests.action.defer')}
              </button>
            )}
            {has('withdraw') && (
              <button disabled={busy}
                onClick={() => { if (confirm(t('admin.requests.owner.withdrawConfirm'))) run(() => declineOrgRequest(id, {}, opt)) }}
                className="px-4 bg-red-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50">
                {t('admin.requests.action.withdraw')}
              </button>
            )}
          </div>
          {has('modify') && (
            <div className="border-t pt-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.owner.modifyLabel')}</label>
              <textarea value={modifyText} onChange={(e) => setModifyText(e.target.value)} rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
              <button disabled={busy || !modifyText.trim()}
                onClick={() => run(async () => { const r = await modifyOrgRequest(id, { description: modifyText }, opt); setModifyText(''); return r })}
                className="mt-2 px-4 bg-gray-700 text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50">
                {t('admin.requests.action.modify')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Owner controls (super) */}
      {isSuper && (
        <div className="bg-white rounded-xl border p-5 space-y-4">
          {/* AI draft */}
          <div>
            <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.owner.aiDraft')}</h2>
            {req.ai_draft_at ? (
              <div className="text-sm text-gray-700 space-y-0.5">
                {req.ai_draft_kind && <p>{t('admin.requests.owner.aiDraftKind')}: {t(kindLabelKey(req.ai_draft_kind))}</p>}
                {req.ai_draft_lane && <p>{t('admin.requests.owner.aiDraftLane')}: {t(laneLabelKey(req.ai_draft_lane))}</p>}
                {req.ai_draft_hours != null && <p>{t('admin.requests.owner.aiDraftHours')}: {req.ai_draft_hours}</p>}
                {req.ai_draft_note && <p className="text-gray-600 whitespace-pre-wrap">{req.ai_draft_note}</p>}
                <p className="text-xs text-gray-400">{t('admin.requests.owner.aiDraftRuns')}: {req.ai_run_count ?? 0}</p>
              </div>
            ) : (
              <p className="text-sm text-gray-400">{t('admin.requests.owner.aiDraftNone')}</p>
            )}
            {has('ai_rerun') && (
              <button disabled={busy} onClick={() => run(() => aiRerunOrgRequest(id, opt))}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50">
                {t('admin.requests.action.aiRerun')}
              </button>
            )}
          </div>

          {/* Triage */}
          {has('triage') && (
            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('admin.requests.owner.triageTitle')}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm">{t('admin.requests.owner.triageKind')}
                  <select value={triageKind} onChange={(e) => setTriageKind(e.target.value as 'bug' | 'feature')}
                    className="mt-1 w-full border rounded-lg px-3 py-2">
                    <option value="feature">{t('admin.requests.kind.feature')}</option>
                    <option value="bug">{t('admin.requests.kind.bug')}</option>
                  </select>
                </label>
                <label className="text-sm">{t('admin.requests.owner.triageLane')}
                  <select value={triageLane} onChange={(e) => setTriageLane(e.target.value as 'small_change' | 'sprint')}
                    className="mt-1 w-full border rounded-lg px-3 py-2">
                    <option value="sprint">{t('admin.requests.lane.sprint')}</option>
                    <option value="small_change">{t('admin.requests.lane.small_change')}</option>
                  </select>
                </label>
              </div>
              <textarea value={triageNote} onChange={(e) => setTriageNote(e.target.value)} rows={2}
                placeholder={t('admin.requests.owner.triageNote')}
                className="mt-3 w-full px-3 py-2 border border-gray-300 rounded-lg" />
              <button disabled={busy}
                onClick={() => run(() => triageOrgRequest(id, { triaged_kind: triageKind, lane: triageLane, note: triageNote }, opt))}
                className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {t('admin.requests.action.triage')}
              </button>
            </div>
          )}

          {/* Quote / Re-quote */}
          {(has('quote') || has('requote')) && (
            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('admin.requests.owner.quoteTitle')}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm">{t('admin.requests.owner.quoteHours')}
                  <input type="number" min="0" step="0.5" value={quoteHours} onChange={(e) => setQuoteHours(e.target.value)}
                    className="mt-1 w-full border rounded-lg px-3 py-2" />
                </label>
                <label className="text-sm">{t('admin.requests.owner.quoteMargin')}
                  <input type="number" min="0" value={quoteMargin} onChange={(e) => setQuoteMargin(e.target.value)}
                    className="mt-1 w-full border rounded-lg px-3 py-2" />
                </label>
              </div>
              <textarea value={quoteNote} onChange={(e) => setQuoteNote(e.target.value)} rows={2}
                placeholder={t('admin.requests.owner.quoteNote')}
                className="mt-3 w-full px-3 py-2 border border-gray-300 rounded-lg" />
              <button disabled={busy || !quoteHours.trim()}
                onClick={() => {
                  const data = { hours: Number(quoteHours), margin_pct: Number(quoteMargin), note: quoteNote }
                  run(() => (has('requote') ? requoteOrgRequest(id, data, opt) : quoteOrgRequest(id, data, opt)))
                }}
                className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {has('requote') ? t('admin.requests.action.requote') : t('admin.requests.action.quote')}
              </button>
            </div>
          )}

          {/* Schedule */}
          {has('schedule') && (
            <div className="border-t pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.owner.scheduleDate')}</label>
              <input type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm" />
              <div>
                <button disabled={busy}
                  onClick={() => run(() => scheduleOrgRequest(id, scheduleDate ? { scheduled_for: scheduleDate } : {}, opt))}
                  className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                  {t('admin.requests.action.schedule')}
                </button>
              </div>
            </div>
          )}

          {/* Done */}
          {has('done') && (
            <div className="border-t pt-4">
              <button disabled={busy} onClick={() => run(() => doneOrgRequest(id, opt))}
                className="px-4 bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                {t('admin.requests.action.done')}
              </button>
            </div>
          )}

          {/* Decline */}
          {has('decline') && (
            <div className="border-t pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.owner.declineReason')}</label>
              <textarea value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              <button disabled={busy || !declineReason.trim()}
                onClick={() => { if (confirm(t('admin.requests.owner.declineConfirm'))) run(() => declineOrgRequest(id, { reason: declineReason }, opt)) }}
                className="mt-2 px-4 bg-red-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50">
                {t('admin.requests.action.decline')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* A terminal request with a router push target — keep the back nav obvious */}
      {(req.status === 'done' || req.status === 'declined') && (
        <button onClick={() => router.push('/admin/requests')} className="mt-4 text-sm text-blue-600 hover:text-blue-800">
          ← {t('admin.requests.detail.back')}
        </button>
      )}
    </div>
  )
}
