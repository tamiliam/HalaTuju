'use client'
/**
 * The Overview's widgets, one component each — lifted OUT of the page unchanged.
 *
 * ⚠⚠ **THE PAGE NO LONGER KNOWS WHAT ORDER TO DRAW THEM IN.** An organisation arranges its own
 * Overview, so the server sends `sections` as an ORDER and the page maps it through
 * `SECTION_RENDERERS`. That is the whole reason these blocks are here rather than inline: a fixed
 * run of JSX cannot be reordered by a list, and a page that "sorted" its own JSX would be a second
 * spelling of the order, one edit away from disagreeing with the saved one.
 *
 * ⚠⚠ **EVERY BLOCK STILL RENDERS BY PRESENCE, NEVER BY ROLE** (`programmeOverview.has`). The
 * server chose the key set before anything was serialised and then narrowed it by the
 * organisation's layout; each component below is gated on its own slice being there and on
 * nothing else. There is deliberately no `if (role === …)` in this file either — a page that
 * fetched everything and drew a subset would be a side door into Payments and Spending for the two
 * roles the menu already withholds them from.
 *
 * ⚠ **MONEY IS A STRING FROM THE SERVER TO THE SCREEN.** `rm()` groups the thousands of the string
 * it was given; `num()` parses only to give a bar a height. Nothing parsed is ever displayed.
 *
 * ⚠ **THE REVIEWER'S FRAMING IS NOT A STYLE CHOICE** (`reviewerDetail.ts`). These are unpaid
 * volunteers: no score, no percentile, no band on the PERSON. Only the case's own clock is banded,
 * and the turnaround is phrased as how long a STUDENT waited.
 */

import { Donut, BarChart, LineChart, type ChartFigure } from '@/components/admin/charts/Charts'
import TableFrame, { TH, TH_RIGHT } from '@/components/admin/TableFrame'
import type { ProgrammeOverview } from '@/lib/admin-api'
import { APPLICATION_STATUSES, statusLabelKey } from '@/lib/applicationStatus'
import { formatDate } from '@/lib/formatDate'
import {
  FULL_AXIS_BOX, SMALL_AXIS_BOX, WIDE_AXIS_BOX, bandTone, monthOf, monthTicks, num,
  orderSlices, rm, rmAxis, thinTicks, weekLabel,
} from '@/lib/programmeOverview'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name, so every file that builds a
 *  key this way must spell it exactly like this or its keys go unchecked. */
const K = 'admin.programmeOverview'

/** The eleven category codes the server always sends, in the order it sends them. Written out so
 *  the i18n guard can enumerate them and so a label is never assembled from an unknown code. */
const CATEGORY_CODES = [
  'food', 'groceries', 'transport', 'study', 'phone', 'hostel',
  'health', 'clothing', 'transfer', 'unsorted', 'none',
]

/** The translator handle, as `useT` hands it over. Passed in rather than read from the context
 *  here, so a section stays a plain function of its data and the tests can hand it a stub. */
export type Translate = (key: string, params?: Record<string, string>) => string

/** What every section is given: the whole payload (it reads only its own slice) and the words. */
export interface SectionProps {
  data: ProgrammeOverview
  t: Translate
}

/** A headline figure. Deliberately not a component per section — a tile is a tile. */
export function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-ground-200 bg-ground-0 p-3.5">
      <div className="text-[11px] font-medium text-ground-500">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums text-ground-900">{value}</div>
      {note && <div className="mt-0.5 text-[11px] text-ground-400">{note}</div>}
    </div>
  )
}

