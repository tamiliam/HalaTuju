/**
 * @jest-environment jsdom
 *
 * Programme → Configuration → Rules, rendered (criteria editor Sprint 4).
 *
 * The tab edits the rule year's stored criteria TREE (`getProgrammeCriteria` /
 * `saveProgrammeCriteria`), which the gate reads live. Pinned:
 *  1. Each live intake (1, 3, 4, 5) loads with its switches ON and the right values.
 *  2. A save sends the whole tree, the year shown (`intake_id`) and the digest it was given.
 *  3. Every refusal says so: each API error code has its own message; an intake whose tree is not
 *     built yet is read-only with a calm notice; another admin's save offers a reload.
 *  4. Every on/off is the site Toggle (role="switch"), never a tick box.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import ProgrammeRulesTab, { ruleYear } from './ProgrammeRulesTab'
import * as api from '@/lib/admin-api'
import { LIVE_TREES, TREE_1, TREE_3, TREE_5 } from '@/test/criteriaShapes'
import type { CriteriaTree } from '@/lib/criteriaTree'

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
  is_active: true, lifecycle: 'active', intake_years: 1, applications: 41, awarded: 12,
  open_year: 2026, delete_blocked_by: 'has_applications', delete_blocked_count: 41,
  apply_url: 'https://halatuju.xyz/scholarship/apply?p=bp',
  apply_copy: {}, apply_copy_sensitive: [], ...over,
})

const payload = (criteria: CriteriaTree | null, over: Partial<api.CriteriaPayload> = {}): api.CriteriaPayload => ({
  intake: { id: 10, code: 'bp-2026', name: 'Intake 2026', year: 2026, is_open: true },
  stored: true, criteria, rules_error: false, beyond_columns: false, digest: 'd1', ...over,
})

const withCriteria = (p: api.CriteriaPayload) => {
  mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [programme()] })
  mockApi.getProgrammeCriteria.mockResolvedValue(p)
  mockApi.saveProgrammeCriteria.mockResolvedValue({ ...p, changed: true })
}

const apiError = (code: string, status = 409, body: Record<string, unknown> = {}) =>
  Object.assign(new Error(code), { code, status, body: { error: code, code, ...body } })

/** Waits for the DATA (the year line), not the container, which appears before the load. */
const loaded = async () => {
  render(<ProgrammeRulesTab />)
  await waitFor(() => expect(screen.getByTestId('rules-year')).toBeTruthy())
}

const sw = (id: string) => screen.getByTestId(`${id}-switch`)
const isOn = (id: string) => sw(id).getAttribute('aria-checked') === 'true'
const value = (id: string) => (screen.getByTestId(`${id}-value`) as HTMLInputElement).value
const save = () => fireEvent.click(screen.getByText('common.save'))

beforeEach(() => { jest.clearAllMocks() })

describe('ruleYear', () => {
  it('is the open year, else the newest', () => {
    const y = (id: number, yr: number, open: boolean) => ({ id, year: yr, is_open: open }) as api.AdminIntakeYear
    expect(ruleYear([])).toBeNull()
    expect(ruleYear([y(1, 2027, false), y(2, 2026, true)])?.id).toBe(2)
    expect(ruleYear([y(1, 2025, false), y(2, 2026, false)])?.id).toBe(2)
  })
})

