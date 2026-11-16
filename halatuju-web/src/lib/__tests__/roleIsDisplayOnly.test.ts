/**
 * TD-623 — THE WEB HALF OF A10: THE ROLE IS A LABEL, NOT A GATE.
 *
 * Owner, 2026-11-15: "there is no such thing as view only admin ... permissions determine what the admin views and
 * edits". Every page gate reads the served v2 keys (`GET admin/role/` always serves `page_keys`) through
 * `pageDoors.opensDoor` / `pageGuard.holdsDoor`. The api's half is `halatuju_api/apps/courses/tests/
 * test_role_is_display_only.py`.
 *
 * This file scans every non-test source under `src/` for a role NAME used in code. The scan reads the WHOLE file
 * with its comments blanked (a real tokenizer: strings are kept, so `'http://…'` is not a comment, and code after
 * a closing star-slash on the same line is still read), so a read split over several lines is caught too:
 *   - a comparison with a role literal, either quote, `===` `==` `!==` `!=`, on either side (`=== 'admin'`, `"qc" !=`);
 *   - `case 'finance':`;
 *   - an array made only of role literals, on one line or many (`['super', 'org_admin']`, often `.includes(...)`);
 *   - a `*_ROLES` constant asked `.includes(` / `.has(`;
 *   - any `…roles` / `…Roles` asked `.includes(` / `.has(` (`row.roles.includes(role)`, `staffRoles.has(r)`).
 * Every hit must be claimed by EXACTLY ONE entry below, and every entry must claim EXACTLY its count. An entry's
 * snippet must CONTAIN the hit (the whole expression, never a bare `'mentor'` or `ctx.role ===`), so an entry
 * cannot quietly claim a different read on the same line. A new role read fails here: make it a key (a door),
 * or add an entry with a reason a reviewer will accept. Never add a gate entry.
 *
 * The classes (what a kept read is FOR — none of them decides what a team member views or edits on its own):
 *   PLATFORM  the platform super (`is_super`): who the person IS; they hold every key, the server exempts them alike
 *   SERVER    server-mirrored: the server ITSELF gates this by label beside the key (lead tier); the web mirrors it so
 *             it does not offer what will be refused. Debt on the server (docs/technical-debt.md), not a web gate
 *   KIND      the kind of login (mentor / source / partner / member): its own screens and endpoints
 *   LANDING   where a person lands, or is sent, after sign-in
 *   TARGET    a rule about the person ACTED ON or listed, not the viewer
 *   SIDE      which side of an organisation request the viewer is on (owner or requester)
 *   DISPLAY   a label, chip, Guide chapter or line of text; never a fence
 *   M4        the money lane, frozen until M4
 *   FALSE     not a role at all (a key name, an invitation kind, a busy state, a session scope, a family role)
 */
import * as fs from 'fs'
import * as path from 'path'

const SRC = path.join(__dirname, '..', '..')

/**
 * The source with every comment blanked to spaces (newlines kept, so offsets and line numbers still match). A
 * small tokenizer, not a line test: a line that merely STARTS with `*` is not skipped, and code after a closing
 * star-slash on the same line is read. A quote opens a string; a `'` or `"` string ends at its line's end at the
 * latest, so a stray apostrophe (JSX text, a regex literal) can blind at most the rest of one line.
 */
function stripComments(src: string): string {
  let out = ''
  let i = 0
  while (i < src.length) {
    const c = src[i]
    const d = src[i + 1]
    if (c === '/' && d === '/') {
      while (i < src.length && src[i] !== '\n') { out += ' '; i++ }
    } else if (c === '/' && d === '*') {
      out += '  '; i += 2
      while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) { out += src[i] === '\n' ? '\n' : ' '; i++ }
      if (i < src.length) { out += '  '; i += 2 }
    } else if (c === "'" || c === '"' || c === '`') {
      out += c; i++
      while (i < src.length && src[i] !== c && !(c !== '`' && src[i] === '\n')) {
        if (src[i] === '\\') { out += src.slice(i, i + 2); i += 2 } else { out += src[i]; i++ }
      }
      if (i < src.length && src[i] === c) { out += c; i++ }
    } else {
      out += c; i++
    }
  }
  return out
}

