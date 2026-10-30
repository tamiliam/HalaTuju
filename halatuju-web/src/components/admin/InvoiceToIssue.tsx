'use client'

/**
 * The "To issue" half of Billing & usage — super only (2026-10-28).
 *
 * `ReadinessCard` moved here VERBATIM from `InvoicesSection.tsx`, which stood at 577 of the
 * 600-line standard; this sprint adds a month picker and an issue-date box, and trimming a file to
 * fit is not what a size guard asks for (TD-413's lesson).
 *
 * WHAT IS NEW, and why both halves are needed to back-issue July:
 *  - the MONTH was never choosable. The screen asked the server for its default — the month just
 *    closed — so July and August were unreachable from the browser even though the endpoint has
 *    taken `?month=` since the day it shipped.
 *  - the ISSUE DATE was always the day the button was pressed. July's invoice has to say 15 August
 *    (owner, 2026-10-28), or a July bill carries a November due date.
 */
import Link from 'next/link'
import { useState } from 'react'
import type { InvoiceProblem, InvoiceReadiness, InvoicesPayload } from '@/lib/admin-api'
import { formatMonth } from '@/lib/billingUsage'
import {
  defaultIssueDate, monthOptions, issueDateProblem, issueMode, orderedProblems, settingsHref,
  todayIso,
} from '@/lib/invoices'

type T = (k: string, vars?: Record<string, string>) => string

const INPUT = 'mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm text-ground-900'
const PRIMARY = 'rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50'