describe('each live intake loads with its switches ON', () => {
  it('intake 1: SPM grades only, income', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    expect(isOn('rules-spm')).toBe(true)
    expect(isOn('rules-post')).toBe(false)
    expect((screen.getByTestId('grade-row-0-count') as HTMLInputElement).value).toBe('4')
    expect((screen.getByTestId('grade-row-0-grade') as HTMLSelectElement).value).toBe('A-')
    expect((screen.getByTestId('grade-row-1-count') as HTMLInputElement).value).toBe('5')
    expect((screen.getByTestId('grade-row-1-grade') as HTMLSelectElement).value).toBe('B+')
    expect([isOn('rules-household'), value('rules-household')]).toEqual([true, '5860'])
    expect([isOn('rules-per-person'), value('rules-per-person')]).toEqual([true, '1584'])
  })

  it('intake 3: 0 counts and a 0 merit are ON with value 0; born in Sabah and Labuan', async () => {
    withCriteria(payload(TREE_3)); await loaded()
    expect([isOn('rules-post'), isOn('rules-pngk'), value('rules-pngk')]).toEqual([true, true, '2'])
    expect((screen.getByTestId('grade-row-0-count') as HTMLInputElement).value).toBe('0')
    expect((screen.getByTestId('grade-row-1-count') as HTMLInputElement).value).toBe('0')
    expect((screen.getByTestId('grade-row-2-count') as HTMLInputElement).value).toBe('3')
    expect([isOn('rules-spm-merit'), value('rules-spm-merit')]).toEqual([true, '0'])
    expect(screen.getByTestId('rules-born-sabah').getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('rules-born-wp_labuan').getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('rules-born-johor').getAttribute('aria-checked')).toBe('false')
    // Both groups on: the join is shown, on "the one for their results".
    expect(screen.getByTestId('rules-results-join-own').getAttribute('aria-checked')).toBe('true')
  })

  it('intake 4: PNGK 2.0 or 3 credits', async () => {
    withCriteria(payload(LIVE_TREES['4'])); await loaded()
    expect([isOn('rules-pngk'), value('rules-pngk')]).toEqual([true, '2'])
    expect((screen.getByTestId('grade-row-0-grade') as HTMLSelectElement).value).toBe('C')
    expect(value('rules-per-person')).toBe('1000')
  })

  it('intake 5: SPM results OFF, course-start years shown', async () => {
    withCriteria(payload(TREE_5)); await loaded()
    expect(isOn('rules-spm')).toBe(false)
    expect([isOn('rules-post'), value('rules-pngk')]).toEqual([true, '3'])
    expect((screen.getByTestId('rules-start-years') as HTMLInputElement).value).toBe('2025, 2026')
    expect(screen.getByTestId('rules-born-sabah').getAttribute('aria-checked')).toBe('false')
    expect(screen.getByTestId('rules-born-perak').getAttribute('aria-checked')).toBe('true')
  })

  it('shows a count at A, B and C+ (blank on the old form)', async () => {
    withCriteria(payload({ all: [{ section: 'results', own: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 1, grade_or_better: 'A' },
      { test: 'grade_count', at_least: 2, grade_or_better: 'B' },
      { test: 'grade_count', at_least: 3, grade_or_better: 'C+' },
    ] }] }] }))
    await loaded()
    expect([0, 1, 2].map((i) => [
      (screen.getByTestId(`grade-row-${i}-count`) as HTMLInputElement).value,
      (screen.getByTestId(`grade-row-${i}-grade`) as HTMLSelectElement).value,
    ])).toEqual([['1', 'A'], ['2', 'B'], ['3', 'C+']])
  })
})

describe('on/off is the site Toggle', () => {
  it('no tick boxes anywhere; switches are role="switch"', async () => {
    withCriteria(payload(TREE_3)); await loaded()
    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
    expect(screen.getAllByRole('switch').length).toBeGreaterThan(16)
    expect(sw('rules-pngk').tagName).toBe('BUTTON')
  })
})

describe('the course-start card has its own switch', () => {
  it('off when no years are stored: the box sleeps', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    expect(isOn('rules-start')).toBe(false)
    expect((screen.getByTestId('rules-start-years') as HTMLInputElement).disabled).toBe(true)
  })

  it('on for intake 5; switched on with no year it asks for one; a year saves the flag', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    fireEvent.click(sw('rules-start'))
    expect(within(screen.getByTestId('rules-problems')).getByText('admin.criteria.problem.yearsBlank')).toBeTruthy()
    fireEvent.change(screen.getByTestId('rules-start-years'), { target: { value: '2026' } })
    save()
    await waitFor(() => expect(mockApi.saveProgrammeCriteria).toHaveBeenCalledTimes(1))
    expect(mockApi.saveProgrammeCriteria.mock.calls[0][2].flag)
      .toEqual([{ test: 'course_start_year', allowed: [2026] }])
  })

  it('intake 5 loads with it on', async () => {
    withCriteria(payload(TREE_5)); await loaded()
    expect(isOn('rules-start')).toBe(true)
  })
})

describe('the save', () => {
  it('sends the whole tree, the year shown and the digest', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(mockApi.saveProgrammeCriteria).toHaveBeenCalledTimes(1))
    const [pid, intakeId, tree, digest] = mockApi.saveProgrammeCriteria.mock.calls[0]
    expect([pid, intakeId, digest]).toEqual([1, 10, 'd1'])
    expect(tree).toEqual({ all: [TREE_1.all[0], { section: 'income', any: [
      { test: 'household_income_max', rm: 6000 }, { test: 'income_per_person_under', rm: 1584 }] }] })
    await waitFor(() => expect(screen.getByText('admin.rules.saved')).toBeTruthy())
  })

  it('an unchanged screen cannot save; a problem keeps Save asleep and says why', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    const btn = screen.getByText('common.save') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '' } })
    expect(btn.disabled).toBe(true)
    expect(within(screen.getByTestId('rules-problems')).getByText('admin.criteria.problem.incomeBlank')).toBeTruthy()
  })

  it('adds and removes a grade rule', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    fireEvent.click(screen.getByTestId('rules-add-grade'))
    fireEvent.change(screen.getByTestId('grade-row-2-count'), { target: { value: '7' } })
    fireEvent.click(screen.getByTestId('grade-row-0-remove'))
    save()
    await waitFor(() => expect(mockApi.saveProgrammeCriteria).toHaveBeenCalledTimes(1))
    const tree = mockApi.saveProgrammeCriteria.mock.calls[0][2]
    expect(tree.all[0]).toEqual({ section: 'results', own: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 5, grade_or_better: 'B+' },
      { test: 'grade_count', at_least: 7, grade_or_better: 'C' }] }] })
  })
})

