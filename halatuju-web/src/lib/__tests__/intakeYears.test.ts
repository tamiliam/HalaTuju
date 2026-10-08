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
  draftToRequirements, requirementsToDraft, sameDraft, EMPTY_REQUIREMENTS,
  outsideWindow, todayIso, windowState,
} from '@/lib/intakeYears'

describe('the SPM B+ requirement is displayed as an EXTRA and stored as a TOTAL', () => {
  const draft = (over: Partial<Parameters<typeof draftToRequirements>[0]> = {}) =>
    ({ aCount: '', spmExtra: '', credits: '', pngk: '', merit: '', income: '', perPerson: '',
       birthStates: [], ...over })

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
      min_spm_a_count: 4, min_spm_bplus_count: 5, min_spm_credit_count: 6, min_stpm_pngk: 2.9,
      min_merit_score: null, income_ceiling: 5860, per_capita_ceiling: 1584,
      allowed_birth_states: ['sabah', 'sarawak'],
    }
    expect(draftToRequirements(requirementsToDraft(stored))).toEqual(stored)
  })

  it('shows an unset requirement as an empty box, not as a zero', () => {
    // Null means the test does not run; zero is a test everybody passes. Reading one as the other
    // would tick a requirement nobody set — the S2a defect in the opposite direction.
    const d = requirementsToDraft({
      min_spm_a_count: null, min_spm_bplus_count: null, min_spm_credit_count: null,
      min_stpm_pngk: null, min_merit_score: null, income_ceiling: null, per_capita_ceiling: null,
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

/**
 * Request #30 — grades at C or better. ⚠ A TOTAL ON SCREEN AND IN THE COLUMN, unlike the B+ box:
 * the owner sets it as "6 at C or better", A's and B's included (8 A's and no C's clears 6). So it
 * passes through untouched — no conversion against the A- or B+ boxes in either direction.
 */
describe('the SPM C-or-better requirement is a TOTAL both ways', () => {
  const draft = (over: Partial<Parameters<typeof draftToRequirements>[0]> = {}) =>
    ({ ...EMPTY_REQUIREMENTS, ...over })

  it('sends what is typed, whatever the A- and B+ boxes say', () => {
    const r = draftToRequirements(draft({ aCount: '4', spmExtra: '1', credits: '6' }))
    expect(r.min_spm_credit_count).toBe(6)
    expect(r.min_spm_bplus_count).toBe(5)
  })

  it('an empty box is null (not applied); a typed zero stays zero', () => {
    expect(draftToRequirements(draft()).min_spm_credit_count).toBeNull()
    expect(draftToRequirements(draft({ credits: '0' })).min_spm_credit_count).toBe(0)
  })

  it('reads back as the same number, and blank as an empty box', () => {
    expect(requirementsToDraft({ min_spm_a_count: 4, min_spm_credit_count: 6 }).credits).toBe('6')
    expect(requirementsToDraft({ min_spm_credit_count: 0 }).credits).toBe('0')
    expect(requirementsToDraft({ min_spm_credit_count: null }).credits).toBe('')
    // An intake year served before the column existed (a stale payload) reads as not applied.
    expect(requirementsToDraft({ min_spm_a_count: 4 }).credits).toBe('')
  })
})

/**
 * Request #31 — "Born in". ⚠ THE LIST IS THE SWITCH: nothing ticked = the rule is not applied, and
 * the list is ALWAYS sent, so unticking the last state clears the rule rather than leaving the
 * stored one in place.
 */
describe('the birth-state requirement', () => {
  const draft = (over: Partial<Parameters<typeof draftToRequirements>[0]> = {}) =>
    ({ ...EMPTY_REQUIREMENTS, ...over })

  it('sends the ticked states, and an empty list when none are ticked', () => {
    expect(draftToRequirements(draft({ birthStates: ['sabah'] })).allowed_birth_states)
      .toEqual(['sabah'])
    expect(draftToRequirements(draft()).allowed_birth_states).toEqual([])
  })

  it('reads the stored list back, and a missing or junk one as nothing ticked', () => {
    expect(requirementsToDraft({ allowed_birth_states: ['sabah', 'sarawak'] }).birthStates)
      .toEqual(['sabah', 'sarawak'])
    expect(requirementsToDraft({ allowed_birth_states: [] }).birthStates).toEqual([])
    // A payload from before the column existed.
    expect(requirementsToDraft({ min_spm_a_count: 4 }).birthStates).toEqual([])
    expect(requirementsToDraft({ allowed_birth_states: null }).birthStates).toEqual([])
  })

  // TD-373: the gate enforces whatever is stored, so the screen must hold every stored key — a
  // wrong-case one included — and a bare string (an api older than `stored_keys`) is one key.
  it('keeps a key the boxes do not offer, and reads a bare string as one key', () => {
    expect(requirementsToDraft({ allowed_birth_states: ['Sabah'] }).birthStates).toEqual(['Sabah'])
    expect(requirementsToDraft({ allowed_birth_states: ['sabah', 'Sabah'] }).birthStates)
      .toEqual(['sabah', 'Sabah'])
    expect(requirementsToDraft({ allowed_birth_states: 'sabah' }).birthStates).toEqual(['sabah'])
    expect(requirementsToDraft({ allowed_birth_states: 'Sabah' }).birthStates).toEqual(['Sabah'])
    expect(requirementsToDraft({ allowed_birth_states: '' }).birthStates).toEqual([])
    // Sent back as held, so the server refuses it rather than the screen quietly dropping it.
    expect(draftToRequirements(requirementsToDraft({ allowed_birth_states: 'Sabah' }))
      .allowed_birth_states).toEqual(['Sabah'])
  })

  it('never hands the screen the same array it was given', () => {
    const stored = ['sabah']
    const d = requirementsToDraft({ allowed_birth_states: stored })
    expect(d.birthStates).not.toBe(stored)
    expect(draftToRequirements(d).allowed_birth_states).not.toBe(d.birthStates)
  })

  it('sameDraft compares the ticked states by VALUE, so putting a tick back is no change', () => {
    const a = draft({ birthStates: ['sabah'] })
    expect(sameDraft(a, draft({ birthStates: ['sabah'] }))).toBe(true)
    expect(sameDraft(a, draft())).toBe(false)
    expect(sameDraft(a, draft({ birthStates: ['sabah'], aCount: '4' }))).toBe(false)
    expect(sameDraft(draft(), EMPTY_REQUIREMENTS)).toBe(true)
  })
})

/**
 * ⚠ A TYPO MUST NEVER LEAVE AS null (request #30 review). `Number('six')` is NaN, `JSON.stringify`
 * sends NaN as null, and the API reads null as "untick" — so a typo in any box switched that rule
 * OFF while the screen said Saved. The text typed is sent instead, and the server refuses it.
 */
describe('a box holding something that is not a number', () => {
  const draft = (over: Partial<Parameters<typeof draftToRequirements>[0]> = {}) =>
    ({ ...EMPTY_REQUIREMENTS, ...over })
  const wire = (over: Parameters<typeof draft>[0]) =>
    JSON.parse(JSON.stringify(draftToRequirements(draft(over))))

  it('reaches the server as the text typed, never as null', () => {
    for (const typo of ['six', '6 credits', '6,0']) {
      expect(wire({ credits: typo }).min_spm_credit_count).toBe(typo)
    }
    expect(wire({ pngk: '2,9' }).min_stpm_pngk).toBe('2,9')
    expect(wire({ income: 'Infinity' }).income_ceiling).toBe('Infinity')
  })

  it('a typo in EITHER SPM box is forwarded for the B+ total, never summed', () => {
    expect(wire({ aCount: '4', spmExtra: 'one' }).min_spm_bplus_count).toBe('one')
    const r = wire({ aCount: 'four', spmExtra: '1' })
    expect([r.min_spm_a_count, r.min_spm_bplus_count]).toEqual(['four', 'four'])
  })

  it('still reads padding and a whole-valued decimal as the number', () => {
    expect(wire({ credits: ' 6 ' }).min_spm_credit_count).toBe(6)
    expect(wire({ credits: '6.0' }).min_spm_credit_count).toBe(6)
  })
})

/**
 * Where TODAY sits against a round's stated window (owner's option A, 2026-09-07).
 *
 * ⚠ THIS DECIDES NOTHING. The 2026-09-06 ruling stands — the window describes, a person presses
 * Open — so every case below drives a SENTENCE and a CONFIRMATION, never a refusal. The owner
 * asked on 2026-09-07 for the dates to control opening, was shown the reason they had ruled the
 * other way the day before (a clock opens a round whose rules may be unfinished), and kept it.
 */
describe('windowState', () => {
  const on = (opens: string | null, closes: string | null, today: string) =>
    windowState({ opens_on: opens, closes_on: closes }, today).kind

  it('says NOTHING about a round with no stated dates', () => {
    // The normal state of every round that predates the column, including the live 2026 intake.
    // Nothing was backfilled, so this is the common case and it must never read as an error.
    expect(on(null, null, '2026-09-07')).toBe('none')
    expect(on('', '', '2026-09-07')).toBe('none')
  })

  it('reads before / during / after against both dates', () => {
    expect(on('2026-03-01', '2026-04-30', '2026-02-28')).toBe('before')
    expect(on('2026-03-01', '2026-04-30', '2026-03-15')).toBe('during')
    expect(on('2026-03-01', '2026-04-30', '2026-05-01')).toBe('after')
  })

  // ⚠ BOTH EDGES ARE INSIDE. An admin opening a round on the very day it is stated to open is
  // doing exactly what the schedule says; warning them there would train them to ignore the
  // warning, which costs the one case it exists for.
  it('counts both boundary days as INSIDE the window', () => {
    expect(on('2026-03-01', '2026-04-30', '2026-03-01')).toBe('during')
    expect(on('2026-03-01', '2026-04-30', '2026-04-30')).toBe('during')
  })

  it('handles one date stated and the other blank', () => {
    expect(on('2026-03-01', null, '2026-02-01')).toBe('before')
    expect(on('2026-03-01', null, '2026-12-01')).toBe('during')
    expect(on(null, '2026-04-30', '2026-01-01')).toBe('during')
    expect(on(null, '2026-04-30', '2026-05-01')).toBe('after')
  })

  it('flags only before and after as outside the window', () => {
    const at = (t: string) => outsideWindow(windowState({ opens_on: '2026-03-01', closes_on: '2026-04-30' }, t))
    expect(at('2026-02-28')).toBe(true)
    expect(at('2026-03-15')).toBe(false)
    expect(at('2026-05-01')).toBe(true)
    // No dates stated is never "outside" — there is no window to be outside of.
    expect(outsideWindow(windowState({}, '2026-05-01'))).toBe(false)
  })
})

describe('todayIso', () => {
  it('zero-pads to the ISO shape the stored dates use, so string compare is date compare', () => {
    expect(todayIso(new Date(2026, 0, 5))).toBe('2026-01-05')
    expect(todayIso(new Date(2026, 11, 31))).toBe('2026-12-31')
  })
})
