'use client'
/**
 * Programme Overview — the page you land on inside a gift, and the answer to "how is this doing?".
 *
 * ⚠⚠ **THE PAGE RENDERS WHAT ARRIVED, NEVER WHAT A ROLE "SHOULD" SEE.** `SECTIONS_BY_ROLE` on the
 * server chooses the key set before anything is serialised, so a reviewer's payload has no `money`
 * key at all and a finance admin's has no `funnel`. Every block below is gated on `has(data, …)`
 * and on nothing else. There is deliberately no `if (role === …)` in this file: a page that
 * fetched everything and drew a subset would be a side door into Payments and Spending for the
 * two roles the menu already withholds them from, and a client-side gate is one edit away from
 * being wrong.
 *
 * ⚠ **MONEY IS A STRING FROM THE SERVER TO THE SCREEN.** `rm()` groups the thousands of the string
 * it was given; `num()` parses only to give a bar a height. Nothing parsed is ever displayed.
 *
 * ⚠ **THE REPORT DATE SITS AT THE TOP, ONCE** — the same rule the Spending page follows. It is a
 * fact about the WHOLE page (every spending figure stops there), not about one section, and it is
 * derived from the newest transaction we hold rather than written down anywhere.
 *
 * ⚠ **SEVERAL GIFTS AND NONE CHOSEN IS A REAL STATE, AND IT GETS A NEUTRAL HEADING** — never
 * `ChooseProgramme`. This page READS; with nothing chosen it describes everything the organisation
 * fence allows, which is a true answer, just a less specific one. That is the line the Applications
 * and Payments pages already draw (`NavItem.needsProgramme`), and it is why this row carries no
 * `needsProgramme` of its own.
 *
 * ⚠ **THE REVIEWER'S FRAMING IS NOT A STYLE CHOICE** (`reviewerDetail.ts`). These are unpaid
 * volunteers: no score, no percentile, no band on the PERSON. Only the case's own clock is banded,
 * and the turnaround is phrased as how long a STUDENT waited.
 */

import { useCallback, useEffect, useState } from 'react'

import { Donut, BarChart, LineChart, type ChartFigure } from '@/components/admin/charts/Charts'
import TableFrame, { TH, TH_RIGHT } from '@/components/admin/TableFrame'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getProgrammeOverview, type ProgrammeOverview } from '@/lib/admin-api'
import { APPLICATION_STATUSES, statusLabelKey } from '@/lib/applicationStatus'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  FULL_BOX, SMALL_AXIS_BOX, bandTone, has, monthOf, monthTicks, num, rm, thinTicks, weekLabel,
} from '@/lib/programmeOverview'
import { useProgrammeParam } from '@/lib/programmeScope'

/** The eleven category codes the server always sends, in the order it sends them. Written out so
 *  the i18n guard can enumerate them and so a label is never assembled from an unknown code. */
const CATEGORY_CODES = [
  'food', 'groceries', 'transport', 'study', 'phone', 'hostel',
  'health', 'clothing', 'transfer', 'unsorted', 'none',
]

const K = 'admin.programmeOverview'

/** A headline figure. Deliberately not a component per section — a tile is a tile. */
function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-ground-200 bg-ground-0 p-3.5">
      <div className="text-[11px] font-medium text-ground-500">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums text-ground-900">{value}</div>
      {note && <div className="mt-0.5 text-[11px] text-ground-400">{note}</div>}
    </div>
  )
}

