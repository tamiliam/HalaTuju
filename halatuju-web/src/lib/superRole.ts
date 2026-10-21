/**
 * Is this admin-role payload a SUPER admin? — the one rule, in a leaf module (TD-360, 2026-10-21).
 *
 * ⚠ WHY A LEAF. `lib/sessionPolicy.ts` needs only this answer, and it is imported by
 * `lib/auth-context.tsx` and `components/AuthGateModal.tsx`, i.e. by EVERY page. It used to import
 * `effectiveRole` from `lib/navigation.ts`, which pulled the admin console's whole route registry
 * (and its `admin.*` label keys) onto every student, public and sponsor route — the reach that
 * `src/messages/__tests__/sliceReach.test.ts` refuses now that the admin words load only with the
 * admin layout. `navigation.ts`'s `effectiveRole` answers `'super'` through this same function, so
 * the rule still has one home.
 */
export function isSuperRole(
  role: { role?: string; is_super_admin?: boolean } | null | undefined,
): boolean {
  return !!role && (!!role.is_super_admin || role.role === 'super')
}
