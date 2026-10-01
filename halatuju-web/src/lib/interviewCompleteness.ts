/**
 * TD-253 — has the reviewer answered EVERY question on the interview agenda? (owner, 2026-09-18)
 *
 * "I want this to be a conscious decision on their part, and I want it to be complete." An item is
 * answered by a pressed verdict, by a typed answer however short ("See conclusion" is legitimate),
 * or by deleting it from the agenda. Silence is what is refused. The api refuses the same silence
 * at submit and at Approve/Decline (`halatuju_api/apps/scholarship/interview_completeness.py`);
 * this module is the cockpit's copy of its "answered" rule, so the buttons stay asleep exactly
 * when the server would refuse them — and the reviewer is told why.
 * drift-test: halatuju-web/src/lib/__tests__/interviewCompleteness.test.ts
 */

export interface AgendaFinding { verdict?: string; rationale?: string }

/** A verdict that is an answer on its own ('' is "not classified yet"; 'deleted' leaves the agenda). */
export const ANSWER_VERDICTS: ReadonlySet<string> = new Set(['resolved', 'still_unclear', 'new_concern'])

/** What does NOT count as a typed answer: Unicode whitespace and the zero-width/BOM characters,
 *  spelled out so it means the same in both languages (review F6: `trim` and Python's `strip`
 *  disagree on U+FEFF). Its `source` must equal the api's `_BLANK` exactly — the drift test reads it. */
export const BLANK = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200d\u2028\u2029\u202f\u205f\u3000\ufeff]/g

export function isAnswered(finding: AgendaFinding | null | undefined): boolean {
  if (!finding || typeof finding !== 'object') return false
  if (ANSWER_VERDICTS.has(finding.verdict ?? '')) return true
  return (finding.rationale ?? '').replace(BLANK, '').length > 0
}

/** The agenda codes neither answered nor deleted, in agenda order, without duplicates. */
export function missingAgendaItems(
  agendaCodes: readonly string[], findings: Record<string, AgendaFinding> | null | undefined,
): string[] {
  const out: string[] = []
  for (const code of agendaCodes) {
    const f = findings?.[code]
    if (f?.verdict === 'deleted' || isAnswered(f) || out.includes(code)) continue
    out.push(code)
  }
  return out
}

/** The statuses at which a case with no recorded decision is in the reviewer's hands — the api's
 *  `_REVIEWER_STAGE`, compared by the drift test. 'interviewed' (awaiting QC) is out on purpose. */
export const REVIEWER_STAGE: ReadonlySet<string> = new Set(['shortlisted', 'profile_complete', 'interviewing'])

/**
 * Does the rule bind on this case? Only where the REVIEWER decides (the api's
 * `decision_gate_applies`): a super has reopened the decision, or none is recorded and the case is
 * at the reviewer's stage. A recorded decision is an Approve or a Decline — a hold or a blank also
 * stamps `verdict_decided_at` and is NOT one (review F1). A decision recorded before the rule
 * existed — 33 of them on 2026-09-18 carried an empty interview — is not reached back over.
 */
export function interviewGateApplies(
  c: { status: string; recordedOutcome: string | null; decisionReopened: boolean },
): boolean {
  if (c.decisionReopened) return true
  const decided = c.recordedOutcome === 'accept' || c.recordedOutcome === 'decline'
  return !decided && REVIEWER_STAGE.has(c.status)
}

type Translate = (key: string, vars?: Record<string, string>) => string

/** The reviewer-facing words for an interview refusal from the api, or null when the error is not
 *  one (review F5: the decision door used to print the server's English). The count is the
 *  server's own `missing` list — the agenda it actually checked. */
export function interviewRefusalText(e: unknown, t: Translate): string | null {
  const err = (e ?? {}) as { code?: string; body?: { missing?: unknown } }
  const missing = err.body?.missing
  const count = String(Array.isArray(missing) ? missing.length : 0)
  if (err.code === 'findings_incomplete') return t('admin.scholarship.interview.unanswered', { count })
  if (err.code === 'interview_incomplete') {
    return t('admin.scholarship.recordVerdict.findingsIncomplete', { count })
  }
  if (err.code === 'interview_not_submitted') return t('admin.scholarship.recordVerdict.finaliseNoInterview')
  return null
}