function Card({ title, note, children, testId }: {
  title: string
  note?: string
  children: React.ReactNode
  testId?: string
}) {
  return (
    <section className="rounded-xl border border-ground-200 bg-ground-0 p-4" data-testid={testId}>
      <h2 className="text-sm font-semibold text-ground-900">
        {title}
        {note && <span className="ml-2 text-xs font-normal text-ground-500">{note}</span>}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export default function ProgrammeOverviewPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/programme/overview', effectiveRole(role))
  // ⚠ WHICH GIFT — from the breadcrumb, sent as an EXPLICIT value the server re-fences on the
  // caller's own organisation (TD-241). `undefined` when several gifts exist and none is chosen;
  // the scope refuses to guess and the server then answers with everything the fence allows.
  const programme = useProgrammeParam()

  const [data, setData] = useState<ProgrammeOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token || !allowed) { setLoading(false); return }
    setLoading(true)
    setError('')
    getProgrammeOverview(programme, { token })
      .then(setData)
      .catch(() => setError(t(`${K}.error`)))
      .finally(() => setLoading(false))
    // ⚠ `programme` IS A DEPENDENCY. Switching gift in the breadcrumb must re-read, or the crumb
    // would name one gift while the figures described another.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed, programme])

  useEffect(() => { load() }, [load])

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const money = data?.money
  const attention = data?.attention
  const appSeries = data?.applications_series
  const moneySeries = data?.money_series
  const intake = data?.intake
  const mine = data?.mine
  const qc = data?.qc

  const rmFig = (v: string) => `RM${rm(v)}`
  /** ⚠ SIGNED. `rm` knows nothing about a minus, so a negative gap would render `RM-40.00`, which
   *  reads as a typo rather than as a number. The gap IS allowed to be negative — a parent may top
   *  a wallet up — and that is the month somebody should ask about. */
  const signed = (v: string) =>
    (num(v) < 0 ? `-RM${rm(String(Math.abs(num(v)).toFixed(2)))}` : `RM${rm(v)}`)

  /** ⚠ MONTHS ARE NAMED, NOT NUMBERED (owner, 2026-09-15): "Jul", not "07/2026". The short
   *  names live in the locale files, so the axis reads the same way as the rest of the page. */
  const monthName = (month: number) => t(`${K}.months.${month}`)
  const monthTick = (iso: string) => monthName(monthOf(iso))

  const perWeek = moneySeries?.per_student_per_week ?? []
  const overall = moneySeries?.per_student_overall ?? null
  /* ⚠ THE FIGURE BENEATH A WEEKLY CHART IS THE WHOLE-PERIOD ONE, not every week's value. Fifty
     weekly figures in a row are not "the numbers a person would quote", they are noise; the
     average over the whole period is the number, and the line is the movement. */
  const averageFigures: ChartFigure[] = overall
    ? [{ label: t(`${K}.series.overallAverage`), value: rmFig(overall.average) }] : []
  const transactionFigures: ChartFigure[] = overall
    ? [{ label: t(`${K}.series.overallTransactions`), value: overall.transactions_per_student }]
    : []
  const weekTicks = monthTicks(perWeek.map((r) => r.week), monthName)
  const months = moneySeries?.money_per_month ?? []
  /* ⚠ THE TOTALS ARE THE LAST MONTH'S RUNNING FIGURES, read straight from the server — never
     summed here. `released_cum`, `spent_cum` and `gap` on the final row ARE payments to date,
     spending to date and the balance, to the cent. */
  const lastMonth = months.length > 0 ? months[months.length - 1] : null

  return (
    <div data-testid="programme-overview">
      <h1 className="text-2xl font-semibold text-ground-900">
        {data?.programme
          ? t(`${K}.titleFor`, { name: data.programme.name })
          : t(`${K}.title`)}
      </h1>
      <p className="mt-1 text-sm text-ground-600">{t(`${K}.subtitle`)}</p>
      {data?.data_to && (
        <p className="mt-1 text-sm text-ground-500" data-testid="overview-data-to">
          {t(`${K}.asAt`, { date: formatDate(data.data_to) })}
        </p>
      )}

      {error && <p className="mt-4 text-sm text-critical-600" role="alert">{error}</p>}
      {loading && !data && <p className="mt-4 text-sm text-ground-500">{t(`${K}.loading`)}</p>}

      {/* ── The funnel. ALL THIRTEEN STATUSES, zero-filled, because a stage at zero is
          information and an absent stage cannot be told from an empty one. No aggregate is
          invented here: "awarded" on this page means the status called awarded, nothing more. ── */}
      {has(data, 'funnel') && data?.funnel && (
        <section className="mt-6" data-testid="overview-funnel">
          <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.funnel.title`)}</h2>
          <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            <Tile label={t(`${K}.funnel.total`)} value={String(data.funnel.total)} />
            {APPLICATION_STATUSES.map((status) => (
              <Tile key={status} label={t(statusLabelKey(status))}
                value={String(data.funnel?.by_status[status] ?? 0)} />
            ))}
          </div>
        </section>
      )}

      {/* ── The money strip. Byte-equal to the Payments footer, and it must stay that way: the
          server floors `remaining` per ROW and the page re-formats nothing. ── */}
      {has(data, 'money') && money && (
        <section className="mt-6" data-testid="overview-money">
          <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.money.title`)}</h2>
          <div className="mt-3 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            <Tile label={t(`${K}.money.committed`)} value={rmFig(money.committed)}
              note={t(`${K}.money.students`, { count: String(money.students) })} />
            <Tile label={t(`${K}.money.paid`)} value={rmFig(money.paid)} />
            <Tile label={t(`${K}.money.remaining`)} value={rmFig(money.remaining)} />
            <Tile label={t(`${K}.money.spent`)} value={rmFig(money.spent)} />
          </div>
        </section>
      )}

      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        {/* ⚠ `due_soon` and `overdue` are SUBSETS of "with a reviewer", not a partition of it — a
            case does not stop being with its reviewer the moment it gets late. */}
        {has(data, 'attention') && attention && (
          <Card title={t(`${K}.attention.title`)} testId="overview-attention">
            <dl className="text-sm">
              {([
                ['unassigned', attention.unassigned],
                ['withReviewer', attention.with_reviewer],
                ['dueSoon', attention.due_soon],
                ['overdue', attention.overdue],
                ['awaitingQc', attention.awaiting_qc],
              ] as const).map(([key, value]) => (
                <div key={key}
                  className="flex items-center justify-between border-b border-ground-100 py-1.5 last:border-b-0">
                  <dt className="text-ground-700">{t(`${K}.attention.${key}`)}</dt>
                  <dd className="tabular-nums font-semibold text-ground-900">{value}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}

        {/* ⚠ THE DATES DESCRIBE THE ROUND; THEY DO NOT OPEN OR CLOSE IT. `is_open` is the switch,
            and a round with no window is normal rather than broken. */}
        {has(data, 'intake') && (
          <Card title={t(`${K}.intake.title`)} testId="overview-intake">
            {!intake ? (
              <p className="text-sm text-ground-500">{t(`${K}.intake.none`)}</p>
            ) : (
              <div className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ground-900">{intake.name}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    intake.is_open ? 'bg-positive-100 text-positive-800'
                      : 'bg-ground-100 text-ground-600'}`}>
                    {t(`${K}.intake.${intake.is_open ? 'open' : 'closed'}`)}
                  </span>
                </div>
                <p className="mt-2 text-ground-700">
                  {t(`${K}.intake.window`, {
                    from: intake.opens_on ? formatDate(intake.opens_on) : t(`${K}.intake.notStated`),
                    to: intake.closes_on ? formatDate(intake.closes_on) : t(`${K}.intake.notStated`),
                  })}
                </p>
                {intake.finished_at && (
                  <p className="mt-1 text-ground-500">
                    {t(`${K}.intake.finished`, { date: formatDate(intake.finished_at) })}
                  </p>
                )}
              </div>
            )}
          </Card>
        )}
      </div>

      {/* ── How the applications arrived, and how the awards followed ── */}
      {has(data, 'applications_series') && appSeries && (
        <div className="mt-3 grid gap-3 lg:grid-cols-2" data-testid="overview-applications-series">
          <Card title={t(`${K}.series.applicationsPerWeek`)}>
            <BarChart
              testId="chart-applications-per-week"
              label={t(`${K}.chart.applicationsLabel`)}
              series={[{ key: 'count', className: 'fill-brand-shape',
                         values: appSeries.applications_per_week.map((r) => r.count) }]}
              columns={appSeries.applications_per_week.map((r) => weekLabel(r.week))}
              figures={appSeries.applications_per_week.map((r) => ({
                label: weekLabel(r.week), value: String(r.count) }))}
            />
          </Card>
          <Card title={t(`${K}.series.awardsPerMonth`)}>
            <BarChart
              testId="chart-awards-per-month"
              label={t(`${K}.chart.awardsLabel`)}
              series={[{ key: 'count', className: 'fill-brand-shape',
                         values: appSeries.awards_per_month.map((r) => r.count) }]}
              columns={appSeries.awards_per_month.map((r) => monthTick(r.month))}
              ticks={thinTicks(appSeries.awards_per_month.map((r, i) => (
                { index: i, label: monthTick(r.month) })))}
              figures={appSeries.awards_per_month.map((r) => ({
                label: monthTick(r.month), value: String(r.count) }))}
            />
          </Card>
        </div>
      )}

      {/* ── The money over time: what we released, what was spent, and what is still in wallets ── */}
      {has(data, 'money_series') && moneySeries && (
        <div className="mt-3 space-y-3" data-testid="overview-money-series">
          <Card title={t(`${K}.series.moneyPerMonth`)} note={t(`${K}.series.gapNote`)}>
            <BarChart
              box={FULL_BOX}
              testId="chart-money-per-month"
              label={t(`${K}.chart.moneyLabel`)}
              series={[
                { key: 'released', className: 'fill-brand-shape',
                  values: moneySeries.money_per_month.map((r) => num(r.released)) },
                { key: 'spent', className: 'fill-ground-300',
                  values: moneySeries.money_per_month.map((r) => num(r.spent)) },
              ]}
              line={{ className: 'stroke-ground-600',
                      values: moneySeries.money_per_month.map((r) => num(r.gap)) }}
              columns={moneySeries.money_per_month.map((r) => monthTick(r.month))}
              ticks={thinTicks(moneySeries.money_per_month.map((r, i) => (
                { index: i, label: monthTick(r.month) })))}
              figures={moneySeries.money_per_month.map((r) => ({
                label: monthTick(r.month), value: signed(r.gap) }))}
            />

            {/* ⚠ THREE FIGURES, NOT A TABLE (owner, 2026-09-15). Payments to date, spending to
                date, and what is still in wallets — the last month's running figures, which the
                server already carries. A month-by-month table was the same information said
                four times per row; anybody who needs a month has the bars and the line. */}
            {lastMonth && (
              <dl className="mt-4 grid grid-cols-3 gap-3" data-testid="money-totals">
                <div className="rounded-lg border border-ground-200 p-3">
                  <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.series.payments`)}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ground-900">
                    {rmFig(lastMonth.released_cum)}
                  </dd>
                </div>
                <div className="rounded-lg border border-ground-200 p-3">
                  <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.series.spending`)}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ground-900">
                    {rmFig(lastMonth.spent_cum)}
                  </dd>
                </div>
                <div className="rounded-lg border border-ground-200 p-3">
                  <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.series.balance`)}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ground-900">
                    {signed(lastMonth.gap)}
                  </dd>
                </div>
              </dl>
            )}
          </Card>

          <div className="grid gap-3 lg:grid-cols-3">
            {/* ⚠ THE DENOMINATOR IS NAMED IN WORDS BENEATH THE CHART. "Average spend" is
                meaningless without "of whom", and the server's answer is: students with a live
                wallet that week. */}
            <Card title={t(`${K}.series.average`)}>
              <LineChart
                box={SMALL_AXIS_BOX}
                testId="chart-average-per-student"
                label={t(`${K}.chart.averageLabel`)}
                values={perWeek.map((r) => num(r.average))}
                columns={perWeek.map((r) => weekLabel(r.week))}
                ticks={weekTicks}
                yAxis={{ label: t(`${K}.chart.yRinggit`), format: (v) => `RM${Math.round(v)}` }}
                figures={averageFigures}
              />
              {overall && (
                <p className="mt-2 text-[11px] text-ground-400">
                  {t(`${K}.series.ofStudentsOverall`, { count: String(overall.students) })}
                </p>
              )}
            </Card>

            {/* ⚠ TRANSACTIONS, NOT ITEMS. A Vircle row is one card transaction and carries no
                item count, so "items bought" is not a question this data can answer. */}
            <Card title={t(`${K}.series.transactions`)}>
              <LineChart
                box={SMALL_AXIS_BOX}
                testId="chart-transactions-per-student"
                label={t(`${K}.chart.transactionsLabel`)}
                values={perWeek.map((r) => num(r.transactions_per_student))}
                columns={perWeek.map((r) => weekLabel(r.week))}
                ticks={weekTicks}
                yAxis={{ label: t(`${K}.chart.yTransactions`),
                         format: (v) => String(Math.round(v * 10) / 10) }}
                figures={transactionFigures}
              />
              <p className="mt-2 text-[11px] text-ground-400">{t(`${K}.series.transactionsNote`)}</p>
            </Card>

            {/* ⚠ ELEVEN SLICES, ALWAYS. "Not yet sorted" and "could not be sorted" are DIFFERENT
                states and neither is ever merged away or hidden at zero — that is what would let
                the other nine read as complete when they are not. */}
            <Card title={t(`${K}.series.byCategory`)}>
              <Donut
                testId="chart-by-category"
                label={t(`${K}.chart.categoryLabel`)}
                rows={moneySeries.by_category
                  .filter((r) => CATEGORY_CODES.indexOf(r.code) !== -1)
                  .map((r) => ({
                    code: r.code,
                    label: t(`${K}.category.${r.code}`),
                    display: rmFig(r.total),
                    total: r.total,
                  }))}
              />
            </Card>
          </div>
        </div>
      )}

      {/* ── A reviewer's own work, and nothing else ── */}
      {has(data, 'mine') && mine && (
        <section className="mt-6 space-y-3" data-testid="overview-mine">
          <div className="grid grid-cols-3 gap-2.5">
            <Tile label={t(`${K}.mine.open`)} value={String(mine.open)} />
            <Tile label={t(`${K}.mine.dueSoon`)} value={String(mine.due_soon)} />
            <Tile label={t(`${K}.mine.overdue`)} value={String(mine.overdue)} />
          </div>

          <Card title={t(`${K}.mine.title`)}>
            {mine.cases.length === 0 ? (
              <p className="text-sm text-ground-500">{t(`${K}.mine.none`)}</p>
            ) : (
              <>
                <div className="space-y-2 md:hidden" data-testid="mine-cards">
                  {mine.cases.map((c) => (
                    <div key={c.id} className="rounded-lg border border-ground-200 p-2.5">
                      <div className="text-sm font-semibold text-ground-900">
                        {c.ref} {c.applicant_name}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-ground-600">
                        <span>{t(statusLabelKey(c.status))}</span>
                        <span>{t(`${K}.mine.dueBy`, { date: formatDate(c.due_at) })}</span>
                        <span className={`rounded-full px-2 py-0.5 font-semibold ${bandTone(c.band)}`}>
                          {t(`${K}.band.${c.band}`)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <TableFrame className="hidden md:block" minWidth={560}
                  label={t(`${K}.mine.title`)}>
                  <table className="w-full text-sm">
                    <thead className="border-b border-ground-200 bg-ground-50">
                      <tr>
                        <th className={TH}>{t(`${K}.mine.applicant`)}</th>
                        <th className={TH}>{t(`${K}.mine.status`)}</th>
                        <th className={TH}>{t(`${K}.mine.assigned`)}</th>
                        <th className={TH}>{t(`${K}.mine.due`)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mine.cases.map((c) => (
                        <tr key={c.id} className="border-b border-ground-100 last:border-b-0">
                          <td className="px-4 py-2 font-medium text-ground-900">
                            {c.ref} {c.applicant_name}
                          </td>
                          <td className="px-4 py-2 text-ground-700">{t(statusLabelKey(c.status))}</td>
                          <td className="px-4 py-2 tabular-nums text-ground-700">
                            {formatDate(c.assigned_at)}
                          </td>
                          <td className="px-4 py-2">
                            <span className="tabular-nums text-ground-700">{formatDate(c.due_at)}</span>
                            <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${bandTone(c.band)}`}>
                              {t(`${K}.band.${c.band}`)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableFrame>
              </>
            )}
          </Card>

          {/* ⚠ NO SCORE, NO PERCENTILE, NO BAND ON THE PERSON. The turnaround is stated as the
              STUDENT'S WAIT, because that is whose experience it describes. */}
          <Card title={t(`${K}.mine.paceTitle`)}>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.mine.completed`)}</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-ground-900">
                  {mine.pace.completed}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.mine.waited`)}</dt>
                <dd className="mt-0.5 text-sm text-ground-700">
                  {mine.pace.turnaround_days === null
                    ? t(`${K}.mine.turnaroundUnknown`)
                    : t(`${K}.mine.turnaround`, { days: String(mine.pace.turnaround_days) })}
                </dd>
              </div>
            </dl>
          </Card>
        </section>
      )}

      {/* ── The QC queue: cases a reviewer has submitted and nobody has checked ── */}
      {has(data, 'qc') && qc && (
        <section className="mt-6 space-y-3" data-testid="overview-qc">
          <div className="grid grid-cols-2 gap-2.5">
            <Tile label={t(`${K}.qc.awaiting`)} value={String(qc.awaiting)} />
            <Tile label={t(`${K}.qc.oldest`)}
              value={qc.oldest_waiting_days === null ? '—' : String(qc.oldest_waiting_days)} />
          </div>

          <Card title={t(`${K}.qc.title`)}>
            {qc.cases.length === 0 ? (
              <p className="text-sm text-ground-500">{t(`${K}.qc.none`)}</p>
            ) : (
              <>
                <div className="space-y-2 md:hidden" data-testid="qc-cards">
                  {qc.cases.map((c) => (
                    <div key={c.id} className="rounded-lg border border-ground-200 p-2.5">
                      <div className="text-sm font-semibold text-ground-900">
                        {c.ref} {c.applicant_name}
                      </div>
                      <div className="mt-1 text-[11px] text-ground-600">
                        {t(`${K}.qc.waitingDays`, { days: String(c.waiting_days ?? 0) })}
                      </div>
                    </div>
                  ))}
                </div>

                <TableFrame className="hidden md:block" minWidth={480}
                  label={t(`${K}.qc.title`)}>
                  <table className="w-full text-sm">
                    <thead className="border-b border-ground-200 bg-ground-50">
                      <tr>
                        <th className={TH}>{t(`${K}.mine.applicant`)}</th>
                        <th className={TH}>{t(`${K}.qc.since`)}</th>
                        <th className={TH_RIGHT}>{t(`${K}.qc.waiting`)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {qc.cases.map((c) => (
                        <tr key={c.id} className="border-b border-ground-100 last:border-b-0">
                          <td className="px-4 py-2 font-medium text-ground-900">
                            {c.ref} {c.applicant_name}
                          </td>
                          <td className="px-4 py-2 tabular-nums text-ground-700">
                            {c.since ? formatDate(c.since) : '—'}
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums text-ground-900">
                            {c.waiting_days === null ? '—' : c.waiting_days}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableFrame>
              </>
            )}
          </Card>

          {/* ⚠ PACE IS KEYED ON EMAIL on the server, because nothing records "who QC'd this". It is
              an approximation and is stated as one — see `programme_overview.qc_queue`. */}
          <Card title={t(`${K}.qc.paceTitle`)}>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.qc.completed`)}</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-ground-900">
                  {qc.pace.completed}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium text-ground-500">{t(`${K}.mine.waited`)}</dt>
                <dd className="mt-0.5 text-sm text-ground-700">
                  {qc.pace.turnaround_days === null
                    ? t(`${K}.mine.turnaroundUnknown`)
                    : t(`${K}.qc.turnaround`, { days: String(qc.pace.turnaround_days) })}
                </dd>
              </div>
            </dl>
          </Card>
        </section>
      )}
    </div>
  )
}
