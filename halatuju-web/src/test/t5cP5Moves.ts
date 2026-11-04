/**
 * T5c P5 (owner, 2026-11-04) — THE ONLY CELLS P5 MOVES in the console access matrices (`teamTablesMatrix`,
 * `teamTablesT5cDoors`). Their BEFORE fixtures stay exactly as they were made; this states the move instead.
 *
 * Organisation → Programmes is a menu row again, the FIRST of the organisation group, for every partner-login
 * role (`PROGRAMMES_ROLES`), and it is their landing:
 *  * each menu gains `programmes:show` where the organisation group begins (after any platform rows);
 *  * `open /admin/organisation/programmes` — until now a redirect matched to the Overview row — answers by the
 *    new row's roles;
 *  * the landing moves to it, EXCEPT where something lands earlier: a super on the platform dashboard (`/admin`),
 *    and the incomplete reviewer held on Profile (`/admin/profile`). Partner and source users do not move.
 * Nothing else moves.
 *
 * ⚠ The roles are typed out here, not read from the registry, so a change to the row is a deliberate act.
 */
export const PROGRAMMES_ROLES = ['super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'mentor']
export const PROGRAMMES_HREF = '/admin/organisation/programmes'
const MENUS = ['menu', 'menuNoGift', 'menuNothingProbed'] as const

/** `isPlatform(id)`: whether a menu id is a platform-group row (they come before the organisation group). */
export function t5cP5Moves(cells: Record<string, unknown>, role: string,
                           isPlatform: (id: string) => boolean): Record<string, unknown> {
  if (!PROGRAMMES_ROLES.includes(role)) return cells
  const out: Record<string, unknown> = { ...cells }
  for (const m of MENUS) {
    const ids = cells[m] as string[]
    const at = ids.findIndex((cell) => !isPlatform(cell.split(':')[0]))
    const i = at < 0 ? ids.length : at
    out[m] = [...ids.slice(0, i), 'programmes:show', ...ids.slice(i)]
  }
  out[`open ${PROGRAMMES_HREF}`] = true
  if (cells.landing !== '/admin' && cells.landing !== '/admin/profile') out.landing = PROGRAMMES_HREF
  return out
}
