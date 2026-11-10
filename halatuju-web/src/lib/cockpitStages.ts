/**
 * Officer cockpit — the decision gates and which cards each stage shows.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */


// ── Officer-decision gates ───────────────────────────────────────────────────
// Lifted verbatim out of the cockpit page (TD audit 2026-06-14) so the decision
// rules are pure + unit-testable, instead of inline IIFEs in 1,700 lines of JSX.

type OfficerVerdict = Record<string, string>

// Application states where a "save verdict = accept" can still apply (case still live).
export const LIVE_STATES = ['shortlisted', 'profile_complete', 'interviewing', 'interviewed']
// States (or a submitted interview) after which querying is closed and Outstanding is read-only.
export const QUERYING_LOCKED_STATES = ['interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn', 'expired']
/**
 * The states meaning "a QC accepted the recommendation" — so the sign-off, and any override
 * trail behind it, must be shown.
 *
 * A NAMED set rather than a literal at each site, because the literal is exactly how this broke.
 * `awarded` was inserted in the MIDDLE of the lifecycle (recommended → awarded → active →
 * maintenance → closed) by the post-award sprints, and three inline conditions listed the states
 * either side of it. The result: 47 of 143 production records showed a bare "recommended by …"
 * with no tick and no QC attribution — the AWARDED ones, i.e. the records where money had
 * already moved and you most want to know who cleared them.
 *
 * `QUERYING_LOCKED_STATES` above lists `awarded` correctly, which is the tell: the omission was
 * staleness, not a decision.
 */
export const QC_ACCEPTED_STATES = ['recommended', 'awarded', 'active', 'maintenance', 'closed']

/** True once a QC has accepted the recommendation, whatever has happened since. */
export function isQcAccepted(status: string): boolean {
  return QC_ACCEPTED_STATES.includes(status)
}

// The four facts the officer rules on.
export const DECISION_FACTS = ['identity', 'academic', 'pathway', 'income'] as const

/**
 * "Save verdict IS accept": the profile is complete and the case is still live.
 *
 * ⚠ THE FOUR PASS/FAIL MARKS ARE DELIBERATELY NOT PART OF THIS TEST (BrightPath #20).
 * They are the reviewer's scorecard OF THE AI — `audit.compute_overrides` reads them against
 * what the AI *asserted* to produce the reliability figure. They say nothing about the student,
 * so they must never decide whether the student's case moves. They used to: a Fail on academic,
 * pathway or income made this return false, the submit was skipped, and NOTHING on screen said
 * so. Application 73 sat at `interviewing` for fourteen days after a recorded Accept, because
 * its reviewer honestly reported that our payslip reading was poor.
 *
 * The red-fact floor has NOT been removed — it lives at the QC gate, where it belongs, and is
 * computed from the AI's OWN live verdict (`build_verdict` → `verdict_gap_floor`), never from a
 * rating of it. Gating here as well was both wrong and redundant.
 *
 * ⚠ The officer verdict is NOT a parameter, on purpose: there is no way to pass the ratings back
 * in. A comment asking a future caller not to is a request; removing the parameter is a rule.
 */
export function isClearAccept(completenessComplete: boolean, status: string): boolean {
  return !!completenessComplete && LIVE_STATES.includes(status)
}

/**
 * A verdict was RECORDED but the case never MOVED — the half-completed Approve.
 *
 * ⚠ THIS EXISTS BECAUSE THE FIRST HALF OF AN APPROVE LOCKS THE PANEL THE SECOND HALF NEEDS.
 * One press does two things: `record-verdict` saves the decision, then `verify-accept` submits
 * the case to QC. Saving a verdict sets `verdict_decided_at`, and that is what makes the
 * Recommendation card read-only — so when the second step does not run (the profile read
 * incomplete, or the accept call failed), the reviewer is left looking at a locked panel with
 * no Approve button and no way to finish. The ONLY exit was Reopen, which is super-only AND is
 * recorded as a correction against the reviewer, asking what she got wrong. She got nothing
 * wrong. Application 144 sat like that from 1 to 7 September, and its reviewer could not have
 * freed it herself. (BrightPath #21, found by the owner 2026-09-07.)
 *
 * ⚠ IT IS KEYED ON `verified_at`, NOT ON THE STATUS, because that field is what `verify-accept`
 * stamps — it is the record of whether the second half ever ran. A status check alone would
 * also unlock a case that moved on and came back by some other route.
 *
 * A DECLINE is unaffected: it leaves the case `rejected`, which is not a live state.
 */
