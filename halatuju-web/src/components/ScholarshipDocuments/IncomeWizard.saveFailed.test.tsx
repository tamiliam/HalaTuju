/**
 * @jest-environment jsdom
 *
 * TD-460(b) (audit A1.12, review L1-L3) — A FAILED ANSWER SAVE IS SHOWN, BY FIELD, WITH "TRY AGAIN".
 *
 * Every answer saves through `save()`. Its failure used to be swallowed, so a student on a bad
 * connection saw her answer while the server held the old one — and the household-income route
 * engine reads the server's. Now the failed values are kept per field (`failedSaves.tsx`): the
 * alert stays until every failed field is saved, and "Try again" re-sends those exact values. It
 * never asks for a repeat tap, because a repeated toggle un-ticks the member (review L1).
 *
 * NOT covered here, on purpose: part (a), the write-on-open of the pre-fill, waits on an owner
 * decision and is unchanged. `t` echoes its key, so text is found by its i18n key. Every answer is
 * already on the application in these fixtures, so the open-time pre-fill write does not fire.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import IncomeWizard from './IncomeWizard'
import type { ScholarshipApplication } from '@/lib/api'
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
const NOT_SAVED = `${W}.notSaved`
const offline = () => mockApi.updateScholarshipDetails.mockRejectedValueOnce(new Error('offline'))

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.updateScholarshipDetails.mockResolvedValue({} as never)
})

const wizard = (extra: Record<string, unknown>) => render(
  <IncomeWizard
    app={{ ...sandboxApplication, ...extra } as unknown as ScholarshipApplication}
    token="sandbox-token"
    t={(k: string) => k}
    renderCard={() => null}
    docs={[]}
    lang="en"
  />,
)
const strApp = { income_route: 'str', income_earner: 'father', income_working_members: ['father'] }
const salaryApp = { income_route: 'salary', income_earner: 'father', income_working_members: ['father'],
                    income_declared: { father: 300 } }

const click = async (key: string) => {
  await act(async () => { fireEvent.click(screen.getByText(`${W}.${key}`)) })
}
const lastPatch = () => mockApi.updateScholarshipDetails.mock.calls.at(-1)?.[1]

describe('TD-460(b) — the income wizard shows a failed save', () => {
  it('a failed save shows the alert with Try again; a save that works shows nothing', async () => {
    wizard(strApp)
    await click('earner.guardian')
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
    offline()
    await click('earner.mother')
    expect(screen.getByRole('alert').textContent).toContain(NOT_SAVED)
    expect(screen.getByText(`${W}.tryAgain`)).toBeTruthy()
  })

  it('L1: a failed toggle + Try again keeps Mother ticked and sends the ticked list', async () => {
    wizard(salaryApp)
    offline()
    await click('member.mother')
    expect(lastPatch()).toEqual({ income_working_members: ['father', 'mother'] })
    expect(screen.getByText(NOT_SAVED)).toBeTruthy()
    await click('tryAgain')
    expect(lastPatch()).toEqual({ income_working_members: ['father', 'mother'] })   // re-sent, not toggled
    expect(screen.getByText(`✓ ${W}.member.mother`, { exact: false })).toBeTruthy()
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })

  it('L2: a later save of a DIFFERENT field does not clear the failed one', async () => {
    wizard(strApp)
    offline()
    await click('earner.mother')
    await click('no')                                       // income_route saves fine
    expect(lastPatch()).toEqual({ income_route: 'salary' })
    expect(screen.getByText(NOT_SAVED)).toBeTruthy()
    await click('tryAgain')
    expect(lastPatch()).toEqual({ income_earner: 'mother' })
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })

  it('a later save of the SAME field (a newer value) clears that field', async () => {
    wizard(strApp)
    offline()
    await click('earner.mother')
    expect(screen.getByText(NOT_SAVED)).toBeTruthy()
    await click('earner.guardian')
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })

  it('an older answer failing late does not bring back its value', async () => {
    let failOld: (e: Error) => void = () => {}
    mockApi.updateScholarshipDetails.mockImplementationOnce(
      () => new Promise((_res, rej) => { failOld = rej }) as never)
    wizard(strApp)
    await click('earner.mother')                            // still in flight
    await click('earner.guardian')                          // newer value, saves
    await act(async () => { failOld(new Error('offline')) })
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })

  it('L3: a typed income that does not save shows the alert, and Try again re-sends the figure', async () => {
    wizard(salaryApp)
    const box = screen.getByPlaceholderText(`${W}.declared.placeholder`)
    offline()
    await act(async () => {
      fireEvent.change(box, { target: { value: '450' } })
      fireEvent.blur(box, { target: { value: '450' } })
    })
    expect(lastPatch()).toEqual({ income_declared: { father: 450 } })
    expect(screen.getByRole('alert').textContent).toContain(NOT_SAVED)
    await click('tryAgain')
    expect(lastPatch()).toEqual({ income_declared: { father: 450 } })
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })
})
