/**
 * F3 (I-11): the one-tap reason a reviewer gives for EVERY fact she marks Fail. The reason is about
 * the student, never about the AI. Codes mirror the server's list (`apps/scholarship/fail_reasons.py`
 * `CODES`); the label key follows the `REQUEST_CATEGORIES` convention:
 * code -> `admin.scholarship.recordVerdict.failReason.<code>`.
 *
 * drift-test: halatuju-web/src/lib/__tests__/failReasonsDrift.test.ts
 */
export const VERDICT_FACTS = ['identity', 'academic', 'pathway', 'income'] as const
export const FAIL_REASON_CODES = [
  'proof_missing', 'document_false', 'documents_differ', 'interview_differs', 'other',
] as const
export type FailReasonCode = (typeof FAIL_REASON_CODES)[number]
/** The chip pre-selected when a fact is marked Fail; the server stores the same when none is sent. */
export const DEFAULT_FAIL_REASON: FailReasonCode = 'other'

/** The facts the reviewer marked Fail (each one takes a reason). */
export function failedFacts(officerVerdict: Record<string, string>): string[] {
  return VERDICT_FACTS.filter((f) => officerVerdict[f] === 'fail')
}

/** One reason for every failed fact: the one chosen, else Other. None for a Pass. */
export function reasonsToSend(
  officerVerdict: Record<string, string>,
  failReasons: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = {}
  for (const f of failedFacts(officerVerdict)) {
    const chosen = failReasons[f]
    out[f] = (FAIL_REASON_CODES as readonly string[]).includes(chosen) ? chosen : DEFAULT_FAIL_REASON
  }
  return out
}
