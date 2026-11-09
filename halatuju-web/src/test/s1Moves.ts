/**
 * Sprint S1 (owner, 2026-11-09) — THE ONLY CELLS S1 MOVES in the console access matrices (`teamTablesMatrix`,
 * `teamTablesT5cDoors`). Their BEFORE fixtures stay exactly as they were made; this states the move instead.
 * Brief `docs/plans/2026-11-09-s1-scholars-access.md`; decisions.md "S1".
 *
 * S1-c: the Scholars row reads its own key, `scholars` (`navigation.ts`: `perms: ['scholars']`, roles super /
 * org_admin / admin / source_partner). `review`, `qc` and `see_all` alone no longer open it, so the shapes that
 * read it by one of those lose the row from every menu, and its page guard answers false. Nothing else moves:
 * the landing, the Guide, the Applications row and every other row answer as before.
 *
 * S1-a / S1-g: the payload the server serves after S1 carries `scholars` for the super, the lead tier, the admin
 * preset and every saved list that held `see_all` (named, or brought by `qc`) — the data migration, courses 0095.
 * `s1Served` gives a BEFORE payload that key, so the shapes that keep the row are measured as the server serves
 * them. The backend half is `halatuju_api/apps/scholarship/tests/team_matrix_s1.py`.
 *
 * ⚠ The shapes are typed out here, not derived, so a change to who reads Scholars is a deliberate act.
 */
export const S1_HREF = '/admin/scholars'

/** The shapes the Scholars row now refuses (they held it by `review`, `qc` or `see_all`). */
export const S1_SHUT = ['qc', 'qc_alone', 'reviewer', 'reviewer_incomplete', 'reviewer_payments_check',
  'finance_custom', 'reviewer_mentor']

/** The shapes whose served `permissions` gain `scholars` (the preset or lead tier, or the migration). */
export const S1_GAIN = ['super', 'reviewer_super', 'org_admin', 'org_admin_mentor', 'org_admin_reviews', 'admin',
  'admin_mentor', 'admin_gift_limited', 'admin_see_all_spending', 'reviewer_admin_keys',
  'reviewer_admin_keys_other_org', 'reviewer_gift_limited_admin_keys', 'reviewer_see_all', 'qc_spending']

const MENUS = ['menu', 'menuNoGift', 'menuNothingProbed'] as const

/** The cells after S1 for `shape`, from the cells it would have without S1. */
export function s1Moves(cells: Record<string, unknown>, shape: string): Record<string, unknown> {
  if (!S1_SHUT.includes(shape)) return cells
  const out: Record<string, unknown> = { ...cells }
  for (const m of MENUS) out[m] = (cells[m] as string[]).filter((id) => !id.startsWith('scholars:'))
  out[`open ${S1_HREF}`] = false
  return out
}

/** The payload the server serves `shape` after S1: `scholars` added, in catalogue order (after `see_all`). */
export function s1Served<P extends { permissions: string[] }>(shape: string, p: P): P {
  if (!S1_GAIN.includes(shape) || p.permissions.includes('scholars')) return p
  const at = p.permissions.indexOf('see_all') + 1
  return { ...p, permissions: [...p.permissions.slice(0, at), 'scholars', ...p.permissions.slice(at)] }
}
