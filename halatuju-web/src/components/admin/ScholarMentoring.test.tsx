/**
 * @jest-environment jsdom
 *
 * A scholar's Mentoring tab (student maintenance S7b; the MentoringTab board), rendered. Pinned:
 *  * the current mentor (staff see the phone), Change / End, meetings with their STAFF-ONLY notes and
 *    next step, the earlier mentor with its staff-only reason;
 *  * the change form: the picker (an invited mentor is offered and says so), the reason, and the
 *    "Email the student" Toggle ONLY when the organisation sends that email — on by default;
 *  * Log a meeting sends the date as ISO from a day-first box;
 *  * the no-mentor state with what the scholar asked for and "Assign a mentor";
 *  * `can_act` false (a closed file): the same read, no buttons.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ScholarMentoring from './ScholarMentoring'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.scholars.mentoring'

const STAFF = { email: 'siti@example.org', name: 'Siti', role: 'org_admin' }
const WITH: api.ScholarMentoring = {
  current: {
    id: 9, mentor_id: 1, name: 'Kavitha Raman', email: 'kavitha@example.org', phone: '012-345 6789',
    area: 'Accounting', languages: ['en', 'ms', 'ta'], other_language: '', status: 'active',
    since: '2026-09-02T00:00:00Z', assigned_by: STAFF, meetings: 1, last_meeting: '2026-10-28', emailed: true,
  },
  history: [{ id: 8, mentor_id: 2, name: 'Faizal Hamid', started_at: '2026-07-15T00:00:00Z',
    ended_at: '2026-09-01T00:00:00Z', end_reason: 'Changed course', ended_by: STAFF, meetings: 1 }],
  meetings: [{ id: 5, met_on: '2026-10-28', mode: 'video', minutes: 45, notes: 'Semester 1 results discussed.',
    next_step: 'Weekly study group', mentor_name: 'Kavitha Raman', logged_by: STAFF, created_at: '2026-10-28T00:00:00Z' }],
  asked_for_help: { university: true, scholarship: false, flagged: false },
  assignable: [
    { id: 2, name: 'Faizal Hamid', area: 'Engineering', languages: ['en', 'ms'], other_language: '', status: 'active',
      scholars_now: 3 },
    { id: 3, name: 'Priya Devi', area: '', languages: [], other_language: '', status: 'invited', scholars_now: 0 },
  ],
  can_act: true, file_closed: false, email_switch_on: true,
}
const NONE: api.ScholarMentoring = { ...WITH, current: null, history: [], meetings: [] }

beforeEach(() => jest.clearAllMocks())

it('shows the current mentor with the phone, the meetings with staff-only notes, and the earlier mentor', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(WITH)
  render(<ScholarMentoring id={104} token="tok" />)
  const cur = await screen.findByTestId('mentoring-current')
  expect(cur.textContent).toContain('Kavitha Raman')
  expect(cur.textContent).toContain('kavitha@example.org · 012-345 6789')
  expect(screen.getByTestId('mentoring-emailed')).toBeTruthy()
  const meeting = screen.getByTestId('mentoring-meeting-5')
  expect(meeting.textContent).toContain('Semester 1 results discussed.')
  expect(meeting.textContent).toContain(`${K}.meetings.nextStepLine`)
  const past = screen.getByTestId('mentoring-past-8')
  expect(past.textContent).toContain('Faizal Hamid')
  expect(past.textContent).toContain('Changed course')
  expect(within(cur).getByText(`${K}.change`)).toBeTruthy()
  expect(within(cur).getByText(`${K}.end.open`)).toBeTruthy()
})

it('changes the mentor: picker, reason, and the email Toggle on by default', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(WITH)
  mockApi.assignMentor.mockResolvedValue({ ...WITH, emailed: true })
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.change`))
  const form = screen.getByTestId('mentoring-assign-form')
  const picker = within(form).getByTestId('mentoring-picker') as HTMLSelectElement
  // The current mentor is not offered; an invited one is, and says so.
  expect(Array.from(picker.options).map((o) => o.value)).toEqual(['2', '3'])
  expect(picker.options[1].textContent).toContain(`${K}.form.invitedOption`)
  const toggle = within(form).getByRole('switch')
  expect(toggle.getAttribute('aria-checked')).toBe('true')
  fireEvent.change(within(form).getByPlaceholderText(`${K}.form.reasonPlaceholder`), { target: { value: 'Changed course' } })
  fireEvent.click(within(form).getByText(`${K}.form.assign`))
  await waitFor(() => expect(mockApi.assignMentor).toHaveBeenCalledWith(
    104, { mentor_id: 2, reason: 'Changed course', email_student: true }, { token: 'tok' }))
  expect(await screen.findByRole('status')).toBeTruthy()
})

it('staff may switch the email off for this one assignment', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(NONE)
  mockApi.assignMentor.mockResolvedValue(WITH)
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.none.assign`))
  fireEvent.click(screen.getByRole('switch'))
  fireEvent.click(screen.getByText(`${K}.form.assign`))
  await waitFor(() => expect(mockApi.assignMentor).toHaveBeenCalledWith(
    104, { mentor_id: 2, reason: '', email_student: false }, { token: 'tok' }))
})

it('offers no email option when the organisation has switched the email off', async () => {
  mockApi.getScholarMentoring.mockResolvedValue({ ...NONE, email_switch_on: false })
  mockApi.assignMentor.mockResolvedValue(WITH)
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.none.assign`))
  expect(screen.queryByTestId('mentoring-email-option')).toBeNull()
  fireEvent.click(screen.getByText(`${K}.form.assign`))
  await waitFor(() => expect(mockApi.assignMentor).toHaveBeenCalledWith(
    104, { mentor_id: 2, reason: '', email_student: false }, { token: 'tok' }))
})

it('logs a meeting, sending the day-first date as ISO', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(WITH)
  mockApi.logMentoringMeeting.mockResolvedValue(WITH)
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.meetings.log`))
  const form = screen.getByTestId('mentoring-meeting-form')
  fireEvent.change(within(form).getByPlaceholderText('DD-MM-YYYY'), { target: { value: '28-10-2026' } })
  fireEvent.change(within(form).getByRole('combobox'), { target: { value: 'phone' } })
  fireEvent.change(within(form).getByLabelText(`${K}.meetings.notes`), { target: { value: 'Budgeting.' } })
  fireEvent.submit(form)
  await waitFor(() => expect(mockApi.logMentoringMeeting).toHaveBeenCalledWith(104,
    { met_on: '2026-10-28', mode: 'phone', minutes: null, notes: 'Budgeting.', next_step: '' }, { token: 'tok' }))
})

it('shows the server refusal in its own words', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(NONE)
  mockApi.assignMentor.mockRejectedValue(Object.assign(new Error('x'), { code: 'own_application' }))
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.none.assign`))
  fireEvent.click(screen.getByText(`${K}.form.assign`))
  expect((await screen.findByRole('alert')).textContent).toBe(`${K}.error.own_application`)
})

// Invitations I4 (2026-11-08): a gift limits who a mentor mentors. The SERVER filters the picker
// (`assignable` holds only mentors whose gifts hold this scholar's) and refuses an assign outside them.
it('I4: the picker offers exactly the mentors the server served for this gift', async () => {
  mockApi.getScholarMentoring.mockResolvedValue({ ...NONE, assignable: [WITH.assignable[1]] })
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.none.assign`))
  const picker = screen.getByTestId('mentoring-picker') as HTMLSelectElement
  expect(Array.from(picker.options).map((o) => o.value)).toEqual(['3'])
  expect(picker.textContent).not.toContain('Faizal Hamid')
})

it('I4: an assign refused outside the mentor\'s gifts reads in its own words', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(NONE)
  mockApi.assignMentor.mockRejectedValue(Object.assign(new Error('x'), { code: 'mentor_not_in_gift' }))
  render(<ScholarMentoring id={104} token="tok" />)
  fireEvent.click(await screen.findByText(`${K}.none.assign`))
  fireEvent.click(screen.getByText(`${K}.form.assign`))
  expect((await screen.findByRole('alert')).textContent).toBe(`${K}.error.mentor_not_in_gift`)
})

it('no mentor: what the scholar asked for, and Assign a mentor', async () => {
  mockApi.getScholarMentoring.mockResolvedValue(NONE)
  render(<ScholarMentoring id={104} token="tok" />)
  const none = await screen.findByTestId('mentoring-none')
  expect(none.textContent).toContain(`${K}.help.asked`)
  expect(within(none).getByText(`${K}.none.assign`)).toBeTruthy()
  expect(screen.queryByText(`${K}.meetings.log`)).toBeNull()        // no mentor, nothing to log
})

it('a closed file (can_act false) reads the same with no buttons', async () => {
  mockApi.getScholarMentoring.mockResolvedValue({ ...WITH, can_act: false, file_closed: true, assignable: [] })
  render(<ScholarMentoring id={104} token="tok" />)
  expect(await screen.findByTestId('mentoring-read-only')).toBeTruthy()
  expect(screen.getByTestId('mentoring-current').textContent).toContain('Kavitha Raman')
  for (const k of [`${K}.change`, `${K}.end.open`, `${K}.meetings.log`]) expect(screen.queryByText(k)).toBeNull()
})

it('review fix: a current mentor who turns out to be the student is flagged for staff to end', async () => {
  mockApi.getScholarMentoring.mockResolvedValue({ ...WITH, current: { ...WITH.current!, is_the_student: true } })
  render(<ScholarMentoring id={104} token="tok" />)
  expect((await screen.findByTestId('mentoring-is-student')).textContent).toBe(`${K}.current.isStudent`)
  expect(within(screen.getByTestId('mentoring-current')).getByText(`${K}.end.open`)).toBeTruthy()
})

describe('S7c: meetings the mentor logged, and the concern', () => {
  const MENTOR_MEETING = { ...WITH.meetings[0], id: 6, notes: 'Worried about Financial Accounting.',
    logged_by: { email: 'kavitha@example.org', name: 'Kavitha Raman', role: 'mentor' },
    logged_by_mentor: true, concern: true, concern_handled_at: null, concern_handled_by: null }
  const CONCERNED: api.ScholarMentoring = {
    ...WITH, meetings: [MENTOR_MEETING, WITH.meetings[0]], concern: { count: 1, raised_at: '2026-10-30T00:00:00Z' },
  }

  it('reads "logged by <name> (mentor)", shows the chip on that meeting and at the top', async () => {
    mockApi.getScholarMentoring.mockResolvedValue(CONCERNED)
    render(<ScholarMentoring id={104} token="tok" />)
    const top = await screen.findByTestId('mentoring-concern')
    expect(within(top).getByTestId('mentor-concerned-chip')).toBeTruthy()
    expect(top.textContent).toContain(`${K}.concern.open`)
    const meeting = screen.getByTestId('mentoring-meeting-6')
    expect(meeting.textContent).toContain(`${K}.meetings.withByMentor|{"mentor":"Kavitha Raman"}`)
    expect(within(meeting).getByTestId('mentor-concerned-chip')).toBeTruthy()
    // The staff-logged one keeps its own line.
    expect(screen.getByTestId('mentoring-meeting-5').textContent).toContain(`${K}.meetings.withBy|`)
  })

  it('"Mark as handled" asks the server and the chip goes', async () => {
    mockApi.getScholarMentoring.mockResolvedValue(CONCERNED)
    mockApi.handleMentorConcern.mockResolvedValue({
      ...CONCERNED, concern: null,
      meetings: [{ ...MENTOR_MEETING, concern_handled_at: '2026-10-31T00:00:00Z', concern_handled_by: STAFF },
        WITH.meetings[0]],
    })
    render(<ScholarMentoring id={104} token="tok" />)
    fireEvent.click(await screen.findByTestId('mentoring-handle-concern'))
    await waitFor(() => expect(mockApi.handleMentorConcern).toHaveBeenCalledWith(104, { token: 'tok' }))
    await waitFor(() => expect(screen.queryByTestId('mentoring-concern')).toBeNull())
    expect(screen.getByTestId('mentoring-meeting-concern-6').textContent).toContain(`${K}.concern.handled`)
    expect(screen.queryByTestId('mentor-concerned-chip')).toBeNull()
  })

  it('a closed file shows the concern with no button', async () => {
    mockApi.getScholarMentoring.mockResolvedValue({ ...CONCERNED, can_act: false, file_closed: true })
    render(<ScholarMentoring id={104} token="tok" />)
    await screen.findByTestId('mentoring-concern')
    expect(screen.queryByTestId('mentoring-handle-concern')).toBeNull()
  })
})
