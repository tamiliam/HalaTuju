/**
 * THE DOCUMENT CHIP STANDARD, WEB SIDE — the ONE colour map, the served-chip types, and the read time.
 *
 * Both screens (the officer drawer, the student checklists) draw the chips the API serves with this
 * map and nothing else. Green ✓, amber !, red ✕, grey with NO symbol. Approved look:
 * `halatuju_api/docs/document-chip-mockup-approved-2026-11-26.html`.
 */
export type ChipState = 'green' | 'amber' | 'red' | 'grey'
export type ChipPillWord = 'verified' | 'check' | 'problem' | 'unread'

/** One served chip. `label` is the STUDENT payload only (today's badge word as an i18n key). */
export interface DocChipData {
  key: string
  status: 'verified' | 'partial' | 'not' | 'unknown'
  state: ChipState
  student_action: string
  reason: string
  kind: 'fact' | 'year' | 'plain' | 'note'
  value?: string | number | null
  label?: string
}

/** The fields every document payload now carries (the API serves them; absent on an old payload). */
export interface ServedChips {
  chips?: DocChipData[]
  chip_pill?: ChipPillWord
  read_at?: string | null
}

/** The i18n key of each state's spoken word (for DocChip's sr-only text). */
export const STATE_WORD_KEY: Record<ChipState, string> = {
  green: 'common.chipState.green', amber: 'common.chipState.amber',
  red: 'common.chipState.red', grey: 'common.chipState.grey',
}

export const CHIP_SYMBOL: Record<ChipState, string> = { green: '✓', amber: '!', red: '✕', grey: '' }

/** The ONE colour map. `chip` = the rounded tag, `text` = a bare fact word, `badge` = the icon
 *  badge tint, `pill` = the document pill, `line` = a reason line. */
export const STATE_COLOURS: Record<ChipState, { chip: string; text: string; badge: string; line: string }> = {
  green: { chip: 'bg-positive-50 text-positive-700 ring-positive-200', text: 'text-positive-700',
    badge: 'bg-positive-50', line: 'text-positive-700' },
  amber: { chip: 'bg-caution-50 text-caution-700 ring-caution-200', text: 'text-caution-700',
    badge: 'bg-caution-50', line: 'text-caution-700' },
  red: { chip: 'bg-critical-50 text-critical-700 ring-critical-200', text: 'text-critical-600',
    badge: 'bg-critical-50', line: 'text-critical-700' },
  grey: { chip: 'bg-ground-50 text-ground-500 ring-ground-200', text: 'text-ground-400',
    badge: 'bg-ground-100', line: 'text-ground-500' },
}

export const PILL_COLOURS: Record<ChipPillWord, string> = {
  verified: 'bg-positive-100 text-positive-700',
  check: 'bg-caution-100 text-caution-700',
  problem: 'bg-critical-100 text-critical-700',
  unread: 'bg-ground-100 text-ground-500',
}

/** The pill's state, for the icon badge beside it. */
export const PILL_STATE: Record<ChipPillWord, ChipState> = {
  verified: 'green', check: 'amber', problem: 'red', unread: 'grey',
}

/** The student checklists' badge kinds -> the one state vocabulary. Both greys are grey now. */
export function kindToState(kind: 'match' | 'partial' | 'mismatch' | 'unreadable' | 'none'): ChipState {
  return kind === 'match' ? 'green' : kind === 'partial' ? 'amber' : kind === 'mismatch' ? 'red' : 'grey'
}

const INTL_LOCALE: Record<string, string> = { en: 'en-GB', ms: 'ms-MY', ta: 'ta-IN' }

/** "25 Nov, 09:12" in the active language, with the year ("25 Nov 2026, 09:12") only when it is not
 *  the current year; `full` always shows the year. null / unparseable -> ''. Local time, 24-hour. */
export function formatReadTime(
  iso: string | null | undefined,
  opts: { full?: boolean; now?: Date; locale?: string } = {},
): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const tag = INTL_LOCALE[opts.locale ?? 'en'] ?? 'en-GB'
  const showYear = opts.full || d.getFullYear() !== (opts.now ?? new Date()).getFullYear()
  const date = new Intl.DateTimeFormat(tag, { day: 'numeric', month: 'short', ...(showYear ? { year: 'numeric' } : {}) }).format(d)
  const time = new Intl.DateTimeFormat(tag, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d)
  return `${date}, ${time}`
}

/** The served fact chip for one row of a student checklist, or undefined (fall back to today's rule).
 *  A payload whose chip list is empty (the server's chip code failed) also falls back. */
export function servedChip(doc: ServedChips, key: string): DocChipData | undefined {
  return doc.chips?.length ? doc.chips.find((c) => c.key === key && c.kind === 'fact') : undefined
}
