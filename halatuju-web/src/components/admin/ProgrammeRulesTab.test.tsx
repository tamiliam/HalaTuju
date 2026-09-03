/**
 * @jest-environment jsdom
 *
 * Programme → Configuration → Rules, rendered (shape sprint, 2026-09-03).
 *
 * This is the most behaviour-sensitive surface the sprint adds: it edits the thresholds
 * `shortlisting.evaluate()` reads LIVE, so a mistake here changes who gets a bursary. Three things
 * are pinned, and each one is a bug that would otherwise be invisible:
 *
 *  1. WHAT IT SENDS. The B+ requirement is shown as an EXTRA and stored as a TOTAL. A screen that
 *     loads 5 and saves 5 turns "4 plus 1" into "4 plus 5" — nine subjects — on the first save
 *     after opening the page, with nobody touching a box.
 *  2. WHICH YEAR. The open round, else the newest. Editing last year's rules while this year's
 *     round is taking applications would change nothing and look like it had.
 *  3. THAT IT SAYS SO. The tab carries a warning the neighbouring tab does not, because "what we
 *     ask for" is frozen per student at submit and these are not.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProgrammeRulesTab, { ruleYear } from './ProgrammeRulesTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const programme = (over: Partial<api.AdminProgramme> = {}): api.AdminProgramme => ({
  id: 1, code: 'bp', name_en: 'BrightPath Bursary', name_ms: '', name_ta: '',
  is_active: true, intake_years: 1, applications: 41, open_year: 2026, ...over,
})

const year = (over: Partial<api.AdminIntakeYear> = {}): api.AdminIntakeYear => ({
  id: 10, code: 'bp-2026', name: 'Intake 2026', year: 2026, is_open: true, is_active: true,
  applications: 41,
  // BrightPath's LIVE rule: four at A- plus one more at B+, stored as a strong TOTAL of five.
  requirements: {
    min_spm_a_count: 4, min_spm_bplus_count: 5, min_stpm_pngk: null,
    min_merit_score: null, income_ceiling: 5860, per_capita_ceiling: 1584,
  },
  ...over,
})

const withYears = (years: api.AdminIntakeYear[], programmes = [programme()]) => {
  mockApi.getAdminProgrammes.mockResolvedValue({ programmes })
  mockApi.getAdminIntakeYears.mockResolvedValue({
    programme: { id: 1, code: 'bp', name_en: 'BrightPath Bursary', is_active: true },
    years,
  })
}

/**
 * ⚠ WAITS FOR THE DATA, NOT THE CONTAINER. The first draft waited for `rules-tab` alone, which
 * appears before the years have arrived — so every assertion ran against empty boxes and the whole
 * file failed for one reason wearing eight faces. Waiting on the year line is waiting on the load
 * that fills the boxes.
 */
const loaded = async () => {
  render(<ProgrammeRulesTab />)
  await waitFor(() => expect(screen.getByTestId('rules-year')).toBeTruthy())
}

const box = (id: string) => document.getElementById(id) as HTMLInputElement
const save = () => screen.getByText('common.save') as HTMLButtonElement

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.updateAdminIntakeYear.mockResolvedValue(year())
})

describe('which round it is editing', () => {
  it('prefers the round taking applications over the newest one', () => {
    const open2025 = year({ id: 1, year: 2025, is_open: true })
    const closed2027 = year({ id: 2, year: 2027, is_open: false })
    expect(ruleYear([closed2027, open2025])?.id).toBe(1)
  })

  it('falls back to the newest when nothing is open', () => {
    const a = year({ id: 1, year: 2025, is_open: false })
    const b = year({ id: 2, year: 2027, is_open: false })
    expect(ruleYear([a, b])?.id).toBe(2)
  })

  it('has no answer for a gift with no rounds — and that is a real state', () => {
    expect(ruleYear([])).toBeNull()
  })

  it('names the round on screen, so nobody edits a year they cannot see', async () => {
    withYears([year()])
    await loaded()
    expect(screen.getByTestId('rules-year').textContent).toContain('2026')
  })
})

