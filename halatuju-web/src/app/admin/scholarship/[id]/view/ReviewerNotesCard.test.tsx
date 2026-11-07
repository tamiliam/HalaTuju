/**
 * @jest-environment jsdom
 *
 * Request #55 (2026-11-07): "Notes for the reviewer", rendered. Pinned: the org admin's face (list,
 * box, live counter, append-only line, Add note), the reader's face (read-only list, or the empty
 * line), the box following the SERVED `can_add` and never the role, the 2,000 limit, and a refusal
 * worded by its code.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { INVISIBLE, ReviewerNotesCard, looksEmpty, noteLength } from './ReviewerNotesCard'
import { readApi } from '@/test/apiSource'
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

// ── The independent review of 2d1ae890 (R4, R6) ─────────────────────────────────────────────────
const ch = (...codes: number[]) => String.fromCharCode(...codes)

describe('DRIFT: the card trims and blanks exactly as the server does (R4)', () => {
  it('the invisible character class is the same source, character for character', () => {
    const src = readApi('apps/scholarship/reviewer_notes.py')
    const m = src.match(/_INVISIBLE = re\.compile\(r'([^']*)'\)/)
    if (!m) throw new Error('drift test: no _INVISIBLE = re.compile(r...) in reviewer_notes.py — follow it.')
    expect(m[1].length).toBeGreaterThan(40)
    expect(INVISIBLE.source).toBe(m[1])
  })

  it('a note of invisible characters only looks empty', () => {
    for (const code of [0xad, 0x2800, 0x3164, 0x115f, 0x1160, 0x180e, 0x200b, 0x200e, 0x2060, 0xfeff, 0xffa0]) {
      expect(looksEmpty(` ${ch(code, code)} `)).toBe(true)
    }
    expect(looksEmpty('a')).toBe(false)
  })

  it('a BOM and a wide space at the ends do not count against the 2,000', () => {
    expect(noteLength(ch(0xfeff) + 'a'.repeat(2000) + ch(0x200b, 0x3000))).toBe(2000)
  })

  it('the button stays off for a note of invisible characters', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    mount(true)
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: ch(0x3164, 0x2800) } })
    expect((screen.getByRole('button', { name: `${P}.add` }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('R6', () => {
  it('a refresh that fails after a first load says so, and keeps the notes on screen', async () => {
    get.mockResolvedValueOnce(payload({ can_add: false })).mockRejectedValueOnce(new Error('offline'))
    const view = render(<ReviewerNotesCard appId={7} token="tok" t={t} isWriter={false} refreshKey="a" />)
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    view.rerender(<ReviewerNotesCard appId={7} token="tok" t={t} isWriter={false} refreshKey="b" />)
    expect(await screen.findByText(`${P}.loadError`)).toBeTruthy()
    expect(screen.getByText(NOTE.body)).toBeTruthy()
  })

  it('keeps the spaces a note was written with', async () => {
    get.mockResolvedValue(payload({ can_add: false }))
    mount(false)
    expect((await screen.findByText(NOTE.body)).className).toContain('whitespace-pre-wrap')
  })

  it('words a bad_body refusal', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_body' }))
    mount(true)
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'x' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.bad_body:2,000`)
  })
})