export function isStuckAfterVerdict(
  opts: {
    status: string | null | undefined
    verdictDecidedAt?: string | null
    verifiedAt?: string | null
    /** The recorded outcome — 'accept' | 'decline'. See the ⚠ below: it decides WHICH mark
     *  proves the submit ran, and without it a decline reads as stuck for ever. */
    outcome?: string | null
  },
): boolean {
  if (!opts.verdictDecidedAt) return false   // no verdict recorded — nothing half-done
  if (!LIVE_STATES.includes(opts.status || '')) return false
  // ⚠ TWO ROADS REACH QC AND THEY LEAVE DIFFERENT MARKS (BrightPath #24, 2026-09-18).
  // Recommend goes through verify-accept, which stamps `verified_at`. DECLINE has no identity or
  // completeness gate — an incomplete applicant is exactly who gets declined — so since 2026-07-19
  // `submit-decline` moves the case to 'interviewed' (AWAITING QC) and stamps NOTHING else.
  // Asking for `verified_at` on that road is asking for a mark that is never written: every
  // declined case awaiting QC read as "not submitted", and the panel told the reviewer to press
  // Approve — which would have replaced her decline with a recommendation.
  if (opts.outcome === 'decline') return opts.status !== 'interviewed'
  return !opts.verifiedAt
}

/**
 * What a "Save verdict" click actually DID, as one closed set of names.
 *
 * ⚠ THIS EXISTS SO THAT NO OUTCOME CAN BE SILENT — the whole of BrightPath #20 was a branch with
 * no message attached. Every value here must have a line on screen; adding a value without one is
 * the bug returning. The caller renders it and nothing else decides.
 */
export type VerdictSaveOutcome =
  | 'accepted'                   // recorded AND submitted to QC
  | 'not_submitted_incomplete'   // asked to submit; the applicant has steps outstanding
  | 'not_submitted_status'       // asked to submit; the case is past a submittable stage
  | 'saved'                      // recorded only — no submit was asked for, or one failed loudly

export function verdictSaveOutcome(input: {
  acceptRequested: boolean
  accepted: boolean
  completenessComplete: boolean
  status: string
}): VerdictSaveOutcome {
  if (input.accepted) return 'accepted'
  if (!input.acceptRequested) return 'saved'
  if (!input.completenessComplete) return 'not_submitted_incomplete'
  if (!LIVE_STATES.includes(input.status)) return 'not_submitted_status'
  // Asked, allowed, and still not accepted: the submit call itself threw. The caller has already
  // surfaced that error, so this must not overwrite it with a second, vaguer explanation.
  return 'saved'
}

/** The words for a Save verdict that threw. ⚠ A `network_failure` (marked by `adminMutate`: no
 *  answer came back) may have SAVED — request #61: a 50 s finalise did, and the reviewer pressed
 *  again, re-running paid AI calls — so it says so instead of printing the browser's text. */
export function verdictSaveErrorText(e: unknown, t: (key: string) => string, fallback: string): string {
  if ((e as { code?: string } | null)?.code === 'network_failure') {
    return t('admin.scholarship.recordVerdict.mayAlreadyBeSaved')
  }
  return e instanceof Error ? e.message : t(fallback)
}

/** Querying (raise / Resolve / Ask again / request doc) is closed once the interview is concluded. */
export function isQueryingLocked(status: string, interviewStatus?: string): boolean {
  return QUERYING_LOCKED_STATES.includes(status) || interviewStatus === 'submitted'
}

