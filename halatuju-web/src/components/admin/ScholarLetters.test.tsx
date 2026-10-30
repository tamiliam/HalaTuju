/**
 * @jest-environment jsdom
 *
 * The scholar file's Letters tab and its issue dialog (student maintenance S6b). Pinned:
 *  * every state reads from the server: awaiting / overdue / acknowledged / withdrawn, emailed or "Not
 *    emailed" with Resend;
 *  * a termination prompts "Close the file?" — the button goes to the file's OWN Close control, "Not
 *    now" dismisses, and nothing here closes anything;
 *  * Withdraw only for who the server allows, and only with a reason;
 *  * the dialog offers only `can_issue`, shows the SERVER's draft and her email, says "documents only"
 *    for suspension and termination, and keeps "Issue and email" shut until the full name is typed
 *    (the server checks again); a refusal is said in words.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ScholarLetters from './ScholarLetters'
import * as api from '@/lib/admin-api/letters'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-api/letters')
const mockApi = api as jest.Mocked<typeof api>
const P = 'admin.scholars.letters'

const letter = (id: number, over: Partial<api.AdminLetter> = {}): api.AdminLetter => ({
  id, kind: 'general', language: 'en', subject: `Letter ${id}`, body: 'Dear Aisyah', clause: '',
  issued_at: '2026-10-30T02:00:00Z', issued_by_name: 'Siti', issued_by_role: 'org_admin',
  response_due_on: '2026-11-13', emailed_at: '2026-10-30T02:01:00Z', emailed_to: 'a…@gmail.com',
  acknowledged_at: null, withdrawn_at: null, withdrawn_by_name: '', withdrawn_reason: '', state: 'awaiting',
  has_pdf: true, ...over,
})
const PAYLOAD = (over: Partial<api.ScholarLetters> = {}): api.ScholarLetters => ({
  letters: [
    letter(1, { kind: 'termination', subject: 'Termination of your bursary (clause 9)' }),
    letter(2, { kind: 'discipline', language: 'ms', emailed_at: null, emailed_to: '', state: 'overdue' }),
    letter(3, { state: 'acknowledged', acknowledged_at: '2026-09-03T00:00:00Z' }),
    letter(4, { kind: 'suspension', withdrawn_at: '2026-08-20T00:00:00Z', withdrawn_by_name: 'Siti',
      withdrawn_reason: 'issued to the wrong student', state: 'withdrawn' }),
  ],
  can_issue: ['general', 'discipline', 'suspension', 'termination', 'close_out'], can_withdraw: true,
  prompt_close: true, response_days: 14, student_name: 'Nur Aisyah binti Rahman', default_language: 'en',
  file_closed: false, ...over,
})
const PREVIEW: api.LetterPreview = {
  subject: 'Termination of your bursary (clause 9)', body: 'Dear Nur Aisyah binti Rahman, …',
  response_due_on: '2026-11-13', needs_confirm: true,
  email: { language: 'ta', subject: 'ஒரு முறையான கடிதம்', body: 'அன்புள்ள …' },
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarLetters.mockResolvedValue(PAYLOAD())
  mockApi.previewLetter.mockResolvedValue(PREVIEW)
})

const mount = (over: Partial<React.ComponentProps<typeof ScholarLetters>> = {}) => {
  const props = { id: 104, token: 'tok', canClose: true, onGoToClose: jest.fn(), onChanged: jest.fn(), ...over }
  render(<ScholarLetters {...props} />)
  return props
}

it('reads every state from the server, with Resend where the email did not go', async () => {
  mount()
  expect((await screen.findByTestId('letter-state-1')).textContent).toContain(`${P}.state.awaiting`)
  expect(screen.getByTestId('letter-state-2').textContent).toContain(`${P}.state.overdue`)
  expect(screen.getByTestId('letter-state-3').textContent).toContain(`${P}.state.acknowledged`)
  expect(screen.getByTestId('letter-withdrawn-4').textContent).toContain('issued to the wrong student')
  expect(screen.queryByTestId('letter-state-4')).toBeNull()
  mockApi.resendLetter.mockResolvedValue(letter(2, { kind: 'discipline', state: 'overdue' }))
  fireEvent.click(within(screen.getByTestId('letter-not-emailed-2')).getByText(`${P}.resend`))
  await waitFor(() => expect(mockApi.resendLetter).toHaveBeenCalledWith(104, 2, { token: 'tok' }))
  expect(await screen.findByText(`${P}.resent`)).toBeTruthy()
})

it('a termination prompts "Close the file?" — the button goes to the file\'s own control; Not now dismisses', async () => {
  const props = mount()
  const prompt = await screen.findByTestId('letters-close-prompt')
  fireEvent.click(within(prompt).getByText(`${P}.closeFile`))
  expect(props.onGoToClose).toHaveBeenCalled()
  fireEvent.click(within(prompt).getByText(`${P}.notNow`))
  expect(screen.queryByTestId('letters-close-prompt')).toBeNull()
})

it('no Close button when the header offers no close, and no prompt when the server says none', async () => {
  mount({ canClose: false })
  const prompt = await screen.findByTestId('letters-close-prompt')
  expect(within(prompt).queryByText(`${P}.closeFile`)).toBeNull()
})

it('Withdraw needs a reason, and is not offered when the server says this officer may not', async () => {
  mockApi.withdrawLetter.mockResolvedValue(letter(1, { state: 'withdrawn', withdrawn_at: '2026-10-31T00:00:00Z' }))
  mount()
  const row = await screen.findByTestId('letter-1')
  fireEvent.click(within(row).getByText(`${P}.withdraw`))
  const confirm = within(row).getByText(`${P}.withdrawConfirm`) as HTMLButtonElement
  expect(confirm.disabled).toBe(true)
  fireEvent.change(within(row).getByRole('textbox'), { target: { value: 'wrong student' } })
  fireEvent.click(confirm)
  await waitFor(() => expect(mockApi.withdrawLetter).toHaveBeenCalledWith(104, 1, 'wrong student', { token: 'tok' }))
})

it('a reviewer sees no Withdraw and only the kinds she may issue', async () => {
  mockApi.getScholarLetters.mockResolvedValue(PAYLOAD({ can_withdraw: false, prompt_close: false,
    can_issue: ['general', 'discipline', 'close_out'] }))
  mount()
  await screen.findByTestId('letter-1')
  expect(screen.queryByText(`${P}.withdraw`)).toBeNull()
  fireEvent.click(screen.getByText(`${P}.issue`))
  const dialog = screen.getByTestId('issue-letter')
  expect(within(dialog).getAllByRole('radio')).toHaveLength(3)
  expect(within(dialog).queryByText(`${P}.kind.termination`)).toBeNull()
  expect(within(dialog).getByText(`${P}.dialog.seniorOnly`)).toBeTruthy()
})

it('the dialog: the server draft and her email, documents-only, and the typed full name', async () => {
  mockApi.issueLetter.mockResolvedValue(letter(9, { kind: 'termination' }))
  mount()
  await screen.findByTestId('letter-1')
  fireEvent.click(screen.getByText(`${P}.issue`))
  const dialog = screen.getByTestId('issue-letter')
  fireEvent.click(within(dialog).getByLabelText(`${P}.kind.termination`))
  fireEvent.change(within(dialog).getByLabelText(`${P}.dialog.clause`), { target: { value: '9' } })
  expect(await within(dialog).findByTestId('letter-preview')).toBeTruthy()
  await waitFor(() => expect(mockApi.previewLetter).toHaveBeenLastCalledWith(
    104, { kind: 'termination', language: 'en', clause: '9', note: '' }, { token: 'tok' }))
  expect(within(dialog).getByTestId('letter-email-preview').textContent).toContain('emailLang.ta')
  expect(within(dialog).getByTestId('letter-docs-only')).toBeTruthy()
  const issue = within(dialog).getByText(`${P}.dialog.issueAndEmail`) as HTMLButtonElement
  expect(issue.disabled).toBe(true)
  fireEvent.change(within(dialog).getByTestId('letter-confirm-name'), { target: { value: 'Nur Aisyah' } })
  expect(issue.disabled).toBe(true)
  fireEvent.change(within(dialog).getByTestId('letter-confirm-name'), { target: { value: ' nur aisyah  binti rahman ' } })
  expect(issue.disabled).toBe(false)
  fireEvent.click(issue)
  await waitFor(() => expect(mockApi.issueLetter).toHaveBeenCalledWith(104, {
    kind: 'termination', language: 'en', clause: '9', note: '', confirm_name: ' nur aisyah  binti rahman ',
  }, { token: 'tok' }))
})

it('a refusal from the server is said in words', async () => {
  mockApi.issueLetter.mockRejectedValue(Object.assign(new Error('x'), { code: 'confirm_mismatch' }))
  mount()
  await screen.findByTestId('letter-1')
  fireEvent.click(screen.getByText(`${P}.issue`))
  const dialog = screen.getByTestId('issue-letter')
  await within(dialog).findByTestId('letter-preview')
  fireEvent.click(within(dialog).getByText(`${P}.dialog.issueAndEmail`))
  expect(await within(dialog).findByText(`${P}.error.confirm_mismatch`)).toBeTruthy()
})
