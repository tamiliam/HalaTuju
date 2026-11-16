/**
 * @jest-environment jsdom
 *
 * Request #75: reject before interview, on the cockpit. The door is SERVED (`app.pre_interview`):
 * without it nothing shows (a reviewer, another stage); with a reviewer on the case only the
 * "unassign first" hint shows. The panel asks for a main reason and a note (counted against the
 * served limit), then an "Are you sure?" step names the student, the reason and the date the email
 * goes (or that it goes at once with no hold). Focus moves with each step (#75 review). The record card
 * shows the held date (the header's cool-off banner carries "Cancel decline"), or the sent date.
 * Dummy data only.
 */
import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { PreInterviewOption, PreInterviewRecord } from './PreInterviewReject'
import * as api from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const P = 'admin.scholarship.preInterview'
const t = ((k: string, p?: Record<string, unknown>) => (p ? `${k}|${JSON.stringify(p)}` : k)) as never
const OFFER = {
  hold_hours: 24,
  reasons: ['not_b40', 'not_government_institution', 'results_too_low', 'programme_requirements', 'not_responsive', 'other'],
  note_max: 20,
}
const caseOf = (over: Record<string, unknown> = {}) =>
  ({ id: 7, name: 'Dummy Student', status: 'profile_complete', assigned_to_id: null, pre_interview: OFFER, ...over }) as unknown as api.AdminScholarshipDetail

let onStale: jest.Mock
/** The page holds the refusal (#75 re-check); this stands in for it. */
function Page({ app, canAssign, onDone }: { app: api.AdminScholarshipDetail; canAssign: boolean; onDone: jest.Mock }) {
  const [err, setErr] = useState('')
  return <PreInterviewOption app={app} t={t} token="tok" busy="" canAssign={canAssign}
    err={err} setErr={setErr} onDone={onDone} onStale={onStale} />
}
const draw = (app: api.AdminScholarshipDetail, canAssign = true) => {
  const onDone = jest.fn()
  onStale = jest.fn()
  render(<Page app={app} canAssign={canAssign} onDone={onDone} />)
  return onDone
}
const fill = (reason: string, note: string) => {
  fireEvent.change(screen.getByLabelText(`${P}.reasonLabel`), { target: { value: reason } })
  fireEvent.change(screen.getByLabelText(`${P}.whyLabel`), { target: { value: note } })
}

beforeEach(() => jest.clearAllMocks())

describe('the door', () => {
  it('shows nothing when the server does not offer it (a reviewer, or another stage)', () => {
    draw(caseOf({ pre_interview: undefined }))
    expect(screen.queryByTestId('pre-interview')).toBeNull()
    expect(screen.queryByTestId('pre-interview-unassign-first')).toBeNull()
  })

  it('offers the secondary button with its help line', () => {
    draw(caseOf())
    expect(screen.getByRole('button', { name: `${P}.start` })).toBeTruthy()
    expect(screen.getByText(`${P}.help`)).toBeTruthy()
  })

  it('with a reviewer on the case: no button, only the hint to unassign first', () => {
    draw(caseOf({ assigned_to_id: 12 }))
    expect(screen.queryByRole('button', { name: `${P}.start` })).toBeNull()
    expect(screen.getByTestId('pre-interview-unassign-first').textContent).toBe(`${P}.unassignFirst`)
  })

  it('a viewer who cannot assign is told to ask someone who assigns reviewers', () => {
    draw(caseOf({ assigned_to_id: 12 }), false)
    expect(screen.getByTestId('pre-interview-unassign-first').textContent).toBe(`${P}.unassignAsk`)
  })
})

describe('the panel', () => {
  it('lists the served reasons and rests until a reason and a note are given', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    const options = screen.getByLabelText(`${P}.reasonLabel`).querySelectorAll('option')
    expect(options).toHaveLength(OFFER.reasons.length + 1)
    const submit = screen.getByRole('button', { name: `${P}.submit` }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    fill('not_b40', '   ')
    expect(submit.disabled).toBe(true)
    fill('', 'Dummy note')
    expect(submit.disabled).toBe(true)
    fill('not_b40', 'Dummy note')
    expect(submit.disabled).toBe(false)
  })

  it('counts the note against the served limit', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fill('other', 'Dummy')
    expect(screen.getByTestId('pre-interview-counter').textContent).toBe(`${P}.counter|{"count":"5","max":"20"}`)
    expect((screen.getByLabelText(`${P}.whyLabel`) as HTMLTextAreaElement).maxLength).toBe(20)
  })

  it('Cancel closes the panel and sends nothing', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.cancel` }))
    expect(screen.getByRole('button', { name: `${P}.start` })).toBeTruthy()
    expect(mockApi.rejectBeforeInterview).not.toHaveBeenCalled()
  })
})

describe('focus and labels (#75 review)', () => {
  it('opening the form puts focus on the reason; Cancel puts it back on the start button', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    expect(document.activeElement).toBe(screen.getByLabelText(`${P}.reasonLabel`))
    fireEvent.click(screen.getByRole('button', { name: `${P}.cancel` }))
    expect(document.activeElement).toBe(screen.getByRole('button', { name: `${P}.start` }))
  })

  it('the note names its hint and its counter', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    const ids = (screen.getByLabelText(`${P}.whyLabel`).getAttribute('aria-describedby') || '').split(' ')
    expect(ids.map((id) => document.getElementById(id)?.textContent)).toEqual([
      `${P}.whyHint`, `${P}.counter|{"count":"0","max":"20"}`])
  })

  it('"Are you sure?" is an alert dialog named by its heading, which takes focus; Go back returns it to Reject', () => {
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fill('not_b40', 'Dummy note')
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    const dialog = screen.getByRole('alertdialog', { name: `${P}.confirmTitle` })
    expect(dialog).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: `${P}.confirmTitle` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.back` }))
    expect(document.activeElement).toBe(screen.getByRole('button', { name: `${P}.submit` }))
  })

  it('a stale refusal stays in view, and is cleared when the form is opened again (#75 re-check)', async () => {
    mockApi.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code: 'has_reviewer' }))
    onStale = jest.fn()
    const page = (app: api.AdminScholarshipDetail) => <Page app={app} canAssign onDone={jest.fn()} />
    const { rerender } = render(page(caseOf()))
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fill('not_b40', 'Dummy note')
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    await waitFor(() => expect(onStale).toHaveBeenCalled())
    rerender(page(caseOf({ assigned_to_id: 5 })))                 // the reload: a colleague assigned
    expect(screen.getByRole('alert').textContent).toBe(`${P}.error.has_reviewer`)
    rerender(page(caseOf()))                                       // later set back to Unassigned
    expect(screen.getByRole('alert').textContent).toBe(`${P}.error.has_reviewer`)
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('a refusal returns focus to Reject, never to the page body', async () => {
    mockApi.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code: 'comments_too_long' }))
    draw(caseOf())
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fill('not_b40', 'Dummy note')
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    await screen.findByRole('alert')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: `${P}.submit` }))
  })
})