export function Card({ title, note, children, testId }: {
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

const rmFig = (v: string) => `RM${rm(v)}`

/** ⚠ SIGNED. `rm` knows nothing about a minus, so a negative gap would render `RM-40.00`, which
 *  reads as a typo rather than as a number. The gap IS allowed to be negative — a parent may top
 *  a wallet up — and that is the month somebody should ask about. */
const signed = (v: string) =>
  (num(v) < 0 ? `-RM${rm(String(Math.abs(num(v)).toFixed(2)))}` : `RM${rm(v)}`)

/** ⚠ MONTHS ARE NAMED, NOT NUMBERED (owner, 2026-09-15): "Jul", not "07/2026". The short
 *  names live in the locale files, so the axis reads the same way as the rest of the page. */
const monthNamer = (t: Translate) => (month: number) => t(`${K}.months.${month}`)

// ── The funnel. The server sends ALL THIRTEEN STATUSES, zero-filled; the page shows the ones with
//    a case in them (owner, 2026-09-18: "when the value is 0, skip the card"). The total is always
//    shown. No aggregate is invented here: "awarded" on this page means the status called awarded,
//    nothing more. ──
export function FunnelSection({ data, t }: SectionProps) {
  const funnel = data.funnel
  if (!funnel) return null
  return (
    <section className="mt-6" data-testid="overview-funnel">
      <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.funnel.title`)}</h2>
      <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        <Tile label={t(`${K}.funnel.total`)} value={String(funnel.total)} />
        {APPLICATION_STATUSES
          .filter((status) => (funnel.by_status[status] ?? 0) > 0)
          .map((status) => (
            <Tile key={status} label={t(statusLabelKey(status))}
              value={String(funnel.by_status[status] ?? 0)} />
          ))}
      </div>
    </section>
  )
}

// ── The money strip. Byte-equal to the Payments footer, and it must stay that way: the server
//    floors `remaining` per ROW and the page re-formats nothing. ──
export function MoneySection({ data, t }: SectionProps) {
  const money = data.money
  if (!money) return null
  return (
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
  )
}

// (The Intake card that sat beside Attention until 2026-09-18 is gone — owner: "doesn't add much
//  value". A round's state lives on Configuration; a round is now a FILTER, not a card.)
export function AttentionSection({ data, t }: SectionProps) {
  const attention = data.attention
  if (!attention) return null
  return (
    // ⚠ `due_soon` and `overdue` are SUBSETS of "with a reviewer", not a partition of it — a case
    //    does not stop being with its reviewer the moment it gets late.
    <div className="mt-6 grid gap-3 lg:grid-cols-2">
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
    </div>
  )
}

// ── How the applications arrived, and how the awards followed ──
export function ApplicationsSeriesSection({ data, t }: SectionProps) {
  const appSeries = data.applications_series
  if (!appSeries) return null
  const monthName = monthNamer(t)
  const monthTick = (iso: string) => monthName(monthOf(iso))
  return (
    <div className="mt-3 grid gap-3 lg:grid-cols-2" data-testid="overview-applications-series">
      {/* ⚠ VALUES ON HOVER, MONTHS ON THE AXIS, NOTHING BENEATH (owner, 2026-09-18). The
          weekly columns stay; the labels sit at each month's first week. */}
      <Card title={t(`${K}.series.applicationsPerWeek`)}>
        <BarChart
          box={WIDE_AXIS_BOX}
          testId="chart-applications-per-week"
          label={t(`${K}.chart.applicationsLabel`)}
          series={[{ key: 'count', className: 'fill-brand-shape',
                     values: appSeries.applications_per_week.map((r) => r.count),
                     titles: appSeries.applications_per_week.map((r) => String(r.count)) }]}
          columns={appSeries.applications_per_week.map((r) => weekLabel(r.week))}
          ticks={monthTicks(appSeries.applications_per_week.map((r) => r.week), monthName)}
          yAxis={{ label: t(`${K}.chart.yApplications`), format: (v) => String(Math.round(v)) }}
        />
      </Card>
      <Card title={t(`${K}.series.awardsPerMonth`)}>
        <BarChart
          box={WIDE_AXIS_BOX}
          testId="chart-awards-per-month"
          label={t(`${K}.chart.awardsLabel`)}
          series={[{ key: 'count', className: 'fill-brand-shape',
                     values: appSeries.awards_per_month.map((r) => r.count),
                     titles: appSeries.awards_per_month.map((r) => String(r.count)) }]}
          columns={appSeries.awards_per_month.map((r) => monthTick(r.month))}
          ticks={thinTicks(appSeries.awards_per_month.map((r, i) => (
            { index: i, label: monthTick(r.month) })))}
          yAxis={{ label: t(`${K}.chart.yAwards`), format: (v) => String(Math.round(v)) }}
        />
      </Card>
    </div>
  )
}

// ── The money over time: what we released, what was spent, and what is still in wallets ──
export function MoneySeriesSection({ data, t }: SectionProps) {
  const moneySeries = data.money_series
  if (!moneySeries) return null
  const money = data.money
  const monthName = monthNamer(t)
  const monthTick = (iso: string) => monthName(monthOf(iso))

  const perWeek = moneySeries.per_student_per_week ?? []
  const overall = moneySeries.per_student_overall ?? null
  /* ⚠ THE FIGURE BENEATH A WEEKLY CHART IS THE WHOLE-PERIOD ONE, not every week's value. Fifty
     weekly figures in a row are not "the numbers a person would quote", they are noise; the
     average over the whole period is the number, and the line is the movement. */
  const averageFigures: ChartFigure[] = overall
    ? [{ label: t(`${K}.series.overallAverage`), value: rmFig(overall.spent_per_transaction) }]
    : []
  const transactionFigures: ChartFigure[] = overall
    ? [{ label: t(`${K}.series.overallTransactions`),
         value: overall.weekly_transactions_per_student }]
    : []
  const weekTicks = monthTicks(perWeek.map((r) => r.week), monthName)
  const months = moneySeries.money_per_month ?? []
  /* ⚠ THE TOTALS ARE THE LAST MONTH'S RUNNING FIGURES, read straight from the server — never
     summed here. `released_cum`, `spent_cum` and `gap` on the final row ARE payments to date,
     spending to date and the balance, to the cent. */
  const lastMonth = months.length > 0 ? months[months.length - 1] : null

  return (
    <div className="mt-3 space-y-3" data-testid="overview-money-series">
      <Card title={t(`${K}.series.moneyPerMonth`)}>
        {/* ⚠ EVERY BAR AND EVERY POINT ANSWERS ON HOVER; NOTHING IS LISTED BENEATH (owner,
            2026-09-18). The y-axis is the BARS' scale; the balance line keeps its own (a
            running total beside monthly bars would flatten every bar), which is why the
            line's value lives on its points rather than on the axis. */}
        <BarChart
          box={FULL_AXIS_BOX}
          testId="chart-money-per-month"
          label={t(`${K}.chart.moneyLabel`)}
          series={[
            { key: 'released', className: 'fill-brand-shape',
              values: moneySeries.money_per_month.map((r) => num(r.released)),
              titles: moneySeries.money_per_month.map((r) => rmFig(r.released)) },
            { key: 'spent', className: 'fill-ground-300',
              values: moneySeries.money_per_month.map((r) => num(r.spent)),
              titles: moneySeries.money_per_month.map((r) => rmFig(r.spent)) },
          ]}
          line={{ className: 'stroke-ground-600',
                  values: moneySeries.money_per_month.map((r) => num(r.gap)),
                  titles: moneySeries.money_per_month.map((r) => signed(r.gap)) }}
          columns={moneySeries.money_per_month.map((r) => monthTick(r.month))}
          ticks={thinTicks(moneySeries.money_per_month.map((r, i) => (
            { index: i, label: monthTick(r.month) })))}
          yAxis={{ label: 'RM', format: rmAxis }}
        />

        {/* ⚠ THREE FIGURES THAT ARE ALSO THE LEGEND (owner, 2026-09-15 and 2026-09-18).
            Payments to date, spending to date, and what is still in wallets — the last
            month's running figures, which the server already carries — each with the
            swatch of the mark that draws it: the blue bar, the grey bar, the dotted line. */}
        {lastMonth && (
          <dl className="mt-4 grid grid-cols-3 gap-3" data-testid="money-totals">
            <div className="rounded-lg border border-ground-200 p-3">
              <dt className="flex items-center gap-1.5 text-[11px] font-medium text-ground-500">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-brand-shape"
                  data-testid="swatch-payments" />
                {t(`${K}.series.payments`)}
              </dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ground-900">
                {rmFig(lastMonth.released_cum)}
              </dd>
            </div>
            <div className="rounded-lg border border-ground-200 p-3">
              <dt className="flex items-center gap-1.5 text-[11px] font-medium text-ground-500">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-ground-300"
                  data-testid="swatch-spending" />
                {t(`${K}.series.spending`)}
              </dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ground-900">
                {rmFig(lastMonth.spent_cum)}
              </dd>
            </div>
            <div className="rounded-lg border border-ground-200 p-3">
              <dt className="flex items-center gap-1.5 text-[11px] font-medium text-ground-500">
                <span className="inline-block w-4 border-t-2 border-dotted border-ground-600"
                  data-testid="swatch-balance" />
                {t(`${K}.series.balance`)}
              </dt>
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
            values={perWeek.map((r) => num(r.spent_per_transaction))}
            columns={perWeek.map((r) => weekLabel(r.week))}
            ticks={weekTicks}
            yAxis={{ label: t(`${K}.chart.yRinggit`), format: (v) => `RM${Math.round(v)}` }}
            pointTitles={perWeek.map((r) => rmFig(r.spent_per_transaction))}
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
            pointTitles={perWeek.map((r) => r.transactions_per_student)}
            yAxis={{ label: t(`${K}.chart.yTransactions`),
                     format: (v) => String(Math.round(v * 10) / 10) }}
            figures={transactionFigures}
          />
          <p className="mt-2 text-[11px] text-ground-400">{t(`${K}.series.transactionsNote`)}</p>
        </Card>

        {/* ⚠ LARGEST FIRST, "NOT CATEGORISED" LAST, "NOT YET SORTED" ONLY WHEN IT HAS MONEY
            (`orderSlices`; owner, 2026-09-18). The ten real categories are always listed, at
            zero or not; the two unknown states are different and stay apart. */}
        <Card title={t(`${K}.series.byCategory`)}>
          <Donut
            testId="chart-by-category"
            label={t(`${K}.chart.categoryLabel`)}
            // ⚠ THE SERVER'S `spent`, the same figure as the money strip — never the rows
            // summed in the browser (money through a float is money we have rounded).
            total={money ? { label: t(`${K}.series.spendingTotal`), value: rmFig(money.spent) }
                         : undefined}
            rows={orderSlices(moneySeries.by_category
              .filter((r) => CATEGORY_CODES.indexOf(r.code) !== -1))
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
  )
}

// ── A reviewer's own work, and nothing else ──
export function MineSection({ data, t }: SectionProps) {
  const mine = data.mine
  if (!mine) return null
  return (
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
  )
}

// ── The QC queue: cases a reviewer has submitted and nobody has checked ──
export function QcSection({ data, t }: SectionProps) {
  const qc = data.qc
  if (!qc) return null
  return (
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
  )
}

/**
 * The section key the server sends → the component that draws it.
 *
 * ⚠ A KEY WITH NO RENDERER IS SKIPPED, SILENTLY AND ON PURPOSE. The server is deployed
 * separately from the browser bundle, so a widget added on the Python side arrives here before
 * this map knows about it; drawing an error where a panel should be would turn a harmless
 * deployment gap into a page that looks broken.
 */
export const SECTION_RENDERERS: Record<string, (props: SectionProps) => JSX.Element | null> = {
  funnel: FunnelSection,
  money: MoneySection,
  attention: AttentionSection,
  applications_series: ApplicationsSeriesSection,
  money_series: MoneySeriesSection,
  mine: MineSection,
  qc: QcSection,
}
