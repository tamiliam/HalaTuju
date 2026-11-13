/**
 * Sprint M2d (D1, owner 2026-11-13): THE ONE LAYOUT of the Permissions tab — two boxes, Organisation and
 * Programme, each a list of page rows in SIDEBAR order (`lib/navigation.ts`), each row naming the key(s)
 * it drives and its control. The design of record is the mock-up the owner approved on 2026-11-13.
 *
 * ⚠ IT PLACES KEYS, IT DECIDES NOTHING. Whether a key may be ticked (`grantable`, `reason`), what opens
 * today (`held`) and what saving does are the server's answers (`staff_permissions_admin.v2_editor`, the
 * dry run). A key the server serves that is neither placed here nor hidden (D3: `never_grantable`, `alias`)
 * still gets a switch under the boxes, and `permissionLayout.test.ts` fails the build until it is placed.
 *
 * Controls (D2): `tri` is "No access / View / View and change" over a page's `.view` and `.edit`; `switch`
 * is one key; `info` has no control (the Overview rows, and Payments, which opens with its sub-items).
 * A row's `subs` are one switch each. Names are i18n keys — the sidebar's own label where the page has
 * one, so a renamed page reads the same in both places.
 */

export type PermControl =
  | { kind: 'tri'; view: string; edit: string }
  | { kind: 'switch'; key: string }
  | { kind: 'info' }

export interface PermSub {
  key: string
  name: string
  desc: string
}

export interface PermRow {
  id: string
  name: string
  desc: string
  control: PermControl
  subs?: readonly PermSub[]
}

export interface PermBox {
  id: 'organisation' | 'programme'
  title: string
  rows: readonly PermRow[]
}

const L = 'admin.permLayout'
const tri = (page: string): PermControl => ({ kind: 'tri', view: `${page}.view`, edit: `${page}.edit` })
const sw = (key: string): PermControl => ({ kind: 'switch', key })
const INFO: PermControl = { kind: 'info' }
/** A sub-item on one of today's keys: its own words (`admin.perm.<key>`). */
const oldSub = (key: string): PermSub => ({ key, name: `admin.perm.${key}.name`, desc: `admin.perm.${key}.desc` })
const sub = (key: string, id: string): PermSub => ({ key, name: `${L}.${id}.name`, desc: `${L}.${id}.desc` })

export const PERMISSION_LAYOUT: readonly PermBox[] = [
  { id: 'organisation', title: `${L}.box.organisation`, rows: [
    { id: 'orgOverview', name: 'admin.orgPage.nav', desc: `${L}.orgOverview.desc`, control: INFO },
    { id: 'invitations', name: 'admin.nav.invitations', desc: `${L}.invitations.desc`, control: tri('invitations') },
    { id: 'team', name: 'admin.nav.reviewers', desc: `${L}.team.desc`, control: sw('team.view') },
    { id: 'sources', name: 'admin.sources.nav', desc: `${L}.sources.desc`, control: tri('sources') },
    { id: 'sponsors', name: 'admin.sponsors.nav', desc: `${L}.sponsors.desc`, control: tri('sponsors'),
      subs: [sub('sponsors.approve', 'sponsorsApprove')] },
    { id: 'billing', name: 'admin.billing.title', desc: `${L}.billing.desc`, control: sw('billing.view') },
    { id: 'requests', name: 'admin.requests.nav', desc: `${L}.requests.desc`, control: tri('requests') },
    { id: 'orgSettings', name: 'admin.orgSettings.nav', desc: `${L}.orgSettings.desc`, control: sw('settings.edit') },
  ] },
  { id: 'programme', title: `${L}.box.programme`, rows: [
    { id: 'programmeOverview', name: 'admin.nav.programmeOverview', desc: `${L}.programmeOverview.desc`, control: INFO },
    { id: 'applications', name: 'admin.scholarship.nav', desc: 'admin.perm.see_all.desc', control: sw('see_all'),
      subs: [sub('students.edit', 'assign'), sub('students.approve', 'approveAwards')] },
    { id: 'scholars', name: 'admin.scholars.nav', desc: `${L}.scholars.desc`, control: sw('scholars'),
      subs: [oldSub('award_withdraw_request'), oldSub('award_withdraw_approve')] },
    { id: 'announcements', name: 'admin.announcements.nav', desc: `${L}.announcements.desc`, control: tri('announcements') },
    { id: 'surveys', name: 'admin.surveys.nav', desc: `${L}.surveys.desc`, control: tri('surveys') },
    { id: 'development', name: 'admin.development.nav', desc: `${L}.development.desc`, control: tri('development') },
    { id: 'mentoring', name: 'admin.permV2.page.mentoring', desc: `${L}.mentoring.desc`, control: tri('mentoring') },
    { id: 'payments', name: 'admin.payments.title', desc: `${L}.payments.desc`, control: INFO,
      subs: [oldSub('payments_prepare'), oldSub('payments_check'), oldSub('payments_approve')] },
    { id: 'spending', name: 'admin.spending.nav', desc: `${L}.spending.desc`, control: sw('spending') },
    { id: 'contracts', name: 'admin.contracts.title', desc: `${L}.contracts.desc`, control: tri('contracts') },
    { id: 'programmeSettings', name: 'admin.programme.config.nav', desc: `${L}.programmeSettings.desc`,
      control: sw('programmes.edit') },
  ] },
]

/** The keys a row's own control drives (not its sub-items). */
export function controlKeys(c: PermControl): string[] {
  if (c.kind === 'tri') return [c.view, c.edit]
  if (c.kind === 'switch') return [c.key]
  return []
}

/** Every key a box places, its rows' controls then their sub-items, in layout order. */
export function boxKeys(box: PermBox): string[] {
  return box.rows.flatMap((r) => [...controlKeys(r.control), ...(r.subs ?? []).map((s) => s.key)])
}

/** Every key the layout places, in layout order. */
export const LAYOUT_KEYS: readonly string[] = PERMISSION_LAYOUT.flatMap(boxKeys)
