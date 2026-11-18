/**
 * @jest-environment jsdom
 *
 * Request #55 (2026-11-07), two-way since #73 (2026-11-16): "Org admin and reviewer notes", rendered.
 * Pinned: the org admin's face (list, box, live counter, append-only line, Add note), the reviewer's face
 * (Reply / Send reply), the reader's face (read-only list, or the empty line), each note's side ("Org
 * admin", "Reviewer", "(you)" on the caller's own only) and the reviewer's tint, the served reason the window
 * is shut ("not yet" before Awaiting review, "finished" after) for both writers, the box
 * following the SERVED `can_add` and `viewer`, the 2,000 limit, and a refusal worded by its code.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ReviewerNotesCard, looksEmpty, noteLength } from './ReviewerNotesCard'
import { addReviewerNote, getReviewerNotes, type ReviewerNotes } from '@/lib/admin-api'
import { NOTES_READ_EVENT } from '@/lib/useNewNoteCount'

jest.mock('@/lib/admin-api', () => ({ getReviewerNotes: jest.fn(), addReviewerNote: jest.fn() }))
const get = getReviewerNotes as jest.Mock
const add = addReviewerNote as jest.Mock

const t = ((k: string, vars?: Record<string, string>) =>
  (vars ? `${k}:${Object.values(vars).join('|')}` : k)) as never
const P = 'admin.scholarship.reviewerNotes'

const NOTE = { id: 1, body: 'Ask about the transport cost.', author_name: 'Org Admin One',
  author_role: 'org_admin' as const, is_you: false, created_at: '2026-11-05T10:42:00+08:00' }
const REPLY = { id: 2, body: 'The bus is RM90 a month.', author_name: 'Reviewer Two',
  author_role: 'reviewer' as const, is_you: false, created_at: '2026-11-06T09:00:00+08:00' }
const payload = (over: Partial<ReviewerNotes> = {}): ReviewerNotes => ({
  notes: [NOTE], viewer: 'org_admin', window_open: true, reason: null, can_add: true, max_length: 2000, ...over,
})

function mount() {
  return render(<ReviewerNotesCard appId={7} token="tok" t={t} refreshKey="interviewing" />)
}

beforeEach(() => { get.mockReset(); add.mockReset() })

describe('the org admin', () => {
  it('sees the notes, the box, the counter and the append-only line', async () => {
    get.mockResolvedValue(payload())
    mount()
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.getByText('Org Admin One')).toBeTruthy()
    expect(screen.getByText(`${P}.introOrgAdmin`)).toBeTruthy()
    expect(screen.getByLabelText(`${P}.addLabel`)).toBeTruthy()
    expect(screen.getByText(`${P}.appendOnly`)).toBeTruthy()
    expect(screen.getByText(`${P}.counter:0|2,000`)).toBeTruthy()
    expect((screen.getByRole('button', { name: `${P}.add` }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('counts as she types, and adds the note', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockResolvedValue(payload({ notes: [NOTE, { ...NOTE, id: 2, body: 'Second note' }] }))
    mount()
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
    mount()
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
    mount()
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'Late note' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.notes_closed:2,000`)
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))   // re-read: the window has closed
  })

  it('outside the window: the notes stay, the box goes, and the hint says why', async () => {
    get.mockResolvedValue(payload({ window_open: false, reason: 'finished', can_add: false }))
    mount()
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.queryByLabelText(`${P}.addLabel`)).toBeNull()
    expect(screen.getByText(`${P}.closedHint`)).toBeTruthy()
    expect(screen.queryByText(`${P}.notYetHint`)).toBeNull()
  })

  it('before Awaiting review (#73 review): the hint says "not yet", never "finished"', async () => {
    get.mockResolvedValue(payload({ notes: [], window_open: false, reason: 'not_yet', can_add: false }))
    mount()
    expect(await screen.findByText(`${P}.notYetHint`)).toBeTruthy()
    expect(screen.queryByText(`${P}.closedHint`)).toBeNull()
  })

  it('words a not-yet refusal by its code, and re-reads', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockRejectedValue(Object.assign(new Error('x'), { code: 'notes_not_yet' }))
    mount()
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'Early note' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.notes_not_yet:2,000`)
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
  })

  it('"Org admin (you)" on her own notes only', async () => {
    const mine = { ...NOTE, id: 3, is_you: true, body: 'Mine.' }
    get.mockResolvedValue(payload({ notes: [NOTE, mine] }))
    const { container } = mount()
    expect(await screen.findByText(mine.body)).toBeTruthy()
    const items = container.querySelectorAll('li[data-note-side]')
    expect(items[0].textContent).toContain(`${P}.role.org_admin`)
    expect(items[0].textContent).not.toContain('orgAdminYou')
    expect(items[1].textContent).toContain(`${P}.role.orgAdminYou`)
  })
})

describe('QC (a reader)', () => {
  it('reads the notes, with no box and no closed hint', async () => {
    get.mockResolvedValue(payload({ viewer: 'reader', can_add: false, window_open: false }))
    mount()
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.getByText(`${P}.introReader`)).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByText(`${P}.closedHint`)).toBeNull()
  })

  it('sees the empty line when there are none', async () => {
    get.mockResolvedValue(payload({ viewer: 'reader', notes: [], can_add: false }))
    mount()
    expect(await screen.findByText(`${P}.empty`)).toBeTruthy()
  })

  it('a writer with no notes and a shut window sees the neutral empty line and the hint', async () => {
    get.mockResolvedValue(payload({ notes: [], window_open: false, can_add: false }))
    mount()
    expect(await screen.findByText(`${P}.closedHint`)).toBeTruthy()
    expect(screen.getByText(`${P}.empty`)).toBeTruthy()
  })

  it('the box follows the server, not the role', async () => {
    get.mockResolvedValue(payload({ can_add: false }))
    mount()
    await screen.findByText(NOTE.body)
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})

describe('the assigned reviewer (#73)', () => {
  it('replies: "Reply" and "Send reply", and the reply is sent', async () => {
    get.mockResolvedValue(payload({ viewer: 'reviewer' }))
    add.mockResolvedValue(payload({ viewer: 'reviewer', notes: [NOTE, { ...REPLY, is_you: true }] }))
    mount()
    expect(await screen.findByText(`${P}.introReviewer`)).toBeTruthy()
    expect(screen.queryByLabelText(`${P}.addLabel`)).toBeNull()
    const box = screen.getByLabelText(`${P}.replyLabel`)
    expect(box.getAttribute('placeholder')).toBe(`${P}.replyPlaceholder`)
    expect(screen.getByText(`${P}.appendOnly`)).toBeTruthy()
    fireEvent.change(box, { target: { value: REPLY.body } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.sendReply` })) })
    expect(add).toHaveBeenCalledWith(7, REPLY.body, { token: 'tok' })
    expect(await screen.findByText(REPLY.body)).toBeTruthy()
    expect(screen.getByText(`${P}.role.reviewerYou`, { exact: false })).toBeTruthy()
  })

  it('once the review is finished: no box, and the closed hint', async () => {
    get.mockResolvedValue(payload({ viewer: 'reviewer', window_open: false, reason: 'finished', can_add: false }))
    mount()
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByText(`${P}.closedHint`)).toBeTruthy()
  })
})

describe('the conversation (#73)', () => {
  it('names each side and tints the reviewer, oldest first', async () => {
    get.mockResolvedValue(payload({ notes: [NOTE, REPLY] }))
    const { container } = mount()
    expect(await screen.findByText(REPLY.body)).toBeTruthy()
    const items = container.querySelectorAll('li[data-note-side]')
    expect(Array.from(items).map((li) => li.getAttribute('data-note-side'))).toEqual(['org_admin', 'reviewer'])
    expect(items[0].textContent).toContain(`${P}.role.org_admin`)
    expect(items[1].textContent).toContain(`${P}.role.reviewer`)
    expect(items[1].textContent).not.toContain('reviewerYou')
    expect(items[1].className).toContain('bg-primary-50')
    expect(items[0].className).not.toContain('bg-primary-50')
  })

  it('"Reviewer (you)" shows on the reviewer\'s own notes only, never on an earlier reviewer\'s', async () => {
    const earlier = { ...REPLY, id: 4, author_name: 'Earlier Reviewer', body: 'Earlier reviewer note.' }
    const mine = { ...REPLY, id: 5, is_you: true, body: 'My reply.' }
    get.mockResolvedValue(payload({ viewer: 'reviewer', notes: [NOTE, earlier, mine] }))
    const { container } = mount()
    expect(await screen.findByText(mine.body)).toBeTruthy()
    const items = Array.from(container.querySelectorAll('li[data-note-side]'))
    const you = items.filter((li) => li.textContent?.includes(`${P}.role.reviewerYou`))
    expect(you).toHaveLength(1)
    expect(you[0].textContent).toContain(mine.body)
    expect(items[1].textContent).toContain(`${P}.role.reviewer`)
    expect(items[0].textContent).not.toContain('You')
  })
})

it('counts characters as the server does (trimmed, code points)', () => {
  expect(noteLength('  ab  ')).toBe(2)
  expect(noteLength('தமிழ்')).toBe(5)
  expect(noteLength('😀')).toBe(1)
})

// ── The independent review of 2d1ae890 (R4, R6) ─────────────────────────────────────────────────
const ch = (...codes: number[]) => String.fromCharCode(...codes)

describe('the card trims and blanks invisible characters (R4; server parity is ReviewerNotesCardDrift.test.tsx)', () => {
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
    mount()
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: ch(0x3164, 0x2800) } })
    expect((screen.getByRole('button', { name: `${P}.add` }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('R6', () => {
  it('a refresh that fails after a first load says so, and keeps the notes on screen', async () => {
    get.mockResolvedValueOnce(payload({ can_add: false })).mockRejectedValueOnce(new Error('offline'))
    const view = render(<ReviewerNotesCard appId={7} token="tok" t={t} refreshKey="a" />)
    expect(await screen.findByText(NOTE.body)).toBeTruthy()
    view.rerender(<ReviewerNotesCard appId={7} token="tok" t={t} refreshKey="b" />)
    expect(await screen.findByText(`${P}.loadError`)).toBeTruthy()
    expect(screen.getByText(NOTE.body)).toBeTruthy()
  })

  it('keeps the spaces a note was written with', async () => {
    get.mockResolvedValue(payload({ can_add: false }))
    mount()
    expect((await screen.findByText(NOTE.body)).className).toContain('whitespace-pre-wrap')
  })

  it('words a bad_body refusal', async () => {
    get.mockResolvedValue(payload({ notes: [] }))
    add.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_body' }))
    mount()
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'x' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
    expect((await screen.findByRole('alert')).textContent).toBe(`${P}.error.bad_body:2,000`)
  })
})

/** #73 re-check M1: an answer for a case this card no longer shows never paints on the next one. */
describe('a late answer for the previous case', () => {
  const deferred = () => {
    let resolve: (v: ReviewerNotes) => void = () => {}
    const promise = new Promise<ReviewerNotes>((r) => { resolve = r })
    return { promise, resolve }
  }
  const B = { ...NOTE, id: 9, body: 'A note on the next student.' }
  const LATE = { ...NOTE, id: 3, body: 'Posted on the first student.' }

  it.each([
    ['keyed by the case, as the page mounts it', true],
    ['even without the key (the guard on its own)', false],
  ])('a POST answer after moving on is dropped: %s', async (_name, keyed) => {
    const late = deferred()
    get.mockImplementation((id: number) => Promise.resolve(payload({ notes: id === 8 ? [B] : [NOTE] })))
    add.mockReturnValue(late.promise)
    const card = (id: number) => <ReviewerNotesCard key={keyed ? id : 'one'} appId={id} token="tok" t={t}
      refreshKey="interviewing" />
    const { rerender } = render(card(7))
    fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'For the first' } })
    fireEvent.click(screen.getByRole('button', { name: `${P}.add` }))
    expect(add).toHaveBeenCalledWith(7, 'For the first', { token: 'tok' })

    rerender(card(8))
    expect(await screen.findByText(B.body)).toBeTruthy()
    await act(async () => { late.resolve(payload({ notes: [NOTE, LATE] })) })
    expect(screen.queryByText(LATE.body)).toBeNull()
    expect(screen.getByText(B.body)).toBeTruthy()
  })
})

/** #73 re-check M2: reading or adding clears the mark on the server, so the card tells the bell at once. */
describe('the bell is told', () => {
  it('after the notes are read, and again after a note is added; never after a failed read', async () => {
    const heard = jest.fn()
    window.addEventListener(NOTES_READ_EVENT, heard)
    try {
      get.mockResolvedValue(payload({ notes: [] }))
      add.mockResolvedValue(payload())
      mount()
      fireEvent.change(await screen.findByLabelText(`${P}.addLabel`), { target: { value: 'Hello' } })
      expect(heard).toHaveBeenCalledTimes(1)
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.add` })) })
      expect(heard).toHaveBeenCalledTimes(2)

      heard.mockClear()
      get.mockRejectedValue(new Error('down'))
      render(<ReviewerNotesCard appId={9} token="tok" t={t} refreshKey="x" />)
      await waitFor(() => expect(get).toHaveBeenCalledWith(9, { token: 'tok' }))
      await act(async () => { await Promise.resolve() })
      expect(heard).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener(NOTES_READ_EVENT, heard)
    }
  })
})
