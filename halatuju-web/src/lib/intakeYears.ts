/**
 * Intake-year requirement arithmetic (Sabah S2b, 2026-09-02).
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
 * a client copy of the server's rule drifts and the button then lies. There is no refusal here:
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

/** The requirements as the SCREEN holds them: strings, because an empty box means "not applied"
 *  and `''` is the only honest representation of an empty box. */
export interface RequirementDraft {
  aCount: string
  /** Shown as the EXTRA beyond the A- grades, which is how the rule is set and spoken. */
  spmExtra: string
  pngk: string
  merit: string
  income: string
  perPerson: string
}

export const EMPTY_REQUIREMENTS: RequirementDraft = {
  aCount: '', spmExtra: '', pngk: '', merit: '', income: '', perPerson: '',
}

/** `''` → null (the test is not applied); anything else → a number. Zero survives: it is a real
 *  requirement that everybody passes, and the engine distinguishes it from "not applied". */
const num = (s: string) => (s.trim() === '' ? null : Number(s))

/**
 * The screen's boxes → the columns the engine reads.
 *
 * ⚠ THE B+ REQUIREMENT IS SHOWN AS AN EXTRA AND STORED AS A TOTAL, and that conversion is the
 * whole reason this function exists. The engine compares `strong >= min_spm_bplus_count`, and the
 * strong count INCLUDES the A grades — so "4 at A- plus 1 more at B+" is stored as 4 and 5. Stored
 * form reached the rejection text as "need 4 A- and 5 at B+", which reads as nine subjects; the
 * owner who wrote the rule read it that way (2026-09-02) and twelve real applicants carry it.
 */
export function draftToRequirements(d: RequirementDraft) {
  const a = num(d.aCount)
  const extra = num(d.spmExtra)
  return {
    min_spm_a_count: a,
    // With no A- requirement the extra IS the total — not "extra plus zero by luck", which would
    // shift the moment an A- count were added beside it.
    min_spm_bplus_count: extra === null ? null : (a ?? 0) + extra,
    min_stpm_pngk: num(d.pngk),
    min_merit_score: num(d.merit),
    income_ceiling: num(d.income),
    per_capita_ceiling: num(d.perPerson),
  }
}

/** What is stored → what the boxes show. */
const str = (n: number | null | undefined) => (n === null || n === undefined ? '' : String(n))

/**
 * The stored columns → the screen's boxes: the exact inverse of `draftToRequirements`.
 *
 * ⚠ IT EXISTS BECAUSE THE RULES CAN NOW BE EDITED, NOT ONLY SET (owner, 2026-09-03: rules are a
 * configuration item, and they come before "what we ask for"). Until then the conversion ran one
 * way — a create form wrote a total and nothing ever read it back — and the retro warned in as many
 * words that "if a future screen ever sends what it displays, 4 plus 1 silently becomes 4 plus 1
 * more than 4". An edit form is that future screen: it loads a TOTAL of 5 and must show an EXTRA
 * of 1, or the first save after opening the page would quietly raise the bar to nine subjects.
 *
 * A stored total BELOW the A- count cannot be spelled by this screen and should not be silently
 * repaired into a negative box: it clamps at zero, which is what "no extra beyond the A grades"
 * means, and a round trip then writes back the honest total.
 */
export function requirementsToDraft(r: {
  min_spm_a_count?: number | null
  min_spm_bplus_count?: number | null
  min_stpm_pngk?: number | null
  min_merit_score?: number | null
  income_ceiling?: number | null
  per_capita_ceiling?: number | null
} | null | undefined): RequirementDraft {
  if (!r) return { ...EMPTY_REQUIREMENTS }
  const a = r.min_spm_a_count
  const total = r.min_spm_bplus_count
  return {
    aCount: str(a),
    spmExtra: total === null || total === undefined
      ? ''
      : String(Math.max(0, total - (a ?? 0))),
    pngk: str(r.min_stpm_pngk),
    merit: str(r.min_merit_score),
    income: str(r.income_ceiling),
    perPerson: str(r.per_capita_ceiling),
  }
}
