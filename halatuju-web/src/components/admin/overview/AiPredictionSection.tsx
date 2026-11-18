'use client'
/**
 * LL1: "AI prediction" — how often the reviewers agreed with what the AI predicted, drawn on the
 * Programme Overview (a section the server sends) and at the foot of the Organisation page (all
 * programmes together). One block, two homes: `AiPredictionBlock` is the whole thing.
 *
 * ⚠⚠ **THE BROWSER ONLY FORMATS** (`docs/domain-rules.md`, serve — never derive in the browser).
 * Counts, rates, the "few cases" flags, the order of every list and who may see what were all
 * decided on the server. This file prints `Math.round(rate * 100) + '%'`, "x of y" from two served
 * counts, and a month name from the `YYYY-MM` key read as a STRING (no Date, no time zone). When a
 * served `few` flag is true it prints the count and a "few cases" pill and NO percent.
 *
 * ⚠⚠ **EVERY BLOCK APPEARS BY PRESENCE, NEVER BY ROLE.** There is no role check in this file. The
 * reviewer table shows only when `by_reviewer` arrived (the server omits the key for anyone who may
 * not see names); the whole section is `null` when its slice is absent.
 *
 * ⚠ The trend reuses `LineChart` as it is. It cannot grey a few-case point or start its axis at
 * 80%, so it does neither; the values row beneath it carries every month's figure as text.
 */

import type { JSX } from 'react'
import { LineChart } from '@/components/admin/charts/Charts'
import type { VerdictMetrics } from '@/lib/admin-api'
import { monthOf, thinTicks } from '@/lib/programmeOverview'
import { DoubtTable, FactTable, Figure, FewPill, ReviewerTable, VersionTable, pct } from './AiPredictionTables'
import type { SectionProps, Translate } from './OverviewSections'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview.aiPrediction'

const H3 = 'text-sm font-semibold text-ground-900'
const HINT = 'mt-1.5 text-xs text-ground-500'

function Headline({ label, value, count, few, t }: {
  label: string; value: string; count: string; few: boolean; t: Translate
}) {
  return (
    <div className="rounded-xl border border-ground-200 bg-ground-0 p-3.5 max-md:p-3">
      <div className="text-xs font-medium text-ground-500">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums text-ground-900 max-md:text-lg">
        {few ? <FewPill t={t} /> : value}
      </div>
      <div className="mt-0.5 text-xs tabular-nums text-ground-500">{count}</div>
    </div>
  )
}

/** "2026", or "2025–2026" when the months cross a year — read off the keys as text. */
function yearsOf(keys: readonly string[]): string {
  const first = keys[0].slice(0, 4)
  const last = keys[keys.length - 1].slice(0, 4)
  return first === last ? first : `${first}–${last}`
}

function Trend({ ai, t }: { ai: VerdictMetrics; t: Translate }) {
  const byMonth = ai.by_month ?? {}
  const keys = Object.keys(byMonth)   // the server's order (oldest first)
  if (keys.length === 0) return null
  const years = yearsOf(keys)
  const multiYear = years.length > 4
  const label = (key: string) =>
    `${t(`admin.programmeOverview.months.${monthOf(key)}`)}${multiYear ? ` ${key.slice(0, 4)}` : ''}`
  const text = (key: string) => {
    const c = byMonth[key]
    return `${label(key)}: ${c.few_green ? t(`${K}.fewCases`) : pct(c.green_agree_rate)}, `
      + t(`${K}.xOfY`, { a: String(c.green_agreed), b: String(c.green) })
  }
  return (
    <div data-testid="ai-trend">
      <h3 className={H3}>
        {t(`${K}.trend`)}
        <span className="ml-2 text-xs font-normal text-ground-500">{years}</span>
      </h3>
      <div className="mt-2">
        <LineChart
          testId="chart-ai-sure-by-month"
          label={t(`${K}.trendChart`)}
          values={keys.map((k) => byMonth[k].green_agree_rate)}
          columns={keys.map(label)}
          ticks={thinTicks(keys.map((k, i) => ({ index: i, label: label(k) })))}
          pointTitles={keys.map(text)}
        />
      </div>
      {/* Every month as text: the chart answers on hover only, and a count nobody can read is no count. */}
      <ol className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" data-testid="ai-trend-values">
        {keys.map((k) => {
          const c = byMonth[k]
          return (
            <li key={k} className="rounded-lg border border-ground-200 p-2 text-xs text-ground-500">
              <div className="font-semibold text-ground-900">{label(k)}</div>
              {c.few_green ? <FewPill t={t} /> : <div className="text-sm text-ground-900">{pct(c.green_agree_rate)}</div>}
              <div className="tabular-nums">{t(`${K}.xOfY`, { a: String(c.green_agreed), b: String(c.green) })}</div>
            </li>
          )
        })}
      </ol>
      <p className={HINT}>{t(`${K}.trendHint`)}</p>
    </div>
  )
}

