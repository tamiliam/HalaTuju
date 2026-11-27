/**
 * @jest-environment jsdom
 *
 * Criteria fix round 3 (review R2, blocker 1), against the REAL request contract: the Intake year
 * tab is rendered over the real `admin-api` client, and only `fetch` is stood in for. A new year is
 * ONE request — a POST to `programmes/<id>/years/` carrying the editor's whole `criteria` tree and
 * no requirement column — and nothing follows it: no criteria GET, no PATCH. (The old
 * create-then-PATCH could leave a year on looser rules than the admin saw when the PATCH failed.)
 * The server's side of the same contract: halatuju_api apps/scholarship/tests/test_criteria_create.py.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import IntakeYearTab from './IntakeYearTab'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))

const PROGRAMME = {
  id: 1, code: 'bp', name_en: 'BrightPath Bursary', name_ms: '', name_ta: '',
  is_active: true, lifecycle: 'active', intake_years: 0, applications: 0, awarded: 0, open_year: null,
  delete_blocked_by: null, delete_blocked_count: 0, apply_url: '', apply_copy: {}, apply_copy_sensitive: [],
}
const ROW = {
  id: 11, code: 'bp-2027', name: 'Intake 2027', year: 2027, is_open: false, is_active: true,
  applications: 0, opens_on: null, closes_on: null, state: 'draft', finished_at: null, finished_by: '',
  unsubmitted: 0, requirements: {},
}

type Call = { method: string; path: string; body: unknown }
let calls: Call[] = []
let postAnswer: { status: number; body: unknown } = { status: 201, body: ROW }

const orig = global.fetch
beforeEach(() => {
  calls = []
  postAnswer = { status: 201, body: ROW }
  global.fetch = jest.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method || 'GET'
    const path = new URL(url, 'http://x').pathname
    calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const answer = (status: number, body: unknown) => ({ ok: status < 400, status, json: async () => body })
    if (method === 'POST') return answer(postAnswer.status, postAnswer.body)
    if (path === '/api/v1/admin/scholarship/programmes/') return answer(200, { programmes: [PROGRAMME] })
    if (path === '/api/v1/admin/scholarship/programmes/1/years/') {
      return answer(200, { programme: { id: 1, code: 'bp', name_en: 'BrightPath Bursary', is_active: true }, years: [] })
    }
    return answer(200, {})
  }) as unknown as typeof fetch
})
afterEach(() => { global.fetch = orig })

const createWithIncomeAll = async () => {
  render(<IntakeYearTab />)
  fireEvent.click(await screen.findByText('+ admin.years.new'))
  fireEvent.change(document.getElementById('y-year') as HTMLInputElement, { target: { value: '2027' } })
  fireEvent.change(document.getElementById('y-code') as HTMLInputElement, { target: { value: 'bp-2027' } })
  fireEvent.change(document.getElementById('y-name') as HTMLInputElement, { target: { value: 'Intake 2027' } })
  // An 'all' income join: a rule the old columns cannot say — the case review R2 found.
  fireEvent.click(screen.getByTestId('new-household-switch'))
  fireEvent.change(screen.getByTestId('new-household-value'), { target: { value: '5000' } })
  fireEvent.click(screen.getByTestId('new-per-person-switch'))
  fireEvent.change(screen.getByTestId('new-per-person-value'), { target: { value: '900' } })
  fireEvent.click(screen.getByTestId('new-income-join-all'))
  fireEvent.click(screen.getByText('admin.years.createClosed'))
}

const writes = () => calls.filter((c) => c.method !== 'GET')
const TREE = { all: [{ section: 'income', all: [
  { test: 'household_income_max', rm: 5000 }, { test: 'income_per_person_under', rm: 900 }] }] }

it('one POST carries the whole tree, and no PATCH or criteria read follows', async () => {
  await createWithIncomeAll()
  await waitFor(() => expect(writes()).toHaveLength(1))
  const [post] = writes()
  expect(post).toEqual({
    method: 'POST', path: '/api/v1/admin/scholarship/programmes/1/years/',
    body: { code: 'bp-2027', name: 'Intake 2027', year: 2027, opens_on: null, closes_on: null, criteria: TREE },
  })
  // The list reloads after the create; nothing else is asked.
  await waitFor(() => expect(calls.filter((c) => c.path.endsWith('/years/') && c.method === 'GET')).toHaveLength(2))
  expect(calls.some((c) => c.path.includes('/criteria/'))).toBe(false)
  expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
})

it('a refused tree is shown with its reasons, and nothing follows', async () => {
  postAnswer = { status: 400, body: { error: 'bad_criteria', code: 'bad_criteria',
    problems: ['results: a post-SPM group needs a min_pngk floor'] } }
  await createWithIncomeAll()
  await waitFor(() => expect(screen.getByTestId('new-server-problems').textContent)
    .toContain('admin.criteria.problem.postNoFloor'))
  expect(screen.getAllByText('admin.criteria.error.badCriteria').length).toBeGreaterThan(0)
  expect(writes()).toHaveLength(1)
  expect(calls.some((c) => c.method === 'PATCH' || c.path.includes('/criteria/'))).toBe(false)
})
