/**
 * Sprint M2d (D1): THE GUARD on the Permissions tab's one layout (`lib/permissionLayout.ts`). A layout that
 * missed a key would hide a power, so every key the server can serve an Admin — the Admins table's keys
 * (`staff_tables.ADMIN_KEYS` less `manage_team`) and every v2 page key (`staff_permissions_v2.CATALOGUE_V2`) —
 * is placed EXACTLY ONCE or hidden by D3 (`NEVER_GRANTABLE`, or an alias: a v2 key an old key already MEANS,
 * `ALIASES`), never both. Read from the api's own source, so a key added there turns this red.
 */
import { PERMISSION_LAYOUT, LAYOUT_KEYS, boxKeys, controlKeys } from '@/lib/permissionLayout'
import { TABLE_KEYS } from '@/components/admin/PermissionEditor'
import { pyDictOfSeqs, pySeq, readApi } from '@/test/apiSource'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const V2 = readApi('apps/courses/staff_permissions_v2.py')
const CATALOGUE = [...V2.matchAll(/^\s+'([a-z_]+\.[a-z_]+)':\s*\(\w+,\s*'[a-z_]+',\s*\w+,\s*\w+\)/gm)].map((m) => m[1])
const NEVER = pySeq(V2, 'NEVER_GRANTABLE')
const ALIAS = Object.values(pyDictOfSeqs(V2, 'ALIASES')).flat().filter((k) => CATALOGUE.includes(k))
const HIDDEN = new Set([...NEVER, ...ALIAS])
const ADMIN_KEYS = pySeq(readApi('apps/courses/staff_tables.py'), 'ADMIN_KEYS').filter((k) => k !== 'manage_team')
const SERVED = [...ADMIN_KEYS, ...CATALOGUE]

it('reads the api (parse sanity)', () => {
  expect(CATALOGUE.length).toBeGreaterThanOrEqual(36)
  expect(NEVER).toEqual(['billing.edit', 'requests.approve'])
  expect(ALIAS.length).toBeGreaterThanOrEqual(8)
  expect([...TABLE_KEYS.admins]).toEqual(ADMIN_KEYS)            // the editor's Admins keys are the server's
})

it('places every key the server serves exactly once, or hides it (D3) — never both', () => {
  const dupes = LAYOUT_KEYS.filter((k, i) => LAYOUT_KEYS.indexOf(k) !== i)
  expect(dupes).toEqual([])
  expect(SERVED.filter((k) => !LAYOUT_KEYS.includes(k) && !HIDDEN.has(k))).toEqual([])    // nothing missed
  expect(LAYOUT_KEYS.filter((k) => HIDDEN.has(k))).toEqual([])                             // nothing hidden drawn
  expect(LAYOUT_KEYS.filter((k) => !SERVED.includes(k))).toEqual([])                       // nothing invented
  expect(TABLE_KEYS.reviewers.filter((k) => LAYOUT_KEYS.includes(k))).toEqual([])          // D10: their own box
})

it('D3 hides exactly the never-grantable keys and the aliases', () => {
  expect([...HIDDEN].sort()).toEqual(['billing.edit', 'payments.approve', 'payments.check', 'payments.prepare',
    'payments.view', 'requests.approve', 'scholars.view', 'spending.edit', 'spending.view', 'sponsors.check',
    'students.view'])
})

it('D1/D2: the rows in sidebar order, each with its control', () => {
  const shape = PERMISSION_LAYOUT.map((b) => [b.id, b.rows.map((r) => `${r.id}:${r.control.kind}:${controlKeys(r.control)
    .join('+')}${r.subs ? `>${r.subs.map((s) => s.key).join(',')}` : ''}`)])
  expect(shape).toEqual([
    ['organisation', ['orgOverview:info:', 'invitations:tri:invitations.view+invitations.edit', 'team:switch:team.view',
      'sources:tri:sources.view+sources.edit', 'sponsors:tri:sponsors.view+sponsors.edit>sponsors.approve',
      'billing:switch:billing.view', 'requests:tri:requests.view+requests.edit', 'orgSettings:switch:settings.edit']],
    ['programme', ['programmeOverview:info:', 'applications:switch:see_all>students.edit,students.approve',
      'scholars:switch:scholars>award_withdraw_request,award_withdraw_approve',
      'announcements:tri:announcements.view+announcements.edit', 'surveys:tri:surveys.view+surveys.edit',
      'development:tri:development.view+development.edit', 'mentoring:tri:mentoring.view+mentoring.edit',
      'payments:info:>payments_prepare,payments_check,payments_approve', 'spending:switch:spending',
      'contracts:tri:contracts.view+contracts.edit', 'programmeSettings:switch:programmes.edit']],
  ])
  expect(PERMISSION_LAYOUT.flatMap(boxKeys)).toEqual([...LAYOUT_KEYS])
})

it('every name and description is worded in all three languages', () => {
  const words = PERMISSION_LAYOUT.flatMap((b) => [b.title, ...b.rows.flatMap((r) =>
    [r.name, r.desc, ...(r.subs ?? []).flatMap((s) => [s.name, s.desc])])])
  const at = (m: unknown, key: string) => key.split('.').reduce<unknown>(
    (o, part) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[part] : undefined), m)
  for (const [lang, m] of [['en', en], ['ms', ms], ['ta', ta]] as const) {
    expect([lang, words.filter((w) => typeof at(m, w) !== 'string' || !(at(m, w) as string).trim())]).toEqual([lang, []])
  }
})

it('D4/D6: no "for now", no reason text and no old subtitle in the tab\'s English', () => {
  const admin = (en as { admin: Record<string, unknown> }).admin
  const tab = JSON.stringify([admin.permEditor, admin.permLayout, admin.permV2])
  expect(tab).not.toMatch(/for now/i)
  expect((admin.permV2 as Record<string, unknown>).reason).toBeUndefined()
  expect((admin.permEditor as Record<string, unknown>).subtitle).toBeUndefined()
})
