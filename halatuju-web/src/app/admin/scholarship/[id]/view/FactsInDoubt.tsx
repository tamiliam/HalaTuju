'use client'

/**
 * LL2b: "Facts in doubt" — the QC's second look, inside the QC panel. It lists only the facts the
 * SERVER put in doubt (`second_look.in_doubt`: the AI said green and the reviewer failed it, or the
 * reviewer failed it and still chose Approve). Doing nothing agrees with the reviewer; one tap on a
 * fact says "I do not agree". It never blocks, delays or confirms a decision.
 *
 * ⚠ The browser decides nothing here: which facts show, and what a silent accept records, are the
 * server's. This file draws the list and remembers the taps until the QC decides.
 */
import type { AdminScholarshipDetail, SecondLookFact } from '@/lib/admin-api'
import { PHONE_PILL_SM } from '@/lib/phonePill'

import type { T } from './shared'

/** The facts the block shows; [] for old cached data with no `second_look` key (no block). */
export function inDoubtOf(app: AdminScholarshipDetail): SecondLookFact[] {
  return app.second_look?.in_doubt ?? []
}

/** What the QC decision sends: only the taps, as "disagreed", and only for a fact still shown.
 *  `{}` = the QC agrees with the reviewer on every fact in doubt. */
export function factChecksFor(items: readonly SecondLookFact[], tapped: readonly string[]) {
  const out: Record<string, 'disagreed'> = {}
  for (const i of items) if (tapped.includes(i.fact)) out[i.fact] = 'disagreed'
  return out
}

const PILL = `inline-block rounded-full border px-2 text-xs font-medium ${PHONE_PILL_SM}`
const NEUTRAL = `${PILL} border-ground-200 bg-ground-100 text-ground-700`
const FAIL = `${PILL} border-critical-200 bg-critical-50 text-critical-700`
const TAP = 'rounded-lg border px-3 py-2 text-xs disabled:opacity-50 max-md:min-h-11 max-md:w-full'

function FactRow({ item, t, off, busy, onTap }: {
  item: SecondLookFact; t: T; off: boolean; busy: boolean; onTap: () => void
}) {
  const accepted = item.groups.includes('failed_but_accepted')
  const showReason = !!item.reason || item.groups.includes('ai_green_reviewer_fail')
  return (
    <div data-testid={`doubt-${item.fact}`}
      className={`space-y-2 rounded-lg border p-2.5 ${off ? 'border-critical-200 bg-critical-50' : 'border-ground-200 bg-ground-0'}`}>
      <p className="text-sm font-medium text-ground-900">{t(`admin.scholarship.verdict.fact.${item.fact}`)}</p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs max-md:grid-cols-1">
        <dt className="text-ground-600">{t('admin.scholarship.qcDecision.secondLook.aiSaid')}</dt>
        <dd className="min-w-0">
          <span className={item.ai_green ? `${PILL} border-positive-600 bg-positive-50 text-positive-700` : NEUTRAL}>
            {item.ai_status ? t(`admin.scholarship.verdict.status.${item.ai_status}`) : '—'}
          </span>
        </dd>
        <dt className="text-ground-600">{t('admin.scholarship.qcDecision.secondLook.reviewerSaid')}</dt>
        <dd className="min-w-0">
          <span className={FAIL}>{t('admin.scholarship.recordVerdict.factFail')}</span>
          {accepted && <>, {t('admin.scholarship.qcDecision.secondLook.butDecision',
            { decision: t('admin.scholarship.recordVerdict.approve') })}</>}
        </dd>
        {showReason && <>
          <dt className="text-ground-600">{t('admin.scholarship.recordVerdict.failReasonLabel')}</dt>
          <dd className="min-w-0 text-ground-900">
            {item.reason ? t(`admin.scholarship.recordVerdict.failReason.${item.reason}`)
              : t('admin.programmeOverview.aiPrediction.notGiven')}
          </dd>
        </>}
      </dl>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <button type="button" aria-pressed={off} onClick={onTap} disabled={busy}
          className={`${TAP} ${off ? 'border-critical-700 bg-critical-50 font-semibold text-critical-700'
            : 'border-critical-200 bg-ground-0 font-medium text-critical-700 hover:bg-critical-50'}`}>
          {t(off ? 'admin.scholarship.qcDecision.secondLook.undo' : 'admin.scholarship.qcDecision.secondLook.disagree')}
        </button>
        {!off && <span className="text-xs text-ground-600">{t('admin.scholarship.qcDecision.secondLook.agree')}</span>}
      </div>
    </div>
  )
}

/** The block. Draws nothing when no fact is in doubt. `tapped` = the facts the QC disagrees on. */
export function FactsInDoubt({ items, t, tapped, setTapped, busy }: {
  items: readonly SecondLookFact[]; t: T; tapped: readonly string[]
  setTapped: (facts: string[]) => void; busy: boolean
}) {
  if (items.length === 0) return null
  const toggle = (fact: string) =>
    setTapped(tapped.includes(fact) ? tapped.filter((f) => f !== fact) : [...tapped, fact])
  return (
    <section data-testid="facts-in-doubt" aria-labelledby="facts-in-doubt-title"
      className="space-y-2.5 rounded-lg border border-ground-200 bg-ground-50 p-3">
      <h3 id="facts-in-doubt-title" className="text-sm font-semibold text-ground-900">
        {t('admin.scholarship.qcDecision.secondLook.title')}
      </h3>
      <p className="text-xs text-ground-600">{t('admin.scholarship.qcDecision.secondLook.help')}</p>
      {items.map((item) => (
        <FactRow key={item.fact} item={item} t={t} off={tapped.includes(item.fact)} busy={busy}
          onTap={() => toggle(item.fact)} />
      ))}
    </section>
  )
}
