/**
 * TD-623 — THE WEB HALF OF A10: THE ROLE IS A LABEL, NOT A GATE.
 *
 * Owner, 2026-11-15: "there is no such thing as view only admin ... permissions determine what the admin views and
 * edits". Every page gate reads the served v2 keys (`GET admin/role/` always serves `page_keys`) through
 * `pageDoors.opensDoor` / `pageGuard.holdsDoor`. The api's half is `halatuju_api/apps/courses/tests/
 * test_role_is_display_only.py`.
 *
 * This file scans every non-test source under `src/` for a role NAME used in code:
 *   - a comparison with a role literal (`=== 'admin'`, `'qc' !==`, ...);
 *   - an array made only of role literals (`['super', 'org_admin']`, often `.includes(...)`);
 *   - a `*_ROLES` constant asked `.includes(...)`.
 * Every hit must be claimed by an entry below, and every entry must claim EXACTLY its count. A new role read fails
 * here: make it a key (a door), or add an entry with a reason a reviewer will accept. Never add a gate entry.
 *
 * The classes (what a kept read is FOR — none of them decides what a team member views or edits):
 *   PLATFORM  the platform super (`is_super`): who the person IS; they hold every key, the server exempts them alike
 *   KIND      the kind of login (mentor / source / partner / member): its own screens and endpoints
 *   LANDING   where a person lands, or is sent, after sign-in
 *   TARGET    a rule about the person ACTED ON or listed, not the viewer
 *   SIDE      which side of an organisation request the viewer is on (owner or requester)
 *   DISPLAY   a label, chip, Guide chapter or line of text; never a fence
 *   MENU      the navigation registry's role rows (the older-payload menu rule) — a follow-up, not TD-623's list
 *   M4        the money lane, frozen until M4
 *   FALSE     not a role at all (a key name, an invitation kind, a busy state, a session scope)
 */
import * as fs from 'fs'
import * as path from 'path'

const SRC = path.join(__dirname, '..', '..')

