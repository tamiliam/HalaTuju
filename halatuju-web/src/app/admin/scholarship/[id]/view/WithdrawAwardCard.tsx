'use client'

/**
 * A1.13b (TD-198, owner rulings 2026-11-08): WITHDRAW AN AWARD — MAKER AND CHECKER. One staff member asks,
 * with a required explanation (internal: the student never sees it); a DIFFERENT staff member approves —
 * and only then is the award withdrawn (the case returns to the pool, the unpaid award goes back to the
 * sponsor's balance, scheduled payments stop) — or refuses, with a reason. The maker may cancel. A
 * pending request nobody decides ends by itself after 14 days.
 *
 * ⚠ THE SERVER DECIDES WHO MAY DO WHAT. The card draws from the case detail's `withdrawal_request`
 * (`award_withdrawal_chain.payload_for`) and nothing else: `your_step` is the server's ONE predicate
 * (`next_step_for`) — 'request' (the ask form), 'cancel' (the maker, waiting), 'decide' (a checker), or
 * null (read only: an outcome, or a super, who sits in neither seat). Every button is re-checked on the
 * server; a refusal comes back as a code and is said in words. The ask prompt, and the approval's
 * confirm (with an optional note for the record), reuse the cockpit's `ReasonBox`. The figures are the request's snapshot (`amount_freed`, `tranches_to_withhold`) plus the
 * case's own award amount and released tranches, added up in whole cents; nothing else is worked out.
 */
import { useState } from 'react'
import {
  approveAwardWithdrawal, cancelAwardWithdrawal, refuseAwardWithdrawal, requestAwardWithdrawal,
  type AdminScholarshipDetail, type AwardWithdrawalRequest,
} from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'

import { ReasonBox } from './ReasonBox'
import type { T } from './shared'

const K = 'admin.scholarship.withdrawAward'
/** The server's `TEXT_MAX`: an explanation or a refusal reason past it is refused, never cut. */
export const TEXT_MAX = 5000

/** The refusal codes the API answers with (`views_admin/award_withdrawal._STATUS`); anything else falls
 *  back to the generic message. */
export const KNOWN_ERRORS = [
  'wrong_role', 'same_person', 'no_checker', 'already_pending', 'not_pending', 'not_awarded', 'stale',
  'has_payments', 'explanation_required', 'explanation_too_long', 'reason_required', 'reason_too_long',
  'note_too_long', 'not_found',
] as const

const TAP = 'max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center'
const DECIMAL = /^(-?)(\d+)(?:\.(\d{1,2}))?$/

/** Has money gone out on this case (a released or returned tranche)? Mirrors the API's rule. */
export function hasPaidTranche(app: AdminScholarshipDetail): boolean {
  return (app.disbursements ?? []).some((d) => d.status === 'released' || d.status === 'returned')
}

/** A served decimal string ("1500.50") as whole cents, or null when it is not one. No floats. */
export function toCents(raw: string | null | undefined): number | null {
  const m = String(raw ?? '').trim().match(DECIMAL)
  if (!m) return null
  const value = Number(m[2]) * 100 + Number((m[3] ?? '').padEnd(2, '0'))
  return m[1] ? -value : value
}

/** "RM 1,500.00" from whole cents — integer arithmetic only, so a sum stays exact. */
export function rmFromCents(c: number): string {
  const whole = String(Math.floor(Math.abs(c) / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${c < 0 ? '-' : ''}RM ${whole}.${String(Math.abs(c) % 100).padStart(2, '0')}`
}

/** What has been released to the student so far, from the case's own tranches. */
export function paidSoFarCents(app: AdminScholarshipDetail): number {
  return (app.disbursements ?? []).filter((d) => d.status === 'released')
    .reduce((sum, d) => sum + (toCents(d.amount) ?? 0), 0)
}

type Tone = 'primary' | 'caution' | 'ground' | 'critical'
const TONE: Record<Tone, string> = {
  primary: 'bg-primary-50 text-primary-800',
  caution: 'bg-caution-100 text-caution-900',
  ground: 'bg-ground-100 text-ground-700',
  critical: 'bg-critical-50 text-critical-800',
}
const STATUS_TONE: Record<NonNullable<AwardWithdrawalRequest['status']>, Tone> = {
  pending: 'primary', approved: 'critical', refused: 'ground', cancelled: 'ground', expired: 'ground',
}

function Pill({ tone, children }: { tone: Tone; children: string }) {
  return (
    <span data-testid="withdrawal-pill"
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE[tone]}`}>{children}</span>
  )
}

function Quote({ heading, text }: { heading: string; text?: string }) {
  if (!text) return null
  return (
    <div>
      <p className="text-xs font-medium text-ground-700">{heading}</p>
      <blockquote className="mt-1 whitespace-pre-wrap break-words border-l-2 border-ground-300 pl-3 text-sm text-ground-800">
        {text}
      </blockquote>
    </div>
  )
}

