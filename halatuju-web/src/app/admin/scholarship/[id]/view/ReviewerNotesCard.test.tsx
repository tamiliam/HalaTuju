/**
 * @jest-environment jsdom
 *
 * Request #55 (2026-11-07): "Notes for the reviewer", rendered. Pinned: the org admin's face (list,
 * box, live counter, append-only line, Add note), the reader's face (read-only list, or the empty
 * line), the box following the SERVED `can_add` and never the role, the 2,000 limit, and a refusal
 * worded by its code.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ReviewerNotesCard, noteLength } from './ReviewerNotesCard'
import { addReviewerNote, getReviewerNotes, type ReviewerNotes } from '@/lib/admin-api'

jest.mock('@/lib/admin-api', () => ({ getReviewerNotes: jest.fn(), addReviewerNote: jest.fn() }))
const get = getReviewerNotes as jest.Mock
const add = addReviewerNote as jest.Mock

const t = ((k: string, vars?: Record<string, string>) =>
  (vars ? `${k}:${Object.values(vars).join('|')}` : k)) as never
const P = 'admin.scholarship.reviewerNotes'

const NOTE = { id: 1, body: 'Ask about the transport cost.', author_name: 'Org Admin One',
  created_at: '2026-11-05T10:42:00+08:00' }
const payload = (over: Partial<ReviewerNotes> = {}): ReviewerNotes => ({
  notes: [NOTE], window_open: true, can_add: true, max_length: 2000, ...over,
})

function mount(isWriter: boolean) {
  return render(<ReviewerNotesCard appId={7} token="tok" t={t} isWriter={isWriter} refreshKey="interviewing" />)
}

beforeEach(() => { get.mockReset(); add.mockReset() })

describe('the org admin', () => {
  it('sees the notes, the box, the counter and the append-only line', async () => {
    get.mockResolvedValue(payload())
    mount(true)
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.getByText('Org Admin One')).toBeTruthy()
    expect(screen.getByText(`${P}.introWriter`)).toBeTruthy()
    expect(screen.getByLabelText(`${P}.addLabel`)).toBeTruthy()
    expect(screen.getByText(`${P}.appendOnly`)).toBeTruthy()
    expect(screen.getByText(`${P}.counter:0|2,000`)).toBeTruthy()
    expect((screen.getByRole('button', { name: `${P}.add` }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('counts as she types, and adds the note', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockResolvedValue(payload({ notes: [NOTE, { ...NOTE, id: 2, body: 'Second note' }] }))
    mount(true)
    const box = await screen.findByLabelText(`${P}.addLabel`)
    fireEvent.change(box, { target: { value: 'Second note' } })
    expect(screen.getByText(`${P}.counter:11|2,000`)).toBeTruthy()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect(add).toHaveBeenCalledWith(7, 'Second note', { token: 'tok' })
    expect(await screen.findByText('Second note')).toBeTruthy()
    expect((box as HTMLTextAreaElement).value).toBe('')
  })

  it('will not send more than 2,000 characters, or only spaces', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    mount(true)
    const box = await screen.findByLabelText(`${P}.addLabel`)
    const button = () => screen.getByRole('button', { name: `${P}.add` }) as HTMLButtonElement
    fireEvent.change(box, { target: { value: '   ' } })
    expect(button().disabled).toBe(true)
    fireEvent.change(box, { target: { value: 'x'.repeat(2001) } })
    expect(screen.getByText(`${P}.counter:2,001|2,000`)).toBeTruthy()
    expect(button().disabled).toBe(true)
    fireEvent.change(box, { target: { value: 'x'.repeat(2000) } })
    expect(button().disabled).toBe(false)
  })

  it('words a refusal by its code', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockRejectedValue(Object.assign(new Error('x'), { code: 'notes_closed' }))
    mount(true)
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'Late note' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.notes_closed:2,000`)
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))   // re-read: the window has closed
  })

  it('outside the window: the notes stay, the box goes, and the hint says why', async () => {
    get.mockResolvedValue(payload({ window_open: false, can_add: false }))
    mount(true)
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.queryByLabelText(`${P}.addLabel`)).toBeNull()
    expect(screen.getByText(`${P}.closedHint`)).toBeTruthy()
  })
})

describe('the reviewer or QC', () => {
  it('reads the notes, with no box', async () => {
    get.mockResolvedValue(payload({ can_add: false }))
    mount(false)
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.getByText(`${P}.introReader`)).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('sees the empty line when there are none', async () => {
    get.mockResolvedValue(payload({ notes: [], can_add: false }))
    mount(false)
    expect(await screen.findByText(`${P}.empty`)).toBeTruthy()
  })

  it('the org admin is never told "no notes from your org admin"', async () => {
    get.mockResolvedValue(payload({ notes: [], window_open: false, can_add: false }))
    mount(true)
    expect(await screen.findByText(`${P}.closedHint`)).toBeTruthy()
    expect(screen.queryByText(`${P}.empty`)).toBeNull()
  })

  it('the box follows the server, not the role', async () => {
    get.mockResolvedValue(payload({ can_add: false }))
    mount(true)
    await screen.findByText(NOTE.body)
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})

it('counts characters as the server does (trimmed, code points)', () => {
  expect(noteLength('  ab  ')).toBe(2)
  expect(noteLength('தமிழ்')).toBe(5)
  expect(noteLength('😀')).toBe(1)
})
