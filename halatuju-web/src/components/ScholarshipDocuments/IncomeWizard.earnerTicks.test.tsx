/**
 * @jest-environment jsdom
 *
 * Request #84, review round 2 (2026-11-25): THE REAL INCOME STEP HOLDS A DISAGREEING TICK. The hook's
 * own tests use a harness; this mounts the real `IncomeWizard` with `earner_tick_conflicts` served and
 * watches its save call (`updateScholarshipDetails`): a disagreeing member is not saved until "Yes",
 * never after "No", and an agreeing member saves at once. A "No" also leaves the roster sync alone
 * (#1): only a tick that actually changes marks the student as choosing.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import IncomeWizard from './IncomeWizard'
import type { ScholarshipApplication } from '@/lib/api'
import type { EarnerTickConflicts } from '@/lib/api/application'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  updateScholarshipDetails: jest.fn(),
}))
jest.mock('../IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const W = 'scholarship.docs.income.wizard'
const C = `${W}.earnerCheck`
const CONFLICTS: EarnerTickConflicts = { mother: { kind: 'not_working', occupation: 'homemaker' }, guardian: { kind: 'not_listed' } }

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.updateScholarshipDetails.mockResolvedValue({} as never)
})

const el = (extra: Record<string, unknown>) => (
  <IncomeWizard
    app={{ ...sandboxApplication, income_route: 'salary', income_earner: 'father',
           earner_tick_conflicts: CONFLICTS, ...extra } as unknown as ScholarshipApplication}
    token="sandbox-token" t={(k: string) => k} renderCard={() => null} docs={[]} lang="en"
  />
)
const saved = { income_working_members: ['father'], income_declared: { father: 300 } }
const tap = async (text: string) => { await act(async () => { fireEvent.click(screen.getByText(text)) }) }
const memberSaves = () => mockApi.updateScholarshipDetails.mock.calls.filter(([, p]) => 'income_working_members' in p)
/** The member's toggle on the income step reads "✓ <label>" when ticked. */
const ticked = (m: string) => screen.getAllByRole('button').some((b) => b.textContent === `✓ ${W}.member.${m}`)

describe('#84 on the real income step: a disagreeing tick is not saved until "Yes"', () => {
  it('"Yes" saves it; until then nothing is sent', async () => {
    render(el(saved))
    await tap(`${W}.member.mother`)
    expect(screen.getByRole('alertdialog').textContent).toContain(`${C}.askNotWorking`)
    expect(mockApi.updateScholarshipDetails).not.toHaveBeenCalled()
    await tap(`${C}.confirm`)
    expect(memberSaves()).toEqual([[sandboxApplication.id, { income_working_members: ['father', 'mother'] }, { token: 'sandbox-token' }]])
  })

  it('"No" never saves that member', async () => {
    render(el(saved))
    await tap(`${W}.member.guardian`)
    await tap(`${C}.cancel`)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(ticked('guardian')).toBe(false)
    expect(mockApi.updateScholarshipDetails).not.toHaveBeenCalled()
  })

  it('an agreeing member saves at once, with no question', async () => {
    render(el(saved))
    await tap(`${W}.member.brother`)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(memberSaves()).toEqual([[sandboxApplication.id, { income_working_members: ['father', 'brother'] }, { token: 'sandbox-token' }]])
  })
})

describe('#84 review round 2: only a tick that changes stops the roster sync (#1)', () => {
  // Nothing saved yet: the ticks follow the family roster (father works) until the student chooses.
  const fresh = { income_working_members: [], father_occupation: 'construction', mother_occupation: 'homemaker' }

  it('"No" leaves the ticks following the roster', async () => {
    const { rerender } = render(el(fresh))
    await tap(`${W}.member.mother`)
    await tap(`${C}.cancel`)
    rerender(el({ ...fresh, mother_occupation: 'teacher' }))   // the family details now say she works
    expect(ticked('mother')).toBe(true)
  })

  it('"Yes" is a choice: the roster no longer re-seeds the ticks', async () => {
    const { rerender } = render(el(fresh))
    await tap(`${W}.member.mother`)
    await tap(`${C}.confirm`)
    rerender(el({ ...fresh, father_occupation: 'unemployed' }))
    expect(ticked('father')).toBe(true)
    expect(ticked('mother')).toBe(true)
  })
})