describe('are you sure?', () => {
  const toConfirm = () => {
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fill('results_too_low', 'Dummy note')
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
  }

  it('names the student and the reason, and says when the email goes (now + the served hold)', () => {
    const now = jest.spyOn(Date, 'now').mockReturnValue(Date.UTC(2026, 10, 16, 4))
    draw(caseOf())
    toConfirm()
    expect(screen.getByTestId('pre-interview-confirm').textContent).toContain(`"date":"${formatDate(Date.UTC(2026, 10, 17, 4))}"`)
    now.mockRestore()
    const box = screen.getByTestId('pre-interview-confirm')
    expect(box.textContent).toContain('Dummy Student')
    expect(box.textContent).toContain(`${P}.reasons.results_too_low`)
    expect(box.textContent).toContain(`${P}.confirmEmail`)
    expect(mockApi.rejectBeforeInterview).not.toHaveBeenCalled()
  })

  it('with no hold, says the email goes at once', () => {
    draw(caseOf({ pre_interview: { ...OFFER, hold_hours: 0 } }))
    toConfirm()
    const box = screen.getByTestId('pre-interview-confirm')
    expect(box.textContent).toContain(`${P}.confirmEmailNow`)
    expect(box.textContent).not.toContain(`${P}.confirmEmail|`)
  })

  it('Go back returns to the panel with the answers kept', () => {
    draw(caseOf())
    toConfirm()
    fireEvent.click(screen.getByRole('button', { name: `${P}.back` }))
    expect((screen.getByLabelText(`${P}.whyLabel`) as HTMLTextAreaElement).value).toBe('Dummy note')
  })

  it('Yes, reject sends the reason and note and hands the case back', async () => {
    const next = caseOf({ status: 'rejected', pre_interview: undefined })
    mockApi.rejectBeforeInterview.mockResolvedValue(next)
    const onDone = draw(caseOf())
    toConfirm()
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(next))
    expect(mockApi.rejectBeforeInterview).toHaveBeenCalledWith(7, 'results_too_low', 'Dummy note', { token: 'tok' })
  })

  it.each([['has_reviewer'], ['bad_status'], ['comments_too_long']])('a %s refusal reads as words', async (code) => {
    mockApi.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code }))
    draw(caseOf())
    toConfirm()
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.${code}`)
    // A stale page (the stage or the reviewer moved) is reloaded; a note refusal is not.
    await waitFor(() => expect(onStale).toHaveBeenCalledTimes(code === 'comments_too_long' ? 0 : 1))
  })

  it('an unknown refusal reads as the generic words', async () => {
    mockApi.rejectBeforeInterview.mockRejectedValue(new Error('x'))
    draw(caseOf())
    toConfirm()
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.generic`)
  })
})

describe('the record', () => {
  const rejected = (over: Record<string, unknown> = {}) => caseOf({
    status: 'rejected', rejection_category: 'pre_interview', rejection_reason: 'not_b40', pre_interview: undefined, ...over,
  })

  it('shows nothing for any other decline', () => {
    render(<PreInterviewRecord app={rejected({ rejection_category: 'interview' })} t={t} />)
    expect(screen.queryByTestId('pre-interview-record')).toBeNull()
  })

  it('while held: the scheduled date, and no second Cancel decline (the header banner has the one)', () => {
    render(<PreInterviewRecord app={rejected({ decline_due_at: '2026-11-17T03:00:00Z', pending_rejection_category: 'pre_interview' })}
      t={t} />)
    const card = screen.getByTestId('pre-interview-record')
    expect(card.textContent).toContain('admin.scholarship.cooloff.declineScheduled')
    expect(card.textContent).toContain(`${P}.reasons.not_b40`)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('once sent: the sent date and no cancel', () => {
    render(<PreInterviewRecord app={rejected({ decline_email_sent_at: '2026-11-17T03:00:00Z' })} t={t} />)
    expect(screen.getByTestId('pre-interview-record').textContent).toContain(`${P}.sent`)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
