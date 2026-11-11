/** TD-342: the pending sign-in intent goes stale, so an abandoned Google sign-in cannot resume later. */
import { isStalePendingAction, PENDING_AUTH_TTL_MS } from '../storage'

it('fresh, stale, and unstamped (older write = fresh)', () => {
  const now = 1_000_000_000_000
  expect(isStalePendingAction({ at: now - 1000 }, now)).toBe(false)
  expect(isStalePendingAction({ at: now - PENDING_AUTH_TTL_MS - 1 }, now)).toBe(true)
  expect(isStalePendingAction({}, now)).toBe(false)
  expect(isStalePendingAction(null, now)).toBe(false)
})
