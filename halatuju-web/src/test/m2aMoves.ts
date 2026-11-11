/**
 * Sprint M2a (owner U1, 2026-11-11) — THE ONLY CELLS M2a MOVES in the console access matrices
 * (`teamTablesMatrix`, `teamTablesT5cDoors`). Their BEFORE fixtures stay exactly as they were made; this
 * states the move instead (the S1 precedent, `test/s1Moves.ts`).
 *
 * The Team row's address moved from `/admin/organisation/reviewers` to `/admin/organisation/team`; the row,
 * its door and its gate did not. So the cell `open /admin/organisation/reviewers` is now measured under the
 * new address and answers exactly as before. `/admin/organisation/mentors` is no longer a menu address at all
 * (the Team row's `match` went; the old address is a permanent redirect in `next.config.js`), so its cell
 * goes. Who reads the Mentors TAB is still `pageGuard.mayReadMentors`, pinned against the frozen fixture's
 * `open /admin/organisation/mentors` key by the matrix test itself. Nothing else moves.
 */
export const M2A_OLD = '/admin/organisation/reviewers'
export const M2A_NEW = '/admin/organisation/team'
const M2A_GONE = '/admin/organisation/mentors'

/** The cells after M2a, from the cells the shape would have without it. */
export function m2aMoves(cells: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...cells }
  if (`open ${M2A_OLD}` in cells) {
    out[`open ${M2A_NEW}`] = cells[`open ${M2A_OLD}`]
    delete out[`open ${M2A_OLD}`]
  }
  delete out[`open ${M2A_GONE}`]
  return out
}
