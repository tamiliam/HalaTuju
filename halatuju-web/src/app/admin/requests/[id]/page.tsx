'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import {
  getOrgRequest, answerOrgRequest, askOrgRequest, commentOrgRequest,
  approveOrgRequestAnalysis, approveOrgRequest,
  deferOrgRequest, modifyOrgRequest,
  declineOrgRequest, triageOrgRequest, quoteOrgRequest, requoteOrgRequest, scheduleOrgRequest,
  doneOrgRequest, aiRerunOrgRequest, type OrgRequestDetail,
} from '@/lib/admin-api'
import {
  statusLabelKey, statusTone, kindLabelKey, laneLabelKey, requestActionsFor,
  hasUnansweredQuestions, canAttach, type RequestAction,
} from '@/lib/requestStatus'
import OrgRequestAttachments from '@/components/OrgRequestAttachments'

// The Requests detail: the clarification thread + the org's requestee actions (accept / defer /
// modify / withdraw) and the owner's controls (triage / quote / requote / schedule / done /
// decline / AI re-run). Which controls appear is decided ENTIRELY by requestActionsFor — keep it
// in step with halatuju_api/apps/scholarship/org_requests.py (the server re-gates each one).

// ⚠ A code ABSENT from this array renders the generic "Something went wrong", which would be
// useless for a refusal that tells the owner what to do next. The TD-204 codes are here for that
// reason, and a rendered test asserts `analysis_required` shows its own message.
const KNOWN_ERR = ['bug_is_free', 'bad_hours', 'reason_required', 'triage_ai_unconfigured',
  'triage_ai_unavailable', 'ai_limit_reached',
  'analysis_required', 'files_required', 'analysis_superseded', 'bad_cited_files']
const errText = (t: (k: string) => string, code?: string) =>
  code && KNOWN_ERR.includes(code) ? t(`admin.requests.error.${code}`) : t('admin.requests.error.generic')

