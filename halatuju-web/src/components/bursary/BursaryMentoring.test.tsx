/**
 * @jest-environment jsdom
 *
 * The student's Mentoring tab on My Bursary (student maintenance S7b; the MentoringStudent board). Pinned:
 *  * the mentor's name, area, languages (in the student's words), About, the Email button and "since";
 *  * the Call button ONLY when the mentor shares their phone (the server sends '' otherwise);
 *  * the meetings as date + how — never notes, a next step or minutes (the payload has none);
 *  * the no-mentor state, pointing to the organisation's own contact.
 */
import { render, screen } from '@testing-library/react'
import BursaryMentoring from './BursaryMentoring'
import * as api from '@/lib/api/bursaryMentoring'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/api/bursaryMentoring')
const mockApi = api as jest.Mocked<typeof api>
const P = 'bursaryTabs.mentoring'

const MENTOR: api.BursaryMentor = {
  name: 'Kavitha Raman', area: 'Accounting', languages: ['en', 'ta'], other_language: 'Mandarin',
  about: 'Chartered accountant.', email: 'kavitha@example.org', phone: '012-345 6789', since: '2026-09-02',
}

beforeEach(() => jest.clearAllMocks())

it('shows the mentor, the Email and Call buttons, and the meetings as date and how', async () => {
  mockApi.getBursaryMentoring.mockResolvedValue({ mentor: MENTOR, meetings: [
    { met_on: '2026-10-28', mode: 'video' }, { met_on: '2026-09-30', mode: 'in_person' }] })
  render(<BursaryMentoring token="tok" />)
  const card = await screen.findByTestId('student-mentor')
  expect(card.textContent).toContain('Kavitha Raman')
  expect(card.textContent).toContain(`Accounting · ${P}.lang.en, ${P}.lang.ta, Mandarin`)
  expect(card.textContent).toContain('Chartered accountant.')
  expect(screen.getByTestId('student-mentor-email').getAttribute('href')).toBe('mailto:kavitha@example.org')
  expect(screen.getByTestId('student-mentor-call').getAttribute('href')).toBe('tel:0123456789')
  expect(card.textContent).toContain(`${P}.since`)
  const meetings = screen.getByTestId('student-meetings')
  expect(meetings.textContent).toContain(`${P}.mode.video`)
  expect(meetings.textContent).toContain(`${P}.mode.in_person`)
  expect(mockApi.getBursaryMentoring).toHaveBeenCalledWith({ token: 'tok' })
  expect(screen.getByText(`${P}.contact`)).toBeTruthy()
  expect(screen.queryByRole('img')).toBeNull()                        // no photo, ever
})

it('offers no Call button when the mentor does not share their phone', async () => {
  mockApi.getBursaryMentoring.mockResolvedValue({ mentor: { ...MENTOR, phone: '' }, meetings: [] })
  render(<BursaryMentoring token="tok" />)
  await screen.findByTestId('student-mentor')
  expect(screen.queryByTestId('student-mentor-call')).toBeNull()
  expect(screen.getByText(`${P}.noMeetings`)).toBeTruthy()
})

it('says calmly when there is no mentor yet', async () => {
  mockApi.getBursaryMentoring.mockResolvedValue({ mentor: null, meetings: [] })
  render(<BursaryMentoring token="tok" />)
  expect((await screen.findByTestId('student-no-mentor')).textContent).toContain(`${P}.none.body`)
  expect(screen.queryByTestId('student-mentor')).toBeNull()
})

it('says so when it cannot load', async () => {
  mockApi.getBursaryMentoring.mockRejectedValue(new Error('x'))
  render(<BursaryMentoring token="tok" />)
  expect(await screen.findByText(`${P}.loadFailed`)).toBeTruthy()
})
