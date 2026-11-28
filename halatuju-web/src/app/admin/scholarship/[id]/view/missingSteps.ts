/**
 * #81 (27 Nov 2026): when Approve saves the verdict but the case cannot move to QC, NAME the step that is missing.
 *
 * ⚠ THE RULE IS THE SERVER'S. The list is the hand-off's own `missing` (`services/handoff.py`, owner ruling
 * 28 Nov 2026: a submitted case at interviewing / interviewed re-checks only what can still be fixed), read
 * through `handoffMissing` in `@/lib/handoff`. This file only words those part keys. Nothing here decides
 * what is required, so the list can never disagree with the gate. A key not in the list is not named.
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

/** The message keys of the hand-off's missing parts, in the student's order. */
export function missingStepKeys(missing: ReadonlyArray<string> | null | undefined): string[] {
  if (!missing?.length) return []
  return STEPS.filter(([field]) => missing.includes(field)).map(([, key]) => key)
}

/** "Saved, but NOT sent to QC — still missing: X and Y." Falls back to the general line when no step is named. */
export function notSubmittedIncompleteText(
  t: TFn, missing: ReadonlyArray<string> | null | undefined, locale?: string,
): string {
  const keys = missingStepKeys(missing)
  if (!keys.length) return t('admin.scholarship.decision.notSubmittedIncomplete')
  return t('admin.scholarship.decision.notSubmittedMissing', {
    steps: joinFacts(keys.map((k) => t(k)), locale ?? 'en'),
  })
}
