'use client'

/**
 * LL2b: "Facts in doubt" — the QC's second look, inside the QC panel. It lists only the facts the
 * SERVER put in doubt (`second_look.in_doubt`: the AI said green and the reviewer failed it, or the
 * reviewer failed it and still chose Approve). The QC may answer each fact with Pass or Fail; nothing
 * is chosen at the start, a second tap on the chosen button clears it, and a fact left alone records
 * nothing. Each fact shows three rows: AI said, Reviewer (Fail and its reason) and QC's verdict. The
 * reviewer's overall Recommend or Decline is not repeated here (the QC panel shows it). It never blocks,
 * delays or confirms a decision.
 *
 * ⚠ The browser decides nothing here: which facts show, and what is stored on Accept / Reopen / Reject,
 * are the server's. "AI said" is the AI Prediction card's own band word (`factBandOf`). Pass is sent as
 * 'disagreed' (the QC disagrees with the reviewer's Fail), Fail as 'agreed'.
 */
import type { AdminScholarshipDetail, SecondLookFact } from '@/lib/admin-api'
import { BAND_TONE, factBandOf, type FactBand, type FactTileTone } from '@/lib/cockpitVerdict'
import { PHONE_PILL, PHONE_PILL_SM } from '@/lib/phonePill'

import type { T } from './shared'

export type QcAnswer = 'agreed' | 'disagreed'

/** The facts the block shows; [] for old cached data with no `second_look` key (no block). */
export function inDoubtOf(app: AdminScholarshipDetail): SecondLookFact[] {
  return app.second_look?.in_doubt ?? []
}

/** What the QC decision sends: ONLY the facts the QC answered (an untouched fact is absent, and the
 *  server records nothing for it). {} when nothing is answered; the caller then omits the key. */
export function factChecksFor(items: readonly SecondLookFact[], answers: Readonly<Record<string, QcAnswer>>) {
  const out: Record<string, QcAnswer> = {}
  for (const i of items) if (answers[i.fact]) out[i.fact] = answers[i.fact]
  return out
}

const PILL = `inline-block rounded-full border px-2 text-xs font-medium ${PHONE_PILL_SM}`
const TONE_PILL: Record<FactTileTone, string> = {
  green: `${PILL} border-positive-600 bg-positive-50 text-positive-700`,
  blue: `${PILL} border-primary-200 bg-primary-50 text-primary-700`,
  amber: `${PILL} border-caution-200 bg-caution-50 text-caution-700`,
  red: `${PILL} border-critical-200 bg-critical-50 text-critical-700`,
}
const FAIL = `${PILL} border-critical-200 bg-critical-50 text-critical-700`
const CHOICE = `rounded-full border px-3 py-1 text-xs font-medium disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center ${PHONE_PILL}`

/** The QC's Pass / Fail row (the look of the reviewer's own fact control), as a label + value pair
 *  inside the fact's grid. ONE place for its markup. Pass = 'disagreed', Fail = 'agreed'. */
function VerdictRow({ fact, t, answer, busy, onChoose }: {
  fact: string; t: T; answer: QcAnswer | undefined; busy: boolean; onChoose: (a: QcAnswer) => void
}) {
  const choices: Array<[QcAnswer, string, string, string]> = [
    ['disagreed', 'factPass', 'border-positive-fill bg-positive-fill text-positive-fill-ink', 'hover:border-positive-400'],
    ['agreed', 'factFail', 'border-critical-fill bg-critical-fill text-critical-fill-ink', 'hover:border-critical-400'],
  ]
  return (
    <>
      <dt className="self-center text-ground-600">{t('admin.scholarship.qcDecision.secondLook.yourVerdict')}</dt>
      <dd role="group" aria-label={t('admin.scholarship.qcDecision.secondLook.yourVerdict')}
        className="flex min-w-0 flex-wrap gap-1.5">
        {choices.map(([value, key, on, hover]) => (
          <button key={value} type="button" data-testid={`doubt-${fact}-${key}`} aria-pressed={answer === value}
            onClick={() => onChoose(value)} disabled={busy}
            className={`${CHOICE} ${answer === value ? on : `border-ground-300 text-ground-600 ${hover}`}`}>
            {t(`admin.scholarship.recordVerdict.${key}`)}
          </button>
        ))}
      </dd>
    </>
  )
}

function FactRow({ item, t, band, answer, busy, onChoose }: {
  item: SecondLookFact; t: T; band: FactBand; answer: QcAnswer | undefined
  busy: boolean; onChoose: (a: QcAnswer) => void
}) {
  return (
    <div data-testid={`doubt-${item.fact}`} className="space-y-2 rounded-lg border border-ground-200 bg-ground-0 p-2.5">
      <p className="text-sm font-medium text-ground-900">{t(`admin.scholarship.verdict.fact.${item.fact}`)}</p>
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1.5 text-xs">
        <dt className="text-ground-600">{t('admin.scholarship.qcDecision.secondLook.aiSaid')}</dt>
        <dd className="min-w-0">
          <span className={TONE_PILL[BAND_TONE[band]]}>{t(`admin.scholarship.verdict.band.${band}`)}</span>
        </dd>
        <dt className="text-ground-600">{t('admin.scholarship.qcDecision.secondLook.reviewer')}</dt>
        <dd className="min-w-0">
          <span className={FAIL}>{t('admin.scholarship.recordVerdict.factFail')}</span>
          {item.reason && <> ({t(`admin.scholarship.recordVerdict.failReason.${item.reason}`)})</>}
        </dd>
        <VerdictRow fact={item.fact} t={t} answer={answer} busy={busy} onChoose={onChoose} />
      </dl>
    </div>
  )
}

/** The block. Draws nothing when no fact is in doubt. `answers` = the QC's Pass / Fail per fact. */
export function FactsInDoubt({ items, t, bands, answers, setAnswers, busy }: {
  items: readonly SecondLookFact[]; t: T; bands: AdminScholarshipDetail['ai_fact_bands']
  answers: Readonly<Record<string, QcAnswer>>
  setAnswers: (next: Record<string, QcAnswer>) => void; busy: boolean
}) {
  if (items.length === 0) return null
  // A tap on the chosen button clears it; a tap on the other moves it.
  const choose = (fact: string, value: QcAnswer) => {
    const next = { ...answers }
    if (next[fact] === value) delete next[fact]
    else next[fact] = value
    setAnswers(next)
  }
  return (
    <section data-testid="facts-in-doubt" aria-labelledby="facts-in-doubt-title"
      className="space-y-2.5 rounded-lg border border-ground-200 bg-ground-50 p-3">
      <h3 id="facts-in-doubt-title" className="text-sm font-semibold text-ground-900">
        {t('admin.scholarship.qcDecision.secondLook.title')}
      </h3>
      <p className="text-xs text-ground-600">{t('admin.scholarship.qcDecision.secondLook.help')}</p>
      {items.map((item) => (
        <FactRow key={item.fact} item={item} t={t} band={factBandOf(bands, item.fact, item.ai_status)}
          answer={answers[item.fact]} busy={busy} onChoose={(v) => choose(item.fact, v)} />
      ))}
    </section>
  )
}