export default function AdminRequestDetailPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const id = Number(params.id)

  const isSuper = effectiveRole(role) === 'super'
  const reqRole: 'super' | 'org_admin' = isSuper ? 'super' : 'org_admin'

  const [req, setReq] = useState<OrgRequestDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Inputs
  const [answer, setAnswer] = useState('')
  const [question, setQuestion] = useState('')   // the owner's question to the requester
  const [commentText, setCommentText] = useState('')      // a statement, from either side
  const [commentInternal, setCommentInternal] = useState(false)   // super-only, off by default
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

  // Seed the quote hours from the approved analysis — ONCE, and never over something typed.
  // ⚠ Deliberately the OPPOSITE of the income wizard (S14), which needed a RE-SEEDING effect: here
  // re-seeding is the bug, because the owner routinely quotes a different number from the
  // engineer's (bundling, goodwill, margin) and a re-render must not undo that. `touched` latches
  // on the first edit and never unlatches.
  const quoteHoursTouched = useRef(false)
  const analysisHours = req?.analyses?.find((a) => a.is_current)?.estimated_hours || ''
  useEffect(() => {
    if (!quoteHoursTouched.current && analysisHours) setQuoteHours(analysisHours)
  }, [analysisHours])

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
  const unanswered = hasUnansweredQuestions(req.comments)
  const actions = requestActionsFor(reqRole, req.status, triagedKind, unanswered)
  const has = (a: RequestAction) => actions.includes(a)
  const opt = { token: token! }

  // TD-204. Absent entirely on an org payload — `|| []` is the org case, not a missing-data case.
  const analyses = req.analyses || []
  const currentAnalysis = analyses.find((a) => a.is_current) || null
  // An ANSWER can change scope without superseding (only `modify` does — answers are frequent and
  // superseding on each would be a treadmill). So say the analysis predates the last thing said,
  // and leave the judgement to the owner rather than blocking.
  const lastComment = (req.comments || [])[(req.comments || []).length - 1]
  const analysisPredatesLastComment = Boolean(
    currentAnalysis && lastComment
    && currentAnalysis.id !== null
    && new Date(lastComment.created_at) > new Date(currentAnalysis.approved_at || currentAnalysis.created_at)
    // The analysis posts its OWN comment on approval, which must not count as "something said
    // since" — compare against the comment it produced, not merely the newest one.
    && lastComment.author_kind !== 'engineer',
  )

  return (
    <div className="max-w-3xl">
      <Link href="/admin/requests" className="text-sm text-blue-600 hover:text-blue-800">← {t('admin.requests.detail.back')}</Link>

      <div className="flex items-start justify-between gap-3 mt-3 mb-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">{req.title}</h1>
          <div className="text-xs text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
            <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{t(kindLabelKey(req.kind))}</span>
            {req.component && (
              <span className="px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700">{t(`admin.requests.component.${req.component}`)}</span>
            )}
            {req.urgency && (
              <span className="px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700">{t(`admin.requests.urgency.${req.urgency}`)}</span>
            )}
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

      {/* Steps to reproduce (bug scoping) */}
      {req.steps_to_reproduce && (
        <div className="bg-white rounded-xl border p-5 mb-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.detail.steps')}</h2>
          <p className="text-gray-800 whitespace-pre-wrap">{req.steps_to_reproduce}</p>
        </div>
      )}

      {/* Screenshots — evidence, so it closes when the quote is ACCEPTED, not merely at a terminal
          status. Adding a screenshot to an accepted request would change what was priced. */}
      <OrgRequestAttachments
        requestId={id}
        attachments={req.attachments || []}
        editable={canAttach(req.status) && (isSuper || reqRole === 'org_admin')}
        token={token}
        onChange={setReq}
      />

      {/* The reviewer's READING of the request — shown to the ORG too (TD-202, owner 2026-07-30).
          The owner filed request #4 as an org_admin and saw silence; the reviewer had in fact
          answered in 21 seconds, into a room the requester was not in. A quote whose reasoning is
          invisible looks arbitrary. Its HOURS stay owner-only: the model has no codebase context
          and has been wrong by a factor of six, so an unreliable number presented as the basis of
          a price is worse than none. Rendered only for the requester — the super has the fuller
          version, with kind/lane/hours, in Owner controls below. */}
      {!isSuper && req.ai_draft_note && (
        <div className="bg-white rounded-xl border p-5 mb-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.detail.aiReading')}</h2>
          <p className="text-gray-800 whitespace-pre-wrap">{req.ai_draft_note}</p>
          <p className="text-xs text-gray-400 mt-2">
            {t('admin.requests.detail.aiReadingNote')}
            {req.ai_draft_model ? ` · ${req.ai_draft_model}` : ''}
          </p>
        </div>
      )}

      {/* The DISCUSSION (TD-201) — one stream, not a question log. The owner's model is Bugzilla:
          "open discussion/debate, even after it has been assigned to someone". A question is
          simply a comment awaiting a reply, which is why they render together and in one order. */}
      <div className="bg-white rounded-xl border p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-500 mb-3">{t('admin.requests.detail.thread')}</h2>
        {(req.comments || []).length === 0 ? (
          <p className="text-sm text-gray-400">{t('admin.requests.detail.noComments')}</p>
        ) : (
          <ul className="space-y-3">
            {(req.comments || []).map((c) => (
              <li key={c.id}
                  className={`text-sm rounded-lg p-3 ${
                    c.visibility === 'internal'
                      ? 'bg-amber-50 border border-amber-200' : 'bg-gray-50'}`}>
                <div className="flex items-baseline gap-2 flex-wrap">
                  {/* WHO spoke is the point of one shared thread: the reviewer's reading, the
                      owner's judgement and the requester's own words carry different weight, and
                      the requester should be able to tell whose question they are answering. */}
                  <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                    c.author_kind === 'owner' ? 'bg-blue-50 text-blue-700'
                      : c.author_kind === 'org' ? 'bg-green-50 text-green-700'
                      : 'bg-gray-100 text-gray-500'}`}>
                    {t(`admin.requests.detail.author.${c.author_kind}`)}
                  </span>
                  {c.author_name && <span className="text-xs text-gray-500">{c.author_name}</span>}
                  <span className="text-xs text-gray-400">{formatDate(c.created_at)}</span>
                  {/* Only ever rendered for the super — the server filters internal ROWS out of
                      the org payload. Badged so the owner can see at a glance what the requester
                      is not reading; an unmarked internal note is how something private gets
                      written as though it were shared. */}
                  {c.visibility === 'internal' && (
                    <span className="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-800">
                      {t('admin.requests.detail.internalBadge')}
                    </span>
                  )}
                </div>
                <p className="text-gray-800 whitespace-pre-wrap mt-1">{c.body}</p>
                {/* "Answer needed" is a DEMAND — only make it where answering is still possible.
                    Once the quote is accepted the reply box unmounts, and an amber prompt with no
                    box behind it asks for something the page has taken away (request #3 sat like
                    that permanently). Then it is simply unanswered. */}
                {c.awaiting_reply && (
                  has('answer')
                    ? <p className="text-amber-600 text-xs mt-1">{t('admin.requests.list.answerNeeded')}</p>
                    : <p className="text-gray-400 text-xs mt-1">{t('admin.requests.detail.unanswered')}</p>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Reply box — org_admin, when a question is waiting. Kept SEPARATE from the comment box
            below because only this one clears `awaiting_reply`: replying closes a question, and
            remarking does not. One box would have to guess which was meant. */}
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

        {/* Comment box — EITHER side, open until the request is terminal. This is the verb the
            module never had: until now only the AI could write here, so a conclusion ("here is
            what we would build, and why") had to travel as a quote note or not at all. */}
        {has('comment') && (
          <div className="mt-4 border-t pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.detail.commentLabel')}</label>
            <textarea value={commentText} onChange={(e) => setCommentText(e.target.value)} rows={3}
              placeholder={t('admin.requests.detail.commentPlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            {/* Internal is the owner's alone. The server refuses it for anyone else (403) and an
                org author can never be internal at all — this checkbox is the convenience, not
                the control. */}
            {isSuper && (
              <label className="flex items-center gap-2 mt-2 text-sm text-gray-700">
                <input type="checkbox" checked={commentInternal}
                  onChange={(e) => setCommentInternal(e.target.checked)}
                  className="rounded border-gray-300" />
                {t('admin.requests.detail.commentInternal')}
              </label>
            )}
            <button disabled={busy || !commentText.trim()}
              onClick={() => run(async () => {
                const r = await commentOrgRequest(
                  id, { body: commentText, visibility: commentInternal ? 'internal' : 'shared' }, opt)
                setCommentText(''); setCommentInternal(false); return r
              })}
              className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {busy ? t('admin.requests.action.working') : t('admin.requests.detail.commentSend')}
            </button>
            {isSuper && commentInternal && (
              <p className="mt-1 text-xs text-amber-600">{t('admin.requests.detail.commentInternalHint')}</p>
            )}
          </div>
        )}

        {/* Ask box — a question, which AWAITS A REPLY and therefore stops at the quote while a
            plain comment runs on. A quoted request must not grow new questions: the quote was
            priced against what was known when it was sent. */}
        {isSuper && has('ask') && (
          <div className="mt-4 border-t pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.detail.askLabel')}</label>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3}
              placeholder={t('admin.requests.detail.askPlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            <button disabled={busy || !question.trim()}
              onClick={() => run(async () => { const r = await askOrgRequest(id, { question }, opt); setQuestion(''); return r })}
              className="mt-2 px-4 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {busy ? t('admin.requests.action.working') : t('admin.requests.detail.askSend')}
            </button>
            <p className="mt-1 text-xs text-gray-400">{t('admin.requests.detail.askHint')}</p>
          </div>
        )}
      </div>

      {/* Quote (org-facing) — deliberately BELOW the thread (owner, 2026-07-30): the quote is the
          CONCLUSION, so the deliberation that produced it should be read first. */}
      {req.quote_hours != null && (
        <div className="bg-white rounded-xl border p-5 mb-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-1">{t('admin.requests.detail.quote')}</h2>
          <p className="text-lg font-semibold text-gray-900">
            {/* Hours only — the margin is not shown to the organisation and is no longer on the
                org-facing payload at all (owner, 2026-07-30). */}
            {t('admin.requests.detail.quoteValue', { hours: req.quote_hours })}
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
                {/* The reviewer is no longer ASKED for hours (owner, 2026-07-30) — it cannot
                    see the codebase and priced greenfield every time. Historical drafts keep
                    theirs in the column; showing them would keep a number in play that we
                    have decided not to trust. The estimate is the engineer's, and cited. */}
                {req.ai_draft_note && <p className="text-gray-600 whitespace-pre-wrap">{req.ai_draft_note}</p>}
                <p className="text-xs text-gray-400">
                  {/* The model was stored from the day this shipped and never shown. Which model
                      produced an estimate is part of reading it — the same draft from flash and
                      from pro does not carry the same weight. */}
                  {req.ai_draft_model && <>{t('admin.requests.owner.aiDraftModel')}: {req.ai_draft_model} · </>}
                  {t('admin.requests.owner.aiDraftRuns')}: {req.ai_run_count ?? 0}
                </p>
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

          {/* The engineer's analysis (TD-204) — ABOVE the quote form, because it is what the
              quote now stands on. The gate refuses to price without one, so seeing it first is
              the order the work actually happens in.

              ⚠ Everything in this block is OWNER-ONLY. The whole `analyses` key is absent from
              the org payload; the requester sees only the PROSE, once approved, in the thread. */}
          <div className="border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('admin.requests.owner.analysisTitle')}</h3>
            {analyses.length === 0 ? (
              /* Honest empty state: no analysis has been RECORDED. Never phrased as though one
                 was refused or is missing — every request predating TD-204 has none. */
              <p className="text-sm text-gray-400">{t('admin.requests.owner.analysisNone')}</p>
            ) : (
              <ul className="space-y-3">
                {analyses.map((a) => (
                  <li key={a.id} className={`rounded-lg border p-3 text-sm ${
                    a.is_current ? 'border-green-200 bg-green-50'
                      : a.superseded_at ? 'border-gray-200 bg-gray-50 opacity-70'
                      : 'border-amber-200 bg-amber-50'}`}>
                    <div className="flex items-baseline gap-2 flex-wrap">
                      {a.approved_at ? (
                        a.superseded_at ? (
                          <span className="rounded-full px-1.5 py-0.5 text-[10px] font-medium bg-gray-200 text-gray-600">
                            {t('admin.requests.owner.analysisSuperseded')}
                          </span>
                        ) : (
                          <span className="rounded-full px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-800">
                            {t('admin.requests.owner.analysisApproved')}
                          </span>
                        )
                      ) : (
                        <span className="rounded-full px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-800">
                          {t('admin.requests.owner.analysisDraft')}
                        </span>
                      )}
                      {a.estimated_hours && (
                        <span className="font-semibold text-gray-900">
                          {t('admin.requests.owner.analysisHoursValue', { hours: a.estimated_hours })}
                        </span>
                      )}
                      {/* Rendered in the same change that stores them — this project has five
                          stored-but-never-surfaced fields already, and that cluster stops here. */}
                      {a.authored_by && <span className="text-xs text-gray-500">{a.authored_by}</span>}
                      {a.repo_sha && (
                        <span className="text-xs text-gray-400 font-mono">{a.repo_sha.slice(0, 12)}</span>
                      )}
                      <span className="text-xs text-gray-400">{formatDate(a.created_at)}</span>
                    </div>
                    <p className="text-gray-800 whitespace-pre-wrap mt-2">{a.body}</p>
                    {a.cited_files.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-500">{t('admin.requests.owner.analysisFiles')}</p>
                        <ul className="mt-1 space-y-0.5">
                          {a.cited_files.map((f) => (
                            <li key={f} className="text-xs font-mono text-gray-600 break-all">{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {a.approved_at && a.approved_by_name && (
                      <p className="text-xs text-gray-400 mt-2">
                        {t('admin.requests.owner.analysisApprovedBy', { name: a.approved_by_name })} · {formatDate(a.approved_at)}
                      </p>
                    )}
                    {/* The amber staleness note: an ANSWER can change scope without triggering a
                        supersede (only `modify` does), so say so rather than block. */}
                    {a.is_current && analysisPredatesLastComment && (
                      <p className="text-xs text-amber-700 mt-2">{t('admin.requests.owner.analysisStale')}</p>
                    )}
                    {!a.approved_at && !a.superseded_at && (
                      <button disabled={busy}
                        onClick={() => { if (confirm(t('admin.requests.owner.analysisApproveConfirm'))) run(() => approveOrgRequestAnalysis(id, a.id, opt)) }}
                        className="mt-3 px-4 bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                        {t('admin.requests.owner.analysisApprove')}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Quote / Re-quote */}
          {(has('quote') || has('requote')) && (
            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('admin.requests.owner.quoteTitle')}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm">{t('admin.requests.owner.quoteHours')}
                  <input type="number" min="0" step="0.5" value={quoteHours}
                    onChange={(e) => { quoteHoursTouched.current = true; setQuoteHours(e.target.value) }}
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