function Decision({ ai, t }: { ai: VerdictMetrics; t: Translate }) {
  const qc = ai.qc_agreement
  if (!qc || qc.total === 0) return null
  return (
    <div className="border-t border-ground-200 pt-4" data-testid="ai-decision">
      <h3 className={H3}>
        {t(`${K}.decision`)}
        <span className="ml-2 text-xs font-normal text-ground-500">{t(`${K}.decisionNote`)}</span>
      </h3>
      <p className="mt-2 text-sm text-ground-900">
        <Figure t={t} a={qc.accept} b={qc.total} rate={qc.accept_rate} few={qc.few} />
        {' '}{t(`${K}.qcAgreed`)}
      </p>
      <p className={HINT}>{t(`${K}.qcOther`, { reopen: String(qc.reopen), reject: String(qc.reject) })}</p>
    </div>
  )
}

/** The whole section. `note` is the small grey words beside the heading ("All programmes together."). */
export function AiPredictionBlock({ ai, t, note }: { ai: VerdictMetrics; t: Translate; note?: string }) {
  const overall = ai.overall
  if (!overall) return null
  const empty = overall.green === 0 && overall.unsure === 0
  const doubts = ai.doubt_codes ?? []
  const versions = ai.by_version ?? {}
  // The server says whose cases it counted; an assigned-only reader sees that note, never "all together".
  const shownNote = ai.counted_scope === 'assigned' ? t(`${K}.assignedOnly`) : note
  return (
    <section className="space-y-5 rounded-xl border border-ground-200 bg-ground-0 p-4" data-testid="overview-ai-prediction">
      <div>
        <h2 className="text-sm font-semibold text-ground-900">
          {t(`${K}.title`)}
          {shownNote && <span className="ml-2 text-xs font-normal text-ground-500">{shownNote}</span>}
        </h2>
        <p className="mt-1 max-w-prose text-xs text-ground-500">{t(`${K}.sub`)}</p>
      </div>

      {empty ? (
        <p className="text-sm text-ground-500" data-testid="ai-empty">{t(`${K}.empty`)}</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <Headline t={t} label={t(`${K}.sureTile`)} few={overall.few_green}
              value={pct(overall.green_agree_rate)}
              count={t(`${K}.factsOf`, { a: String(overall.green_agreed), b: String(overall.green) })} />
            <Headline t={t} label={t(`${K}.doubtTile`)} few={overall.few_unsure}
              value={pct(overall.unsure_pass_rate)}
              count={t(`${K}.factsOf`, { a: String(overall.unsure_passed), b: String(overall.unsure) })} />
          </div>

          <Trend ai={ai} t={t} />

          {ai.fact_counts && (
            <div data-testid="ai-by-fact">
              <h3 className={`${H3} mb-2`}>{t(`${K}.byFact`)}</h3>
              <FactTable t={t} counts={ai.fact_counts} />
            </div>
          )}

          {doubts.length > 0 && (
            <div data-testid="ai-doubts">
              <h3 className={`${H3} mb-2`}>{t(`${K}.doubts`)}</h3>
              <DoubtTable t={t} rows={doubts} />
              <p className={HINT}>{t(`${K}.doubtsHint`)}</p>
            </div>
          )}

          <Decision ai={ai} t={t} />

          {Object.keys(versions).length > 0 && (
            <details className="rounded-xl border border-ground-200 px-3" data-testid="ai-by-version">
              <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-ground-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-fill">
                {t(`${K}.byVersion`)}
              </summary>
              <div className="pb-3"><VersionTable t={t} versions={versions} /></div>
            </details>
          )}

          {ai.by_reviewer && (
            <div data-testid="ai-by-reviewer">
              <h3 className={`${H3} mb-2`}>
                {t(`${K}.byReviewer`)}
                <span className="ml-2 rounded-full border border-ground-200 bg-ground-50 px-2 text-xs font-medium text-brand-fill max-md:rounded-md">
                  {t(`${K}.leadsOnly`)}
                </span>
              </h3>
              <ReviewerTable t={t} rows={ai.by_reviewer} />
              <p className={HINT}>{t(`${K}.reviewerHint`)}</p>
            </div>
          )}

          <p className="border-t border-ground-200 pt-3 text-xs text-ground-500">{t(`${K}.footer`)}</p>
        </>
      )}
    </section>
  )
}

/** The Programme Overview's renderer: this section, or nothing when the slice did not arrive. */
export function AiPredictionSection({ data, t }: SectionProps): JSX.Element | null {
  if (!data.ai_prediction) return null
  return (
    <div className="mt-6">
      <AiPredictionBlock ai={data.ai_prediction} t={t} />
    </div>
  )
}
