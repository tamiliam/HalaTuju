'use client'

/** What the work ACTUALLY took, and what we charge for it (2026-10-29).
 *
 * The owner audited all sixteen billed requests and found five wrong — 10, 14, 28, 30, 31 — because
 * billing read `quote_hours`, the PLAN, while the closing report had already published a different
 * number to the organisation. Request 14's report said *"approximately 5 hours spent … None of it is
 * charged"* and it was billed 2.0.
 *
 * ⚠ **THIS IS A TRANSCRIPTION, NOT A DECISION.** The figures exist already, in the prose above this
 * form. The owner copies them into boxes so the invoice can read them. **Nothing parses the prose**,
 * and nothing should: a machine guessing a number that lands on an invoice is exactly how the five
 * got through, and a wrong number is worse than a blank, because a blank REFUSES the month.
 *
 * ⚠ It lives in its own file because `src/app/admin/requests/[id]/page.tsx` sits in the oversize
 * ledger at 663 lines against a 683-line allowance — one line of headroom.
 */

import { useState } from 'react'
import type { OrgRequestAnalysis } from '@/lib/admin-api'

type T = (k: string, vars?: Record<string, string>) => string

/** Hours as the boxes accept them, or an i18n key suffix saying why not.
 *
 * ⚠ The SERVER decides (`request_hours.record_hours`); this puts the message beside the box and
 * saves a round trip. Its rules are the server's, with one difference that matters: ZERO IS VALID.
 * `org_requests._clean_hours` refuses zero because a quote of nothing is meaningless — but a
 * REPORT of nothing is how "none of it is charged" is written down.
 */
export function hoursProblem(value: string, { required }: { required: boolean }): string {
  const text = (value || '').trim()
  if (text === '') return required ? 'hoursRequired' : ''
  if (!/^\d+(\.\d)?$/.test(text)) return 'badHours'
  if (Number(text) > 100000) return 'badHours'
  return ''
}

/** Does the charged figure differ from the hours spent?
 *
 * ⚠ Compared as NUMBERS, and a BLANK charged box means "the same as actual" — which is what the
 * server does with it. So '4' against '4.0', and a blank against anything, are not differences,
 * and nobody is asked to explain a trailing zero.
 */
export function chargedDiffers(actual: string, charged: string): boolean {
  const chargedText = (charged || '').trim()
  const actualText = (actual || '').trim()
  if (chargedText === '' || actualText === '') return false
  if (!/^\d+(\.\d)?$/.test(chargedText) || !/^\d+(\.\d)?$/.test(actualText)) return false
  return Number(chargedText) !== Number(actualText)
}

/** Why this pair cannot be saved, as an i18n key suffix, or '' when it can. */
export function hoursFormProblem(actual: string, charged: string, note: string): string {
  const actualProblem = hoursProblem(actual, { required: true })
  if (actualProblem) return actualProblem
  const chargedProblem = hoursProblem(charged, { required: false })
  if (chargedProblem) return chargedProblem
  // ⚠ A DIFFERENCE NEEDS A REASON. An unexplained write-off is money moved with nothing on the
  // record — the same defect `OrgBuildHours.basis` exists to prevent. Compared as NUMBERS, so
  // '4' and '4.0' are the same figure and do not demand a note for a typing difference.
  if (chargedDiffers(actual, charged) && (note || '').trim() === '') return 'chargeNoteRequired'
  return ''
}

