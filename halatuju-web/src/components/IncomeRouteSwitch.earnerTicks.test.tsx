/**
 * @jest-environment jsdom
 *
 * Request #84, review round 1 (2026-11-25): THE PROMISE HOLDS AFTER SUBMISSION TOO. Once submitted,
 * the student's only way to change the "who works" ticks is the Action Centre's income-route switch.
 * Its member chips saved with no check; now a tick the family details disagree with (the SERVED
 * `earner_tick_conflicts`, carried page → Action Centre → switch) is asked about first, exactly as
 * on the income step. This mounts the real Action Centre, locked (a submitted case), with an open
 * income task.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'
import type { EarnerTickConflicts } from '@/lib/api/application'
import { readWeb } from '@/test/sourceGuard'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
  switchIncomeRoute: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null, CoachCard: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const S = 'scholarship.incomeRouteSwitch'
const W = 'scholarship.docs.income.wizard.earnerCheck'
const CONFLICTS: EarnerTickConflicts = { mother: { kind: 'not_working', occupation: 'unemployed' }, guardian: { kind: 'not_listed' } }

const INCOME_TASK: ResolutionItem = {
  id: 41, fact: 'income', code: 'income_doc_missing', params: {},
  prompt: '', kind: 'doc', doc_type: 'salary_slip', status: 'open',
  source: 'check2' as ResolutionItem['source'], resolution_text: '',
  created_at: '2026-11-25T09:00:00.000Z', resolved_at: null,
}

const chip = (m: string) => screen.getByText(`${S}.member.${m}`)

/** A submitted student, salary route chosen in the switch. */
async function openSalary(conflicts: EarnerTickConflicts | null = CONFLICTS) {
  mockApi.getResolutionItems.mockResolvedValue({ open: [INCOME_TASK], resolved: [] })
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  mockApi.switchIncomeRoute.mockResolvedValue({ income_route: 'salary', requirements: { route: 'salary', members: [], compulsory: [], optional: [] } })
  render(<ActionCentre token="test-token" applicationId={7} formLocked earnerTickConflicts={conflicts} />)
  fireEvent.click(await screen.findByText(`${S}.cta`))
  fireEvent.click(screen.getByText(`${S}.route.salary`))
}

beforeEach(() => { jest.clearAllMocks() })

describe('#84 after submission: the Action Centre asks before holding a disagreeing tick', () => {
  it('a disagreeing member is asked about, not ticked; "No" leaves it unticked', async () => {
    await openSalary()
    fireEvent.click(chip('mother'))
    expect(screen.getByRole('alertdialog').textContent).toContain(`${W}.askNotWorking`)
    expect(chip('mother').getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(screen.getByText(`${W}.cancel`))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(chip('mother').getAttribute('aria-pressed')).toBe('false')
    expect((screen.getByText(`${S}.confirm`) as HTMLButtonElement).disabled).toBe(true)   // nothing chosen, nothing sent
    expect(mockApi.switchIncomeRoute).not.toHaveBeenCalled()
  })

  it('an agreeing member is ticked at once, with no question', async () => {
    await openSalary()
    fireEvent.click(chip('father'))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(chip('father').getAttribute('aria-pressed')).toBe('true')
  })

  it('"Yes" ticks them, keeps the standing note, and the switch sends the tick', async () => {
    await openSalary()
    fireEvent.click(chip('guardian'))
    expect(screen.getByRole('alertdialog').textContent).toContain(`${W}.askNotListed`)
    fireEvent.click(screen.getByText(`${W}.confirm`))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(chip('guardian').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByTestId('earner-tick-note-guardian').textContent).toContain(`${W}.noteNotListed`)
    await act(async () => { fireEvent.click(screen.getByText(`${S}.confirm`)) })
    expect(mockApi.switchIncomeRoute).toHaveBeenCalledWith(
      7, { income_route: 'salary', income_working_members: ['guardian'] }, { token: 'test-token' })
  })

  it('focus moves into the question (on "No") and back to the chip that opened it', async () => {
    await openSalary()
    fireEvent.click(chip('mother'))
    const dialog = screen.getByRole('alertdialog')
    expect(document.activeElement).toBe(screen.getByText(`${W}.cancel`))
    expect(document.getElementById(dialog.getAttribute('aria-describedby') || '')?.textContent).toBe(`${W}.askCheck`)
    fireEvent.click(screen.getByText(`${W}.cancel`))
    expect(document.activeElement).toBe(chip('mother'))
  })

  it('review round 2: Confirm is held while a question is open, so the held member is never silently left out', async () => {
    await openSalary()
    fireEvent.click(chip('father'))                                     // agreeing: Confirm is ready
    const confirm = screen.getByText(`${S}.confirm`) as HTMLButtonElement
    expect(confirm.disabled).toBe(false)
    fireEvent.click(chip('mother'))                                     // disagreeing: asked
    expect(confirm.disabled).toBe(true)
    fireEvent.click(confirm)
    expect(mockApi.switchIncomeRoute).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText(`${W}.cancel`))                     // answered: Confirm is back
    expect(confirm.disabled).toBe(false)
  })

  it('a route change drops an open question (STR and back does not revive it)', async () => {
    await openSalary()
    fireEvent.click(chip('mother'))
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    fireEvent.click(screen.getByText(`${S}.route.str`))
    fireEvent.click(screen.getByText(`${S}.route.salary`))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(chip('mother').getAttribute('aria-pressed')).toBe('false')
  })

  it('no served answer (an older api) asks nothing', async () => {
    await openSalary(null)
    fireEvent.click(chip('mother'))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(chip('mother').getAttribute('aria-pressed')).toBe('true')
  })
})

it('the application page hands the served conflicts to the (locked) Action Centre', () => {
  const page = readWeb('src/app/scholarship/application/page.tsx', 'the page that mounts the post-submit Action Centre')
  expect(page).toContain('earnerTickConflicts={app.earner_tick_conflicts}')
})
