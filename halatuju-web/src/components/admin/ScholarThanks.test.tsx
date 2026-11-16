/**
 * @jest-environment jsdom
 *
 * Sprint THANKS-SCHOLARS (owner 2026-11-16, "Thank yous are part of the scholar maintenance process."):
 * the graduation thank-you card on the scholar file, rendered. Pinned: the controls follow the served
 * `may_decide` and nothing else (read only without it: no box, no buttons); a pending thank-you's editable
 * text (the student's words to start), Approve and Reject with an optional note; a blocked one offers
 * Reject only and says why; the server's `scrubbed_leak` is said plainly; a decided one is read only.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import ScholarThanks from './ScholarThanks'
import {
  getScholarThanks, reviewScholarThanks, type AdminGraduationMessage,
} from '@/lib/admin-api'

jest.mock('@/lib/admin-api', () => ({ getScholarThanks: jest.fn(), reviewScholarThanks: jest.fn() }))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k) }),
}))
const get = getScholarThanks as jest.Mock
const review = reviewScholarThanks as jest.Mock

const K = 'admin.scholarship.graduationThanks'

const msg = (over: Partial<AdminGraduationMessage> = {}): AdminGraduationMessage => ({
  id: 5, application: 7, ref: 'HT-ABC123', status: 'pending', raw_text: 'Thank you for everything.',
  scrubbed_text: '', scan_result: [], approved_by: '', review_note: '',
  created_at: '2026-11-15T09:00:00+08:00', reviewed_at: null, ...over,
})

function mount() {
  return render(<ScholarThanks id={7} token="tok" />)
}
/** What the server serves: the messages and whether THIS reader may decide. */
const served = (messages: AdminGraduationMessage[], may_decide = true) => ({ messages, may_decide })

beforeEach(() => { get.mockReset(); review.mockReset() })

describe('without the served may_decide (a mentor, or anyone the server says may only read)', () => {
  it('shows a pending thank-you read only: no box, no Approve, no Reject', async () => {
    get.mockResolvedValue(served([msg()], false))
    mount()
    expect(await screen.findByText(`${K}.introReadOnly`)).toBeTruthy()
    expect(screen.getByRole('blockquote').textContent).toContain('Thank you for everything.')
    expect(screen.getByText(`${K}.status.pending`)).toBeTruthy()
    expect(screen.queryByLabelText(`${K}.sponsorSees`)).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a blocked one says why but offers no Reject', async () => {
    get.mockResolvedValue(served([msg({ status: 'blocked', scan_result: ['name'] })], false))
    mount()
    expect(await screen.findByTestId('thanks-blocked-reason')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a missing flag is read only too', async () => {
    get.mockResolvedValue({ messages: [msg()] })
    mount()
    expect(await screen.findByText(`${K}.introReadOnly`)).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })
})

it('draws nothing when the scholar has no thank-you', async () => {
  get.mockResolvedValue(served([]))
  const { container } = mount()
  await act(async () => {})
  expect(get).toHaveBeenCalledWith(7, { token: 'tok' })
  expect(container.innerHTML).toBe('')
})

describe('a pending thank-you', () => {
  it('starts the sponsor text as the student wrote it, and approves the edited text', async () => {
    get.mockResolvedValue(served([msg()]))
    review.mockResolvedValue(msg({ status: 'approved', scrubbed_text: 'Thank you, truly.',
      approved_by: 'officer@example.test', reviewed_at: '2026-11-16T10:00:00+08:00' }))
    mount()
    const box = await screen.findByLabelText(`${K}.sponsorSees`) as HTMLTextAreaElement
    expect(box.value).toBe('Thank you for everything.')
    expect(screen.getByText(`${K}.status.pending`)).toBeTruthy()
    fireEvent.change(box, { target: { value: 'Thank you, truly.' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${K}.approve` })) })
    expect(review).toHaveBeenCalledWith(7, 5, { action: 'approve', scrubbed_text: 'Thank you, truly.' }, { token: 'tok' })
    expect(await screen.findByText(`${K}.status.approved`)).toBeTruthy()
    expect(screen.getByText('Thank you, truly.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: `${K}.approve` })).toBeNull()
  })

  it('rejects with an optional note', async () => {
    get.mockResolvedValue(served([msg()]))
    review.mockResolvedValue(msg({ status: 'rejected', review_note: 'Please write it again.',
      reviewed_at: '2026-11-16T10:00:00+08:00' }))
    mount()
    await screen.findByLabelText(`${K}.sponsorSees`)
    fireEvent.click(screen.getByRole('button', { name: `${K}.reject` }))
    const reasonBox = screen.getByTestId('thanks-reject-box')
    fireEvent.change(reasonBox.querySelector('textarea') as HTMLTextAreaElement,
      { target: { value: 'Please write it again.' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${K}.reject` })) })
    expect(review).toHaveBeenCalledWith(7, 5, { action: 'reject', review_note: 'Please write it again.' }, { token: 'tok' })
    expect(await screen.findByText(`${K}.status.rejected`)).toBeTruthy()
  })

  it('says plainly when the text still names the student', async () => {
    get.mockResolvedValue(served([msg()]))
    review.mockRejectedValue(Object.assign(new Error('scrubbed_leak'), { status: 400, code: 'scrubbed_leak' }))
    mount()
    await screen.findByLabelText(`${K}.sponsorSees`)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${K}.approve` })) })
    expect(screen.getByRole('alert').textContent).toBe(`${K}.error.scrubbed_leak`)
    expect(screen.getByText(`${K}.status.pending`)).toBeTruthy()
  })

  it('will not approve an empty text', async () => {
    get.mockResolvedValue(served([msg()]))
    mount()
    const box = await screen.findByLabelText(`${K}.sponsorSees`)
    fireEvent.change(box, { target: { value: '   ' } })
    expect((screen.getByRole('button', { name: `${K}.approve` }) as HTMLButtonElement).disabled).toBe(true)
  })
})

it('a blocked thank-you offers Reject only, with the reason', async () => {
  get.mockResolvedValue(served([msg({ status: 'blocked', scan_result: ['name', 'school'] })]))
  mount()
  expect((await screen.findByTestId('thanks-blocked-reason')).textContent)
    .toBe(`${K}.blockedReason:${K}.field.name, ${K}.field.school`)
  expect(screen.queryByLabelText(`${K}.sponsorSees`)).toBeNull()
  expect(screen.queryByRole('button', { name: `${K}.approve` })).toBeNull()
  expect(screen.getByRole('button', { name: `${K}.reject` })).toBeTruthy()
})

it('lists earlier versions read only', async () => {
  get.mockResolvedValue(served([msg(), msg({ id: 4, status: 'blocked', raw_text: 'First try', scan_result: ['city'] })]))
  mount()
  expect(await screen.findByText(`${K}.earlier:1`)).toBeTruthy()
  expect(screen.getByText('First try')).toBeTruthy()
})
