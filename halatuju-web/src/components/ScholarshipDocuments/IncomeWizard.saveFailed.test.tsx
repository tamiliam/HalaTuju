/**
 * @jest-environment jsdom
 *
 * TD-460(b) (audit A1.12) — A FAILED ANSWER SAVE IS SHOWN, NOT SWALLOWED.
 *
 * Every answer pill saves through `save()`. Its failure used to be swallowed ("soft"), so a student
 * on a bad connection saw her answer while the server held the old one — and the household-income
 * route engine (who is means-tested how) reads the server's. Now a failed save shows
 * "Not saved — tap your answer again", and the next successful save clears it.
 *
 * NOT covered here, on purpose: part (a), the write-on-open of the pre-fill, waits on an owner
 * decision and is unchanged. `t` echoes its key, so text is found by its i18n key.
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

beforeEach(() => { jest.clearAllMocks() })

const wizard = () => render(
  <IncomeWizard
    // Every answer already on the application, so the open-time pre-fill write does not fire.
    app={{ ...sandboxApplication, income_route: 'str', income_earner: 'father',
           income_working_members: ['father'] } as unknown as ScholarshipApplication}
    token="sandbox-token"
    t={(k: string) => k}
    renderCard={() => null}
    docs={[]}
    lang="en"
  />,
)

const tap = async (key: string) => {
  await act(async () => { fireEvent.click(screen.getByText(`${W}.${key}`)) })
}

describe('TD-460(b) — the income wizard shows a failed save', () => {
  it('shows "not saved" as an alert when the answer did not reach the server', async () => {
    mockApi.updateScholarshipDetails.mockRejectedValue(new Error('offline'))
    wizard()
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
    await tap('earner.mother')
    expect(mockApi.updateScholarshipDetails).toHaveBeenCalledWith(
      expect.anything(), { income_earner: 'mother' }, expect.anything())
    expect(screen.getByRole('alert').textContent).toBe(NOT_SAVED)
  })

  it('clears the message once the next tap saves', async () => {
    mockApi.updateScholarshipDetails.mockRejectedValueOnce(new Error('offline'))
    mockApi.updateScholarshipDetails.mockResolvedValue({} as never)
    wizard()
    await tap('earner.mother')
    expect(screen.getByText(NOT_SAVED)).toBeTruthy()
    await tap('earner.mother')
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })

  it('a save that works shows nothing', async () => {
    mockApi.updateScholarshipDetails.mockResolvedValue({} as never)
    wizard()
    await tap('earner.guardian')
    expect(screen.queryByText(NOT_SAVED)).toBeNull()
  })
})
