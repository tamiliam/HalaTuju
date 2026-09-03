'use client'
// Payments landing (P2) — the run list, a "New payment run" date dialog, and the funding
// summary. Entered from the Administration panel's Payments card (no top-level nav entry); the
// layout keeps "Administration" active here.
// Access: admin / org_admin / finance / super. Finance may READ everything here but creates
// nothing — the "New payment run" control is hidden for it (the backend 403s it anyway).

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { formatDate } from '@/lib/formatDate'
import {
  getPaymentRuns, createPaymentRun, getFundingSummary, getAdminScopes,
  type PaymentRunSummary, type FundingSummary, type AdminScopeProgramme,
} from '@/lib/admin-api'
import { statusPill, monthLabel } from '@/lib/paymentStatus'

// Whole ringgit with thousands grouping, matching the run-detail table ("RM 2,200").
// Hand-formatted so server and browser render identically (no locale drift).
const rm = (v: string | number) => {
  const n = Number(v)
  return Number.isFinite(n) ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',') : String(v)
}

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function PaymentsLandingPage() {
  const { token, role } = useAdminAuth()
  const { t, locale } = useT()
  const router = useRouter()
  const r = effectiveRole(role)
  const allowed = canAccess('/admin/payments', r)
  // Finer than the route: finance may READ a run and sign the finance check, but may never
  // create, edit, cancel or price one (role matrix). That stays a local capability check.
  const canCreate = allowed && r !== 'finance'

  const [runs, setRuns] = useState<PaymentRunSummary[]>([])
  const [funding, setFunding] = useState<FundingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [payDate, setPayDate] = useState('')
  const [payMonth, setPayMonth] = useState('')   // 'YYYY-MM'; defaults to the pay date's month
  const [busy, setBusy] = useState(false)
  // A cancelled run is never deleted (the service has no delete — `payments.cancel` only flips
  // the status, so a superseded run stays on the record). It is still clutter on the list, so
  // hide it behind a toggle rather than dropping it: the row explains, e.g., why a re-created
  // run is referenced `PR-2026-07-26-02`. Client-side — the list is one run per month per org
  // and is fetched whole, so a query param would split filtering across two layers for nothing
  // (same call as the sponsor pool's status filter, decisions.md 2026-07-21).
  const [showCancelled, setShowCancelled] = useState(false)
  // The gifts this admin's OWN organisation runs — the picker's options (Sabah S1).
  //
  // ⚠ Filtered on `owning_org_id` because that is literally what the server does: the create
  // endpoint reads `org = admin.owning_organisation` even for a super. Offering a super the
  // programmes of an organisation they are merely LOOKING at would build a picker whose choices
  // the server answers 404 to.
  //
  // ⚠ NOT a fence, and must never become one. `scopes` is a display list derived from the same
  // `owning_organisation` the fence uses; a client ignoring it reaches exactly the same data.
  const [programmes, setProgrammes] = useState<AdminScopeProgramme[]>([])
  const [programmeId, setProgrammeId] = useState<number | null>(null)

  useEffect(() => {
    if (!token || !allowed) { setLoading(false); return }
    getPaymentRuns({ token })
      .then((d) => setRuns(d.runs))
      .catch(() => setError(t('admin.payments.loadFailed')))
      .finally(() => setLoading(false))
    // Best-effort: the funding summary is a supplementary section, so a failure here hides it
    // rather than breaking the runs list this page exists for.
    getFundingSummary({ token }).then(setFunding).catch(() => setFunding(null))
    // Also best-effort, and the fallback is SAFE rather than merely quiet: with no list the
    // picker does not render and no `programme_id` is sent, which is exactly today's behaviour —
    // the server then uses the org's only gift, or refuses with `programme_required` if there are
    // two. A failed fetch can therefore never cause a run to be paid from the wrong fund.
    getAdminScopes(locale, { token })
      .then((s) => setProgrammes(
        (s?.programmes ?? []).filter((p) => p.organisation_id === role?.owning_org_id)))
      .catch(() => setProgrammes([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  // ⚠ ONE gift → NO picker, and nothing sent. A control with a single option is furniture, and
  // BrightPath must see the screen it has always seen. The moment a second gift exists the
  // operator states which one — never a default, because a preselected fund is how one
  // benefactor's money quietly pays another's students (`payments.create_run`'s own argument for
  // taking the programme positionally).
  const needsProgramme = programmes.length > 1
  const cancelledCount = runs.filter((r) => r.status === 'cancelled').length
  const visibleRuns = showCancelled ? runs : runs.filter((r) => r.status !== 'cancelled')

  const create = async () => {
    if (!token || !payDate) return
    setBusy(true); setError('')
    try {
      // `null` when the picker is not shown — the org runs one gift, so the server resolves it
      // unambiguously. See `createPaymentRun`'s docstring for why absence is safe here.
      const run = await createPaymentRun(
        payDate, payMonth || payDate.slice(0, 7), needsProgramme ? programmeId : null, { token })
      router.push(`/admin/payments/${run.id}`)
    } catch (e) {
      const code = (e as { code?: string })?.code
      // 'too_early' = advance pay before the 25th of the month preceding the covered month.
      // The backend sends the earliest valid date with the error (the rule lives only in
      // payments.earliest_payment_date), so we name it rather than restate the rule here.
      const earliest = String((e as { body?: { earliest?: string } })?.body?.earliest ?? '')
      setError(code === 'past_date' ? t('admin.payments.pastDate')
        : code === 'too_early' ? t('admin.payments.tooEarly', { date: earliest || '' })
        : code === 'no_org' ? t('admin.payments.noOrg')
        // The server refuses rather than picking when the organisation runs more than one gift.
        // ⚠ It is reachable even with the picker shipped — a programme created between this
        // page's load and the Create press is not in `programmes`, so the screen would send
        // nothing. An unexplained failure on a money screen is the thing this sprint exists to
        // remove, so it gets real words rather than falling through to `admin.actionFailed`.
        : code === 'programme_required' ? t('admin.payments.programmeRequired')
        : (e instanceof Error ? e.message : t('admin.actionFailed')))
      setBusy(false)
    }
  }

  const inputCls = 'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-info-500 focus:border-info-500'

  return (
    <div className="max-w-4xl font-plex">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ground-900">{t('admin.payments.title')}</h1>
          <p className="mt-1 text-sm text-ground-500">{t('admin.payments.subtitle')}</p>
        </div>
        {canCreate && (
          <button onClick={() => { setPayDate(''); setPayMonth(''); setProgrammeId(null); setError(''); setDialogOpen(true) }}
            className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            + {t('admin.payments.newRun')}
          </button>
        )}
      </div>

      {error && <div className="mt-4 rounded-lg bg-critical-50 border border-critical-200 p-3 text-sm text-critical-600">{error}</div>}

      <div className="mt-6 bg-ground-0 rounded-xl shadow-sm border overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-ground-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.reference')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.paymentDate')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.month')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.status')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.students')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.total')}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-ground-100">
            {visibleRuns.map((r) => (
              <tr key={r.id} className="hover:bg-info-50/40">
                <td className="px-4 py-3">
                  <Link href={`/admin/payments/${r.id}`} className="font-medium text-info-600 hover:underline">{r.reference}</Link>
                </td>
                <td className="px-4 py-3 text-ground-600">{formatDate(r.payment_date)}</td>
                <td className="px-4 py-3 text-ground-600">{monthLabel(r.period_month)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusPill(r.status)}`}>
                    {t(`admin.payments.status.${r.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ground-700 tabular-nums">{r.students}</td>
                <td className="px-4 py-3 text-ground-900 font-medium tabular-nums">RM {Number(r.total)}</td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/admin/payments/${r.id}`} className="text-ground-400 hover:text-info-600">›</Link>
                </td>
              </tr>
            ))}
            {!loading && visibleRuns.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-ground-400">{t('admin.payments.empty')}</td></tr>
            )}
            {loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-ground-400">{t('common.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Only offered when there is something to reveal — no dead control on a clean list. */}
      {!loading && cancelledCount > 0 && (
        <button type="button" onClick={() => setShowCancelled((v) => !v)}
          className="mt-3 text-xs font-medium text-ground-500 hover:text-ground-700">
          {showCancelled
            ? t('admin.payments.hideCancelled')
            : t('admin.payments.showCancelled', { count: String(cancelledCount) })}
        </button>
      )}

      {/* Funding summary — the funding-side view of the same cohort the runs pay. Server-side
          allowlist (FundingSummaryRowSerializer); names are plain text, never links into an
          applicant page (finance has no B40 route, and a role-dependent link is worse than
          none for everyone). */}
      {funding && funding.rows.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-bold text-ground-900">{t('admin.payments.funding.title')}</h2>
          <p className="mt-1 text-sm text-ground-500">{t('admin.payments.funding.subtitle')}</p>
          <div className="mt-3 bg-ground-0 rounded-xl shadow-sm border overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-ground-50 border-b">
                <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.student')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.status')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.award')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.paid')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.remaining')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.wallet')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.lastRun')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ground-100">
                {funding.rows.map((r) => (
                  <tr key={r.application_id} className="hover:bg-info-50/40">
                    <td className="px-4 py-3">
                      <span className="font-medium text-ground-900">{r.name || '—'}</span>
                      {r.ref && <span className="ml-2 text-xs text-ground-400">{r.ref}</span>}
                    </td>
                    <td className="px-4 py-3 text-ground-600">{r.status ? t(`admin.payments.funding.state.${r.status}`) : '—'}</td>
                    <td className="px-4 py-3 text-ground-700 tabular-nums">RM {rm(r.award_amount)}</td>
                    <td className="px-4 py-3 text-ground-700 tabular-nums">RM {rm(r.paid_to_date)}</td>
                    <td className="px-4 py-3 font-medium text-ground-900 tabular-nums">RM {rm(r.remaining)}</td>
                    <td className="px-4 py-3 text-ground-500 tabular-nums">{r.vircle_id || '—'}</td>
                    {/* Request #5 (BrightPath, 2026-08-01): the date ALONE. The column is headed
                        with a question about WHEN, and the run reference beside it answered a
                        different question while earning very little — it is not clickable, and
                        reconciling a particular run means opening the payment runs list anyway.
                        The API still sends `reference`: it costs nothing, and making it a LINK to
                        its run is the shape the requester may still choose (quoted separately). */}
                    <td className="px-4 py-3 text-ground-600">
                      {r.last_run ? formatDate(r.last_run.payment_date) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-primary-50 border-t border-primary-100 font-semibold text-ground-900">
                <tr>
                  <td className="px-4 py-3">{t('admin.payments.funding.totals', { count: String(funding.totals.students) })}</td>
                  <td className="px-4 py-3" />
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.award_total)}</td>
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.paid_total)}</td>
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.remaining_total)}</td>
                  <td className="px-4 py-3" colSpan={2} />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setDialogOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-ground-900">{t('admin.payments.newRun')}</h2>
            {needsProgramme && (
              <>
                {/* First field on purpose: which fund the money leaves is a bigger decision than
                    when it leaves, and it is the one with no undo once a run is signed. */}
                <label htmlFor="run-programme" className="mt-4 block text-sm font-medium text-ground-700">
                  {t('admin.payments.programme')}
                </label>
                <select id="run-programme" className={`mt-1 ${inputCls}`}
                  value={programmeId === null ? '' : String(programmeId)}
                  onChange={(e) => setProgrammeId(e.target.value ? Number(e.target.value) : null)}>
                  {/* Blank first, and no auto-selection — the operator states the gift. */}
                  <option value="">{t('admin.payments.programmeChoose')}</option>
                  {programmes.map((p) => (
                    <option key={p.id} value={String(p.id)}>{p.name}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-ground-500">{t('admin.payments.programmeHint')}</p>
              </>
            )}
            {/* `htmlFor`/`id` added with the picker: these two labels were never associated with
                their inputs, so a screen reader announced an unnamed date field on a money form.
                Four attributes, no visual change. */}
            <label htmlFor="run-date" className="mt-4 block text-sm font-medium text-ground-700">{t('admin.payments.paymentDate')}</label>
            <input id="run-date" type="date" min={todayISO()} value={payDate} onChange={(e) => setPayDate(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-ground-500">{t('admin.payments.pastDateHint')}</p>
            <label htmlFor="run-month" className="mt-4 block text-sm font-medium text-ground-700">{t('admin.payments.paymentMonth')}</label>
            <input id="run-month" type="month" value={payMonth || payDate.slice(0, 7)} onChange={(e) => setPayMonth(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-ground-500">{t('admin.payments.paymentMonthHint')}</p>
            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
            <div className="mt-5 flex items-center justify-end gap-3">
              <button onClick={() => setDialogOpen(false)} disabled={busy} className="text-sm font-medium text-ground-500 hover:text-ground-700">{t('common.cancel')}</button>
              <button onClick={create} disabled={busy || !payDate || (needsProgramme && programmeId === null)} className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {busy ? t('common.loading') : t('admin.payments.createDraft')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
