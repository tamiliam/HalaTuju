/**
 * @jest-environment jsdom
 *
 * A MENTOR's own pages (student maintenance S7c; the MentorStudents, MentorStudentFile and MentorPhone
 * boards), rendered. Pinned:
 *  * My students: one card per current student — the result chip, what they asked for help with, since
 *    when and the meetings; the empty state names the organisation;
 *  * one student: contact, the latest result with its term, the team's meeting as date + how only and
 *    the mentor's own in full; a student who is no longer theirs reads "not one of your current students";
 *  * Log a meeting opens the shared Sheet: pill buttons for how, the worried Toggle, the date sent as ISO
 *    from a day-first box, the concern sent only when switched on.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import MyStudents, { programmeInUrl } from './MyStudents'
import MyStudentFile from './MyStudentFile'
import * as api from '@/lib/admin-api'
import * as desk from '@/lib/admin-api/mentorDesk'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'mentor' } }) }))
jest.mock('@/lib/admin-api')
jest.mock('@/lib/admin-api/mentorDesk')
const mockApi = api as jest.Mocked<typeof api>
const mockDesk = desk as jest.Mocked<typeof desk>
const K = 'admin.myStudents'

const CARD: api.MyStudentCard = {
  id: 104, name: 'Nur Aisyah binti Rahman', course: 'Diploma in Accounting', institution: 'Politeknik Ungku Omar',
  email: 'aisyah@example.test', phone: '017-222 3344', since: '2026-09-02', meetings: 3, last_meeting: '2026-10-28',
  latest_result: { cgpa: '3.21', semester: 'Semester 1, 2026' }, standing: 'performing',
  asked_for_help: { university: true, scholarship: false, flagged: false },
}
const PAGE: api.MyStudent = {
  id: 104, name: CARD.name, course: CARD.course, institution: CARD.institution, email: CARD.email,
  phone: CARD.phone, since: CARD.since, asked_for_help: CARD.asked_for_help, latest_result: CARD.latest_result,
  standing: 'performing', organisation: 'BrightPath',
  meetings: [
    { id: 7, met_on: '2026-10-28', mode: 'video', by_you: true, minutes: 45, notes: 'Semester 1 results discussed.',
      next_step: 'Weekly study group', concern: true },
    { id: 6, met_on: '2026-09-30', mode: 'in_person', by_you: false },
  ],
}

beforeEach(() => jest.clearAllMocks())

describe('My students', () => {
  it('draws one card per current student', async () => {
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [CARD] })
    render(<MyStudents />)
    const card = await screen.findByTestId('my-student-104')
    expect(card.textContent).toContain('Nur Aisyah binti Rahman')
    expect(card.textContent).toContain('Diploma in Accounting · Politeknik Ungku Omar')
    expect(within(card).getByTestId('my-student-result').textContent)
      .toBe(`${K}.cgpa|{"cgpa":"3.21"} · admin.scholars.standing.performing`)
    expect(card.textContent).toContain('admin.scholars.mentoring.help.chip')
    expect(card.textContent).toContain(`${K}.meetings|{"count":"3"}`)
    expect(within(card).getAllByRole('link', { name: CARD.name })[0].getAttribute('href')).toBe('/admin/my-students/104')
    expect(within(card).getByText(`${K}.call`).getAttribute('href')).toBe('tel:0172223344')
    expect(screen.getByText(`${K}.subtitle|{"org":"BrightPath"}`)).toBeTruthy()
  })

  it('no result yet, and the empty state', async () => {
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [
      { ...CARD, latest_result: null, standing: 'no_result_yet', meetings: 0, last_meeting: null }] })
    const { unmount } = render(<MyStudents />)
    const card = await screen.findByTestId('my-student-104')
    expect(within(card).getByTestId('my-student-result').textContent).toBe('admin.scholars.standing.no_result_yet')
    expect(card.textContent).toContain(`${K}.noMeetings`)
    unmount()
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [] })
    render(<MyStudents />)
    expect((await screen.findByTestId('my-students-empty')).textContent).toContain(`${K}.emptyBody|{"org":"BrightPath"}`)
  })

  it('Log a meeting opens the Sheet and sends the meeting; the concern only when switched on', async () => {
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [CARD] })
    mockApi.logMyMeeting.mockResolvedValue(PAGE)
    render(<MyStudents />)
    fireEvent.click(await screen.findByTestId('log-meeting-104'))
    const sheet = await screen.findByRole('dialog')
    fireEvent.change(within(sheet).getByTestId('log-meeting-date'), { target: { value: '30-10-2026' } })
    fireEvent.click(within(sheet).getByTestId('log-meeting-mode-in_person'))
    expect(within(sheet).getByTestId('log-meeting-mode-in_person').getAttribute('aria-pressed')).toBe('true')
    fireEvent.change(within(sheet).getByTestId('log-meeting-minutes'), { target: { value: '45' } })
    fireEvent.change(within(sheet).getByTestId('log-meeting-notes'), { target: { value: '  Went well.  ' } })
    // The worried Toggle is the site Toggle (a switch), never a tick box.
    const worried = within(within(sheet).getByTestId('log-meeting-worried')).getByRole('switch')
    expect(within(sheet).queryByRole('checkbox')).toBeNull()
    fireEvent.click(worried)
    fireEvent.click(within(sheet).getByTestId('log-meeting-save'))
    await waitFor(() => expect(mockApi.logMyMeeting).toHaveBeenCalledWith(104, {
      met_on: '2026-10-30', mode: 'in_person', minutes: 45, notes: 'Went well.', next_step: '', concern: true,
    }, { token: 'tok' }))
    expect(await screen.findByText(`${K}.savedConcern`)).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Save waits for notes, and a refusal is worded', async () => {
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [CARD] })
    mockApi.logMyMeeting.mockRejectedValue(Object.assign(new Error('x'), { status: 400, code: 'future_date' }))
    render(<MyStudents />)
    fireEvent.click(await screen.findByTestId('log-meeting-104'))
    const sheet = await screen.findByRole('dialog')
    const save = within(sheet).getByTestId('log-meeting-save') as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.change(within(sheet).getByTestId('log-meeting-notes'), { target: { value: 'Went well.' } })
    expect(save.disabled).toBe(false)
    fireEvent.click(save)
    expect(await within(sheet).findByText('admin.scholars.mentoring.error.future_date')).toBeTruthy()
    expect(mockApi.logMyMeeting.mock.calls[0][1].concern).toBe(false)
  })
})

// T5c P5: a mentor's Programmes card opens `/admin/my-students?programme=<id>`, narrowed to that gift.
describe('My students, narrowed to one programme', () => {
  afterEach(() => window.history.replaceState(null, '', '/'))

  it('reads a positive whole-number programme id from the URL, and nothing else', () => {
    expect(programmeInUrl('?programme=12')).toBe(12)
    expect(programmeInUrl('?programme= 12 ')).toBe(12)
    expect(programmeInUrl('')).toBeUndefined()
    expect(programmeInUrl('?programme=0')).toBeUndefined()
    expect(programmeInUrl('?programme=-3')).toBeUndefined()
    expect(programmeInUrl('?programme=b40')).toBeUndefined()
    expect(programmeInUrl('?programme=1.5')).toBeUndefined()
  })

  it('asks the server for that programme only', async () => {
    window.history.replaceState(null, '', '/admin/my-students?programme=12')
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [CARD] })
    render(<MyStudents />)
    await screen.findByTestId('my-student-104')
    expect(mockApi.getMyStudents).toHaveBeenCalledWith({ token: 'tok' }, 12)
  })

  it('asks for every student when the URL names no programme', async () => {
    mockApi.getMyStudents.mockResolvedValue({ organisation: 'BrightPath', students: [CARD] })
    render(<MyStudents />)
    await screen.findByTestId('my-student-104')
    expect(mockApi.getMyStudents).toHaveBeenCalledWith({ token: 'tok' }, undefined)
  })
})

describe('One student', () => {
  it("the team's meeting is date + how only; the mentor's own is in full", async () => {
    mockApi.getMyStudent.mockResolvedValue(PAGE)
    render(<MyStudentFile id={104} />)
    await screen.findByTestId('my-student-file')
    expect(screen.getByTestId('my-student-contact').textContent).toBe('aisyah@example.test · 017-222 3344')
    expect(screen.getByText(`${K}.term|{"term":"Semester 1, 2026","org":"BrightPath"}`)).toBeTruthy()
    const mine = screen.getByTestId('my-meeting-7')
    expect(mine.textContent).toContain('Semester 1 results discussed.')
    expect(mine.textContent).toContain(`${K}.byYou`)
    expect(mine.textContent).toContain(`${K}.toldTeam`)
    const theirs = screen.getByTestId('my-meeting-6')
    expect(theirs.textContent).toContain(`${K}.byTeam|{"org":"BrightPath"}`)
    expect(theirs.textContent).not.toContain('minutesShort')
  })

  it('S10: their development modules show read-only, with the reflection, Late and the file link', async () => {
    mockApi.getMyStudent.mockResolvedValue({ ...PAGE, modules: [{ id: 3, title: 'Managing your money',
      status: 'published', due_on: '2026-11-30', task_kind: 'reflection', lessons: 3, read: 3, done: true,
      late: false, task_sent_at: '2026-11-12T00:00:00Z', task_text: 'Cook three days a week.',
      task_file: { name: 'cv.pdf', type: 'application/pdf' },
      reviewed_at: null, review_comment: '' }] })
    mockDesk.myStudentTaskFile.mockResolvedValue({ url: 'https://storage.test/signed', expires_in: 300 })
    const tab = { location: { href: '' }, close: jest.fn() }
    const open = jest.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    render(<MyStudentFile id={104} />)
    const growth = await screen.findByTestId('my-student-growth')
    expect(growth.textContent).toContain('Cook three days a week.')
    expect(growth.textContent).toContain('admin.scholars.growth.done')
    fireEvent.click(screen.getByTestId('growth-file-3'))   // signed on the tap, never from the payload
    await waitFor(() => expect(tab.location.href).toBe('https://storage.test/signed'))
    expect(mockDesk.myStudentTaskFile).toHaveBeenCalledWith(104, 3, { token: 'tok' })
    open.mockRestore()
  })

  it('S10: no modules, no Growth section', async () => {
    mockApi.getMyStudent.mockResolvedValue(PAGE)
    render(<MyStudentFile id={104} />)
    await screen.findByTestId('my-student-file')
    expect(screen.queryByTestId('my-student-growth')).toBeNull()
  })

  it('a student who is no longer theirs reads as such, never as an error', async () => {
    mockApi.getMyStudent.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }))
    render(<MyStudentFile id={104} />)
    expect((await screen.findByTestId('my-student-gone')).textContent).toBe(`${K}.notYours`)
  })
})