export function ReadinessCard({ row, month, busy, t, onIssue }: {
  row: InvoiceReadiness
  month: string
  busy: boolean
  t: T
  onIssue: (orgId: number, reason: string) => void
}) {
  const [reason, setReason] = useState('')
  // A month already invoiced is DONE, not "not ready": its other warnings were weighed when it was
  // issued, and re-listing them as blockers would read as an alarm about a settled decision.
  if (row.problems.some((p) => p.code === 'already_issued')) {
    return (
      <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border bg-ground-0 p-4 shadow-sm"
        data-testid={`readiness-${row.organisation_id}`}>
        <p className="text-sm">
          <span className="font-semibold text-ground-900">{row.organisation}</span>
          <span className="text-ground-400"> · {formatMonth(month)}</span>
        </p>
        <span className="rounded-full bg-info-100 px-2 py-0.5 text-[11px] font-semibold text-info-700">
          {t('admin.billing.invoice.alreadyIssued')}
        </span>
      </div>
    )
  }
  const mode = issueMode(row.problems)
  const chip = mode === 'ready'
    ? { key: 'admin.billing.invoice.ready', cls: 'bg-positive-100 text-positive-700' }
    : mode === 'override'
      ? { key: 'admin.billing.invoice.needsReason', cls: 'bg-caution-100 text-caution-700' }
      : { key: 'admin.billing.invoice.notReady', cls: 'bg-critical-50 text-critical-700' }

  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm" data-testid={`readiness-${row.organisation_id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm">
          <span className="font-semibold text-ground-900">{row.organisation}</span>
          <span className="text-ground-400"> · {formatMonth(month)}</span>
        </p>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${chip.cls}`}>{t(chip.key)}</span>
      </div>

      {row.problems.length > 0 && (
        <ul className="mt-3 space-y-2">
          {orderedProblems(row.problems).map((p: InvoiceProblem) => (
            <li key={p.code} className="grid grid-cols-[5.5rem_1fr] items-baseline gap-2 text-sm">
              <span className={`w-fit rounded-full px-2 py-0.5 text-[11px] font-semibold ${p.overridable
                ? 'bg-caution-100 text-caution-700' : 'bg-critical-50 text-critical-700'}`}>
                {t(p.overridable ? 'admin.billing.invoice.warning' : 'admin.billing.invoice.mustFix')}
              </span>
              <span className="text-ground-700">{p.message}</span>
            </li>
          ))}
        </ul>
      )}
      {/* ⚠ TWO DESTINATIONS, because the two blank forms now live on different pages and a
          single "Settings" link would send half the readers to the wrong one. Who is BILLING is
          platform-wide; who is BILLED belongs to the organisation. */}
      {settingsHref(row.problems, row.organisation_code).map((dest) => (
        <Link key={dest.code} href={dest.href}
          className="mt-2 block text-sm text-primary-600 underline">
          {t(`admin.billing.invoice.fix.${dest.code}`)}
        </Link>
      ))}

      {mode === 'override' && (
        <label className="mt-3 block">
          <span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.overrideReason')}</span>
          <textarea className={`${INPUT} min-h-[4rem]`} value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-label={t('admin.billing.invoice.overrideReason')} />
        </label>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {mode === 'ready' && (
          <button type="button" className={PRIMARY} disabled={busy}
            onClick={() => onIssue(row.organisation_id, '')}>
            {t('admin.billing.invoice.issue')}
          </button>
        )}
        {mode === 'override' && (
          <button type="button" className={PRIMARY} disabled={busy || reason.trim() === ''}
            onClick={() => onIssue(row.organisation_id, reason.trim())}>
            {t('admin.billing.invoice.issueAnyway')}
          </button>
        )}
        {mode === 'blocked' && (
          <>
            {/* Shown disabled rather than hidden: the reader should see there IS an action, and
                that the list above is what stands between them and it. */}
            <button type="button" className={PRIMARY} disabled>{t('admin.billing.invoice.issue')}</button>
            <span className="text-xs text-ground-400">{t('admin.billing.invoice.blockedHelp')}</span>
          </>
        )}
      </div>
    </div>
  )
}

export default function InvoiceToIssue({ data, busy, t, onMonth, onIssue }: {
  data: InvoicesPayload
  busy: boolean
  t: T
  onMonth: (month: string) => void
  onIssue: (orgId: number, month: string, reason: string, issuedOn: string) => void
}) {
  const today = todayIso()
  const month = data.month || ''
  // ⚠ RE-DEFAULTED WHENEVER THE MONTH CHANGES, and the parent does it by passing `key={month}`,
  // which remounts this panel. Keeping a stale 15 September while the reader switches to July
  // would date July's bill inside the month it bills — the server would then refuse a value
  // nobody typed. A `key` rather than an effect because the default is derived, not fetched.
  const [issuedOn, setIssuedOn] = useState(() => defaultIssueDate(month, today))
  const problem = issueDateProblem(month, issuedOn, today)

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-ground-0 p-4 shadow-sm">
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.monthLabel')}</span>
          <select className={`${INPUT} w-auto`} value={month} disabled={busy}
            aria-label={t('admin.billing.invoice.monthLabel')}
            onChange={(e) => onMonth(e.target.value)}>
            {/* The server's chosen month is always an option, even when it predates the window —
                otherwise a select would silently show a different month from the cards below it —
                but it keeps its place in DATE order rather than being hoisted to the top, and the
                list is floored at the ledger's first month. See `monthOptions`. */}
            {monthOptions(today, month, data.first_billable_month).map((m) => (
              <option key={m} value={m}>{formatMonth(m)}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.issueDate')}</span>
          {/* ⚠ A plain text box, not type="date": a native picker follows the BROWSER's locale and
              can report no value at all until it is satisfied — the receipt form's own note. */}
          <input type="text" inputMode="numeric" placeholder="YYYY-MM-DD" className={`${INPUT} w-36`}
            value={issuedOn} disabled={busy} data-testid="issue-date"
            aria-label={t('admin.billing.invoice.issueDate')}
            onChange={(e) => setIssuedOn(e.target.value)} />
        </label>
        <p className="max-w-sm text-xs text-ground-500">
          {problem
            ? <span className="text-critical-600" role="alert">{t(`admin.billing.invoice.${problem}`)}</span>
            : t('admin.billing.invoice.issueDateHelp', { day: String(data.issue_day ?? 15) })}
        </p>
      </div>

      <p className="text-sm text-ground-500">{t('admin.billing.invoice.superLead', {
        month: formatMonth(month), day: String(data.issue_day ?? 15),
      })}</p>

      {(data.readiness || []).map((row) => (
        <ReadinessCard key={row.organisation_id} row={row} month={month}
          busy={busy || problem !== ''} t={t}
          onIssue={(orgId, reason) => onIssue(orgId, month, reason, issuedOn.trim())} />
      ))}
    </div>
  )
}