const R = '(?:super|admin|org_admin|partner|reviewer|qc|finance|source_partner|mentor|member)'
const PATTERNS = [
  new RegExp(`(?:===|!==)\\s*'${R}'|'${R}'\\s*(?:===|!==)`),
  new RegExp(`\\[\\s*'${R}'(?:\\s*,\\s*'${R}')*\\s*,?\\s*\\]`),
  /\b[A-Z_]+_ROLES\b[^;]*\.includes\(/,
]

type Klass = 'PLATFORM' | 'KIND' | 'LANDING' | 'TARGET' | 'SIDE' | 'DISPLAY' | 'MENU' | 'M4' | 'FALSE'
/** [file under src/, a snippet of the hit line, how many hit lines in that file contain it, class, reason]. */
type Entry = [file: string, snippet: string, count: number, klass: Klass, reason: string]

const ALLOWED: Entry[] = [
  // ── PLATFORM: the platform super ─────────────────────────────────────────────────────────────────────────
  ['lib/superRole.ts', "role.role === 'super'", 1, 'PLATFORM', 'the one definition of "is the platform super"'],
  ['lib/profileCards.ts', "role?.role === 'super'", 1, 'PLATFORM', 'the profile context\'s super flag (cards, not access)'],
  ['app/admin/course-data/page.tsx', "=== 'super'", 1, 'PLATFORM', 'course data is a platform page; the server refuses anyone else'],
  ['app/admin/scholarship/page.tsx', "effRole === 'super'", 1, 'PLATFORM', 'the platform override beside the keys (a super holds every key)'],
  ['app/admin/scholarship/[id]/view.tsx', "=== 'super'", 1, 'PLATFORM', 'cross-organisation super cases in the cockpit panels (the server\'s is_super)'],
  ['app/admin/scholarship/[id]/view/QcPanel.tsx', "role?.role === 'super'", 1, 'PLATFORM', 'the super is exempt from QC separation, as on the server'],
  ['app/admin/auth/callback/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the sign-in record says whether a super signed in'],
  ['app/admin/login/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the sign-in record says whether a super signed in'],
  ['app/admin/contracts/[id]/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the deploy panel\'s platform-only actions'],
  ['app/admin/requests/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the super answers requests, never raises one (the platform is not an organisation)'],
  ['app/admin/requests/[id]/page.tsx', "effectiveRole(role) === 'super'", 1, 'PLATFORM', 'the super answers as the platform (organisation name, internal notes)'],
  ['app/admin/students/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the students list is a platform page'],
  ['app/admin/students/[id]/page.tsx', "=== 'super'", 1, 'PLATFORM', 'platform-only actions on a student'],
  ['app/admin/billing/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the super sees every organisation\'s billing block'],
  ['app/admin/organisation/team/page.tsx', "=== 'super'", 1, 'PLATFORM', 'the super may act on an organisation admin'],
  ['app/admin/sponsors/terms/[id]/page.tsx', "['super', 'org_admin'].includes", 1, 'PLATFORM', 'the platform fence beside the key, mirrors may_approve_platform_sponsors (M3c call 1)'],
  ['components/admin/AppShell.tsx', "=== 'super' && role?.owning_org_id", 1, 'PLATFORM', 'a super with no organisation sees the platform shell'],
  ['components/admin/AppShell.tsx', "r === 'super' ?", 1, 'PLATFORM', 'the system-health light is the platform operator\'s'],
  ['components/admin/AppShell.tsx', "r !== 'super'", 1, 'PLATFORM', 'the platform is not billed, so its shell shows no billing banner'],
  // ── KIND: the kind of login ──────────────────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/page.tsx', "=== 'source_partner'", 1, 'KIND', 'a source login gets its own Applications screen'],
  ['app/admin/scholarship/[id]/page.tsx', "=== 'source_partner'", 1, 'KIND', 'a source login gets its own student screen'],
  ['app/admin/programme/overview/page.tsx', "=== 'source_partner'", 1, 'KIND', 'a source login gets its own Overview'],
  ['app/admin/scholars/page.tsx', "=== 'source_partner'", 1, 'KIND', 'a source login gets its own Scholars screen'],
  ['app/admin/scholars/page.tsx', "=== 'mentor'", 1, 'KIND', 'a mentor login reads only its own current students'],
  ['app/admin/scholars/[id]/page.tsx', "=== 'source_partner'", 1, 'KIND', 'a source login gets its own scholar screen'],
  ['app/admin/profile/page.tsx', "ctx.role ===", 3, 'KIND', 'the profile page\'s cards per kind of login (source, partner, reviewer)'],
  ['app/admin/profile/page.tsx', "ctx.role !== 'mentor'", 1, 'KIND', 'staff who mentor, as against a mentor login'],
  ['components/admin/AppShell.tsx', "role?.role === 'mentor' || role?.role === 'member'", 1, 'KIND', 'mentor and member logins call no staff endpoint'],
  ['components/admin/AppShell.tsx', "r === 'source_partner' || r === 'mentor'", 1, 'KIND', 'outsider logins probe no staff menu'],
  ['components/admin/AppShell.tsx', "r === 'source_partner' &&", 1, 'KIND', 'a source login\'s header names its source'],
  ['components/adminProfile/ContactCard.tsx', "role ===", 2, 'KIND', 'the contact card per kind of login'],
  ['components/adminProfile/OrganisationCard.tsx', "=== 'source_partner'", 1, 'KIND', 'a source\'s organisation card, not a partner\'s'],
  ['components/adminProfile/AccessCard.tsx', "role !== 'partner'", 1, 'KIND', 'partner and mentor logins have no staff access card'],
  ['lib/profileCards.ts', "ctx.role === 'mentor' ||", 1, 'KIND', 'the mentoring card for a mentor login or staff who mentor'],
  ['lib/profileCards.ts', "ctx.role === 'partner' ||", 1, 'KIND', 'the organisation card for partner and source logins'],
  ['lib/pageGuard.ts', "r === 'mentor' || r === 'source_partner'", 1, 'KIND', 'a mentor or source login reads only its own scholars (server scholars_scope)'],
  // ── LANDING ──────────────────────────────────────────────────────────────────────────────────────────────
  ['lib/navigation.ts', "role?.role === 'reviewer' && reviewerProfileComplete", 1, 'LANDING', 'a reviewer with an unfinished profile lands on Profile'],
  ['lib/adminLanding.ts', "role.role !== 'reviewer'", 1, 'LANDING', 'the reviewer onboarding hold'],
  ['lib/adminLanding.ts', "OUTSIDER_ROLES = [", 1, 'LANDING', 'outsider logins land on their own page'],
  ['lib/adminLanding.ts', 'OUTSIDER_ROLES as readonly string[]).includes', 1, 'LANDING', 'outsider logins land on their own page'],
  // ── TARGET: the person acted on or listed ────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/[id]/view/AssignAndWitness.tsx', "a.role !== 'reviewer'", 1, 'TARGET', 'the assignee\'s role named beside them'],
  ['app/admin/organisation/team/page.tsx', "a.role === 'org_admin'", 1, 'TARGET', 'which listed people have a person page'],
  ['app/admin/organisation/team/page.tsx', 'PERSON_PAGE_ROLES as readonly string[]).includes', 1, 'TARGET', 'which listed people have a person page'],
  ['app/admin/organisation/staff/page.tsx', "subRole", 3, 'TARGET', 'the role being invited decides the gift fields'],
  ['app/admin/organisation/staff/page.tsx', "r === 'super' || !row.role", 1, 'TARGET', 'canCancel: which invitations a super may cancel (a target rule)'],
  ['components/admin/StaffAdmin.tsx', "a.role ===", 3, 'TARGET', 'a super or organisation admin row is not acted on by the team'],
  ['components/admin/StaffAdmin.tsx', "x.role === 'org_admin'", 1, 'TARGET', 'the sole organisation admin cannot be removed'],
  ['components/admin/PermissionEditor.tsx', "view.role ===", 1, 'TARGET', 'the edited person\'s by-role rows'],
  ['components/admin/PermissionEditor.tsx', "['reviewer', 'qc'].includes(view.role)", 1, 'TARGET', 'the edited person\'s unlisted keys'],
  ['components/admin/person/MentorGroupPage.tsx', "viewerRole !== 'super'", 1, 'TARGET', 'a lead mentor\'s page is read-only to anyone but a super'],
  ['components/admin/person/ReviewerGroupPage.tsx', "viewerRole !== 'super'", 1, 'TARGET', 'an organisation admin\'s reviewer page is read-only to anyone but a super'],
  ['components/mentors/MentorsAdmin.tsx', "m.staff_role !== 'member'", 1, 'TARGET', 'returning mentors are staff, not members'],
  ['lib/adminStaff.ts', 'PROGRAMME_STAFF_ROLES = [', 1, 'TARGET', 'which listed people are programme staff'],
  ['lib/adminStaff.ts', 'PROGRAMME_STAFF_ROLES as readonly string[]).includes', 1, 'TARGET', 'which listed people are programme staff'],
  ['lib/adminStaff.ts', 'a.role ===', 2, 'TARGET', 'the partner and organisation-admin lists'],
  ['lib/cockpitTrail.ts', "a.role === 'reviewer'", 1, 'TARGET', 'who may be handed a case when the server serves no assignable flag'],
  ['lib/assignOptions.ts', "rv.role === 'reviewer'", 1, 'TARGET', 'who may be handed a case when the server serves no assignable flag'],
  // ── SIDE ─────────────────────────────────────────────────────────────────────────────────────────────────
  ['lib/requestStatus.ts', "role === 'org_admin'", 1, 'SIDE', 'the requesting organisation\'s actions, as against the owner\'s'],
  // ── DISPLAY ──────────────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/requests/[id]/page.tsx', "approved_by_role === 'super'", 1, 'DISPLAY', 'names who approved'],
  ['components/ActionCentre.tsx', "=== 'reviewer'", 1, 'DISPLAY', 'names who an item came from'],
  ['content/manual/index.ts', "effectiveRole(role) === 'super'", 2, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "role.role === 'reviewer'", 1, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "role.role === 'admin'", 1, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "role === 'super' || role === 'org_admin'", 1, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', 'TEAM_ROLES as readonly string[]).includes', 1, 'DISPLAY', 'the Guide reads a team member\'s keys'],
  ['content/manual/faq.tsx', "role === 'super'", 2, 'DISPLAY', 'the FAQ\'s audiences by role'],
  ['lib/profileCards.ts', "['admin', 'qc', 'reviewer', 'source_partner'].includes", 1, 'DISPLAY', 'activity filter chips: a shortcut, never a fence'],
  ['lib/profileCards.ts', "['admin', 'finance'].includes", 1, 'DISPLAY', 'activity filter chips: a shortcut, never a fence'],
  ['lib/profileCards.ts', 'lines.push', 5, 'DISPLAY', 'the "what you can do" lines on the profile'],
  // ── MENU: the navigation registry (a follow-up; not in TD-623's list) ───────────────────────────────────
  ['lib/navigation.ts', "['super', 'admin', 'org_admin', 'partner', 'reviewer', 'qc', 'finance', 'source_partner', 'mentor', 'member']", 1, 'MENU', 'ROLE_NAMES, the list of labels'],
  ['lib/navigation.ts', 'roles: [', 27, 'MENU', 'the menu rows\' roles: the older-payload rule and the rows with no door yet'],
  ['lib/staffPermissions.ts', 'TEAM_ROLES = [', 1, 'MENU', 'the server\'s TEAM_ROLES, held by a drift test'],
  ['lib/staffPermissions.ts', 'TEAM_ROLES as readonly string[]).includes', 1, 'MENU', 'a menu row reads keys for a team member'],
  // ── M4: money, frozen ────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/payments/page.tsx', "r !== 'finance'", 1, 'M4', 'payments prepare fallback; the money lane is frozen until M4'],
  ['app/admin/payments/[id]/page.tsx', "=== 'finance'", 1, 'M4', 'the finance viewer of a payment; frozen until M4'],
  ['lib/sponsorDetail.ts', "viewerRole === 'super'", 2, 'M4', 'sponsor credit maker and approver; frozen until M4'],
  ['lib/sponsorDetail.ts', "viewerRole === 'org_admin'", 1, 'M4', 'sponsor credit approval wait; frozen until M4'],
  // ── FALSE: not a role ────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/[id]/view/QcPanel.tsx', "busy === 'qc'", 3, 'FALSE', 'a busy state named qc'],
  ['app/admin/organisation/staff/page.tsx', "'mentor'", 5, 'FALSE', 'the invitation kind mentor'],
  ['components/admin/StaffList.tsx', "row.kind === 'mentor'", 2, 'FALSE', 'a row kind'],
  ['components/admin/TeamEmails.tsx', "(['admin', 'reviewer', 'mentor'] as const)", 1, 'FALSE', 'the email kinds'],
  ['components/admin/ScholarActivityParts.tsx', "actor.kind === 'mentor'", 1, 'FALSE', 'an actor kind'],
  ['components/admin/PermissionEditor.tsx', "=== 'qc'", 3, 'FALSE', 'the key named qc'],
  ['lib/sessionPolicy.ts', "current === 'admin'", 2, 'FALSE', 'the session scope admin or sponsor'],
  ['lib/familyRoster.ts', 'FAMILY_ROLES', 2, 'FALSE', 'family member roles'],
]

