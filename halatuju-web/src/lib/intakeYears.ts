/**
 * Intake-year window helpers (Sabah S2b, 2026-09-02). The requirement-box arithmetic that lived
 * here went with the seven-box form (criteria editor Sprint 4: `criteriaTree.ts`).
 *
 * ⚠ THIS LIVES IN `lib`, NOT BESIDE THE PAGE, AND `next build` IS WHY. A page module may not carry
 * ANY export beyond its default — Layer 1 F7c hit this three times and `tsc`, `jest` and `next
 * lint` were green through every one of them. A helper the page needs and a test needs is a lib
 * module; putting it in the page is a build failure waiting for the next deploy.
 */

/**
 * Where TODAY sits against a round's stated window (owner's option A, 2026-09-07).
 *
 * ⚠ THE WINDOW STILL OPENS NOTHING, AND THIS FUNCTION IS NOT A CLOCK. The 2026-09-06 ruling
 * stands: `opens_on`/`closes_on` record when the round is MEANT to run, and a person presses Open,
 * because a clock would let a gift whose rules and questions were never finished start taking real
 * students. What the owner reported on 2026-09-07 was the other half of that — dates printed on a
 * screen that said nothing at all, which reads as furniture. So the dates now SPEAK (this) and
 * they WARN (the confirmation before opening outside the window), and they still decide nothing.
 *
 * ⚠ THIS IS DERIVED IN THE BROWSER ON PURPOSE, and it does not breach "serve, don't derive". That
 * rule bans a screen PREDICTING A SERVER REFUSAL from what the payload happens to carry — because
 * a client-side re-derivation of the server's rule drifts and the button then lies. There is no refusal here:
 * the server accepts an out-of-window open, deliberately. This compares two dates the row already
 * carries against today, and no server answer exists for it to disagree with.
 *
 * `today` is a parameter, never a hidden `new Date()`, so the behaviour at both edges is testable.
 * All three values are ISO `YYYY-MM-DD`, which compares correctly as a string.
 */
export type WindowState =
  /** No dates stated. Normal — every round predating the column has NULL and nothing was
   *  backfilled, including the live 2026 intake. It must never render as an error. */
  | { kind: 'none' }
  /** Stated to open later. */
  | { kind: 'before'; opensOn: string }
  /** Today is inside the stated window, or past an opening date with no closing date. */
  | { kind: 'during' }
  /** The stated window has passed. */
  | { kind: 'after'; closesOn: string }

export function windowState(
  year: { opens_on?: string | null; closes_on?: string | null },
  today: string,
): WindowState {
  const opens = year.opens_on || ''
  const closes = year.closes_on || ''
  if (!opens && !closes) return { kind: 'none' }
  // Boundaries are INCLUSIVE at both ends: a round stated to open on the 1st is within its window
  // on the 1st, and one stated to close on the 30th is still within it on the 30th. Anything else
  // would warn an admin doing exactly what the schedule says.
  if (opens && today < opens) return { kind: 'before', opensOn: opens }
  if (closes && today > closes) return { kind: 'after', closesOn: closes }
  return { kind: 'during' }
}

/** Would opening this round today go against its own stated schedule? Only ever a WARNING. */
export function outsideWindow(state: WindowState): boolean {
  return state.kind === 'before' || state.kind === 'after'
}

/** Today as an ISO date in the VIEWER's own timezone — the same basis `formatDate` renders in, so
 *  the state and the printed dates can never disagree by a day. */
export function todayIso(now: Date = new Date()): string {
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${mm}-${dd}`
}
