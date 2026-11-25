/**
 * @jest-environment jsdom
 *
 * First-load budget fix (25 Nov 2026): the interview scheduling card is fetched as its own chunk. Pinned
 * here: the lazy card still draws the real card once loaded, and the case page never imports the card
 * statically again (that put /admin/scholarship/[id] over its 250 kB ceiling and stopped the web build).
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { render, screen } from '@testing-library/react'
import { LazyInterviewScheduleCard } from './LazyInterviewSchedule'
import type { InterviewSchedule } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t, locale: 'en' }) }))
jest.mock('@/lib/admin-api', () => ({ proposeInterviewSlots: jest.fn() }))

const P = 'admin.scholarship.interview.schedule'

function booked(): InterviewSchedule {
  return {
    enabled: true, status: 'booked', start: '2026-11-07T13:30:00+08:00',
    meeting_url: 'https://meet.example/abc', meeting_provider: 'google', booked_slot_id: 7,
    slots: [{ id: 7, start: '2026-11-07T13:30:00+08:00' } as InterviewSchedule['slots'][number]],
    reschedule_cutoff_hours: 12, slot_min_lead_hours: 24, reviewer_busy: [],
  }
}

it('draws the real card once its chunk has loaded', async () => {
  render(<LazyInterviewScheduleCard appId={42} token="tok" schedule={booked()} onChange={jest.fn()} />)
  expect(await screen.findByText(`${P}.reschedule`)).toBeTruthy()
})

it('the case page reaches the card only through the lazy loader', () => {
  const src = readFileSync(join(__dirname, '..', 'view.tsx'), 'utf8')
  expect(src).not.toMatch(/import\s+InterviewScheduleCard\b/)
  expect(src).toContain('<LazyInterviewScheduleCard')
})
