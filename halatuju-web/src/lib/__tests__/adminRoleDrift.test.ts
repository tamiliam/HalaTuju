/**
 * THE DRIFT TEST for `ROLE_NAMES` in `navigation.ts` — named by its `drift-test:` marker
 * (code health H9).
 *
 * `navigation.ts` is explicit that it is NOT the security fence, and that stays true: hiding a
 * link has never been access control. What the registry decides is what is worth SHOWING, and it
 * decides it per role — so a role added to `PartnerAdmin.ROLE_CHOICES` and not here is a person
 * who signs in to a console with **no sidebar at all**, because no `NavItem` names them. That is
 * the failure the 2026-07-15 surface-partition sprint was called to fix, in the other direction:
 * `apps/courses/models.py` records it as "nav hid it, backend didn't".
 *
 * Characterised first (the H8 rule): the seven roles on each side were compared on the untouched
 * tree. They AGREE, in the same order.
 *
 * `navigation.test.ts` already snapshots which PAGES each role reaches; that is the web's own
 * decision and stays there. This file guards only the VOCABULARY — that the two sides know the
 * same seven roles.
 */
import { NAV_ITEMS, ROLE_NAMES, type AdminRoleName } from '@/lib/navigation'
import { pyChoiceValues, readApi } from '@/test/apiSource'

const MODELS = 'apps/courses/models.py'
const backendRoles = pyChoiceValues(readApi(MODELS), 'ROLE_CHOICES')

describe('ROLE_NAMES vs PartnerAdmin.ROLE_CHOICES', () => {
  test('the parse found a real role list (parse sanity)', () => {
    expect(backendRoles.length).toBe(7)
    expect(backendRoles).toContain('super')
    expect(backendRoles).toContain('reviewer')
  })

  test('the two lists agree, in the same order', () => {
    expect([...ROLE_NAMES]).toEqual(backendRoles)
  })

  test('every role the api can store reaches at least one page', () => {
    // The concrete harm behind the vocabulary: a role nothing names gets an empty console.
    const reached = new Set(NAV_ITEMS.flatMap((i) => i.roles as readonly string[]))
    expect(backendRoles.filter((r) => !reached.has(r))).toEqual([])
  })

  test('no NavItem names a role the api cannot store', () => {
    const named = [...new Set(NAV_ITEMS.flatMap((i) => i.roles as readonly AdminRoleName[]))]
    expect(named.filter((r) => !backendRoles.includes(r)).sort()).toEqual([])
  })
})
