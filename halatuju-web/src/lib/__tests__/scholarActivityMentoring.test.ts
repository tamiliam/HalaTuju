/**
 * Student maintenance S7b: the four mentoring lines on a scholar's activity timeline read as the
 * MentoringTouches board does — the mentor's name as it was at the time, "was" on a change, why it
 * ended, and the meeting's mode and minutes. Never raw JSON, never a staff-only reason.
 */
import { activityText } from '@/lib/scholarActivity'
import type { ScholarActivity } from '@/lib/admin-api'

const t = (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k)
const row = (event: string, meta: Record<string, unknown>): ScholarActivity => ({
  id: 1, kind: 'system', event, body: '', meta, actor_email: 'siti@example.org', internal: false,
  created_at: '2026-10-28T00:00:00Z',
})

it('reads assigned, changed, ended (each cause) and a logged meeting', () => {
  expect(activityText(row('mentor_assigned', { mentor: 'Kavitha Raman' }), t))
    .toBe('admin.scholars.event.mentor_assigned|{"mentor":"Kavitha Raman"}')
  expect(activityText(row('mentor_changed', { mentor: 'Kavitha Raman', was: 'Faizal Hamid' }), t))
    .toBe('admin.scholars.event.mentor_changed|{"mentor":"Kavitha Raman","was":"Faizal Hamid"}')
  for (const cause of ['staff', 'mentor_deactivated', 'file_closed']) {
    expect(activityText(row('mentor_ended', { mentor: 'K', cause }), t))
      .toBe(`admin.scholars.event.mentor_ended.${cause}|{"mentor":"K"}`)
  }
  expect(activityText(row('mentor_ended', { mentor: 'K', cause: 'nonsense' }), t))
    .toBe('admin.scholars.event.mentor_ended.staff|{"mentor":"K"}')
  expect(activityText(row('session_logged', { mode: 'video', minutes: 45 }), t))
    .toBe('admin.scholars.event.session_logged|{"mode":"admin.scholars.mentoring.mode.video","minutes":"45"}')
  expect(activityText(row('session_logged', { mode: 'phone', minutes: null }), t))
    .toBe('admin.scholars.event.session_logged_no_minutes|{"mode":"admin.scholars.mentoring.mode.phone","minutes":""}')
})
