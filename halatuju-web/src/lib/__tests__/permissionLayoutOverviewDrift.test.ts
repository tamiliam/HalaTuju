/**
 * Sprint S1 (TD-618): THE TWO OVERVIEW ROWS on the Permissions tab have no control, only a sentence saying when
 * each Overview opens. The sentences were checked by hand against the server; this pins each fact to the
 * server's own source, so a changed door turns this red instead of leaving the words wrong.
 *
 *  * Organisation box, "Overview" (`admin.permLayout.orgOverview.desc`, "Opens with any switch on this tab"):
 *    the landing opens for `my_programmes.lands` = `sees_every_gift` or the Reviewers table or a mentor, and
 *    `sees_every_gift` holds for anyone at the Admins table (`staff_tables.in_admins`), which a team member
 *    reaches with any old Admins key (`admin_keys`) or any stored grantable v2 page key (`stored_v2`).
 *  * Programme box, "Overview" (`admin.permLayout.programmeOverview.desc`, "Every gift once any switch in these
 *    two boxes is on; otherwise only the gifts with cases assigned to them"): `may_open_overview` opens every
 *    gift for `sees_every_gift`, and otherwise a named gift only where the caller has review work.
 *  * The link between the two: EVERY key the layout gives a switch is an Admins key or a grantable v2 key,
 *    so switching any one of them on seats the person at Admins and so opens both Overviews in full.
 */
import { PERMISSION_LAYOUT, LAYOUT_KEYS } from '@/lib/permissionLayout'
import { pyDictOfSeqs, pySeq, readApi } from '@/test/apiSource'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const TABLES = readApi('apps/courses/staff_tables.py')
const V2 = readApi('apps/courses/staff_permissions_v2.py')
const PROGRAMMES = readApi('apps/scholarship/views_admin/my_programmes.py')
const OVERVIEW = readApi('apps/scholarship/views_admin/overview.py')
const PENDING = readApi('apps/scholarship/views_admin/my_pending.py')

const V2_BLOCK = V2.slice(V2.indexOf('CATALOGUE_V2 = {'), V2.indexOf('\n}', V2.indexOf('CATALOGUE_V2 = {')))
const CATALOGUE = [...V2_BLOCK.matchAll(/^\s+'([a-z0-9_]+\.[a-z0-9_]+)':/gm)].map((m) => m[1])
const NEVER = pySeq(V2, 'NEVER_GRANTABLE')
const ALIAS = new Set(Object.values(pyDictOfSeqs(V2, 'ALIASES')).flat())
/** `staff_permissions_v2.GRANTABLE_V2`, recomputed from its parts (its own definition is pinned below). */
const GRANTABLE = CATALOGUE.filter((k) => !NEVER.includes(k) && !ALIAS.has(k))
const ADMIN_KEYS = pySeq(TABLES, 'ADMIN_KEYS')

/** The body of a top-level `def name(` in `src`, up to the next top-level line. Throws if absent. */
function pyDef(src: string, name: string): string {
  const at = src.indexOf(`\ndef ${name}(`)
  if (at < 0) throw new Error(`drift test: def ${name} has moved`)
  const next = src.slice(at + 1).search(/\n(?=\S)/)
  return src.slice(at + 1, next < 0 ? undefined : at + 1 + next)
}

const words = (desc: string): unknown => desc.split('.')
  .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en)
const row = (id: string) => PERMISSION_LAYOUT.flatMap((b) => b.rows.map((r) => ({ box: b.id, ...r })))
  .find((r) => r.id === id)

it('reads the api (parse sanity)', () => {
  expect(CATALOGUE.length).toBeGreaterThanOrEqual(36)
  expect(ADMIN_KEYS.length).toBeGreaterThanOrEqual(9)
  expect(GRANTABLE.length).toBeGreaterThanOrEqual(20)
  expect(LAYOUT_KEYS.length).toBeGreaterThanOrEqual(30)
  // The recomputed set is the server's: its definition is exactly these three parts.
  expect(V2).toContain(
    'GRANTABLE_V2 = tuple(k for k in CATALOGUE_V2 if k not in NEVER_GRANTABLE and k not in ALIAS_V2)')
})

describe('the two rows say what the server does', () => {
  it('each is an info row (no control) in its own box, with the pinned sentence', () => {
    const org = row('orgOverview')
    const prog = row('programmeOverview')
    expect([org?.box, org?.control.kind, org?.desc]).toEqual(['organisation', 'info', 'admin.permLayout.orgOverview.desc'])
    expect([prog?.box, prog?.control.kind, prog?.desc])
      .toEqual(['programme', 'info', 'admin.permLayout.programmeOverview.desc'])
    expect(words('admin.permLayout.orgOverview.desc')).toBe('Opens with any switch on this tab.')
    expect(words('admin.permLayout.programmeOverview.desc')).toBe(
      'Every gift once any switch in these two boxes is on; otherwise only the gifts with cases assigned to them.')
    for (const lang of [ms, ta] as const) {
      expect(typeof lang.admin.permLayout.orgOverview.desc).toBe('string')
      expect(typeof lang.admin.permLayout.programmeOverview.desc).toBe('string')
    }
  })

  it('every switch on the tab seats its holder at Admins (an Admins key or a grantable v2 key)', () => {
    const neither = LAYOUT_KEYS.filter((k) => !ADMIN_KEYS.includes(k) && !GRANTABLE.includes(k))
    expect(neither).toEqual([])
    expect(pyDef(TABLES, 'in_admins')).toContain('return bool(admin_keys(admin)) or bool(v2.stored_v2(admin))')
    expect(pyDef(V2, 'stored_v2')).toContain('return tuple(k for k in GRANTABLE_V2 if k in held)')
    expect(pyDef(TABLES, 'admin_keys')).toContain('return tuple(k for k in ADMIN_KEYS if k in held)')
  })

  it('a seat at Admins sees every gift, and seeing every gift opens the landing (the Organisation row)', () => {
    expect(pyDef(PROGRAMMES, 'sees_every_gift')).toContain(
      "return b40_scope == 'all' or staff_tables.in_admins(admin)")
    expect(pyDef(PROGRAMMES, 'lands')).toMatch(/return \(sees_every_gift\(admin, b40_scope\) or /)
    // The landing and its pending cards both ask `lands`.
    expect(PENDING).toContain('if not lands(admin, scope):')
    expect(PROGRAMMES).toContain('if not lands(admin, scope):')
  })

  it('the Programme Overview opens every gift for sees_every_gift, else only gifts with review work', () => {
    const rule = pyDef(PROGRAMMES, 'may_open_overview')
    expect(rule).toMatch(/if sees_every_gift\(admin, b40_scope\):\n\s+return True\n\s+if programme is not None:\n\s+return has_review_work\(admin, programme\.pk\)/)
    expect(OVERVIEW).toContain('if not may_open_overview(admin, self._b40_scope(admin), programme, cohort):')
  })
})
