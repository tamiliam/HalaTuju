/**
 * The LIVE application states, a LEAF module (TD-341): the dashboard banner needs the same rule as
 * `applicationScreen` but must not pull `lib/scholarship.ts` (and its `scholarship.*` words) onto /dashboard.
 * `lib/scholarship.ts` re-exports both names, so every existing import is unchanged.
 */

/**
 * The LIVE applications — the first thing `applicationScreen` (applicationScreen.ts) looks at to
 * decide which application the student's screen is about.
 *
 * The application screen used to take `applications[0]` — the same "assume one" shape the
 * backend carried in `_current_application`, and the same shape PF-1 fixed in
 * `resolve_open_cohort`. It is not a tie-break; it is a guess about which programme the student
 * is looking at, and with two live applications it silently shows one and hides the other. A
 * screen that cannot say which application it is showing must not show one — the chooser itself
 * is M4 of `docs/plans/2026-07-28-multi-programme-applications-roadmap.md`.
 *
 * Live means the editable funnel plus the funded post-award states, mirroring the backend's
 * `POST_SHORTLIST_EDITABLE + _FUNDED_STATES`. ⚠ KEEP-IN-SYNC PAIR — if a status is added there,
 * add it here; a drift makes the two disagree about what the student is even working on.
 *
 * drift-test: halatuju-web/src/lib/__tests__/studentScreenDrift.test.ts
 */
export const LIVE_APPLICATION_STATES = [
  'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
  'awarded', 'active', 'maintenance',
] as const

export function liveApplications<T extends { status: string }>(apps: readonly T[]): T[] {
  return apps.filter((a) => (LIVE_APPLICATION_STATES as readonly string[]).includes(a.status))
}