const R = '(?:super|admin|org_admin|partner|reviewer|qc|finance|source_partner|mentor|member)'
const LIT = `['"]${R}['"]`
const SCAN = new RegExp([
  `(?:===?|!==?)\\s*${LIT}`,                              // x === 'admin', x != "qc"
  `${LIT}\\s*(?:===?|!==?)`,                              // 'admin' === x
  `\\bcase\\s+${LIT}`,                                   // case 'finance':
  `\\[\\s*${LIT}(?:\\s*,\\s*${LIT})*\\s*,?\\s*\\]`,          // ['super', 'org_admin'], one line or many
  `\\b[A-Z_]+_ROLES\\b[^;\\n]*?\\.(?:includes|has)\\(`,      // (OUTSIDER_ROLES as …).includes(
  `\\w*[Rr]oles\\??\\.(?:includes|has)\\(`,                 // row.roles.includes(, staffRoles.has(
].join('|'), 'g')

const norm = (s: string) => s.replace(/\s+/g, ' ').trim()

type Hit = { file: string; line: number; match: string; text: string }

/** Every role read in `src`: the hit itself (`match`) and the whole line(s) it spans (`text`), both normalised. */
function scan(file: string, src: string): Hit[] {
  const code = stripComments(src)
  const out: Hit[] = []
  for (const m of code.matchAll(SCAN)) {
    const at = m.index ?? 0
    const from = code.lastIndexOf('\n', at) + 1
    const nl = code.indexOf('\n', at + m[0].length)
    const to = nl < 0 ? code.length : nl
    out.push({ file, line: code.slice(0, at).split('\n').length, match: norm(m[0]), text: norm(code.slice(from, to)) })
  }
  return out
}

type Klass = 'PLATFORM' | 'SERVER' | 'KIND' | 'LANDING' | 'TARGET' | 'SIDE' | 'DISPLAY' | 'M4' | 'FALSE'
/** [file under src/, the whole expression read, how many hits in that file it claims, class, reason]. */
type Entry = [file: string, snippet: string, count: number, klass: Klass, reason: string]

const SUPER = "effectiveRole(role) === 'super'"

