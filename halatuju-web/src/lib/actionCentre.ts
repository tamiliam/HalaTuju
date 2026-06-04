/**
 * Pure logic for the Student Action Centre (Sprint 4).
 *
 * Keeps the maths and the code→i18n-key mapping out of the component so they can
 * be unit-tested in a plain node env (no jsdom/RTL). The component reads these
 * helpers; it never re-implements them.
 */

import type { ResolutionItem } from '@/lib/api'

// The icon family a ticket renders, derived purely from its `kind`.
//   doc         → a document icon (upload something)
//   confirm     → a checklist icon (review / re-check a fact)
//   explanation → a chat icon (type a short reply)
export type ActionIcon = 'document' | 'checklist' | 'chat'

/** Map a ticket kind to its icon family. */
export function iconFor(kind: ResolutionItem['kind']): ActionIcon {
  switch (kind) {
    case 'doc':
      return 'document'
    case 'explanation':
      return 'chat'
    case 'confirm':
    default:
      return 'checklist'
  }
}

export interface Progress {
  done: number
  total: number
  pct: number
}

/**
 * Overall completion across all tickets ever raised for this student.
 * `done` = resolved tickets, `total` = open + resolved. `pct` is an integer
 * 0–100. When nothing has ever been raised we treat the student as 100% done
 * (there is genuinely nothing to finish), which keeps the bar full and avoids a
 * divide-by-zero.
 */
export function computeProgress(
  open: ResolutionItem[],
  resolved: ResolutionItem[],
): Progress {
  const done = resolved.length
  const total = open.length + resolved.length
  const pct = total === 0 ? 100 : Math.round((done / total) * 100)
  return { done, total, pct }
}

// System codes the Action Centre knows how to title/describe from i18n. Officer
// tickets (code like "officer_1") are NOT in this set — they carry their own
// `prompt`, which the component renders verbatim as the title.
export const KNOWN_CODES = [
  'ic_missing',
  'ic_unreadable',
  'nric_mismatch',
  'name_mismatch',
  'address_state_mismatch',
  'results_slip_missing',
  'results_slip_unreadable',
  'results_slip_name_mismatch',
  'academic_missing_subjects',
  'academic_grade_mismatch',
  'str_claimed_no_doc',
  'income_proof_missing',
  // Income Check-1 (item 3: earner identity + relationship). The officer-only
  // `income_unverified_needs_interview` is NOT here — it's an interview flag, not a to-do.
  'income_earner_undeclared',
  'earner_ic_missing',
  'earner_ic_unreadable',
  'birth_cert_missing',
  'birth_cert_mismatch',
  'father_patronymic_mismatch',
  'guardianship_letter_missing',
  'offer_unreadable',
  'offer_no_identity',
  'offer_name_mismatch',
  'pathway_undeclared',
  'pathway_confirm',
] as const

export type KnownCode = (typeof KNOWN_CODES)[number]

/** True when a ticket was raised by an officer (free-text) rather than the
 *  system. Officer tickets render `prompt` as their title. We treat anything
 *  with source==='officer', OR a code we don't recognise, as officer-style so a
 *  new/unknown system code still shows something useful instead of a raw key. */
export function isOfficerItem(item: Pick<ResolutionItem, 'source' | 'code'>): boolean {
  if (item.source === 'officer') return true
  return !(KNOWN_CODES as readonly string[]).includes(item.code)
}

/** The i18n key prefix for a system code's title/desc copy. */
export function i18nKeyFor(code: string): string {
  return `scholarship.actionCentre.item.${code}`
}

/**
 * Resolve the display title for a ticket. Officer tickets (and unknown codes)
 * use their own `prompt`; known system codes return the i18n key for the title
 * (the component runs it through `t()` with the ticket params). Returns a
 * discriminated result so the component knows whether to translate or render
 * raw text.
 */
export function titleSourceFor(
  item: Pick<ResolutionItem, 'source' | 'code' | 'prompt'>,
):
  | { kind: 'raw'; text: string }
  | { kind: 'i18n'; titleKey: string; descKey: string } {
  if (isOfficerItem(item)) {
    return { kind: 'raw', text: item.prompt || '' }
  }
  return {
    kind: 'i18n',
    titleKey: `${i18nKeyFor(item.code)}.title`,
    descKey: `${i18nKeyFor(item.code)}.desc`,
  }
}

// Where a `confirm`-kind ticket sends the student to fix the underlying fact.
// 'results'   → the academic results / grades area
// 'documents' → the Documents tab (identity & income proof)
// 'story'     → "Your story" (pathway / narrative)
export type ConfirmTarget = 'results' | 'documents' | 'story'

/**
 * Map a ticket's `fact` to the section a `confirm` ticket should scroll/switch
 * to. Falls back to the Documents tab — most verification facts are document
 * grounded, so it's the safest default.
 */
export function confirmTargetFor(fact: string): ConfirmTarget {
  const f = (fact || '').toLowerCase()
  if (f.includes('academic') || f.includes('result') || f.includes('grade')) {
    return 'results'
  }
  if (f.includes('pathway') || f.includes('story') || f.includes('aspiration')) {
    return 'story'
  }
  // identity, income, address, nric, name, etc. all live behind Documents.
  return 'documents'
}

/** Convert ticket params (string|number values) to the string map `t()` wants. */
export function paramsToStrings(
  params: Record<string, string | number> | undefined | null,
): Record<string, string> {
  const out: Record<string, string> = {}
  if (!params) return out
  for (const [k, v] of Object.entries(params)) out[k] = String(v)
  return out
}

/**
 * Like `paramsToStrings`, but t-aware so the income reason codes' `members` list
 * (e.g. ['father','brother']) renders as localized, joined labels ("Father, Elder
 * brother") instead of raw codes. Used by both the student Action Centre and the
 * officer verdict tile so a member-tagged income gap reads naturally in en/ms/ta.
 */
export function localiseParams(
  params: Record<string, string | number | string[]> | undefined | null,
  t: (key: string) => string,
): Record<string, string> {
  const out: Record<string, string> = {}
  if (!params) return out
  for (const [k, v] of Object.entries(params)) {
    if (k === 'members' && Array.isArray(v)) {
      out[k] = v.map((m) => t(`scholarship.docs.income.wizard.member.${m}`)).join(', ')
    } else {
      out[k] = String(v)
    }
  }
  return out
}