/** The removed role fallbacks: none may come back (TD-623). */
const GONE = ['opensDoorOr', 'MAKER_ROLES', 'POSTER_ROLES', 'MENTORING_ROLES', 'MENTORS_READ_ROLES', 'CAN_EDIT_EMAILS',
  'EMAIL_EDIT_ROLES']

function sources(dir: string): string[] {
  const out: string[] = []
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) {
      if (['__tests__', 'test', 'messages', 'data'].includes(name)) continue
      out.push(...sources(p))
    } else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) && !name.endsWith('.d.ts')) {
      out.push(p)
    }
  }
  return out
}

const isComment = (line: string) => /^\s*(\*|\/\/|\/\*)/.test(line)
const rel = (p: string) => path.relative(SRC, p).split(path.sep).join('/')

const HITS: Array<{ file: string; line: number; text: string }> = []
for (const file of sources(SRC)) {
  fs.readFileSync(file, 'utf8').split('\n').forEach((text, i) => {
    if (!isComment(text) && PATTERNS.some((re) => re.test(text))) HITS.push({ file: rel(file), line: i + 1, text })
  })
}

describe('TD-623 / A10 (web): a role name is never a permission gate', () => {
  it('the scan reads the source (it is not blind)', () => {
    expect(HITS.length).toBeGreaterThan(50)
    expect(HITS.some((h) => h.file === 'lib/superRole.ts')).toBe(true)
  })

  it('every role read is claimed by an allowlist entry', () => {
    const unclaimed = HITS.filter((h) => !ALLOWED.some(([f, snippet]) => f === h.file && h.text.includes(snippet)))
      .map((h) => `${h.file}:${h.line}: ${h.text.trim()}`)
    expect(unclaimed).toEqual([])
  })

  it('every entry claims exactly its count (so a kept read cannot multiply unseen)', () => {
    const wrong = ALLOWED.map(([f, snippet, count]) => {
      const got = HITS.filter((h) => h.file === f && h.text.includes(snippet)).length
      return got === count ? null : `${f} "${snippet}": pinned ${count}, found ${got}`
    }).filter(Boolean)
    expect(wrong).toEqual([])
  })

  it('every entry gives a reason, and none is a gate', () => {
    for (const [, , , klass, reason] of ALLOWED) {
      expect(reason.length).toBeGreaterThan(8)
      expect(klass).not.toBe('GATE')
    }
  })

  it('the removed role fallbacks do not come back', () => {
    const back = sources(SRC).flatMap((file) => {
      // Code only: a comment may still name what TD-623 removed.
      const text = fs.readFileSync(file, 'utf8').split('\n').filter((l) => !isComment(l)).join('\n')
      return GONE.filter((name) => new RegExp(`\\b${name}\\b`).test(text)).map((name) => `${rel(file)}: ${name}`)
    })
    expect(back).toEqual([])
  })
})
