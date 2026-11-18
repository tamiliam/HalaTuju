/**
 * LL2: the one-tap reason when a reviewer fails a fact the engine called green (`verified`).
 * Codes are the server's (`apps/scholarship/fail_reasons.py`); the label key follows the
 * `REQUEST_CATEGORIES` convention: code -> `admin.scholarship.recordVerdict.failReason.<code>`.
 */
export const VERDICT_FACTS = ['identity', 'academic', 'pathway', 'income'] as const
export const FAIL_REASON_CODES = ['engine_wrong', 'read_wrong', 'new_information', 'programme_rule', 'other'] as const

/** The facts the engine showed green and the reviewer failed (the only ones that take a reason). */
export function greenFailFacts(
  verdict: readonly { fact: string; status: string }[] | null | undefined,
  officerVerdict: Record<string, string>,
): string[] {
  return VERDICT_FACTS.filter((f) =>
    officerVerdict[f] === 'fail' && (verdict || []).some((v) => v.fact === f && v.status === 'verified'))
}

/** Reasons the server will keep: only for green -> fail facts, and only a known code. */
export function reasonsToSend(
  verdict: readonly { fact: string; status: string }[] | null | undefined,
  officerVerdict: Record<string, string>,
  failReasons: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = {}
  for (const f of greenFailFacts(verdict, officerVerdict)) if (failReasons[f]) out[f] = failReasons[f]
  return out
}
