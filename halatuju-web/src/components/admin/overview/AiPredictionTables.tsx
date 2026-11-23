'use client'
/**
 * F4b: the tables of the "AI prediction" card — By fact, By reviewer, and (for the AI team only)
 * Doubts often passed and By model version.
 *
 * ⚠⚠ **THE BROWSER ONLY FORMATS.** Every count, score, point total and top-reason list below was
 * served (`ai_score.py`). This file adds a sign, a thousands separator and a word. It sums nothing,
 * divides nothing, and never asks who the reader is: a table exists because its data did.
 *
 * ⚠ On a phone the tables SCROLL SIDEWAYS inside their own box (`TableFrame`, no `phoneRows`): the
 * page itself must never scroll sideways.
 */

import TableFrame, { TH } from '@/components/admin/TableFrame'
import type { DoubtRow, FactScore, ReviewerRow, ScoreBlock, ScoreReason, VersionScore } from '@/lib/admin-api'
import { FAIL_REASON_CODES } from '@/lib/failReasons'
import { tOr } from '@/lib/i18n'
import type { Translate } from './sectionTypes'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview.aiPrediction'

/** The four facts, in the order the cockpit and the picture list them. */
export const FACT_CODES = ['identity', 'academic', 'pathway', 'income'] as const

/** "+736", "−390", "0": a real minus sign, a thousands separator, no derivation. */
export const signed = (n: number): string =>
  n > 0 ? `+${n.toLocaleString('en-GB')}` : n < 0 ? `−${Math.abs(n).toLocaleString('en-GB')}` : '0'

/** The served whole percent (it may be below 0), or a dash when no fact was marked. */
export const scorePct = (p: number | null): string =>
  p === null ? '–' : p < 0 ? `−${Math.abs(p)}%` : `${p}%`

const TD = 'px-3 py-3 text-sm tabular-nums text-ground-700 align-top'
const ROW = 'border-b border-ground-100 last:border-b-0'
const HEAD = 'border-b border-ground-200 bg-ground-50'
const NAME = 'px-3 py-3 text-sm font-medium text-ground-900 align-top'
const THC = `${TH} !px-3 whitespace-nowrap`

/** A fact's name: the cockpit's own words when it is one of the four, else the plain code. */
export function factName(t: Translate, fact: string): string {
  return (FACT_CODES as readonly string[]).includes(fact)
    ? t(`admin.scholarship.verdict.fact.${fact}`)
    : fact.replace(/_/g, ' ')
}

/**
 * The engine's reason code as words. The cockpit already has sentences for most codes
 * (`admin.scholarship.verdict.item.<code>`); they are written for ONE student and some carry a
 * `{placeholder}` this list cannot fill, so such a sentence is not used. No label — or one with a
 * hole in it — shows the code as plain text.
 */
export function doubtName(t: Translate, code: string): string {
  const own = tOr(t, `admin.scholarship.verdict.item.${code}`, '')
  return own && !own.includes('{') ? own : code.replace(/_/g, ' ')
}

/** A lost-points reason key as words: `fail:<code>` (the reviewer's own reason), `fail:not_given`
 *  (an old row), or `pass:<band>` (what the AI said when the reviewer passed). */
export function reasonName(t: Translate, key: string): string {
  const [kind, rest = ''] = key.split(':')
  if (kind === 'fail') {
    if (rest === 'not_given') return t(`${K}.notGiven`)
    return (FAIL_REASON_CODES as readonly string[]).includes(rest)
      ? t(`admin.scholarship.recordVerdict.failReason.${rest}`)
      : rest.replace(/_/g, ' ')
  }
  if (rest === 'ruleNotMet') return t(`${K}.reasonPassRuleNotMet`)
  if (rest === 'unverifiable') return t(`${K}.reasonPassUnverifiable`)
  return key.replace(/[_:]/g, ' ')
}

const OUTCOMES = ['right_sure', 'right_leaning', 'unsure', 'wrong_leaning', 'wrong_sure'] as const
const OUTCOME_COLOUR = {
  right_sure: 'text-positive-800 font-semibold', right_leaning: 'text-positive-700', unsure: 'text-ground-600',
  wrong_leaning: 'text-caution-800', wrong_sure: 'text-critical-800 font-bold',
} as const

function ReasonChips({ t, reasons }: { t: Translate; reasons: readonly ScoreReason[] }) {
  if (reasons.length === 0) return <span className="text-ground-400">{'–'}</span>
  return (
    <ul className="flex flex-wrap gap-1.5">
      {reasons.map((r) => (
        <li key={r.key} className="rounded-full bg-ground-100 px-2.5 py-0.5 text-xs text-ground-700">
          {reasonName(t, r.key)} {signed(r.points)}
        </li>
      ))}
    </ul>
  )
}