/**
 * WHY querying is locked — because the boolean above folds two independent reasons together
 * and the caller has to put one of them on screen.
 *
 * ⚠ THE COPY USED TO HARD-CODE "the interview is concluded", which is a statement about a thing
 * that never happened on 44 production records: an application rejected at `shortlisted` or
 * expired is locked by its STATUS, with no interview anywhere in its history. Second instance of
 * the same shape as `_can_review` reporting `not_reviewer` about a paused reviewer (lessons.md
 * 2026-08-03) — when a predicate collapses several reasons into one boolean, the caller that
 * renders it will state the wrong one. Return the reason instead of re-deriving it at the call
 * site, so there is one place to be right.
 *
 * A genuinely submitted interview names itself; everything else is simply a case that is no
 * longer under review (which reads true for a rejection, an expiry AND a funded student).
 */
export type QueryingLockReason = 'interview' | 'closed'

export function queryingLockReason(
  status: string, interviewStatus?: string,
): QueryingLockReason | null {
  if (!isQueryingLocked(status, interviewStatus)) return null
  return interviewStatus === 'submitted' ? 'interview' : 'closed'
}

/** Approve/Decline activate only once the interview is submitted AND every agenda item answered
 *  (TD-253 — the word "submitted" alone let an empty interview through, app #32; see
 *  `interviewCompleteness`), all four facts are pass/fail, and a reason is written. */
export function isDecisionReady(interviewStatus: string | undefined, officerVerdict: OfficerVerdict, reason: string, interviewComplete: boolean): boolean {
  return interviewStatus === 'submitted' && interviewComplete
    && DECISION_FACTS.every((f) => officerVerdict[f] === 'pass' || officerVerdict[f] === 'fail')
    && (reason || '').trim().length > 0
}

/** Approve additionally requires a recommended assistance amount (the slider or an already-saved one). */
export function isApproveReady(decisionReady: boolean, hasAssistance: boolean): boolean {
  return decisionReady && hasAssistance
}

/**
 * A `shortlisted` application is PRE-SUBMISSION by definition — submitting Step 2 is exactly
 * what moves it out of 'shortlisted' — so it can never have a submitted interview, and
 * `isDecisionReady` above can never be true there.
 *
 * That makes a whole group of cards dead weight at this stage: Rate AI Prediction, the
 * Interview Stage capture, Recommendation (buttons permanently greyed), the funding
 * projection (no award decided yet) and the generated Final profile (only produced at the
 * verdict). Hidden rather than disabled — a disabled card still eats the screen and invites
 * clicking. Mirrors the Assignment card's long-standing `status !== 'shortlisted'` guard —
 * which is now this same function: the cockpit holds no second copy of the test, and the drift
 * test asserts that none comes back.
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 * Owner decision 2026-07-22.
 *
 * What DOES stay at shortlisted: Blockers, Check 2 (chasing the student), Documents,
 * AI Prediction (the verification read as documents arrive) and Reject-this-student
 * (`ORG_REJECT_FROM = ('shortlisted',)` — it exists only there).
 */
export function isPreSubmissionStage(status: string | null | undefined): boolean {
  return (status || '') === 'shortlisted'
}

/** Show the verdict-flow / funding-projection / generated-profile cards? Hidden pre-submission. */
export function showsPostSubmissionCards(status: string | null | undefined): boolean {
  return !isPreSubmissionStage(status)
}

// ── The other end of the lifecycle: a CLOSED case (2026-08-18) ───────────────

/**
 * The terminal off-ramps — the review is over and nothing further can be decided.
 *
 * `closed` joined 2026-10-06 (TD-352): an officer may now close a stalled case from ANY in-play
 * status, so a closed case may never have been decided. A FUNDED closed case keeps its records
 * through the arms below (a recorded verdict, an interview, a profile, Check 2 items); only dead
 * controls go. drift-test: halatuju_api/apps/scholarship/tests/test_closed_case_writes.py
 */
export const CASE_CLOSED_STATES = new Set<string>(['closed', 'rejected', 'withdrawn', 'expired'])

/**
 * Is this case off the review track for good?
 *
 * ⚠ THE REOPEN ARM IS LOAD-BEARING, NOT DEFENSIVE. `reopen.reopen_decision` walks most
 * statuses back toward the reviewer, but `rejected` is NOT in its mapping — a super who
 * reopens a rejected decision leaves the case sitting at `rejected` with
 * `decision_reopened_at` set, and is then expected to re-record the verdict. Keying on
 * status alone would hide the very panel that reopen exists to reach, and the backend guard
 * that mirrors this would refuse the write. See `services.review_writes_closed`.
 *
 * drift-test: halatuju_api/apps/scholarship/tests/test_closed_case_writes.py
 */
