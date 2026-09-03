/**
 * Intake-year requirement arithmetic (Sabah S2b, 2026-09-02).
 *
 * ⚠ THIS LIVES IN `lib`, NOT BESIDE THE PAGE, AND `next build` IS WHY. A page module may not carry
 * ANY export beyond its default — Layer 1 F7c hit this three times and `tsc`, `jest` and `next
 * lint` were green through every one of them. A helper the page needs and a test needs is a lib
 * module; putting it in the page is a build failure waiting for the next deploy.
 */

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