function ScoreCell({ t, b }: { t: Translate; b: ScoreBlock }) {
  return (
    <div>
      <div className="text-base font-bold text-brand-fill" data-testid="ai-score-pct">{scorePct(b.score_pct)}</div>
      <div className="text-xs text-ground-500">
        {t(`${K}.pointsOfBest`, { points: signed(b.points), best: signed(b.best) })}
      </div>
      <div className="text-xs text-critical-800">{t(`${K}.lost`, { points: signed(b.lost) })}</div>
    </div>
  )
}

export function FactTable({ t, facts }: { t: Translate; facts: Record<string, FactScore> }) {
  const rows = FACT_CODES.filter((f) => facts[f])
  if (rows.length === 0) return null
  return (
    <TableFrame minWidth={1100} label={t(`${K}.byFact`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr>
            <th className={THC}>{t(`${K}.col.fact`)}</th>
            <th className={THC}>{t(`${K}.outcome.right_sure`)}</th>
            <th className={THC}>{t(`${K}.outcome.right_leaning`)}</th>
            <th className={THC}>{t(`${K}.outcome.unsure`)}</th>
            <th className={THC}>{t(`${K}.outcome.wrong_leaning`)}</th>
            <th className={THC}>{t(`${K}.outcome.wrong_sure`)}</th>
            <th className={THC}>{t(`${K}.col.score`)}</th>
            <th className={THC}>{t(`${K}.col.lostMost`)}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => {
            const b = facts[f]
            return (
              <tr key={f} className={ROW} data-testid={`ai-fact-${f}`}>
                <td className={NAME}>
                  {factName(t, f)}
                  <div className="text-xs font-normal text-ground-500">{t(`${K}.nFacts`, { n: String(b.facts) })}</div>
                </td>
                {OUTCOMES.map((o) => (
                  <td key={o} className={`${TD} ${OUTCOME_COLOUR[o]}`}>{b[o]}</td>
                ))}
                <td className={TD}><ScoreCell t={t} b={b} /></td>
                <td className={TD} data-testid={`ai-reasons-${f}`}><ReasonChips t={t} reasons={b.top_reasons} /></td>
              </tr>
            )
          })}
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

/** COUNTS only, per recorder. "Green but failed" and "Unsure but passed" are the served
 *  `green_failed` and `unsure_passed`; the QC columns are the served QC decisions. */
export function ReviewerTable({ t, rows }: { t: Translate; rows: readonly ReviewerRow[] }) {
  return (
    <TableFrame minWidth={900} label={t(`${K}.byReviewer`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr>
            <th className={THC}>{t(`${K}.col.reviewer`)}</th>
            <th className={THC}>{t(`${K}.col.applications`)}</th>
            <th className={THC}>{t(`${K}.col.greenFailed`)}</th>
            <th className={THC}>{t(`${K}.col.unsurePassed`)}</th>
            <th className={THC}>{t(`${K}.col.qcAccepted`)}</th>
            <th className={THC}>{t(`${K}.col.qcSentBack`)}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.id ?? 'x'}-${i}`} className={ROW} data-testid="ai-reviewer-row">
              <td className={NAME}>{reviewerName(t, r)}</td>
              <td className={TD}>{r.applications}</td>
              <td className={TD}>{r.green_failed}</td>
              <td className={TD}>{r.unsure_passed}</td>
              <td className={TD}>{r.qc_accepted}</td>
              <td className={TD}>{r.qc_sent_back}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}

/** For the AI team: the doubts reviewers passed most often, as a plain list with the served count. */
export function DoubtList({ t, rows }: { t: Translate; rows: readonly DoubtRow[] }) {
  return (
    <ul className="divide-y divide-ground-100 rounded-lg border border-ground-200 bg-ground-0">
      {rows.map((r) => (
        <li key={`${r.fact}-${r.code}`} className="flex items-start justify-between gap-4 px-3.5 py-2.5 text-sm">
          <span className="min-w-0 break-words text-ground-900">
            {doubtName(t, r.code)}
            <span className="ml-1.5 text-xs text-ground-500">{factName(t, r.fact)}</span>
          </span>
          <span className="shrink-0 font-semibold text-ground-900">
            {t(`${K}.nPassed`, { n: String(r.passed) })}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function VersionTable({ t, versions }: { t: Translate; versions: readonly VersionScore[] }) {
  return (
    <TableFrame minWidth={480} label={t(`${K}.byVersion`)}>
      <table className="w-full">
        <thead className={HEAD}>
          <tr>
            <th className={THC}>{t(`${K}.col.version`)}</th>
            <th className={THC}>{t(`${K}.col.factsMarked`)}</th>
            <th className={THC}>{t(`${K}.col.score`)}</th>
            <th className={THC}>{t(`${K}.col.points`)}</th>
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => (
            <tr key={v.version} className={ROW} data-testid="ai-version-row">
              <td className={NAME}>{v.version || t(`${K}.versionUnknown`)}</td>
              <td className={TD}>{v.facts}</td>
              <td className={TD}>{scorePct(v.score_pct)}</td>
              <td className={TD}>{t(`${K}.pointsOfBest`, { points: signed(v.points), best: signed(v.best) })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}