export function isCaseClosed(
  opts: { status: string | null | undefined; decisionReopened?: boolean | null },
): boolean {
  if (opts.decisionReopened) return false
  return CASE_CLOSED_STATES.has(opts.status || '')
}

/**
 * Show the Interview Stage box?
 *
 * The pre-submission half is `showsPostSubmissionCards` (no interview can exist before Step 2
 * is submitted) — called here, not restated. The closed half is its counterpart at the other end
 * of the lifecycle: on a case that expired or was rejected before anyone reviewed it, this box
 * offered a live "Suggest interview questions" (a billable Gemini
 * call), Save draft and Submit findings on a file nobody can act on — 44 production records on
 * 2026-08-18, none of which had ever held an interview.
 *
 * A closed case that DOES hold a session keeps the box: it is then a record of an interview
 * that really happened, and the box already renders read-only once the session is submitted.
 * Hiding a record is a different mistake from hiding a dead control.
 */
export function showsInterviewStage(
  opts: {
    status: string | null | undefined
    decisionReopened?: boolean | null
    hasInterviewSession?: boolean | null
  },
): boolean {
  if (!showsPostSubmissionCards(opts.status)) return false
  if (!isCaseClosed(opts)) return true
  return !!opts.hasInterviewSession
}

/**
 * Show the Rate AI Prediction and Recommendation cards?
 *
 * Same shape, different record: what makes these worth keeping on a closed case is a RECORDED
 * VERDICT, not an interview. With one they show the frozen decision trail ("Declined by … ·
 * date") — that is the audit trail and must survive. Without one they offered live Pass/Fail
 * buttons, an editable justification and an Approve that would have stamped a verdict, and an
 * award amount, onto a rejected file.
 */
export function showsDecisionCards(
  opts: {
    status: string | null | undefined
    decisionReopened?: boolean | null
    decisionRecorded?: boolean | null
  },
): boolean {
  if (!showsPostSubmissionCards(opts.status)) return false
  if (!isCaseClosed(opts)) return true
  return !!opts.decisionRecorded
}

/**
 * Show the system-generated Student profile card?
 *
 * ⚠ EMPTY, THIS CARD IS THREE FALSE SENTENCES. On a closed case with no profile it titles itself
 * "(draft)" when no draft exists, promises the draft "will be replaced with an updated final
 * version when you save your verdict" — a verdict the endpoint now refuses — and explains that
 * the profile "is generated automatically when the application is handed over for review", a
 * handoff that will never happen. Its Output-language selector is worse: the only consumer of
 * that value is the `record-verdict` call, so on a closed case it is a live control wired to
 * nothing. 49 production records on 2026-08-18.
 *
 * FULL, it is a record and stays: the 16 rejected applications carrying a final profile already
 * render the correct title and hint ("generated from the interview findings and your verdict").
 */
export function showsGeneratedProfileCard(
  opts: {
    status: string | null | undefined
    decisionReopened?: boolean | null
    hasProfile?: boolean | null
  },
): boolean {
  if (!showsPostSubmissionCards(opts.status)) return false
  if (!isCaseClosed(opts)) return true
  return !!opts.hasProfile
}

/**
 * Show the Check 2 — Outstanding box?
 *
 * Empty on a closed case it asserts "Nothing outstanding — all student tasks are clear", which
 * reads as an achievement. 43 of the 44 closed-with-no-record applications have never had a
 * single resolution item raised against them — nothing was outstanding because nothing was ever
 * asked, and one of them was rejected over the college named on their offer letter. Same rule as
 * the cards above: with items it is the record of what was asked and stays (22 records).
 */
export function showsCheck2Box(
  opts: {
    status: string | null | undefined
    decisionReopened?: boolean | null
    hasItems?: boolean | null
  },
): boolean {
  if (!isCaseClosed(opts)) return true
  return !!opts.hasItems
}
