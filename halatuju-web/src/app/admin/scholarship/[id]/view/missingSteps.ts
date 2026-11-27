/**
 * #81 (27 Nov 2026): when Approve saves the verdict but the case cannot move to QC, NAME the step that is missing.
 *
 * ⚠ THE RULE IS THE SERVER'S. `completeness` is `services/completeness.py`'s answer, served on the record-verdict
 * payload; this file only reads its `*_done` keys and words them. Nothing here decides what is required, so the list
 * can never disagree with the gate. A key the payload does not carry is not listed (only an explicit `false` is).
 */
import type { AdminCompleteness } from '@/lib/admin-api'

import { joinFacts } from './DecisionMissing'
import type { TFn } from './cockpitCtx'

/** The gate's steps, in the order the student meets them, each with its words. */
const STEPS: ReadonlyArray<[keyof AdminCompleteness, string]> = [
  ['quiz_done', 'admin.scholarship.decision.missingStep.quiz'],
  ['details_done', 'admin.scholarship.decision.missingStep.details'],
  ['address_done', 'admin.scholarship.decision.missingStep.address'],
  ['family_done', 'admin.scholarship.decision.missingStep.family'],
  ['funding_done', 'admin.scholarship.decision.missingStep.funding'],
  ['documents_done', 'admin.scholarship.decision.missingStep.documents'],
  ['guardian_docs_done', 'admin.scholarship.decision.missingStep.guardianDocs'],
  ['consent_done', 'admin.scholarship.decision.missingStep.consent'],
]

/** The message keys of the steps the served completeness marks not done. */
export function missingStepKeys(c: Partial<AdminCompleteness> | null | undefined): string[] {
  if (!c) return []
  return STEPS.filter(([field]) => c[field] === false).map(([, key]) => key)
}

/** "Saved, but NOT sent to QC — still missing: X and Y." Falls back to the general line when no step is named. */
export function notSubmittedIncompleteText(
  t: TFn, c: Partial<AdminCompleteness> | null | undefined, locale?: string,
): string {
  const keys = missingStepKeys(c)
  if (!keys.length) return t('admin.scholarship.decision.notSubmittedIncomplete')
  return t('admin.scholarship.decision.notSubmittedMissing', {
    steps: joinFacts(keys.map((k) => t(k)), locale ?? 'en'),
  })
}
