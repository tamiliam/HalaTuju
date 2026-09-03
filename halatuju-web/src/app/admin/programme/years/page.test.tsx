/**
 * @jest-environment jsdom
 *
 * Sabah S2b — the one piece of real arithmetic on the intake-years screen.
 *
 * The requirement is SET as "4 at A- plus 1 more at B+" and STORED as a total strong count of 5,
 * because that is what the engine compares against (`strong >= min_spm_bplus_count`, and the B+
 * count includes the A grades). The screen must show the difference and send the total.
 *
 * ⚠ THIS IS THE CONVERSION THAT MADE THE OWNER MISREAD THEIR OWN RULE. The stored form reached the
 * rejection text as "need 4 A- and 5 at B+", which reads as nine subjects; twelve real applicants
 * carry that wording. If the screen ever sends what it displays, a programme meaning "4 plus 1"
 * silently becomes "4 plus 1 more than 4".
 */
import { draftToRequirements } from '@/lib/intakeYears'

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