const ALLOWED: Entry[] = [
  // ── PLATFORM: the platform super ─────────────────────────────────────────────────────────────────────────
  ['lib/superRole.ts', "role.role === 'super'", 1, 'PLATFORM', 'the one definition of "is the platform super"'],
  ['lib/profileCards.ts', "role?.role === 'super' || !!role?.is_super_admin", 1, 'PLATFORM', 'the profile context\'s super flag (cards, not access)'],
  ['app/admin/course-data/page.tsx', SUPER, 1, 'PLATFORM', 'course data is a platform page; the server refuses anyone else'],
  ['app/admin/scholarship/page.tsx', "effRole === 'super'", 1, 'PLATFORM', 'the platform override beside the keys (a super holds every key)'],
  ['app/admin/scholarship/[id]/view.tsx', SUPER, 1, 'PLATFORM', 'cross-organisation super cases in the cockpit panels (the server\'s is_super)'],
  ['app/admin/scholarship/[id]/view/QcPanel.tsx', "!!role?.is_super_admin || role?.role === 'super'", 1, 'PLATFORM', 'the super is exempt from QC separation, as on the server'],
  ['app/admin/auth/callback/page.tsx', `isSuper: ${SUPER}`, 1, 'PLATFORM', 'the sign-in record says whether a super signed in'],
  ['app/admin/login/page.tsx', `isSuper: ${SUPER}`, 1, 'PLATFORM', 'the sign-in record says whether a super signed in'],
  ['app/admin/contracts/[id]/page.tsx', SUPER, 1, 'PLATFORM', 'the deploy panel\'s platform-only actions'],
  ['app/admin/requests/page.tsx', SUPER, 1, 'PLATFORM', 'the super answers requests, never raises one (the platform is not an organisation)'],
  ['app/admin/requests/[id]/page.tsx', SUPER, 1, 'PLATFORM', 'the super answers as the platform (organisation name, internal notes)'],
  ['app/admin/students/page.tsx', SUPER, 1, 'PLATFORM', 'the students list is a platform page'],
  ['app/admin/students/[id]/page.tsx', SUPER, 1, 'PLATFORM', 'platform-only actions on a student'],
  ['app/admin/billing/page.tsx', SUPER, 1, 'PLATFORM', 'the super sees every organisation\'s billing block'],
  ['app/admin/organisation/team/page.tsx', `viewerSuper = ${SUPER}`, 1, 'PLATFORM', 'the super may act on an organisation admin'],
  ['components/admin/AppShell.tsx', `${SUPER} && role?.owning_org_id == null`, 1, 'PLATFORM', 'a super with no organisation sees the platform shell'],
  ['components/admin/AppShell.tsx', "r === 'super' ? <SystemHealthLight", 1, 'PLATFORM', 'the system-health light is the platform operator\'s'],
  ['components/admin/AppShell.tsx', "probes.billing === 'live' && r !== 'super'", 1, 'PLATFORM', 'the platform is not billed, so its shell shows no billing banner'],
  ['components/admin/person/MentorGroupPage.tsx', "page.viewerRole !== 'super'", 1, 'PLATFORM', 'a lead mentor\'s page is read-only to anyone but the platform super'],
  ['components/admin/person/ReviewerGroupPage.tsx', "page.viewerRole !== 'super'", 1, 'PLATFORM', 'an organisation admin\'s reviewer page is read-only to anyone but the platform super'],
  // ── SERVER: the server gates this by label itself (debt there, not here) ────────────────────────────────
  ['app/admin/sponsors/terms/[id]/page.tsx', "holdsDoor(role, 'sponsor_vet') && ['super', 'org_admin'].includes(effectiveRole(role))", 1, 'SERVER',
    'mirrors apps/scholarship/surface_gates.py:107 may_approve_platform_sponsors (sponsors.approve AND super-or-lead-tier, M3c call 1); the label half is server debt'],
  // ── KIND: the kind of login ──────────────────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/page.tsx', "role?.role === 'source_partner' ? <SourceApplications", 1, 'KIND', 'a source login gets its own Applications screen'],
  ['app/admin/scholarship/[id]/page.tsx', "role?.role === 'source_partner') return <SourceStudent", 1, 'KIND', 'a source login gets its own student screen'],
  ['app/admin/programme/overview/page.tsx', "role?.role === 'source_partner' ? <SourceOverview", 1, 'KIND', 'a source login gets its own Overview'],
  ['app/admin/scholars/page.tsx', "role?.role === 'source_partner' ? <SourceScholars", 1, 'KIND', 'a source login gets its own Scholars screen'],
  ['app/admin/scholars/page.tsx', "effectiveRole(role) === 'mentor' || role?.mentoring === true", 1, 'KIND', 'a mentor login reads only its own current students'],
  ['app/admin/scholars/[id]/page.tsx', "role?.role === 'source_partner') return <SourceScholar", 1, 'KIND', 'a source login gets its own scholar screen'],
  ['app/admin/profile/page.tsx', "isSource = ctx.role === 'source_partner'", 1, 'KIND', 'the profile page\'s cards for a source login'],
  ['app/admin/profile/page.tsx', "isPartner = ctx.role === 'partner'", 1, 'KIND', 'the profile page\'s cards for a partner login'],
  ['app/admin/profile/page.tsx', "isReviewerRole = ctx.role === 'reviewer'", 1, 'KIND', 'the profile page\'s reviewer-onboarding card'],
  ['app/admin/profile/page.tsx', "isMentor && ctx.role !== 'mentor'", 1, 'KIND', 'staff who mentor, as against a mentor login'],
  ['components/admin/AppShell.tsx', "role?.role === 'mentor' || role?.role === 'member' ? null : authToken", 2, 'KIND', 'mentor and member logins call no staff endpoint'],
  ['components/admin/AppShell.tsx', "r === 'source_partner' || r === 'mentor' || r === 'member' ? null : token", 3, 'KIND', 'outsider logins probe no staff menu'],
  ['components/admin/AppShell.tsx', "r === 'source_partner' && role?.source_name", 1, 'KIND', 'a source login\'s header names its source'],
  ['components/adminProfile/ContactCard.tsx', "mentor = role === 'mentor'", 1, 'KIND', 'the contact card for a mentor login'],
  ['components/adminProfile/ContactCard.tsx', "role === 'source_partner' || role === 'partner' || mentor", 2, 'KIND', 'the contact card for outside logins'],
  ['components/adminProfile/OrganisationCard.tsx', "state.role === 'source_partner' ? <SourceOrganisation", 1, 'KIND', 'a source\'s organisation card, not a partner\'s'],
  ['components/adminProfile/AccessCard.tsx', "role !== 'partner' && role !== 'mentor'", 2, 'KIND', 'partner and mentor logins have no staff access card'],
  ['lib/profileCards.ts', "ctx.role === 'mentor' || ctx.mentoring === true", 1, 'KIND', 'the mentoring card for a mentor login or staff who mentor'],
  ['lib/profileCards.ts', "ctx.role === 'partner' || ctx.role === 'source_partner'", 2, 'KIND', 'the organisation card for partner and source logins'],
  ['lib/pageGuard.ts', "r === 'mentor' || r === 'source_partner'", 2, 'KIND', 'a mentor or source login reads only its own scholars (server scholars_scope)'],
  // ── LANDING ──────────────────────────────────────────────────────────────────────────────────────────────
  ['lib/navigation.ts', "role?.role === 'reviewer' && reviewerProfileComplete === false", 1, 'LANDING', 'a reviewer with an unfinished profile lands on Profile'],
  ['lib/adminLanding.ts', "role.role !== 'reviewer' || role.reviewer_profile_complete", 1, 'LANDING', 'the reviewer onboarding hold'],
  ['lib/adminLanding.ts', "OUTSIDER_ROLES = ['source_partner', 'mentor', 'member']", 1, 'LANDING', 'outsider logins land on their own page'],
  ['lib/adminLanding.ts', '!(OUTSIDER_ROLES as readonly string[]).includes(r)', 1, 'LANDING', 'outsider logins land on their own page'],
  // ── TARGET: the person acted on or listed ────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/[id]/view/AssignAndWitness.tsx', "a.role !== 'reviewer' ? ` (${a.role})`", 1, 'TARGET', 'the assignee\'s role named beside them'],
  ['app/admin/organisation/team/page.tsx', "a.role === 'org_admin' || a.manageable !== false", 1, 'TARGET', 'which listed people have a person page'],
  ['app/admin/organisation/team/page.tsx', '(PERSON_PAGE_ROLES as readonly string[]).includes(a.role)', 1, 'TARGET', 'which listed people have a person page'],
  ['app/admin/organisation/staff/page.tsx', 'payload.invitable_roles.includes(cur)', 1, 'TARGET', 'the role being invited stays one the server serves as invitable'],
  ['app/admin/organisation/staff/page.tsx', "subRole !== 'reviewer' ? {}", 1, 'TARGET', 'the role being invited decides the gift fields'],
  ['app/admin/organisation/staff/page.tsx', "subRole === 'reviewer' && (", 1, 'TARGET', 'the role being invited decides the gift fields'],
  ['app/admin/organisation/staff/page.tsx', "subRole === 'reviewer' ? t(", 1, 'TARGET', 'the role being invited decides the gift fields'],
  ['app/admin/organisation/staff/page.tsx', "subRole === 'reviewer' && nothingTicked(rGifts)", 2, 'TARGET', 'a reviewer being invited needs at least one gift ticked (form check and button state)'],
  ['app/admin/organisation/staff/page.tsx', "r === 'super' || !row.role", 1, 'TARGET', 'canCancel: which invitations may be cancelled (a rule about the invited role)'],
  ['components/admin/StaffAdmin.tsx', "a.role === 'super' || a.manageable === false", 1, 'TARGET', 'a super row is not acted on by the team'],
  ['components/admin/StaffAdmin.tsx', "orgAdmin={a.role === 'org_admin'}", 1, 'TARGET', 'an organisation admin row is labelled as one'],
  ['components/admin/StaffAdmin.tsx', "a.role === 'org_admin' && a.is_active && a.owning_org_id", 1, 'TARGET', 'the sole organisation admin cannot be removed'],
  ['components/admin/StaffAdmin.tsx', "x.role === 'org_admin' && x.is_active", 1, 'TARGET', 'the sole organisation admin cannot be removed'],
  ['components/admin/PermissionEditor.tsx', "view.role === 'org_admin' ? BY_ROLE_ROWS", 1, 'TARGET', 'the edited person\'s by-role rows'],
  ['components/admin/PermissionEditor.tsx', "['reviewer', 'qc'].includes(view.role)", 1, 'TARGET', 'the edited person\'s unlisted keys'],
  ['components/admin/person/MentorGroupPage.tsx', "mentor?.mentor.staff_role === 'org_admin'", 1, 'TARGET', 'the mentor shown is an organisation admin'],
  ['components/admin/person/ReviewerGroupPage.tsx', "data.reviewer?.role === 'org_admin'", 1, 'TARGET', 'the reviewer shown is an organisation admin'],
  ['components/mentors/MentorsAdmin.tsx', "m.staff_role !== 'member'", 1, 'TARGET', 'returning mentors are staff, not members'],
  ['lib/adminStaff.ts', "PROGRAMME_STAFF_ROLES = ['reviewer', 'admin', 'qc', 'org_admin', 'finance', 'member']", 1, 'TARGET', 'which listed people are programme staff'],
  ['lib/adminStaff.ts', '(PROGRAMME_STAFF_ROLES as readonly string[]).includes(role)', 1, 'TARGET', 'which listed people are programme staff'],
  ['lib/adminStaff.ts', "a.role === 'partner'", 1, 'TARGET', 'the partner list'],
  ['lib/adminStaff.ts', "a.role === 'org_admin' && !a.is_super_admin", 1, 'TARGET', 'the organisation-admin list'],
  ['lib/cockpitTrail.ts', "isSuper || a.role === 'reviewer'", 1, 'TARGET', 'who may be handed a case when the server serves no assignable flag'],
  ['lib/assignOptions.ts', "isSuper || rv.role === 'reviewer'", 1, 'TARGET', 'who may be handed a case when the server serves no assignable flag'],
  // ── SIDE ─────────────────────────────────────────────────────────────────────────────────────────────────
  ['lib/requestStatus.ts', "if (role === 'org_admin') {", 1, 'SIDE', 'the requesting organisation\'s actions, as against the owner\'s'],
  ['app/admin/scholarship/[id]/view/ReviewerNotesCard.tsx', "const replying = viewer === 'reviewer'", 1, 'SIDE', 'the served notes side (#73): the reviewer\'s wording; the box is can_add'],
  ['app/admin/scholarship/[id]/view/ReviewerNotesCard.tsx', "viewer === 'org_admin' ? 'introOrgAdmin'", 1, 'SIDE', 'the served notes side (#73) picks the intro line'],
  // ── DISPLAY ──────────────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/requests/[id]/page.tsx', "req.approved_by_role === 'super'", 1, 'DISPLAY', 'names who approved'],
  ['components/ActionCentre.tsx', "attributionFor(item) === 'reviewer'", 1, 'DISPLAY', 'names who an item came from'],
  ['components/action-centre/ActionCard.tsx', "attributionFor(item) === 'reviewer'", 1, 'DISPLAY', 'names who an item came from'],
  ['app/admin/scholarship/[id]/view/ReviewerNotesCard.tsx', "n.author_role === 'reviewer'", 2, 'DISPLAY', 'names which side a note came from (#73), and tints it'],
  ['content/manual/index.ts', `${SUPER}) return 'super'`, 1, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', `!role || ${SUPER}) return []`, 1, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "role.role === 'reviewer' || role.role === 'qc' || role.role === 'org_admin'", 3, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "|| role.role === 'admin' || role.role === 'finance')", 2, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "seesAllRoles = role === 'super' || role === 'org_admin'", 2, 'DISPLAY', 'the Guide\'s chapters by role'],
  ['content/manual/index.ts', "(TEAM_ROLES as readonly string[]).includes(role.role ?? '')", 1, 'DISPLAY', 'the Guide reads a team member\'s keys'],
  ['content/manual/faq.tsx', "if (role === 'super') return ['everyone'", 1, 'DISPLAY', 'the FAQ\'s audiences by role'],
  ['content/manual/faq.tsx', "return role === 'super' || role === 'org_admin'", 2, 'DISPLAY', 'the FAQ\'s audiences by role'],
  ['lib/profileCards.ts', "['admin', 'qc', 'reviewer', 'source_partner'].includes(role)", 1, 'DISPLAY', 'activity filter chips: a shortcut, never a fence'],
  ['lib/profileCards.ts', "['admin', 'finance'].includes(role)", 1, 'DISPLAY', 'activity filter chips: a shortcut, never a fence'],
  ['lib/profileCards.ts', "ctx.role === 'org_admin') lines.push", 1, 'DISPLAY', 'the "what you can do" lines on the profile'],
  ['lib/profileCards.ts', "ctx.role === 'partner') lines.push", 1, 'DISPLAY', 'the "what you can do" lines on the profile'],
  ['lib/profileCards.ts', "ctx.role === 'source_partner') lines.push", 1, 'DISPLAY', 'the "what you can do" lines on the profile'],
  ['lib/profileCards.ts', "ctx.role === 'mentor') lines.push", 1, 'DISPLAY', 'the "what you can do" lines on the profile'],
  ['lib/profileCards.ts', "ctx.role !== 'mentor' && mentorsNow(ctx)", 1, 'DISPLAY', 'the "what you can do" lines on the profile'],
  // ── NAVKEYS (2026-11-16): the navigation registry. The MENU class is gone: a row with a door reads it alone, a
  // row the server gates by a key names it (`perms`), and `roles` holds only WHO THE LOGIN IS (`admitsRow`).
  ['lib/navigation.ts', "['super', 'admin', 'org_admin', 'partner', 'reviewer', 'qc', 'finance', 'source_partner', 'mentor', 'member']", 1, 'DISPLAY', 'ROLE_NAMES, the list of labels (held to the server\'s ROLE_CHOICES)'],
  ['lib/navigation.ts', "roles: ['super']", 4, 'PLATFORM', 'Course data, Organisations, Referral partners, Billing rates: the platform super only'],
  ['lib/navigation.ts', "roles: ['super', 'partner']", 2, 'PLATFORM', 'Dashboard and Students: the platform super, and the referral-partner KIND whose two pages they are'],
  ['lib/navigation.ts', "roles: ['super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'mentor']", 1, 'LANDING', 'Programmes, the front door every organisation login lands on (defaultRoute); a holder of programmes.edit is also admitted by its door (NAVKEYS review)'],
  ['lib/navigation.ts', "roles: ['super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'source_partner']", 1, 'SERVER', 'the gift Overview row: the server shapes the page by keys (programme_overview.sections_for, LABELS) and refuses a login holding none; the row\'s list moves with TD-632'],
  ['lib/navigation.ts', "roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance']", 2, 'DISPLAY', 'the Guide and FAQ rows: the roles the manual writes a chapter for (manualRole); help pages, never a fence'],
  ['lib/navigation.ts', "roles: ['mentor']", 1, 'KIND', 'My students, the mentor login\'s own page (staff who mentor by the mentor record)'],
  ['lib/navigation.ts', "roles: ['source_partner']", 1, 'KIND', 'Applications for a source login renders its own page and endpoint; staff by the key'],
  ['lib/navigation.ts', "roles: ['source_partner', 'mentor']", 1, 'KIND', 'Scholars for a source or mentor login: its own page, or its own students; staff by the key'],
  ['lib/navigation.ts', "roles: ['org_admin']", 1, 'M4', 'Payments: the lead tier holds no payment key and is paid in by role on the server (LEAD_MONEY_UNTIL_M4, TD-620)'],
  ['lib/staffPermissions.ts', "TEAM_ROLES = ['admin', 'finance', 'qc', 'reviewer']", 1, 'SERVER', 'the server\'s TEAM_ROLES (who carries a permission set), held by a drift test'],
  ['lib/staffPermissions.ts', 'if (row.roles?.includes(role)) return true', 1, 'KIND', 'admitsRow: a row\'s KIND or PLATFORM logins (who the login is), never a staff role on a key row'],
  // ── M4: money, frozen ────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/payments/page.tsx', "canPrepare ?? r !== 'finance'", 1, 'M4', 'payments prepare fallback; the money lane is frozen until M4'],
  ['app/admin/payments/[id]/page.tsx', "isFinanceViewer = effectiveRole(role) === 'finance'", 1, 'M4', 'the finance viewer of a payment; frozen until M4'],
  ['lib/sponsorDetail.ts', "isSuper = viewerRole === 'super'", 1, 'M4', 'sponsor credit maker and approver; frozen until M4'],
  ['lib/sponsorDetail.ts', "viewerRole === 'super' || viewerRole === 'admin'", 2, 'M4', 'canRecordCredit mirrors record_admin_credit; frozen until M4'],
  ['lib/sponsorDetail.ts', "viewerRole === 'org_admin' && !holdsChecker", 1, 'M4', 'sponsor credit approval wait; frozen until M4'],
  // ── FALSE: not a role ────────────────────────────────────────────────────────────────────────────────────
  ['app/admin/scholarship/[id]/view/QcPanel.tsx', "busy === 'qc' ? t(", 3, 'FALSE', 'a busy state named qc'],
  ['app/admin/organisation/staff/page.tsx', "KINDS.filter((k) => k !== 'mentor')", 2, 'FALSE', 'the invitation kind mentor'],
  ['app/admin/organisation/staff/page.tsx', "data?.kind === 'mentor' ? data", 1, 'FALSE', 'the invitation kind mentor'],
  ['app/admin/organisation/staff/page.tsx', ") : kind === 'mentor' ? (", 2, 'FALSE', 'the invitation kind mentor'],
  ['components/admin/StaffList.tsx', "row.kind === 'mentor' && row.mentor_id", 2, 'FALSE', 'a row kind'],
  ['components/admin/TeamEmails.tsx', "(['admin', 'reviewer', 'mentor'] as const)", 1, 'FALSE', 'the email kinds'],
  ['components/admin/ScholarActivityParts.tsx', "actor.kind === 'mentor'", 1, 'FALSE', 'an actor kind'],
  ['components/admin/PermissionEditor.tsx', "id === 'qc' && (", 1, 'FALSE', 'the key named qc'],
  ['components/admin/PermissionEditor.tsx', "key === 'qc' && on", 1, 'FALSE', 'the key named qc'],
  ['components/admin/PermissionEditor.tsx', "key === 'qc' && !on", 1, 'FALSE', 'the key named qc'],
  ['lib/sessionPolicy.ts', "current === 'admin' ?", 2, 'FALSE', 'the session scope admin or sponsor'],
  ['lib/familyRoster.ts', 'FAMILY_ROLES.includes(', 2, 'FALSE', 'family member roles (father, mother, …)'],
  ['app/admin/scholarship/[id]/view/FamilyAnswers.tsx', 'OTHER_ROLES.has(', 2, 'FALSE', 'family member roles (sibling, guardian, …)'],
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

const rel = (p: string) => path.relative(SRC, p).split(path.sep).join('/')

const HITS: Hit[] = sources(SRC).flatMap((file) => scan(rel(file), fs.readFileSync(file, 'utf8')))

/** The entries that claim `h`: same file, the entry's snippet inside the hit's line(s), the hit inside the snippet. */
const claims = (h: Hit) => ALLOWED.filter(([f, snippet]) => f === h.file && h.text.includes(norm(snippet))
  && norm(snippet).includes(h.match))

describe('the scanner itself', () => {
  // Each form the scan must see, and the comments it must not. If a pattern goes blind, this fails first.
  const SAMPLE = [
    'if (x == "admin") a()',                                // 1: double quotes, ==
    "if (x != 'qc') a()",                                   // 2: !=
    "switch (r) { case 'finance': break }",                 // 3: case
    'const ok = item.roles.includes(r)',                    // 4: .roles.includes(
    'const ok = staffRoles.has(r)',                         // 5: camelCase …Roles.has(
    "const L = [\n  'super',\n  'org_admin',\n]",            // 6: an array over several lines
    "/* note */ if (r === 'mentor') a()",                   // 10: code after a block comment, same line
    "// if (r === 'member') a()",                           // a line comment: not a hit
    "/* r === 'partner'\n   r === 'reviewer' */",            // a block comment: not a hit
    "const u = 'http://x'; if (r === 'reviewer') a()",      // 14: a // inside a string is not a comment
    "if ((OUTSIDER_ROLES as readonly string[]).has(r)) a()",  // 15: a *_ROLES constant
  ].join('\n')

  it('catches every form, at the line it starts on', () => {
    expect(scan('x.ts', SAMPLE).map((h) => [h.line, h.match])).toEqual([
      [1, '== "admin"'], [2, "!= 'qc'"], [3, "case 'finance'"], [4, 'roles.includes('], [5, 'staffRoles.has('],
      [6, "[ 'super', 'org_admin', ]"], [10, "=== 'mentor'"], [14, "=== 'reviewer'"],
      [15, 'OUTSIDER_ROLES as readonly string[]).has('],
    ])
  })

  it('blanks comments without moving a line', () => {
    const src = "a /* x\ny */ b // c\n'/* kept */'"
    const out = stripComments(src)
    expect(out.split('\n').map((l) => l.trim())).toEqual(['a', 'b', "'/* kept */'"])
    expect(out.length).toBe(src.length)
  })
})

describe('TD-623 / A10 (web): a role name is never a permission gate', () => {
  it('the scan reads the source (it is not blind)', () => {
    // About 90% of the 156 hits counted when this floor was set (TD-623 review): a scan that quietly loses a
    // pattern or a directory falls through it.
    expect(HITS.length).toBeGreaterThanOrEqual(140)
    expect(HITS.some((h) => h.file === 'lib/superRole.ts')).toBe(true)
  })

  it('every role read is claimed by exactly one allowlist entry', () => {
    const wrong = HITS.map((h) => [h, claims(h).length] as const).filter(([, n]) => n !== 1)
      .map(([h, n]) => `${h.file}:${h.line}: ${h.match}  in  ${h.text}  (claimed ${n}x)`)
    expect(wrong).toEqual([])
  })

  it('every entry claims exactly its count (so a kept read cannot multiply unseen)', () => {
    const wrong = ALLOWED.map((entry) => {
      const [f, snippet, count] = entry
      const got = HITS.filter((h) => claims(h).includes(entry)).length
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
      const text = stripComments(fs.readFileSync(file, 'utf8'))
      return GONE.filter((name) => new RegExp(`\\b${name}\\b`).test(text)).map((name) => `${rel(file)}: ${name}`)
    })
    expect(back).toEqual([])
  })
})
