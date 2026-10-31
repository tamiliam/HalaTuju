/**
 * The shortest password a staff or source account may choose. The SERVER's rule is
 * `halatuju_api/apps/courses/supabase_admin.py` `MIN_PASSWORD_LENGTH` (read by `admin/set-password/`
 * and `admin/me/password/`); this copy only lets the screen say so before the call, and is held to it.
 * drift-test: halatuju-web/src/lib/__tests__/adminPasswordDrift.test.ts
 *
 * Read by `app/admin/set-password` and the Profile page's Sign-in card (common profile S1).
 */
export const MIN_PASSWORD_LENGTH = 8
