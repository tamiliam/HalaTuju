'use client'
/**
 * LL1: the tables of the "AI prediction" section — by fact, by doubt, by engine version, by reviewer.
 *
 * ⚠⚠ **THE BROWSER ONLY FORMATS.** Every count, rate and "few cases" flag below was served. A cell
 * prints "x of y" from two served counts, `Math.round(rate * 100) + '%'` from a served rate, and —
 * when the served flag is true — a "few cases" pill INSTEAD of the percent. Nothing here sums,
 * divides, compares to a threshold, or asks who the reader is: a table exists because its data did.
 *
 * ⚠ On a phone each row becomes a small card (`TableFrame phoneRows`: the cells carry `data-label`).
 */

import TableFrame, { TH } from '@/components/admin/TableFrame'
import type { PredictionCounts, DoubtRow, ReviewerRow } from '@/lib/admin-api'
import { tOr } from '@/lib/i18n'
import { PHONE_PILL_SM } from '@/lib/phonePill'
import type { Translate } from './sectionTypes'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview.aiPrediction'

/** The four facts, in the order the cockpit and the picture list them. */
export const FACT_CODES = ['identity', 'academic', 'pathway', 'income'] as const

export const pct = (rate: number): string => `${Math.round(rate * 100)}%`

export function FewPill({ t }: { t: Translate }) {
  return (
    <span data-testid="few-pill"
      className={`inline-block md:whitespace-nowrap rounded-full border border-ground-200 bg-ground-100 px-2 text-xs text-ground-600 ${PHONE_PILL_SM}`}>
      {t(`${K}.fewCases`)}
    </span>
  )
}

/** "x of y" and then the served percent, or the pill and NO percent when the served flag says few. */
export function Figure({ t, a, b, rate, few }: {
  t: Translate; a: number; b: number; rate: number; few: boolean
}) {
  return (
    <>
      {t(`${K}.xOfY`, { a: String(a), b: String(b) })}{' '}
      {few ? <FewPill t={t} /> : <span className="text-ground-500">({pct(rate)})</span>}
    </>
  )
}

const TD = 'px-4 py-2.5 text-sm tabular-nums text-ground-700'
const ROW = 'border-b border-ground-100 last:border-b-0'

/** The two figure cells every table repeats: the AI sure and the reviewer agreed; the AI in doubt and
 *  the reviewer passed. */
function CountCells({ t, c }: { t: Translate; c: PredictionCounts }) {
  return (
    <>
      <td className={TD} data-label={t(`${K}.col.sure`)}>
        <Figure t={t} a={c.green_agreed} b={c.green} rate={c.green_agree_rate} few={c.few_green} />
      </td>
      <td className={TD} data-label={t(`${K}.col.doubt`)}>
        <Figure t={t} a={c.unsure_passed} b={c.unsure} rate={c.unsure_pass_rate} few={c.few_unsure} />
      </td>
    </>
  )
}

function CountHeads({ t }: { t: Translate }) {
  return (
    <>
      <th className={TH}>{t(`${K}.col.sure`)}</th>
      <th className={TH}>{t(`${K}.col.doubt`)}</th>
    </>
  )
}

const HEAD = 'border-b border-ground-200 bg-ground-50'
const NAME = 'px-4 py-2.5 text-sm font-medium text-ground-900'

/** A fact's name: the cockpit's own words when it is one of the four, else the plain code. */
export function factName(t: Translate, fact: string): string {
  return (FACT_CODES as readonly string[]).includes(fact)
    ? t(`admin.scholarship.verdict.fact.${fact}`)
    : fact.replace(/_/g, ' ')
}

/**
 * The engine's reason code as words. The cockpit already has sentences for most codes
 * (`admin.scholarship.verdict.item.<code>`); they are written for ONE student and some carry a
 * `{placeholder}` this table cannot fill, so such a sentence is not used. No label — or one with a
 * hole in it — shows the code as plain text. No new label table is invented here.
 */
export function doubtName(t: Translate, code: string): string {
  const own = tOr(t, `admin.scholarship.verdict.item.${code}`, '')
  return own && !own.includes('{') ? own : code.replace(/_/g, ' ')
}

export function FactTable({ t, counts }: { t: Translate; counts: Record<string, PredictionCounts> }) {
  const rows = FACT_CODES.filter((f) => counts[f])
  if (rows.length === 0) return null
  return (
    <TableFrame phoneRows minWidth={520} label={t(`${K}.byFact`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr><th className={TH}>{t(`${K}.col.fact`)}</th><CountHeads t={t} /></tr>
        </thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f} className={ROW} data-testid={`ai-fact-${f}`}>
              <td className={NAME}>{factName(t, f)}</td>
              <CountCells t={t} c={counts[f]} />
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}

export function DoubtTable({ t, rows }: { t: Translate; rows: readonly DoubtRow[] }) {
  return (
    <TableFrame phoneRows minWidth={520} label={t(`${K}.doubts`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr>
            <th className={TH}>{t(`${K}.col.doubtCode`)}</th>
            <th className={TH}>{t(`${K}.col.fact`)}</th>
            <th className={TH}>{t(`${K}.col.passed`)}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.fact}-${r.code}`} className={ROW}>
              <td className={NAME}>{doubtName(t, r.code)}</td>
              <td className={TD} data-label={t(`${K}.col.fact`)}>{factName(t, r.fact)}</td>
              <td className={TD} data-label={t(`${K}.col.passed`)}>
                <Figure t={t} a={r.passed} b={r.total} rate={r.pass_rate} few={r.few} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}

export function VersionTable({ t, versions }: { t: Translate; versions: Record<string, PredictionCounts> }) {
  return (
    <TableFrame phoneRows minWidth={520} label={t(`${K}.byVersion`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr><th className={TH}>{t(`${K}.col.version`)}</th><CountHeads t={t} /></tr>
        </thead>
        <tbody>
          {Object.entries(versions).map(([version, c]) => (
            <tr key={version} className={ROW}>
              <td className={NAME}>{version || t(`${K}.versionUnknown`)}</td>
              <CountCells t={t} c={c} />
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}

/** The reviewer's name, or — for the two neutral rows the server marks with `label_key` — a
 *  translated neutral label in place of `name`. */
function reviewerName(t: Translate, r: ReviewerRow): string {
  if (r.label_key === 'unmatched_reviewer') return t(`${K}.unmatchedReviewer`)
  if (r.label_key === 'unnamed_reviewer') return t(`${K}.unnamedReviewer`)
  return r.name
}

export function ReviewerTable({ t, rows }: { t: Translate; rows: readonly ReviewerRow[] }) {
  return (
    <TableFrame phoneRows minWidth={620} label={t(`${K}.byReviewer`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr>
            <th className={TH}>{t(`${K}.col.reviewer`)}</th>
            <th className={TH}>{t(`${K}.col.applications`)}</th>
            <CountHeads t={t} />
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.id ?? 'x'}-${i}`} className={ROW} data-testid="ai-reviewer-row">
              <td className={NAME}>{reviewerName(t, r)}</td>
              <td className={TD} data-label={t(`${K}.col.applications`)}>{r.applications}</td>
              <CountCells t={t} c={r} />
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}
