/**
 * THE DRIFT TEST for `RESCHEDULE_MIN_LEAD_HOURS` in `lib/interviewSlots.ts` — named by its
 * `drift-test:` marker. The server's number is the rule (`apps/scholarship/constants.py`); the
 * picker's copy must say the same. When they disagreed (the server had no relaxed floor at all),
 * the picker offered same-day times the server refused, and the reviewer saw only
 * "Could not save" (2026-11-07).
 */
import { RESCHEDULE_MIN_LEAD_HOURS } from '@/lib/interviewSlots'
import { readApi } from '@/test/apiSource'

it('the picker\'s reschedule notice is the server\'s', () => {
  const m = readApi('apps/scholarship/constants.py').match(/^RESCHEDULE_MIN_LEAD_HOURS = (\d+)$/m)
  if (!m) throw new Error('drift test: RESCHEDULE_MIN_LEAD_HOURS is no longer an int literal in constants.py')
  expect(RESCHEDULE_MIN_LEAD_HOURS).toBe(Number(m[1]))
})

it('the server applies it on the propose door', () => {
  // A copy the server never reads would pass the line above and still refuse every reschedule.
  const view = readApi('apps/scholarship/views_admin/interview_slots.py')
  expect(view).toMatch(/meets_min_lead\(.*, reschedule=/)
  expect(readApi('apps/scholarship/scheduling.py')).toMatch(/hours = RESCHEDULE_MIN_LEAD_HOURS if reschedule else/)
})
