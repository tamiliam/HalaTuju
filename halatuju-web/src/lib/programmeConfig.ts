/**
 * Layer 0 Sprint 5 — pure helpers behind the "What we ask for" screen (`/admin/programme`).
 *
 * ⚠ THE CATALOGUE IS NOT A FENCE, and this file is not a rule. It shapes what the server sent for
 * display (grouping, ordering, the diff behind the Save button, the summary sentence); the server
 * decides what may be written and what a programme asks for. Nothing here is consulted by any gate.
 *
 * The Layer 2 constraint holds here too: the ROW ORDER below is a display convention computed at
 * render from the item's kind and code — never stored, never per-programme.
 */
import type { ProgrammeConfigItem, ProgrammeItemState } from '@/lib/admin-api'

export const ITEM_STATES: readonly ProgrammeItemState[] = ['off', 'optional', 'required']

/**
 * Display order within each kind — the approved design leads with the four core documents, then
 * the offered extras; questions follow the wizard's own reading order. An item the list does not
 * know sorts last, alphabetically, so a new catalogue row is visible rather than lost.
 */
const DOCUMENT_ORDER = [
  'ic', 'results_slip', 'offer_letter', 'income_proof',
  'electricity_bill', 'water_bill', 'school_leaving_cert', 'statement_of_intent', 'photo',
]
const QUESTION_ORDER = [
  'family_roster', 'address', 'aspirations', 'plans', 'daily_life', 'fears',
  'funding', 'consent', 'justification', 'anything_else',
]

function rank(order: string[], code: string): number {
  const i = order.indexOf(code)
  return i === -1 ? order.length : i
}

export function sortItems(items: ProgrammeConfigItem[]): ProgrammeConfigItem[] {
  return [...items].sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'document' ? -1 : 1
    const order = a.kind === 'document' ? DOCUMENT_ORDER : QUESTION_ORDER
    const d = rank(order, a.code) - rank(order, b.code)
    return d !== 0 ? d : a.code.localeCompare(b.code)
  })
}

export function documents(items: ProgrammeConfigItem[]): ProgrammeConfigItem[] {
  return sortItems(items.filter((i) => i.kind === 'document'))
}

export function questions(items: ProgrammeConfigItem[]): ProgrammeConfigItem[] {
  return sortItems(items.filter((i) => i.kind === 'question'))
}

/** `income_proof` is drawn heavier (owner decision 3): it is the whole means test, not one upload. */
export function isHeavy(item: ProgrammeConfigItem): boolean {
  return item.kind === 'document' && item.code === 'income_proof'
}

export type Draft = Record<string, ProgrammeItemState>   // key = `${kind}:${code}`

export const itemKey = (i: Pick<ProgrammeConfigItem, 'kind' | 'code'>) => `${i.kind}:${i.code}`

export function draftFrom(items: ProgrammeConfigItem[]): Draft {
  return Object.fromEntries(items.map((i) => [itemKey(i), i.state]))
}

/**
 * The rows whose draft state differs from what the server holds — exactly what the PUT sends.
 * The Save button is disabled when this is empty (the platform "nothing to save" standard,
 * owner ruling request #6): a COMPUTED diff, never a constant.
 */
export function changes(
  items: ProgrammeConfigItem[], draft: Draft,
): Pick<ProgrammeConfigItem, 'kind' | 'code' | 'state'>[] {
  const out: Pick<ProgrammeConfigItem, 'kind' | 'code' | 'state'>[] = []
  for (const i of items) {
    const next = draft[itemKey(i)]
    if (next !== undefined && next !== i.state) out.push({ kind: i.kind, code: i.code, state: next })
  }
  return out
}

/**
 * A core row is LOCKED at required (the owner's policy floor): the control still SHOWS all three
 * so the lock is legible, but only `required` is selectable. Read from the item's own `is_core`
 * flag — never a constant — so a screen cannot lie about what is locked (the IC-padlock lesson).
 */
export function allowedStates(item: ProgrammeConfigItem): readonly ProgrammeItemState[] {
  return item.is_core ? ['required'] : ITEM_STATES
}

/** Counts for the footer sentence — "asks for N and offers M" — off one kind's rows. */
export function tally(rows: ProgrammeConfigItem[], draft: Draft): { required: number; optional: number; off: number } {
  const t = { required: 0, optional: 0, off: 0 }
  for (const r of rows) t[draft[itemKey(r)] ?? r.state] += 1
  return t
}
