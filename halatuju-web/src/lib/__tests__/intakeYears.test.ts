/**
 * Sabah S2b — the one piece of real arithmetic on the intake-year requirements.
 *
 * The requirement is SET as "4 at A- plus 1 more at B+" and STORED as a total strong count of 5,
 * because that is what the engine compares against (`strong >= min_spm_bplus_count`, and the B+
 * count includes the A grades). The screen must show the difference and send the total.
 *
 * ⚠ THIS IS THE CONVERSION THAT MADE THE OWNER MISREAD THEIR OWN RULE. The stored form reached the
 * rejection text as "need 4 A- and 5 at B+", which reads as nine subjects; twelve real applicants
 * carry that wording. If the screen ever sends what it displays, a programme meaning "4 plus 1"
 * silently becomes "4 plus 1 more than 4".
 *
 * ⚠ THE RETURN JOURNEY IS NEW AND IS THE DANGEROUS ONE (shape sprint, 2026-09-03). Until now the
 * conversion ran one way — a create form wrote a total and nothing ever read one back — and the
 * S2b retro warned in as many words that a screen which one day LOADS the stored value would turn
 * "4 plus 1" into "4 plus 5". The Rules tab is that screen, and every save it makes starts from a
 * value it read. The round-trip tests below are what stop it.
 *
 * Moved here from `app/admin/programme/years/page.test.tsx` when that route became a redirect: it
 * was always a test of `lib/intakeYears`, never of a page.
 */
import {
  draftToRequirements, requirementsToDraft, EMPTY_REQUIREMENTS,
} from '@/lib/intakeYears'

describe('the SPM B+ requirement is displayed as an EXTRA and stored as a TOTAL', () => {
  const draft = (over: Partial<Parameters<typeof draftToRequirements>[0]> = {}) =>
    ({ aCount: '', spmExtra: '', pngk: '', merit: '', income: '', perPerson: '', ...over })

  it("BrightPath's rule round-trips: 4 A- plus 1 more is stored as 4 and 5", () => {
    const r = draftToRequirements(draft({ aCount: '4', spmExtra: '1' }))
    expect(r.min_spm_a_count).toBe(4)
    expect(r.min_spm_bplus_count).toBe(5)
  })

  it('with NO A- requirement, the extra IS the total', () => {
    // Otherwise "at least 5 at B+" would be stored as 5 + nothing = 5 by luck rather than by rule,
    // and the moment an A- count were added the total would silently shift.
    const r = draftToRequirements(draft({ spmExtra: '5' }))
    expect(r.min_spm_a_count).toBeNull()
    expect(r.min_spm_bplus_count).toBe(5)
  })

  it('an empty box unticks the test — null, never zero', () => {
    // ⚠ Zero is a real requirement that everybody passes; null means the test does not run. The
    // engine distinguishes them, so the screen must not collapse one into the other.
    const r = draftToRequirements(draft({ aCount: '', pngk: '', merit: '' }))
    expect(r.min_spm_a_count).toBeNull()
    expect(r.min_stpm_pngk).toBeNull()
    expect(r.min_merit_score).toBeNull()
  })

  it('keeps a deliberate zero as zero', () => {
    expect(draftToRequirements(draft({ aCount: '0' })).min_spm_a_count).toBe(0)
  })

  it('carries the financial pair through unchanged', () => {
    const r = draftToRequirements(draft({ income: '5860', perPerson: '1584' }))
    expect(r.income_ceiling).toBe(5860)
    expect(r.per_capita_ceiling).toBe(1584)
  })

  it('accepts a decimal PNGK and a decimal merit point', () => {
    const r = draftToRequirements(draft({ pngk: '2.9', merit: '80.5' }))
    expect(r.min_stpm_pngk).toBe(2.9)
    expect(r.min_merit_score).toBe(80.5)
  })
})

describe('reading the stored rules back into the boxes', () => {
  // ⚠ THE ONE THAT MATTERS. BrightPath's live row is (4, 5) meaning "4 at A- plus 1 more". Load it
  // as an extra of 5 and the very first save on the Rules tab would write (4, 9) — nine subjects,
  // silently, on a live programme. Nothing else in the suite can catch that.
  it("BrightPath's live row reads back as the rule the owner wrote", () => {
    const d = requirementsToDraft({ min_spm_a_count: 4, min_spm_bplus_count: 5 })
    expect(d.aCount).toBe('4')
    expect(d.spmExtra).toBe('1')
  })

  it('survives a full round trip unchanged — load, touch nothing, save', () => {
    const stored = {
      min_spm_a_count: 4, min_spm_bplus_count: 5, min_stpm_pngk: 2.9,
      min_merit_score: null, income_ceiling: 5860, per_capita_ceiling: 1584,
    }
    expect(draftToRequirements(requirementsToDraft(stored))).toEqual(stored)
  })

  it('shows an unset requirement as an empty box, not as a zero', () => {
    // Null means the test does not run; zero is a test everybody passes. Reading one as the other
    // would tick a requirement nobody set — the S2a defect in the opposite direction.
    const d = requirementsToDraft({
      min_spm_a_count: null, min_spm_bplus_count: null, min_stpm_pngk: null,
      min_merit_score: null, income_ceiling: null, per_capita_ceiling: null,
    })
    expect(d).toEqual(EMPTY_REQUIREMENTS)
  })

  it('keeps a stored zero visible as a ticked zero', () => {
    expect(requirementsToDraft({ min_spm_a_count: 0 }).aCount).toBe('0')
  })

  it('with no A- requirement, the stored total IS the extra', () => {
    const d = requirementsToDraft({ min_spm_a_count: null, min_spm_bplus_count: 5 })
    expect(d.aCount).toBe('')
    expect(d.spmExtra).toBe('5')
  })

  it('clamps a total below the A- count rather than showing a negative box', () => {
    // Not reachable from this screen, but a hand-written row could hold it. A negative in a box
    // would round-trip into a smaller total and quietly LOWER the bar.
    expect(requirementsToDraft({ min_spm_a_count: 5, min_spm_bplus_count: 3 }).spmExtra).toBe('0')
  })

  it('treats a missing record as nothing set', () => {
    expect(requirementsToDraft(null)).toEqual(EMPTY_REQUIREMENTS)
    expect(requirementsToDraft(undefined)).toEqual(EMPTY_REQUIREMENTS)
  })
})