describe('what the boxes show', () => {
  it('shows the B+ requirement as the EXTRA, not the stored total', async () => {
    withYears([year()])
    await loaded()
    expect(box('rules-a').value).toBe('4')
    expect(box('rules-b').value).toBe('1')   // stored 5, shown as 1 more than the four A-
  })

  it('leaves an unapplied test as an empty box', async () => {
    withYears([year()])
    await loaded()
    expect(box('rules-p').value).toBe('')    // STPM PNGK: null = the test does not run
    expect(box('rules-m').value).toBe('')
  })
})

describe('what it sends', () => {
  // ⚠ THE ONE THAT PREVENTS A LIVE DEFECT. Nudge the A- count and save: the B+ box was never
  // touched, and what must reach the server is the TOTAL that box implies — not the 1 on screen,
  // and not the 5 it was loaded from if the A- count moved beneath it.
  it('sends the TOTAL strong count, recomputed from what is on screen', async () => {
    withYears([year()])
    await loaded()

    fireEvent.change(box('rules-a'), { target: { value: '3' } })
    fireEvent.click(save())

    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    const [id, body] = mockApi.updateAdminIntakeYear.mock.calls[0]
    expect(id).toBe(10)
    expect(body.min_spm_a_count).toBe(3)
    expect(body.min_spm_bplus_count).toBe(4)   // 3 at A- plus the same 1 more
  })

  it('unticking a test clears it to null — not to zero', async () => {
    withYears([year()])
    await loaded()

    fireEvent.change(box('rules-i'), { target: { value: '' } })
    fireEvent.click(save())

    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(mockApi.updateAdminIntakeYear.mock.calls[0][1].income_ceiling).toBeNull()
  })
})

describe('the Save rule', () => {
  // The platform's nothing-to-save standard (request #6). ⚠ The dangerous direction is the
  // opposite of the bug: a Save wrongly ASLEEP strands real work, so the wake case is asserted
  // too, not just the sleep.
  it('sleeps with nothing changed and wakes on a real edit', async () => {
    withYears([year()])
    await loaded()
    expect(save().disabled).toBe(true)
    expect(screen.getByText('common.nothingToSave')).toBeTruthy()

    fireEvent.change(box('rules-a'), { target: { value: '5' } })
    expect(save().disabled).toBe(false)
    expect(screen.queryByText('common.nothingToSave')).toBeNull()
  })

  it('sleeps again when the edit is put back', async () => {
    withYears([year()])
    await loaded()
    fireEvent.change(box('rules-a'), { target: { value: '5' } })
    fireEvent.change(box('rules-a'), { target: { value: '4' } })
    expect(save().disabled).toBe(true)
  })
})

describe('what it refuses to draw', () => {
  it('says a gift with no round has nowhere to keep its rules, and offers no Save', async () => {
    withYears([])
    render(<ProgrammeRulesTab />)
    await waitFor(() => expect(screen.getByText('admin.rules.noYear')).toBeTruthy())
    expect(screen.queryByText('common.save')).toBeNull()
  })

  // ⚠ NEVER PICKS SILENTLY. Two gifts and no choice made must ASK — an admin who believes they
  // are editing Sabah's rules while looking at BrightPath's would change a live programme.
  it('asks which gift when there is more than one and none is chosen', async () => {
    withYears([year()], [programme(), programme({ id: 2, code: 'sabah', name_en: 'Sabah' })])
    render(<ProgrammeRulesTab />)
    await waitFor(() => expect(screen.getByTestId('choose-programme')).toBeTruthy())
    expect(screen.queryByTestId('rules-tab')).toBeNull()
    expect(mockApi.getAdminIntakeYears).not.toHaveBeenCalled()
  })
})

describe('what it says', () => {
  // The asymmetry this tab exists to make honest: "what we ask for" is frozen per student at
  // submit (`requirements_snapshot`); these thresholds are read live. Two settings on one screen
  // with different blast radius must not look like the same kind of switch.
  it('warns that a rule change is NOT frozen for students already in', async () => {
    withYears([year()])
    await loaded()
    expect(screen.getByText('admin.rules.liveWarning')).toBeTruthy()
  })
})
