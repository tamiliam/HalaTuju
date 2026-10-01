/**
 * @jest-environment jsdom
 *
 * TD-288 — AN ANSWER IN THE INCOME WIZARD KEEPS THE KEYBOARD WHERE IT WAS.
 *
 * `Pills` and `Question` were declared INSIDE `IncomeWizard`, so every render handed React two new
 * component types: each answer unmounted and remounted every question, and the pill a keyboard
 * user had just pressed left the document — focus fell to `<body>`, the top of the page. Lint
 * cannot see it (`ApplyCopyTab.tsx` documents the same trap). They now live at module scope.
 *
 * What this proves: after a press, the SAME button node is still in the document and still holds
 * focus. `t` echoes its key, so the pills are found by their i18n keys.
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

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.updateScholarshipDetails.mockResolvedValue({} as never)
})

const wizard = () => render(
  <IncomeWizard
    app={{ ...sandboxApplication, income_route: 'str', income_earner: 'father',
           income_working_members: ['father'] } as unknown as ScholarshipApplication}
    token="sandbox-token"
    t={(k: string) => k}
    renderCard={() => null}
    docs={[]}
    lang="en"
  />,
)

/** Focus a button the way a keyboard user reaches it, then press it. */
async function press(button: HTMLElement) {
  button.focus()
  expect(document.activeElement).toBe(button)
  await act(async () => { fireEvent.click(button) })
}

describe('TD-288 — the income wizard keeps focus on the pill that was pressed', () => {
  it('"whose STR" — pressing Mother keeps that same button in the page and focused', async () => {
    wizard()
    const mother = screen.getByText(`${W}.earner.mother`)
    await press(mother)
    expect(mother.isConnected).toBe(true)                 // not remounted
    expect(document.activeElement).toBe(mother)           // not dropped to <body>
    expect(mockApi.updateScholarshipDetails).toHaveBeenCalledWith(
      expect.anything(), { income_earner: 'mother' }, expect.anything())
  })

  it('"STR document?" — pressing No keeps that button focused while the next question changes', async () => {
    wizard()
    const no = screen.getByText(`${W}.no`)
    await press(no)
    expect(no.isConnected).toBe(true)
    expect(document.activeElement).toBe(no)
    // the control: the answer did land (the salary route's question replaced the STR one)
    expect(screen.getByText(`${W}.q2Multi`)).toBeTruthy()
    expect(screen.queryByText(`${W}.q2Str`)).toBeNull()
  })
})