/** The read-only account of a request: its status, who asked and when, who decided and their words. */
function Outcome({ wr, t }: { wr: AwardWithdrawalRequest; t: T }) {
  if (!wr.status) return null
  const who = (name?: string) => name || t(`${K}.someone`)
  let decided = ''
  if (wr.status === 'expired') decided = t(`${K}.decided.expired`, { date: formatDate(wr.expires_at) })
  else if (wr.status !== 'pending') {
    decided = t(`${K}.decided.${wr.status}`, { name: who(wr.decided_by_name), date: formatDate(wr.decided_at) })
  }
  return (
    <div data-testid="withdrawal-outcome" className="space-y-2">
      <Pill tone={STATUS_TONE[wr.status]}>{t(`${K}.pill.${wr.status}`)}</Pill>
      <p className="text-xs text-ground-600">
        {t(`${K}.requestedBy`, { name: who(wr.requested_by_name), date: formatDate(wr.requested_at) })}
      </p>
      <Quote heading={t(`${K}.explanationHeading`)} text={wr.explanation} />
      {decided && <p className="text-xs text-ground-600">{decided}</p>}
      <Quote heading={t(wr.status === 'refused' ? `${K}.refusedReasonHeading` : `${K}.noteHeading`)}
        text={wr.decision_note} />
    </div>
  )
}

type Busy = '' | 'request' | 'approve' | 'refuse' | 'cancel'

