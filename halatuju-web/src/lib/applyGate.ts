/**
 * Does the apply form let this student in? — the half of `applicationScreen.ts` the apply page needs.
 *
 * A LEAF on purpose (2026-10-05): `/scholarship/apply` sat on its first-load budget, and importing
 * `applicationScreen` carried that page the whole screen rule it never runs. The two halves are ONE
 * rule — `applicationScreen` imports this, and `applicationScreen.test.ts` asserts the invariant
 * between them over every status — so neither may be edited without the other.
 */

/**
 * The statuses that do NOT stop a fresh application — the same STATUS list the server's duplicate
 * check excludes (`.exclude(status='expired')` in `ApplicationListCreateView.post`): an auto-closed
 * application never blocks a restart. The drift test pins this list to that line.
 *
 * ⚠ THE SCOPE DELIBERATELY DIFFERS, AND THE WEB IS THE STRICTER ONE. The server refuses a duplicate
 * PER ROUND (`filter(cohort=cohort, profile=profile)`); `mustLeaveApplyPage` refuses on ANY standing
 * application in ANY round. That is on purpose — one application per student until applying to
 * several programmes (M2–M4 of `docs/plans/2026-07-28-multi-programme-applications-roadmap.md`) is
 * approved. Its cost is real and accepted: a student rejected, withdrawn or closed in an old round
 * cannot start one in a new round from the form. Do not "fix" one side to match the other without
 * that approval.
 *
 * drift-test: halatuju-web/src/lib/__tests__/studentScreenDrift.test.ts
 */
export const REAPPLY_ALLOWED_STATUSES = ['expired'] as const

/** Every application that still counts — anything not in the allow-list above. */
export function standingApplications<T extends { status: string }>(apps: readonly T[]): T[] {
  return apps.filter((a) => !(REAPPLY_ALLOWED_STATUSES as readonly string[]).includes(a.status))
}

/** Must the apply form send this student to her application instead? True iff she holds any
 *  standing application, in any round (see the scope note above). Its partner is
 *  `applicationScreen`, which then never answers 'none' for her. */
export function mustLeaveApplyPage(apps: readonly { status: string }[]): boolean {
  return standingApplications(apps).length > 0
}
