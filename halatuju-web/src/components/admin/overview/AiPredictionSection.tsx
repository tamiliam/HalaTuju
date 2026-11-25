'use client'
/**
 * F4b: "AI prediction" — how good the AI's prediction was, in marks (owner design 2026-11-23).
 * Drawn on the Programme Overview (a section the server sends) and at the foot of the Programmes
 * page (all programmes together). One block, two homes: `AiPredictionBlock` is the whole thing.
 *
 * ⚠⚠ **THE BROWSER ONLY FORMATS** (`docs/domain-rules.md`, serve — never derive in the browser).
 * The score, the points, the five outcome counts, the top reasons and who may see what were all
 * decided on the server (`ai_score.py`, `prediction_metrics.py`). This file prints them.
 *
 * ⚠⚠ **EVERY BLOCK APPEARS BY PRESENCE, NEVER BY ROLE.** There is no role check in this file. The
 * reviewer table shows only when `by_reviewer` arrived; the "For the AI team" fold shows only when
 * `ai_team` arrived (a super's only); the whole section is `null` when its slice is absent (a
 * reviewer gets no card at all: the server refuses or omits it).
 */

import type { JSX } from 'react'
import type { AiOutcome, VerdictMetrics } from '@/lib/admin-api'
import { DoubtList, FactTable, ReviewerTable, VersionTable, factName, scorePct, signed } from './AiPredictionTables'
import type { SectionProps, Translate } from './sectionTypes'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview.aiPrediction'

const H3 = 'text-sm font-semibold text-ground-900'
const HINT = 'mt-1.5 text-xs text-ground-500'

const LEGEND: ReadonlyArray<readonly [AiOutcome, string]> = [
  ['right_sure', 'text-positive-800'], ['right_leaning', 'text-positive-700'], ['unsure', 'text-ground-600'],
  ['wrong_leaning', 'text-caution-800'], ['wrong_sure', 'text-critical-800'],
]

function Tile({ tone, label, value, sub, testId }: {
  tone: 'brand' | 'loss'; label: string; value: string; sub: string; testId: string
}) {
  const box = tone === 'brand' ? 'border-brand-fill/30 bg-brand-fill/5' : 'border-critical-200 bg-critical-50'
  const text = tone === 'brand' ? 'text-brand-fill' : 'text-critical-800'
  return (
    <div className={`rounded-xl border p-4 ${box}`} data-testid={testId}>
      <div className={`text-sm font-semibold ${text}`}>{label}</div>
      <div className={`mt-1 text-3xl font-bold tabular-nums max-md:text-2xl ${text}`}>{value}</div>
      <div className="mt-1.5 text-xs text-ground-600">{sub}</div>
    </div>
  )
}

function Legend({ t }: { t: Translate }) {
  return (
    <ul className="mt-2 space-y-1 text-xs text-ground-600" data-testid="ai-legend">
      {LEGEND.map(([o, colour]) => (
        <li key={o}>
          <b className={colour}>{t(`${K}.outcome.${o}`)} ({t(`${K}.points.${o}`)}):</b>{' '}
          {t(`${K}.meaning.${o}`)}
        </li>
      ))}
    </ul>
  )
}

function AiTeam({ ai, t }: { ai: NonNullable<VerdictMetrics['ai_team']>; t: Translate }) {
  return (
    <details open className="rounded-xl border border-brand-fill/30 bg-brand-fill/5 px-4" data-testid="ai-team">
      <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-brand-fill focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-fill">
        {t(`${K}.aiTeam`)}
      </summary>
      <div className="space-y-5 pb-4 pt-1">
        <p className="text-xs text-ground-600">{t(`${K}.aiTeamOnly`)}</p>
        {ai.doubt_codes.length > 0 && (
          <div data-testid="ai-doubts">
            <h3 className={`${H3} mb-2`}>{t(`${K}.doubts`)}</h3>
            <DoubtList t={t} rows={ai.doubt_codes} />
          </div>
        )}
        {ai.by_version.length > 0 && (
          <div data-testid="ai-by-version">
            <h3 className={`${H3} mb-2`}>{t(`${K}.byVersion`)}</h3>
            <VersionTable t={t} versions={ai.by_version} />
          </div>
        )}
      </div>
    </details>
  )
}

/** The whole section. `note` is the small grey words beside the heading ("All programmes together."). */
export function AiPredictionBlock({ ai, t, note }: { ai: VerdictMetrics; t: Translate; note?: string }) {
  const score = ai.score
  if (!score) return null
  const empty = score.facts === 0
  return (
    <section className="min-w-0 space-y-5 rounded-xl border border-ground-200 bg-ground-0 p-4" data-testid="overview-ai-prediction">
      <div>
        <h2 className="text-base font-semibold text-ground-900">
          {t(`${K}.title`)}
          {note && <span className="ml-2 text-xs font-normal text-ground-500">{note}</span>}
        </h2>
        <p className="mt-1 text-sm text-ground-600">{t(`${K}.counted`, { n: String(ai.applications) })}</p>
        {score.not_scored > 0 && (
          <p className={HINT} data-testid="ai-not-scored">{t(`${K}.notScored`, { n: String(score.not_scored) })}</p>
        )}
      </div>

      {empty ? (
        <p className="text-sm text-ground-500" data-testid="ai-empty">{t(`${K}.empty`)}</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Tile tone="brand" testId="ai-tile-score" label={t(`${K}.scoreTile`)} value={scorePct(score.score_pct)}
              sub={t(`${K}.scoreSub`, { points: signed(score.points), best: signed(score.best) })} />
            <Tile tone="loss" testId="ai-tile-lost" label={t(`${K}.lostTile`)} value={signed(score.lost)}
              sub={score.most_lost
                ? t(`${K}.mostFrom`, { fact: factName(t, score.most_lost.fact), points: signed(score.most_lost.points) })
                : t(`${K}.nothingLost`)} />
          </div>

          <div data-testid="ai-by-fact">
            <h3 className={H3}>{t(`${K}.byFact`)}</h3>
            <p className={HINT}>{t(`${K}.byFactHint`)}</p>
            <Legend t={t} />
            <div className="mt-3"><FactTable t={t} facts={score.by_fact} /></div>
          </div>

          {ai.by_reviewer && (
            <div data-testid="ai-by-reviewer">
              <h3 className={`${H3} mb-2`}>{t(`${K}.byReviewer`)}</h3>
              <ReviewerTable t={t} rows={ai.by_reviewer} />
              <p className={HINT}>{t(`${K}.reviewerFootnote`)}</p>
            </div>
          )}

          {ai.ai_team && <AiTeam ai={ai.ai_team} t={t} />}
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