describe('every refusal has its message', () => {
  it.each([
    ['bad_criteria', 400, 'badCriteria'], ['rules_error', 409, 'rulesError'],
    ['criteria_not_built', 409, 'notBuilt'], ['rule_year_changed', 409, 'ruleYearChanged'],
    ['criteria_changed', 409, 'criteriaChanged'], ['not_found', 404, 'notFound'],
    ['criteria_required', 400, 'generic'], ['unknown_field', 400, 'generic'],
    ['intake_id_required', 400, 'generic'], ['network_failure', 0, 'network'],
  ])('%s', async (code, status, key) => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(apiError(code, status))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-save-error').textContent)
      .toBe(`admin.criteria.error.${key}`))
  })

  it('a 403 says the admin may not change them', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 403 }))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-save-error').textContent)
      .toBe('admin.criteria.error.forbidden'))
  })

  it('a 404 with no code says the intake was not found', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 404 }))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-save-error').textContent)
      .toBe('admin.criteria.error.notFound'))
  })

  it('bad_criteria lists the server problems in the admin language; unknown ones as technical detail', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(apiError('bad_criteria', 400, { problems: [
      'results: a post-SPM group needs a min_pngk floor',
      'merit: min_merit (the post-SPM merit) needs a post-SPM group with a min_pngk floor',
      'spm: too many',
    ] }))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-server-problems')).toBeTruthy())
    const list = screen.getByTestId('rules-server-problems')
    expect(within(list).getByText('admin.criteria.problem.postNoFloor')).toBeTruthy()
    expect(within(list).getByText('admin.criteria.problem.meritNeedsFloor')).toBeTruthy()
    expect(list.textContent).not.toContain('min_pngk floor')
    const technical = screen.getByTestId('rules-server-problems-technical')
    expect(within(technical).getByText('admin.criteria.technical')).toBeTruthy()
    expect(within(technical).getByText('spm: too many')).toBeTruthy()
  })

  it('digest_required offers a reload too', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(apiError('digest_required', 400))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-stale').textContent)
      .toContain('admin.criteria.error.digestRequired'))
    expect(screen.getByTestId('rules-save-error').textContent).toBe('admin.criteria.error.digestRequired')
  })

  it('criteria_changed offers a reload that fetches the latest', async () => {
    withCriteria(payload(TREE_1)); await loaded()
    mockApi.saveProgrammeCriteria.mockRejectedValueOnce(apiError('criteria_changed'))
    fireEvent.change(screen.getByTestId('rules-household-value'), { target: { value: '6000' } })
    save()
    await waitFor(() => expect(screen.getByTestId('rules-stale')).toBeTruthy())
    fireEvent.click(screen.getByTestId('rules-reload'))
    await waitFor(() => expect(mockApi.getProgrammeCriteria).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('rules-stale')).toBeNull())
    expect(value('rules-household')).toBe('5860')
  })
})

describe('states that cannot be edited', () => {
  it('not built yet: a calm notice, the rules shown, Save asleep', async () => {
    withCriteria(payload(TREE_1, { stored: false })); await loaded()
    expect(screen.getByTestId('rules-not-built').textContent).toContain('admin.criteria.notReady')
    expect(value('rules-household')).toBe('5860')
    expect((screen.getByTestId('rules-household-value') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByText('common.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('stored rules that cannot be read: the block notice and no editor', async () => {
    withCriteria(payload(null, { rules_error: true })); await loaded()
    expect(screen.getByTestId('rules-error')).toBeTruthy()
    expect(screen.queryByTestId('rules-editor')).toBeNull()
    expect((screen.getByText('common.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('a tree the screen cannot show is not saved over', async () => {
    withCriteria(payload({ all: [{ section: 'merit', all: [{ test: 'min_merit', value: 80 }] }] }))
    await loaded()
    expect(screen.getByTestId('rules-cannot-show')).toBeTruthy()
    expect((screen.getByText('common.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('no intake year: points to the Intake year tab', async () => {
    mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [programme()] })
    mockApi.getProgrammeCriteria.mockRejectedValue(apiError('no_intake_year', 404))
    const goToYear = jest.fn()
    render(<ProgrammeRulesTab goToYear={goToYear} />)
    await waitFor(() => expect(screen.getByText('admin.rules.noYear')).toBeTruthy())
    fireEvent.click(screen.getByTestId('rules-go-to-year'))
    expect(goToYear).toHaveBeenCalled()
  })
})

describe('owner copy rules', () => {
  it('no "route" and no B40 label in the keys the editor renders', async () => {
    withCriteria(payload(TREE_3)); await loaded()
    const text = screen.getByTestId('rules-tab').textContent ?? ''
    expect(text.toLowerCase()).not.toContain('route')
    expect(text).not.toContain('B40')
  })
})
