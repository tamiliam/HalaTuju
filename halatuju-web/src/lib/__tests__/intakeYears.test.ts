/**
 * The intake-year window helpers (`lib/intakeYears`).
 *
 * The requirement-box helpers that used to live here (the B+ extra/total conversion and its round
 * trips) went with the seven-box form: the criteria editor (Sprint 4) edits the stored tree, and
 * its own tests are `criteriaTree.test.ts`.
 */
import { outsideWindow, todayIso, windowState } from '@/lib/intakeYears'


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
