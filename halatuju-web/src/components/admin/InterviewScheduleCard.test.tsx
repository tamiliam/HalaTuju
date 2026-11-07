/**
 * @jest-environment jsdom
 *
 * The reviewer's reschedule, rendered (2026-11-07). An interviewer moved a booked 1:30 pm interview
 * to later the same day: the picker offered the times, the server refused them as `too_soon`, and
 * the card said only "Could not save. Please try again." Pinned here: the reschedule is sent AS a
 * reschedule (the server's short notice depends on it), and a `too_soon` refusal names the notice.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import InterviewScheduleCard from './InterviewScheduleCard'
import { proposeInterviewSlots, type InterviewSchedule } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t, locale: 'en' }) }))
jest.mock('@/lib/admin-api', () => ({ proposeInterviewSlots: jest.fn() }))
const propose = proposeInterviewSlots as jest.Mock

const P = 'admin.scholarship.interview.schedule'

function booked(): InterviewSchedule {
  return {
    enabled: true, status: 'booked', start: '2026-11-07T13:30:00+08:00',
    meeting_url: 'https://meet.example/abc', meeting_provider: 'google', booked_slot_id: 7,
    slots: [{ id: 7, start: '2026-11-07T13:30:00+08:00' } as InterviewSchedule['slots'][number]],
    reschedule_cutoff_hours: 12, slot_min_lead_hours: 24, reviewer_busy: [],
  }
}

// The day of the report, before the booked time — so the only times on offer are later TODAY.
beforeEach(() => {
  jest.useFakeTimers().setSystemTime(new Date(2026, 10, 7, 10, 57))
  propose.mockReset()
})
afterEach(() => { jest.useRealTimers() })

function rescheduleAndPickThree() {
  render(<InterviewScheduleCard appId={42} token="tok" schedule={booked()} onChange={jest.fn()} />)
  fireEvent.click(screen.getByText(`${P}.reschedule`))
  fireEvent.click(screen.getByText(`${P}.rescheduleYes`))
  for (let i = 0; i < 3; i++) {
    const free = screen.getAllByRole('button', { name: /\d:\d\d/ })
      .filter((b) => !(b as HTMLButtonElement).disabled && !b.className.includes('bg-brand-fill'))
    fireEvent.click(free[0])
  }
  fireEvent.click(screen.getByText(`${P}.propose`))
}

it('offers same-day times and sends them as a reschedule', () => {
  propose.mockResolvedValue(booked())
  rescheduleAndPickThree()
  expect(propose).toHaveBeenCalledTimes(1)
  const [appId, starts, opts] = propose.mock.calls[0]
  expect(appId).toBe(42)
  expect(starts).toHaveLength(3)
  for (const s of starts as string[]) expect(s.startsWith('2026-11-07T')).toBe(true)
  expect(opts).toMatchObject({ reschedule: true })
})

it('a too-soon refusal names the notice instead of "Could not save"', async () => {
  propose.mockRejectedValue(new Error('too_soon'))
  rescheduleAndPickThree()
  expect(await screen.findByText(`${P}.tooSoon:2`)).toBeTruthy()
  expect(screen.queryByText(`${P}.error`)).toBeNull()
})

it('any other refusal still reads as the general error', async () => {
  propose.mockRejectedValue(new Error('reviewer_conflict'))
  rescheduleAndPickThree()
  expect(await screen.findByText(`${P}.error`)).toBeTruthy()
})