export function WithdrawAwardCard({
  app, t, token, onChanged,
}: {
  app: AdminScholarshipDetail
  t: T
  token: string | null | undefined
  onChanged: (next: AdminScholarshipDetail) => void
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  /** The checker's approve confirm (its optional note is `note`, kept apart from the refusal reason in
   *  `text`, so neither is lost when the other is used). */
  const [approving, setApproving] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<Busy>('')
  const [error, setError] = useState('')

  const wr = app.withdrawal_request
  if (!wr || (!wr.status && !wr.your_step)) return null

  const say = (code: string) => setError(t(`${K}.error.${code}`))
  const run = async (which: Exclude<Busy, ''>, call: () => Promise<AdminScholarshipDetail>) => {
    if (!token || busy) return
    setBusy(which)
    setError('')
    try {
      const next = await call()
      setOpen(false)
      setText('')
      setApproving(false)
      setNote('')
      onChanged(next)
    } catch (err) {
      const code = (err as { code?: string })?.code
      say(KNOWN_ERRORS.includes(code as (typeof KNOWN_ERRORS)[number]) ? (code as string) : 'generic')
    } finally {
      setBusy('')
    }
  }
  /** The server refuses a blank or over-long text; say so here without a round trip. Never cut it. */
  const checked = (field: 'explanation' | 'reason'): string | null => {
    const value = text.trim()
    if (!value) { say(`${field}_required`); return null }
    if (value.length > TEXT_MAX) { say(`${field}_too_long`); return null }
    return value
  }
  const id = wr.id
  const auth = { token: token || undefined }
  const request = () => {
    const value = checked('explanation')
    if (value !== null) void run('request', () => requestAwardWithdrawal(app.id, value, auth))
  }
  /** The approval's note is optional; past TEXT_MAX it is refused here (as the server would), never cut. */
  const approve = () => {
    const value = note.trim()
    if (value.length > TEXT_MAX) { say('note_too_long'); return }
    if (id != null) void run('approve', () => approveAwardWithdrawal(id, value, auth))
  }
  const closeApprove = () => { setApproving(false); setNote(''); setError('') }
  const refuse = () => {
    const value = checked('reason')
    if (value !== null && id != null) void run('refuse', () => refuseAwardWithdrawal(id, value, auth))
  }
  const cancel = () => { if (id != null) void run('cancel', () => cancelAwardWithdrawal(id, auth)) }

  const step = wr.your_step
  const pendingNow = wr.status === 'pending'
  let body

  if (step === 'cancel' && pendingNow) {
    body = (
      <div data-testid="withdrawal-maker" className="space-y-2">
        <Pill tone="primary">{t(`${K}.pill.pending`)}</Pill>
        <p className="text-sm text-ground-700">{t(`${K}.askedOn`, { date: formatDate(wr.requested_at) })}</p>
        <Quote heading={t(`${K}.yourExplanation`)} text={wr.explanation} />
        <p className="text-xs text-ground-600">{t(`${K}.checkersEmailed`)}</p>
        <button type="button" onClick={cancel} disabled={!!busy} data-testid="withdrawal-cancel"
          className="min-h-11 text-sm font-medium text-primary-700 underline underline-offset-2 disabled:opacity-50">
          {busy === 'cancel' ? t('common.loading') : t(`${K}.cancelRequest`)}
        </button>
      </div>
    )
  } else if (step === 'decide' && pendingNow) {
    const award = toCents(app.award_amount)
    const freed = toCents(wr.amount_freed)
    const facts: [string, string][] = []
    if (award !== null) facts.push([t(`${K}.fact.award`), rmFromCents(award)])
    facts.push([t(`${K}.fact.paid`), rmFromCents(paidSoFarCents(app))])
    if (freed !== null) facts.push([t(`${K}.fact.freed`), rmFromCents(freed)])
    if (wr.tranches_to_withhold != null) facts.push([t(`${K}.fact.stopped`), String(wr.tranches_to_withhold)])
    body = (
      <div data-testid="withdrawal-checker" className="space-y-3">
        <Pill tone="caution">{t(`${K}.pill.yourApproval`)}</Pill>
        <p className="text-sm text-ground-700">
          {t(`${K}.requestedBy`, { name: wr.requested_by_name || t(`${K}.someone`), date: formatDate(wr.requested_at) })}
        </p>
        <Quote heading={t(`${K}.theirExplanation`)} text={wr.explanation} />
        <dl data-testid="withdrawal-facts" className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {facts.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-ground-600">{label}</dt>
              <dd className="text-right font-medium tabular-nums text-ground-900">{value}</dd>
            </div>
          ))}
        </dl>
        {hasPaidTranche(app) && <p className="text-xs text-caution-800">{t(`${K}.paidNote`)}</p>}
        <p className="rounded-lg bg-info-50 p-3 text-xs text-info-800">{t(`${K}.approveNote`)}</p>
        {approving ? (
          <ReasonBox optional testId="withdrawal-approve-box"
            title={t(`${K}.approveDialogTitle`)} hint={t(`${K}.approveDialogHint`)}
            placeholder={t(`${K}.approvePlaceholder`)} confirmLabel={t(`${K}.approveConfirm`)}
            workingLabel={t('common.loading')} cancelLabel={t('common.cancel')}
            value={note} onChange={setNote} onConfirm={approve} onCancel={closeApprove}
            disabled={!!busy} working={busy === 'approve'} />
        ) : (
          <>
            <label className="block text-xs font-medium text-ground-700">
              {t(`${K}.refuseReasonLabel`)}
              <textarea value={text} rows={2} onChange={(e) => setText(e.target.value)} data-testid="withdrawal-reason"
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm font-normal" />
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => { setError(''); setApproving(true) }} disabled={!!busy}
                data-testid="withdrawal-approve"
                className="min-h-11 rounded-lg bg-critical-fill px-4 text-sm font-medium text-critical-fill-ink disabled:opacity-50">
                {t(`${K}.approve`)}
              </button>
              <button type="button" onClick={refuse} disabled={!!busy} data-testid="withdrawal-refuse"
                className="min-h-11 rounded-lg border border-ground-300 px-4 text-sm font-medium text-ground-700 disabled:opacity-50">
                {busy === 'refuse' ? t('common.loading') : t(`${K}.refuse`)}
              </button>
            </div>
          </>
        )}
        <p className="text-xs text-ground-500">{t(`${K}.selfNote`)}</p>
      </div>
    )
  } else if (step === 'request') {
    body = (
      <div data-testid="withdrawal-request" className="space-y-3">
        {wr.status && <Outcome wr={wr} t={t} />}
        <p className="text-xs text-ground-600">{t(`${K}.hint`)}</p>
        {hasPaidTranche(app) ? (
          <p className="text-xs text-caution-800">{t(`${K}.paidNote`)}</p>
        ) : open ? (
          <ReasonBox
            title={t(`${K}.dialogTitle`)} hint={t(`${K}.dialogHint`)} placeholder={t(`${K}.placeholder`)}
            confirmLabel={t(`${K}.confirm`)} workingLabel={t('common.loading')} cancelLabel={t('common.cancel')}
            value={text} onChange={setText} onConfirm={request}
            onCancel={() => { setOpen(false); setText(''); setError('') }}
            disabled={!!busy} working={busy === 'request'} />
        ) : (
          <button type="button" onClick={() => setOpen(true)}
            className={`px-3 py-1.5 border border-critical-200 rounded-lg text-sm text-critical-700 ${TAP}`}>
            {t(`${K}.action`)}
          </button>
        )}
      </div>
    )
  } else {
    body = <Outcome wr={wr} t={t} />
  }

  return (
    <section data-testid="withdraw-award"
      className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-3">
      <h2 className="text-base font-semibold tracking-tight text-ground-900">{t(`${K}.title`)}</h2>
      {body}
      {error && <p role="alert" className="text-xs text-critical-700">{error}</p>}
    </section>
  )
}