export function RequestHoursForm({ analysis, t, busy, onSave }: {
  analysis: OrgRequestAnalysis
  t: T
  busy: boolean
  onSave: (data: { actual_hours: string; charged_hours?: string; charge_note?: string }) => void
}) {
  const [open, setOpen] = useState(false)
  const [actual, setActual] = useState(analysis.actual_hours || '')
  const [charged, setCharged] = useState(analysis.charged_hours || '')
  const [note, setNote] = useState(analysis.charge_note || '')

  const recorded = analysis.charged_hours !== null
  const problem = hoursFormProblem(actual, charged, note)
  const differs = chargedDiffers(actual, charged)

  if (!open) {
    return (
      <div className="mt-3" data-testid={`hours-${analysis.id}`}>
        {recorded ? (
          <p className="text-xs text-ground-600">
            {t('admin.requests.owner.hoursRecorded', {
              actual: analysis.actual_hours || '—',
              charged: analysis.charged_hours || '0.0',
            })}
            {analysis.charge_note && (
              <span className="block text-[11px] text-ground-400">{analysis.charge_note}</span>
            )}
          </p>
        ) : (
          /* ⚠ AMBER, not silence. Until this is filled in, the month's invoice is REFUSED —
             so the owner has to be able to see that from the request, not only from billing. */
          <p className="text-xs text-caution-700">{t('admin.requests.owner.hoursMissing')}</p>
        )}
        <button type="button" disabled={busy} onClick={() => setOpen(true)}
          className="mt-1 text-xs text-ground-500 underline disabled:opacity-40">
          {t(recorded ? 'admin.requests.owner.hoursEdit' : 'admin.requests.owner.hoursRecord')}
        </button>
      </div>
    )
  }

  return (
    <div className="mt-3 rounded-lg border border-ground-200 bg-ground-0 p-3"
      data-testid={`hours-form-${analysis.id}`}>
      <p className="text-xs text-ground-500">{t('admin.requests.owner.hoursHelp')}</p>
      <div className="mt-2 flex flex-wrap gap-3">
        <label className="text-xs text-ground-600">
          {t('admin.requests.owner.hoursActual')}
          {/* ⚠ A TEXT box, not type="number": a native numeric input follows the browser locale,
              and a comma decimal would reach the server as something it refuses. */}
          <input type="text" inputMode="decimal" value={actual} aria-label="actual_hours"
            onChange={(e) => setActual(e.target.value)}
            className="mt-0.5 block w-24 rounded border border-ground-300 px-2 py-1 text-sm" />
        </label>
        <label className="text-xs text-ground-600">
          {t('admin.requests.owner.hoursCharged')}
          <input type="text" inputMode="decimal" value={charged} aria-label="charged_hours"
            placeholder={actual}
            onChange={(e) => setCharged(e.target.value)}
            className="mt-0.5 block w-24 rounded border border-ground-300 px-2 py-1 text-sm" />
        </label>
      </div>
      {/* ⚠ THE NOTE EXISTS ONLY TO EXPLAIN A DIFFERENCE, so it is offered only while there is
          one — and `onSave` below does not send it otherwise. Leaving it on screen when the two
          figures match let a write-off be reversed with its explanation still attached: a note
          saying "our overrun, absorbed in full" sitting on a request that was charged in full. */}
      {differs && (
        <label className="mt-2 block text-xs text-ground-600">
          {t('admin.requests.owner.hoursNote')}
          <textarea value={note} rows={2} aria-label="charge_note"
            onChange={(e) => setNote(e.target.value)}
            className="mt-0.5 block w-full rounded border border-ground-300 px-2 py-1 text-sm" />
        </label>
      )}
      {problem && (
        <p className="mt-2 text-xs text-critical-600">
          {t(`admin.requests.owner.hoursError.${problem}`)}
        </p>
      )}
      <div className="mt-2 flex items-center gap-2">
        <button type="button" disabled={busy || problem !== ''}
          onClick={() => {
            onSave({
              actual_hours: actual.trim(),
              charged_hours: charged.trim() || undefined,
              // ⚠ Never sent when the figures match: the service stores a blank as NULL, which
              // is how a stale explanation is cleared rather than carried forward.
              charge_note: (differs && note.trim()) || undefined,
            })
            setOpen(false)
          }}
          className="rounded-lg bg-positive-fill px-4 py-2 text-sm font-medium text-positive-fill-ink hover:bg-positive-fill-hover disabled:opacity-50">
          {t('admin.requests.owner.hoursSave')}
        </button>
        <button type="button" onClick={() => setOpen(false)}
          className="rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50">
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}
