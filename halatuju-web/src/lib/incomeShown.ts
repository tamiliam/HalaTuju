/** The per-earner "has this earner's income been SHOWN?" answer, as SERVED on the officer's
 *  applicant-detail payload (TD-262 chunks 2+3).
 *
 *  ⚠ THE RULE IS SERVED, NOT MIRRORED. `officerCockpit.incomeSubSections` used to decide an
 *  earner's income evidence for itself — `slip || epfDoc || supportFor(m)`, which is document
 *  PRESENCE — while the submission gate asked whether the document could be READ. So the officer's
 *  panel showed a `not_salary` photo, a blank EPF and an unbacked support letter as satisfied
 *  income evidence about households the gate was holding shut (W2 / W3 / W4), and the red *Missing*
 *  row the officer needed never appeared. The answer now comes from
 *  `apps/scholarship/income_shown.py` — the same function the gate, the chase list and the AI
 *  verdict read — so the two can no longer differ.
 *
 *  ⚠ THERE IS NO STR ARM AND THERE MUST NOT BE ONE. An STR is evidence about the HOUSEHOLD; it
 *  clears the gate and settles the verdict by precedence, and a working adult's income proof is
 *  ADDITIONAL to it (owner 2026-09-19). A household STR never ticks an earner.
 *
 *  The FALLBACK is the old presence reading, not "nothing is evidenced": the two services deploy
 *  together but not atomically, so a cached payload or an api one revision behind must leave the
 *  panel exactly as it was rather than painting every earner red.
 */

/** A stable reason code from `income_shown.REASONS`. Kept as `string`: the api owns the
 *  vocabulary, and a code this build has never heard of must degrade, never crash. */
export type IncomeShownReason = string

export interface IncomeShownUnusable {
  doc_id: number
  doc_type: string
  reason: IncomeShownReason
}

export interface IncomeShownAnswer {
  /** Has this earner's income been shown any one of the three per-earner ways? */
  shown: boolean
  /** Which way carried it: 'salary_slip' | 'epf' | 'declared_letter'; null when nothing did. */
  way: string | null
  /** The document ids that CARRY the winning way. */
  documents: number[]
  /** Every income document on file for this earner that cannot carry it, and why. */
  unusable: IncomeShownUnusable[]
}

export type IncomeShownMap = Record<string, IncomeShownAnswer>

/** The served answer for one earner, or `null` when the field is absent (old payload) or
 *  malformed. `null` means "fall back to today's behaviour" — never "nothing is shown". */
export function answerFor(
  served: IncomeShownMap | null | undefined, member: string,
): IncomeShownAnswer | null {
  const a = served?.[member]
  if (!a || typeof a !== 'object' || typeof a.shown !== 'boolean') return null
  return a
}

/** The reason this document cannot carry that earner's income, or '' when it can (or when there
 *  is no served answer to ask). */
export function unusableReason(
  answer: IncomeShownAnswer | null, docId: number | null | undefined,
): IncomeShownReason {
  if (!answer || docId == null) return ''
  const hit = (answer.unusable || []).find((u) => u.doc_id === docId)
  return hit ? hit.reason : ''
}
