'use client'

/**
 * THE DRAWER'S CHIP LINE, PILL, READ TIME AND REASON LINES — drawn from what the API serves.
 *
 * A payload with no `chips` (an old cache, a server that has not shipped) keeps today's drawing as a
 * FALLBACK: `documentFacts` / `documentPill` and the year rule below. The fallback is deleted in
 * Sprint 9. Colours come from `@/lib/docChips` only.
 */
import { useT } from '@/lib/i18n'
import { documentFacts, documentPill } from '@/lib/officerCockpit'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { STATE_COLOURS, formatReadTime, type ChipPillWord, type ChipState, type DocChipData } from '@/lib/docChips'
import { DocChip } from '@/components/DocChip'

import type { T } from './shared'

const FACT_STATE: Record<string, ChipState> = { verified: 'green', partial: 'amber', not: 'red', unknown: 'grey' }
const YEAR_STATE: Record<string, ChipState> = { current: 'green', off: 'amber' }

/** The chips to draw: the served ones, or today's functions when the payload has none. */
export function drawerChips(d: AdminApplicantDocument): DocChipData[] {
  if (d.chips?.length) return d.chips
  const out: DocChipData[] = documentFacts(d).map((f) => ({
    key: f.key, status: f.status, state: FACT_STATE[f.status] ?? 'grey', student_action: 'none',
    reason: '', kind: 'fact',
  }))
  const y: [string, string, string, string | undefined, string | undefined][] = [
    ['results_slip', 'examYear', 'academic', d.academic_check?.exam_year, d.academic_check?.exam_year_status],
    ['higher_results', 'stpmExamYear', 'higher', d.higher_check?.exam_year, d.higher_check?.exam_year_status],
    ['offer_letter', 'intakeYear', 'pathway', d.pathway_check?.intake_year, d.pathway_check?.intake_year_status],
  ]
  // Chip Sprint 2: a bill's amount is a plain value after its chips (none when the type is wrong).
  const amount = typeof d.utility_check?.monthly_bill === 'string' ? d.utility_check.monthly_bill.trim() : ''
  if ((d.doc_type === 'water_bill' || d.doc_type === 'electricity_bill') && amount
    && !out.some((c) => c.key === 'type' && c.state === 'red')) {
    out.push({ key: 'amount', status: 'unknown', state: 'grey', student_action: 'none', reason: 'read', kind: 'plain', value: amount })
  }
  const hit = y.find((r) => r[0] === d.doc_type && r[3])
  if (hit) {
    out.push({ key: hit[1], status: 'unknown', state: (typeof hit[4] === 'string' && YEAR_STATE[hit[4]]) || 'grey',
      student_action: 'none', reason: '', kind: 'year', value: hit[3] })
  }
  return out
}

/** The pill to draw: the served one, or today's function (which has no Problem) as a fallback.
 *  An empty served chip list means the server's chip code failed (it serves `[]` and 'unread'), so
 *  the pill falls back with the chips. */
export function drawerPill(d: AdminApplicantDocument): ChipPillWord {
  if (d.chips?.length && d.chip_pill) return d.chip_pill
  // Fallback: the pill follows the chips the row draws, so a red fact chip reads Problem.
  if (drawerChips(d).some((c) => c.kind === 'fact' && c.state === 'red')) return 'problem'
  return documentPill(d)
}

export function chipText(c: DocChipData, t: T): string {
  if (c.kind === 'plain') return c.key === 'amount' ? `RM ${c.value ?? ''}` : String(c.value ?? '')
  return c.kind === 'year'
    ? t(`admin.scholarship.docsDrawer.${c.key}`, { year: String(c.value ?? '') })
    : t(`admin.scholarship.docsDrawer.fact.${c.key}`)
}

export function ChipLine({ chips, t }: { chips: DocChipData[]; t: T }) {
  if (chips.length === 0) return null
  return (
    <p className="mt-1 flex flex-wrap items-center gap-1.5" data-chip-line>
      {chips.map((c, i) => <DocChip key={`${c.key}-${i}`} state={c.state} plain={c.kind === 'plain'}>{chipText(c, t)}</DocChip>)}
    </p>
  )
}

/** FIXED reason words per chip key + served reason code -> i18n key, so a raw engine word is never
 *  shown. Chip Sprint 2 fills the bill words (owner 2026-11-28); the family sprints add theirs. */
const R = 'admin.scholarship.docsDrawer.reason.'
export const REASON_WORDS: Record<string, string> = {
  'type.not_water_bill': `${R}notWaterBill`,
  'type.not_electricity_bill': `${R}notElectricityBill`,
  'name.unrelated': `${R}billOtherName`,
  'address.mismatch': `${R}billAddressMismatch`,
  'address.unconfirmed': `${R}billAddressUnchecked`,
  'address.unreadable': `${R}billAddressUnchecked`,
  'address.not_found': `${R}billAddressUnchecked`,
  'date.ageing': `${R}billDateAgeing`,
  'date.stale': `${R}billDateStale`,
  'date.unknown': `${R}billDateUnknown`,
}

/** One short line per amber or red chip that has a fixed-word reason. Nothing when none does. */
export function ReasonLines({ chips, t, words = REASON_WORDS }: {
  chips: DocChipData[]; t: T; words?: Record<string, string>
}) {
  const lines = chips.filter((c) => (c.state === 'amber' || c.state === 'red') && words[`${c.key}.${c.reason}`])
  if (lines.length === 0) return null
  return (
    <ul className="mt-1 space-y-0.5" data-reason-lines>
      {lines.map((c) => (
        <li key={c.key} className={`text-[11.5px] leading-snug ${STATE_COLOURS[c.state].line}`}>
          <b>{chipText(c, t)}:</b> {t(words[`${c.key}.${c.reason}`])}
        </li>
      ))}
    </ul>
  )
}

/** The active language for dates. `useT` throws outside the provider (a bare render in a unit test);
 *  the app always has it. */
function useDateLocale(): string | undefined {
  try {
    return useT().locale
  } catch {
    return undefined
  }
}

/** True when `ReadTime` will draw something: "not read yet" (null) or a time that parses. */
export function readTimeShows(readAt: string | null | undefined): boolean {
  return readAt === null || (readAt !== undefined && formatReadTime(readAt) !== '')
}

/** "read 25 Nov, 09:12"; "not read yet" ONLY when `read_at` is null. Nothing when it is undefined
 *  (an old payload) or does not parse. */
export function ReadTime({ readAt, t, now, locale }: {
  readAt: string | null | undefined; t: T; now?: Date; locale?: string
}) {
  const active = useDateLocale()
  if (readAt === undefined) return null
  const when = formatReadTime(readAt, { now, locale: locale ?? active })
  if (readAt !== null && !when) return null
  return (
    <span className="whitespace-nowrap text-ground-400" data-read-at>
      {when ? t('admin.scholarship.docsDrawer.readAt', { date: when }) : t('admin.scholarship.docsDrawer.readAtNone')}
    </span>
  )
}

/** The grey speech-bubble with a count. Hidden unless the payload has an AI-notes count (none does yet). */
export function NotesIcon({ count, t }: { count: number | undefined; t: T }) {
  if (!count || count < 1) return null
  return (
    <span className="inline-flex cursor-help items-center gap-0.5 text-[10px] text-ground-400" data-notes-icon
      title={t('admin.scholarship.docsDrawer.notesHint', { count: String(count) })}>
      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
      </svg>
      {count}
    </span>
  )
}
