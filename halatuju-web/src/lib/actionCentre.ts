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
    case 'clarify': // Check 2: a one-line answer, same as an explanation
      return 'chat'
    case 'confirm':
    default:
      return 'checklist'
  }
}

// Action-Centre ordering by WEIGHT, not recency: a hard blocker (a missing document
// that stops verification — birth cert, IC, results slip, offer) must sit above a soft
// clarify question (device / transport / sibling), so the student tackles the
// make-or-break item first.
const _KIND_WEIGHT: Record<string, number> = {
  doc: 0,          // upload a blocking document — highest priority
  confirm: 1,      // review / correct a fact
  explanation: 1,  // type a short reply
  clarify: 2,      // soft Check-2 question — lowest priority
  human: 3,        // reviewer-only (never shown to a student, ordered last if present)
}

/** Stable sort of open tickets by weight (blockers first), preserving the server's
 *  within-group order. Pure — the component calls this before rendering. */
export function sortByWeight<T extends { kind: string }>(items: T[]): T[] {
  return items
    .map((item, i) => ({ item, i }))
    .sort((a, b) =>
      ((_KIND_WEIGHT[a.item.kind] ?? 1) - (_KIND_WEIGHT[b.item.kind] ?? 1)) || (a.i - b.i))
    .map(({ item }) => item)
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
  'str_not_current',
  'str_recipient_mismatch',
  'offer_letter_missing',
  'offer_not_official',
  'offer_unreadable',
  'offer_no_identity',
  'offer_name_mismatch',
  'pathway_undeclared',
  'pathway_confirm',
  // Check 2 STEP 2 — AI clarify queries (kind='clarify', source='check2').
  'course_unspecified',
  'sibling_level_unknown',
  'device_status_unknown',
  'transport_cost_unknown',
  // #8 — utility-bill consistency clarify queries (dark until CHECK2_STUDENT_QUERIES_ENABLED).
  'utility_holder_unknown',
  'utility_address_mismatch',
  // Full-household-income completeness (reviewer-query automation S1): a parent's income
  // proof (kind='doc') or their work/status when the slot is blank (kind='clarify').
  'father_income_proof_missing',
  'mother_income_proof_missing',
  'father_status_unknown',
  'mother_status_unknown',
  // S2 — stale salary slip (doc) + sibling-in-tertiary funding (clarify).
  'income_doc_stale',
  'sibling_tertiary_funding',
  // S3 — offer carries no readable reporting date → ask when/where to report (clarify).
  'reporting_date_unknown',
  // Phase 2A — a declared informal income needs a flexible supporting doc (kind='doc').
  'declared_income_evidence_missing',
  // Phase 2B — unemployment detail (clarify) + optional EPF corroboration (doc).
  'unemployment_detail_unknown',
  'unemployment_epf_missing',
  // Post-award payout — the bank-details task. The OPEN state renders via the dedicated
  // BankDetailsTask component (special-cased in ActionCentre), but the RESOLVED state falls
  // through to the generic Done card, so it must be a KNOWN code — otherwise it's mistaken
  // for a free-text officer ticket ("From your reviewer" + a blank title).
  'bank_details_missing',
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

/** Who raised this task, for the "From …" attribution line.
 *  - 'reviewer'  → a human reviewer raised it (free-text officer tickets)
 *  - 'assistant' → the system / Check-2 "review assistant" raised it (known codes:
 *                  the AI clarify questions, the pathway confirm, and the
 *                  missing-compulsory-document upload requests). */
export function attributionFor(item: Pick<ResolutionItem, 'source' | 'code'>): 'reviewer' | 'assistant' {
  return isOfficerItem(item) ? 'reviewer' : 'assistant'
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
  // The bank-details task has no `item.<code>` copy block (its OPEN card is the dedicated
  // BankDetailsTask component); reuse the bank card's own title so the RESOLVED Done card
  // reads "Add your bank account for payment" (struck-through) instead of a blank line.
  if (item.code === 'bank_details_missing') {
    return {
      kind: 'i18n',
      titleKey: 'scholarship.actionCentre.bank.title',
      descKey: 'scholarship.actionCentre.bank.intro',
    }
  }
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
// 'grades'    → the onboarding grades editor (entered subjects/grades — there is no
//               grades surface in /application, so academic fixes deep-link there)
// 'documents' → the Documents tab (identity, income proof, the results SLIP)
// 'story'     → "Your story" (pathway / narrative)
export type ConfirmTarget = 'grades' | 'documents' | 'story'

/**
 * Map a ticket's `fact` to the section a `confirm` ticket should scroll/switch
 * to. Falls back to the Documents tab — most verification facts are document
 * grounded, so it's the safest default.
 */
export function confirmTargetFor(fact: string): ConfirmTarget {
  const f = (fact || '').toLowerCase()
  // The results SLIP is an uploaded document → re-upload it in the Documents tab.
  if (f.includes('slip')) return 'documents'
  // The student's entered subjects/grades live in the onboarding grades editor —
  // there is no grades surface in /application — so academic_* facts go there.
  if (f.includes('academic') || f.includes('grade')) return 'grades'
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
