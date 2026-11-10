/**
 * The admin console's route registry and the ONE role predicate behind it.
 *
 * Pure: no React, no next/navigation, no fetch — node-testable exactly like `adminLanding.ts`.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THIS IS NOT THE SECURITY FENCE.
 * ─────────────────────────────────────────────────────────────────────────────
 * Hiding a link has never been access control. The fence is server-side:
 * `_AdminBase._org_scoped` / `_org_allows` in `apps/scholarship/views_admin.py`, plus the
 * per-endpoint role gates, plus each page's own guard. A user who types a URL still gets
 * that page's 403 and the endpoint still 404s cross-org. This registry only decides what is
 * worth SHOWING. The 2026-07-15 surface-partition sprint exists because the two were once
 * confused — `apps/courses/models_staff.py` (PartnerAdmin docstring): "nav hid it, backend didn't".
 *
 * KEEP-IN-SYNC PAIR: `NavItem.roles` mirrors the authority in
 * `docs/scholarship/role-matrix.md` and `PartnerAdmin.ROLE_CHOICES`
 * (`halatuju_api/apps/courses/models_staff.py`). A role's powers change in the matrix FIRST, then
 * here, then in the page guard — all in one commit.
 *
 * Both halves are held by a test, each by the right instrument (code health H9): the drift test
 * below reads `ROLE_CHOICES` itself, so the two sides cannot know different roles and no stored
 * role can end up with an empty console; and `navigation.test.ts` pins the per-role visibility as
 * a snapshot, so a change to WHICH pages a role sees has to be deliberate. The matrix document
 * stays prose — it is written for people, and a guard over it could only cry wolf.
 * drift-test: halatuju-web/src/lib/__tests__/adminRoleDrift.test.ts
 */

import { ORG_READ_KEYS, admitsRow } from './staffPermissions'
import { isSuperRole } from './superRole'
import {
  SIDEBAR_SCOPES, type NavScope, type ProbeKey, type BadgeKey, type ProbeState, type NavGate, type NavItemOf,
} from './navigationTypes'
export { SIDEBAR_SCOPES, type NavScope, type ProbeKey, type BadgeKey, type ProbeState, type NavGate, type NavItemOf }

/** Mirrors PartnerAdmin.ROLE_CHOICES (halatuju_api/apps/courses/models_staff.py) — same nine,
 *  same order, asserted on every run.
 *  ⚠ `source_partner` (source sign-in, 2026-10-30) is named here so `effectiveRole` never folds
 *  a source user into 'reviewer'. Its rows: Overview / Applications / Scholars (the pages render
 *  `components/source/*`, which call `admin/source/` only) and Profile; it lands on Overview.
 *  ⚠ `mentor` (student maintenance S7a, 2026-10-31) likewise: its rows are Programmes (T5c P5: every partner
 *  login lands there, `defaultRoute`), My students (S7c), Scholars (sprint S1: its current students only,
 *  read-only) and Profile, and the layout sends it back from any other page (`outsiderMustLeave`).
 *  drift-test: halatuju-web/src/lib/__tests__/adminRoleDrift.test.ts */
export type AdminRoleName =
  | 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance' | 'source_partner'
  | 'mentor'

export const ROLE_NAMES: readonly AdminRoleName[] =
  ['super', 'admin', 'org_admin', 'partner', 'reviewer', 'qc', 'finance', 'source_partner', 'mentor']

/** One registry row (`navigationTypes.ts` holds its documented fields). */
export type NavItem = NavItemOf<AdminRoleName>

export interface NavGroup {
  scope: NavScope
  headingKey: string
  items: readonly NavItem[]
}

/**
 * Every route in the console, grouped by scope.
 *
 * Role sets reproduce the page guards (payments, contracts, sources `canManage`, billing); `sponsors`
 * and `requests` have NO client guard — their sets drive menu visibility only (the backend fences).
 * Team tables T1: `adminKeys` widens a row to the Admins table by a key, never narrows it. T5c P4: a row
 * with no `door` is not converted on the server yet (T5d money, T5e lead / platform) and keeps its rule.
 *
 * NO item is marked `placeholder` — `billingRates` was the last one and its page shipped on
 * 2026-09-11. See that field's own note for the rule that governs the next request for one.
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    scope: 'platform',
    headingKey: 'admin.nav.group.platform',
    items: [
      // The platform base — the student account and the course selector. Super-only since the
      // surface-partition sprint (2026-07-15); `partner` is a referral-org rep, whose two pages
      // are platform pages, not any organisation's.
      { id: 'overview', href: '/admin', labelKey: 'common.dashboard', chord: 'D',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' },
        exact: true },
      { id: 'students', href: '/admin/students', labelKey: 'admin.students', chord: 'S',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' } },
      { id: 'courseData', href: '/admin/course-data', labelKey: 'admin.courseData.nav', chord: 'C',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // Lifted out of the Administration hub in N3b. Creating a tenant and appointing its
      // org_admin are withheld from every ORGANISATION role (role matrix), so both are super.
      { id: 'organisations', href: '/admin/organisations', labelKey: 'admin.nav.organisations', chord: 'O',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // A referral org is an attribution relationship, never an access scope — which is why it
      // sits in the PLATFORM scope rather than inside any organisation.
      { id: 'referralPartners', href: '/admin/partners', chord: 'R',
        labelKey: 'admin.nav.referralPartners',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // `billing_rates` (2026-07-27, super-only: a tenant's margin is a commercial disclosure). Its page
      // landed 2026-09-11, ending the registry's only `placeholder` (the endpoint had shipped first).
      { id: 'billingRates', href: '/admin/billing-rates', labelKey: 'admin.nav.billingRates',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
    ],
  },
  {
    scope: 'organisation',
    headingKey: 'admin.nav.group.organisation',
    items: [
      // ⚠ T5c P5b (owner, 2026-11-05): ONE ROW, "Overview" — everyone's front door on partner login, and so the
      // FIRST row of this group (`defaultRoute` lands each of these roles here; super still lands on Platform).
      // The page is the per-person pending cards above the programme cards (`ProgrammesLanding.tsx`). It keeps
      // the route `/admin/organisation/programmes` (open to every partner role, no door, no v2 key — lead ruling
      // 2026-11-04, decisions.md); the old Organisation Overview and Administration rows are gone, and their
      // routes (`/admin/organisation`, `/admin/administration`) are redirects here, so `match` lights this row
      // for an old bookmark. `exact` so `/admin/organisation/staff` stays its SIBLING, not its child.
      { id: 'programmes', href: '/admin/organisation/programmes', labelKey: 'admin.orgPage.nav', chord: 'V',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'mentor'],
        gate: { mode: 'always' }, exact: true,
        match: ['/admin/organisation', '/admin/administration'] },
      // Renamed "Staff" → "Invitations" on 2026-08-03: reviewers moved to their own page in
      // request #10, and what is left is the asking. The ROUTE is unchanged deliberately — every
      // bookmark, the `/admin/invite` redirect and the highlight rules keep working; only the
      // label and the page moved.
      { id: 'staff', href: '/admin/organisation/staff', labelKey: 'admin.nav.invitations', chord: 'T',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'], adminKeys: ORG_READ_KEYS,
        door: 'team_read', gate: { mode: 'always' }, match: ['/admin/invite'] },
      // Sibling of Invitations, and deliberately next to it. **Invitations asks; People is where
      // everybody who is already in lives** — reviewers and admins, one tab each, and Revoke now
      // sits here rather than on a page about asking (2026-09-09). Same four roles as Invitations.
      // Organisation scope, not programme — a `PartnerAdmin` belongs to a tenant and has no
      // programme field at all (request #10, 2026-08-02).
      //
      // ⚠ THE ROUTE STAYS `/admin/organisation/reviewers` THOUGH THE LABEL IS NOW "People", for
      // exactly the reason the Staff → Invitations rename kept its own route: bookmarks, the
      // highlight rules and the ⌘K key all keep working, and only the word changed. The `id` is
      // likewise still `reviewers` — it is the snapshot key, never derived from the label.
      //
      // ⚠ TEAM TABLES T3 (2026-11-03): `/admin/organisation/mentors` REDIRECTS HERE (Team → Mentors) and is
      // matched to this row, so a bookmark lights Team. Who sees the Mentors TAB and the mentor detail
      // page is NOT this row's rule: it is `MENTORS_READ_ROLES` (the server's `mentor_invite.may_read`).
      { id: 'reviewers', href: '/admin/organisation/reviewers', labelKey: 'admin.nav.reviewers',
        chord: 'E', scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        adminKeys: ORG_READ_KEYS, door: 'team_read', gate: { mode: 'always' }, match: ['/admin/organisation/mentors'] },
      // Sources before Sponsors (owner, 2026-09-14): the people who send us students come
      // before the people who fund them, in the order the work actually flows.
      { id: 'sources', href: '/admin/sources', labelKey: 'admin.sources.nav', chord: 'U',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin'], door: 'sources', gate: { mode: 'always' } },
      // ⚠ MENTORS had a row here from S7a (2026-10-31) until Team tables T3 (2026-11-03): they are Team →
      // Mentors now (owner ruling 6), and the old route redirects (matched to the Team row above).
      { id: 'sponsors', href: '/admin/sponsors', labelKey: 'admin.sponsors.nav', chord: 'P',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'], adminKeys: ORG_READ_KEYS,
        door: 'sponsors_read', gate: { mode: 'always' }, badge: 'pendingSponsors' },
      { id: 'billing', href: '/admin/billing', labelKey: 'admin.billing.title', chord: 'B',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'billing', dark: 'soon' } },
      { id: 'requests', href: '/admin/requests', labelKey: 'admin.requests.nav', chord: 'Q',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'requests', dark: 'hide' },
        badge: 'requestsWaiting' },
      // The organisation's own settings, echoing the shape of Programme → Configuration one level up
      // (owner, 2026-09-03: "each Org would have its own config/setting, and each programme would
      // likewise have its own"). Colours moved here from the Programme screen, where they had
      // never belonged: `OrganisationTheme` is ONE colour for the whole tenant, so setting it
      // while standing inside a gift would have changed every other gift too — invisible with one
      // gift, wrong the day there are two. super + org_admin: the endpoint refuses everyone else.
      //
      // LAST in the group, and labelled "Organisation Settings" (owner, 2026-09-14). Settings is
      // the thing you touch least, so it sits at the bottom rather than second from the top; the
      // longer label says whose settings, now that a programme has settings of its own. The route
      // and the `id` are unchanged — only the position and the word moved.
      { id: 'orgSettings', href: '/admin/organisation/settings', labelKey: 'admin.orgSettings.nav',
        scope: 'organisation', roles: ['super', 'org_admin'], gate: { mode: 'always' } },
    ],
  },
  {
    scope: 'programme',
    headingKey: 'admin.nav.group.programme',
    items: [
      // The gift itself. `finance` is absent deliberately: it has no B40 scope at all
      // (`_b40_scope` -> 'none'), so an Applications link would only ever 403.
      // Layer 0 Sprint 5 (2026-08-30): the reserved "Overview" slot became the configuration
      // screen — what the programme ASKS FOR (documents + questions), Off / Optional / Required.
      // super + org_admin only: the page's endpoint refuses every other role, and a menu row that
      // opens a 403 is worse than no row. ⚠ Visibility only — the fence is the endpoint.
      //
      // ⚠ TWO ROWS, AND FOUR WERE DELETED TO GET HERE (owner, 2026-09-03). Everything a person
      // SETS about a gift is one screen with tabs — Rules, What we ask for, Intake year — because
      // they are one job: what this gift asks of an applicant and who it says yes to. The rows
      // that went, and why each was not a page:
      //   · `rules`  — the seven thresholds are COLUMNS ON THE INTAKE YEAR the create form already
      //     writes, so a Rules page was a second view of a form that exists. It is now the first
      //     tab, ahead of "what we ask for", which is the order the owner reads them in.
      //   · `years`  — a year is a child of the gift, not its sibling. `/admin/programme/years`
      //     redirects here and is matched below so the bookmark lights this row.
      //   · `reviewerScoping` — which gift a reviewer covers is one FIELD on that reviewer, and
      //     belongs on their record under Organisation → Reviewers. A `PartnerAdmin` has no
      //     programme column at all today; reserving a page for it guessed the shape wrongly.
      //   · `fund`   — a report, not a setting. Money in lives under Sponsors and money out under
      //     Payments; a third surface with no scope agreed was a slot waiting to be misread.
      //
      // WHICH gift comes from the breadcrumb switcher (`lib/programmeScope`), which is a display
      // preference passed to each endpoint explicitly — never an ambient scope. See that module.
      // ⚠ APPLICATIONS SITS ABOVE CONFIGURATION (owner, 2026-09-08), and the reason is FREQUENCY,
      // not hierarchy. Configuration is what you set up once; the applicants are what you come
      // back to — so the row you use daily leads. It also matches where the gift card now takes
      // you (`GiftProgrammes.enterGift`), so pressing a gift lands on the first row of its own
      // group rather than the second.
      //
      // ⚠ THIS IS NOT THE 2026-09-07 TAB ORDER, AND MUST NOT BE "MADE CONSISTENT" WITH IT. Inside
      // the Configuration screen the tabs follow the DATA (Intake year → Rules → What we ask for),
      // because the rules are columns on the year. That is a different question from which page a
      // person opens most.
      // ⚠⚠ **OVERVIEW LEADS THE GROUP, AND IT IS THE ONE ROW EVERY CONSOLE ROLE HAS.** It is where
      // the gift card now lands you, and it is shaped by role SERVER-SIDE
      // (`programme_overview.SECTIONS_BY_ROLE`): an org_admin gets the funnel, the money and what
      // needs attention; a reviewer gets their own cases and nothing else; a QC gets their queue.
      //
      // ⚠ **`finance` IS ON THIS ROW THOUGH IT IS NOT ON APPLICATIONS — AND THAT IS NOT AN
      // INCONSISTENCY.** Applications is a list of PEOPLE: `_b40_scope` is 'none' for finance, so
      // that row can only ever 403, which is why the registry omits it. The Overview hands finance
      // AGGREGATES ONLY — committed, paid, remaining, spent, per month, per category — and never a
      // name, a file or a verdict, because none of those is in a section it is given. The widening
      // is deliberate and recorded in `docs/decisions.md` and `role-matrix.md`; the server is what
      // enforces it, and `test_the_key_set_per_role_is_exact` is what pins it.
      //
      // ⚠ **NO `needsProgramme`.** This row READS: with no gift chosen it describes everything the
      // organisation fence allows, under a neutral heading — the Applications rule, not
      // Configuration's (nor, since 2026-09-28, Payments'/Spending's). See `NavItem.needsProgramme` for why the test is CONSEQUENCE, not scope.
      //
      // ⚠ `programmeConfig` is `exact: true`, so `/admin/programme/overview` cannot be swallowed by
      // `/admin/programme`; longest match then makes this child the active row.
      // ⚠ 'I' for the Information about a gift — 'D' is the platform Dashboard, 'O' is
      // Organisations, and 'G' can never be a chord because it is the prefix that arms one.
      { id: 'programmeOverview', href: '/admin/programme/overview',
        labelKey: 'admin.nav.programmeOverview', chord: 'I', scope: 'programme',
        roles: ['super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'source_partner'],
        gate: { mode: 'always' } },
      { id: 'applications', href: '/admin/scholarship', labelKey: 'admin.scholarship.nav', chord: 'A',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'qc', 'reviewer', 'source_partner'],
        perms: ['see_all', 'review'], gate: { mode: 'always' } },
      // ⚠ SCHOLARS (student maintenance S2, 2026-10-29): every funded student from award acceptance
      // to closure. Sprint S1 (owner 2026-11-09): ITS OWN KEY, `scholars` — no longer the Applications
      // rule. The server (`base.scholars_scope`) opens it to a super and a `scholars` holder (the admin
      // preset, the lead tier, a saved set naming it); `review`, `qc` and `see_all` alone are refused.
      // A team member is admitted by `perms` whatever their label (`admitsRow`), so a reviewer whose
      // saved set names `scholars` keeps the row. `source_partner` keeps its row: the page renders the
      // source's own `SourceScholars` (`components/source/*`, its own endpoint). S1-h: a MENTOR reads its
      // CURRENT students here, read-only — a mentor login by its role, staff who mentor by the mentor record
      // (`staffMentors`, the signal My students reads); the server narrows the list and answers 404 for
      // anyone else's (`scholars_scope` 'mentor'). `needsProgramme`: a list of one gift's scholars (a mentor
      // has no gift door, so it never waits on one). 'M' for maintenance — 'S' is Students. No badge yet.
      { id: 'scholars', href: '/admin/scholars', labelKey: 'admin.scholars.nav', chord: 'M',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'source_partner', 'mentor'],
        perms: ['scholars'], staffMentors: true, gate: { mode: 'always' }, needsProgramme: true },
      // ⚠ ANNOUNCEMENTS (S8), SURVEYS (S9), DEVELOPMENT (S10): super / org_admin / admin, each endpoint's own rule (`may_post` / `may_make`); no `needsProgramme` — each belongs to the organisation.
      { id: 'announcements', href: '/admin/programme/announcements', labelKey: 'admin.announcements.nav',
        scope: 'programme', roles: ['super', 'org_admin', 'admin'], door: 'announcements', gate: { mode: 'always' } },
      { id: 'surveys', href: '/admin/programme/surveys', labelKey: 'admin.surveys.nav', // S9: as Announcements
        scope: 'programme', roles: ['super', 'org_admin', 'admin'], door: 'surveys', gate: { mode: 'always' } },
      { id: 'development', href: '/admin/programme/development', labelKey: 'admin.development.nav', scope: 'programme', roles: ['super', 'org_admin', 'admin'], door: 'development', gate: { mode: 'always' } },
      // ⚠ **PAYMENTS AND SPENDING MOVED HERE FROM ORGANISATION — TD-241, owner, 2026-09-11.**
      // Money is raised, released and spent PER GIFT: `PaymentRun.programme` has said so since
      // P2b, and a run that spanned two gifts would pay one benefactor's students from
      // another's money. They were under Organisation only because that is where the console
      // put money-shaped things before gifts existed as a scope.
      // ⚠ **THEY MOVE TOGETHER, ALWAYS** (recorded when the owner first raised this): released
      // money and spent money are two halves of one story, and a console where one is
      // gift-scoped and the other is not invites a reader to compare two different totals.
      // ⚠ The scope here changes what the BREADCRUMB says and what each page SENDS; it is not
      // a fence. Both endpoints re-resolve `?programme=<code>` inside the caller's own
      // organisation (`_AdminBase._gift_narrowing`), so a client ignoring it reaches the same
      // rows the organisation fence already allowed.
      // ⚠ `needsProgramme` on BOTH (2026-09-28) — you enter a gift first. See that field's note.
      { id: 'payments', href: '/admin/payments', labelKey: 'admin.payments.title', chord: 'Y',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'finance'],
        perms: ['payments_prepare', 'payments_check', 'payments_approve'],
        gate: { mode: 'always' }, needsProgramme: true, badge: 'paymentsWaiting' },
      // ⚠ `finance` is DELIBERATELY ABSENT, unlike its neighbour. The backend refuses it for
      // the same reason: `_b40_scope` promises a finance admin never sees student data beyond
      // the Payments allowlist, and this screen carries names beside purchases. This row and
      // `_SpendingBase` (the `spending` key since #39 S3) must agree; the page's test pins the pair.
      // ⚠ NOT 'G' — that is CHORD_PREFIX, the key that ARMS a chord, so it can never be one.
      // 'X' for expenses; 'S' is Students and 'P' is Sponsors.
      { id: 'spending', href: '/admin/spending', labelKey: 'admin.spending.nav', chord: 'X',
        scope: 'programme', roles: ['super', 'org_admin', 'admin'], perms: ['spending'],
        gate: { mode: 'always' }, needsProgramme: true },
      // ⚠ MOVED HERE FROM ORGANISATION (TD-229, 2026-10-03): the agreement is PER GIFT (owner,
      // 2026-09-04). Same roles. No `needsProgramme` — with no gift chosen it lists every gift's.
      // Not a fence: the endpoint re-resolves `?programme=` inside the caller's own organisation.
      { id: 'contracts', href: '/admin/contracts', labelKey: 'admin.contracts.title', chord: 'K',
        scope: 'programme', roles: ['super', 'org_admin'], gate: { mode: 'always' } },
      { id: 'programmeConfig', href: '/admin/programme', labelKey: 'admin.programme.config.nav',
        chord: 'W', scope: 'programme', roles: ['super', 'org_admin'], gate: { mode: 'always' },
        exact: true, match: ['/admin/programme/years'], needsProgramme: true },
    ],
  },
  {
    // ⚠ A MENTOR's OWN GROUP (student maintenance S7c, 2026-11-01). A mentor is not staff: its rows
    // are Programmes, My students, Scholars (sprint S1, read-only) and Profile, and nothing else
    // (`outsiderMustLeave` sends it back from any other page). The server is the fence —
    // `admin/mentor/students/` serves the caller's CURRENT students only and refuses every other role. A mentor lands on Programmes (T5c P5, the first row they may open);
    // this group is reached from the programme card or the menu, and no staff role ever sees it.
    scope: 'mentoring',
    headingKey: 'admin.nav.group.mentoring',
    items: [
      { id: 'myStudents', href: '/admin/my-students', labelKey: 'admin.nav.myStudents',
        scope: 'mentoring', roles: ['mentor'], staffMentors: true, gate: { mode: 'always' } },
    ],
  },
  {
    scope: 'utility',
    headingKey: 'admin.nav.group.utility',
    items: [
      // Yours, not any scope's — the sidebar skips this group (SIDEBAR_SCOPES) and the account
      // and help menus render it instead.
      { id: 'profile', href: '/admin/profile', labelKey: 'admin.profile',
        scope: 'utility', roles: ROLE_NAMES, gate: { mode: 'always' } },
      { id: 'guide', href: '/admin/guide', labelKey: 'admin.guideNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' } },
      { id: 'faq', href: '/admin/faq', labelKey: 'admin.faqNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' } },
    ],
  },
]

/** Flat view of the registry. */
export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items)

/** Routes that render WITHOUT the admin chrome (login / OAuth callback / set-password). */
export const CHROMELESS: readonly string[] = [
  '/admin/login', '/admin/auth/', '/admin/set-password',
]

export interface NavContext {
  role: AdminRoleName
  probes: Record<ProbeKey, ProbeState>
  /** The served `/admin/role/` `permissions` (#39 S3). Absent = the rows' `roles` answer. */
  permissions?: readonly string[] | null
  /**
   * Is the gift the person is looking at KNOWN? Read by `needsProgramme` rows only.
   *
   * ⚠ OPTIONAL, AND `undefined` MEANS SHOW. Checked as `=== false`, the same shape as
   * `reviewer_profile_complete` in `adminLanding.ts` and for the same reason: a caller that has
   * not been taught about this dimension must never lose a menu row because of it. The module
   * docstring's rule — "absence from the registry must never invent a new block" — applies to a
   * missing FIELD exactly as it applies to a missing route.
   *
   * The shell is the one caller that supplies it, from `useProgrammeScope().chosen`. That value
   * fills itself in when there is exactly ONE gift, so on a single-gift tenant — production
   * today — this is always true and nothing changes.
   */
  programmeChosen?: boolean
  /**
   * The current path, so the Programme group can fold away until you are inside a gift.
   *
   * Owner, 2026-09-14: *"Hide Programme section. It can only be accessed by clicking on
   * Programmes above."* See `programmeGroupFolded` for the rule and the two roles it must not
   * apply to. OPTIONAL, and absent means NOT folded — a caller that has not been taught about
   * this dimension must never lose a menu group because of it (the module rule, again).
   *
   * ⚠ NOT `programmeChosen`. That looked like the obvious signal and it is the wrong one: it
   * fills itself in whenever a tenant has exactly ONE gift, which is production today, so on
   * it the group would never fold at all. Whether you are INSIDE a gift is a fact about the
   * page you are on, and only the path knows that.
   */
  pathname?: string
  mentoring?: boolean   // S7d: `/admin/role/` `mentoring` (a staff member who mentors now); absent = no
  tables?: readonly string[] | null   // Team tables T1: `/admin/role/` `tables`; absent = the rows' roles
  pageKeys?: readonly string[] | null   // T5c P4: `/admin/role/` `page_keys` (a row's `door`); absent = its roles
}

/** A context with nothing probed yet — the safe default (see `canSee`). */
export const NO_PROBES: Record<ProbeKey, ProbeState> = { requests: 'unknown', billing: 'unknown' }

/**
 * THE one place `is_super_admin ? 'super' : role` lives. It was written out eleven times
 * across the layout and the admin pages before this.
 *
 * Falls back to 'reviewer' for an unknown/missing role, preserving the previous behaviour of
 * `admin/layout.tsx` — the least-privileged role, so a payload we don't understand shows the
 * smallest menu rather than the largest.
 */
export function effectiveRole(
  role: { role?: string; is_super_admin?: boolean } | null | undefined,
): AdminRoleName {
  if (!role) return 'reviewer'
  if (isSuperRole(role)) return 'super'
  return (ROLE_NAMES as readonly string[]).includes(role.role ?? '')
    ? (role.role as AdminRoleName)
    : 'reviewer'
}

/**
 * Visibility of ONE item.
 *
 * Probe semantics are exact: 'unknown' (not yet loaded) and 'dark' (404) BOTH mean not-live,
 * matching today's comment in `admin/administration/page.tsx` — "null = dark OR not yet
 * loaded". Treating 'unknown' as live would flash a dark feature in during the round trip.
 */
export function canSee(item: NavItem, ctx: NavContext): 'show' | 'soon' | 'hide' {
  if (!admitsRow(item, ctx.role, ctx.permissions, ctx.mentoring, ctx.tables, ctx.pageKeys)) return 'hide'
  // Hidden, never 'soon': a "Soon" pill promises a feature that is coming, and this one is here
  // already — it is waiting on the reader, not on us. See `NavItem.needsProgramme`.
  if (item.needsProgramme && ctx.programmeChosen === false && hasGiftDoor(ctx.role)) return 'hide'
  if (item.gate.mode === 'probe') {
    return ctx.probes[item.gate.probe] === 'live' ? 'show' : item.gate.dark
  }
  return 'show'
}

export interface VisibleNavItem extends NavItem { state: 'show' | 'soon' }
export interface VisibleNavGroup extends Omit<NavGroup, 'items'> { items: VisibleNavItem[] }

/** Groups → the items this context may see, with empty groups dropped. */
export function visibleNav(ctx: NavContext): VisibleNavGroup[] {
  return NAV_GROUPS
    .map((g) => ({
      ...g,
      items: g.items
        .map((i) => ({ ...i, state: canSee(i, ctx) }))
        .filter((i): i is VisibleNavItem => i.state !== 'hide'),
    }))
    .filter((g) => g.items.length > 0)
    .filter((g) => g.scope !== 'programme' || !programmeGroupFolded(ctx))
}

/**
 * Should the Programme group be hidden right now?
 *
 * Owner, 2026-09-14: the Programme section is reached by opening **Programmes** and choosing a
 * gift; it is not a standing fixture of the menu. So it shows only while the page you are on is
 * INSIDE a gift, and folds away on every organisation and platform page.
 *
 * ⚠ **TWO ROLES ARE EXEMPT, AND IT IS NOT A COURTESY.** A reviewer's and a QC's only menu row is
 * Applications, which lives in this group — fold it and they log in to an empty sidebar with no
 * way to their own queue. And a plain `admin` or `finance` cannot fold it either, for a subtler
 * reason: the Programmes page shows its gift cards only to super and org_admin (it applies the
 * programmes endpoint's own gate — that page's rule, not this module's), so those two roles have
 * **no door** into a gift; folding the group would strand them on the outside for good.
 *
 * That is why the exemption is keyed on `programmeConfig`'s roles rather than on a role list:
 * whoever may open a gift's configuration is exactly whoever the Programmes page offers a gift
 * to click on. The two facts are one fact, stated once. The day the cards open to another role,
 * the fold follows without anyone remembering to update it here.
 */
export function programmeGroupFolded(ctx: NavContext): boolean {
  if (ctx.pathname === undefined) return false
  if (activeItem(ctx.pathname)?.scope === 'programme') return false
  return hasGiftDoor(ctx.role)
}

/** May this role step INTO a gift from the Programmes page? ONE answer for the fold above,
 *  `needsProgramme` in `canSee` and `useGiftGate` (2026-09-28): with a door a money row waits for
 *  a gift and its page redirects there; without one the row stays and the page asks. */
export function hasGiftDoor(role: AdminRoleName): boolean {
  return NAV_ITEMS.find((i) => i.id === 'programmeConfig')?.roles.includes(role) ?? false
}

/** True when `pathname` is `href` or sits underneath it. The boundary matters: without the
 *  trailing slash, '/admin/scholarshipX' would match '/admin/scholarship'. */
function under(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + '/')
}

/**
 * The registry item a path belongs to, by LONGEST match.
 *
 * Longest-match is load-bearing, not a nicety: '/admin' is a prefix of every admin route, so
 * a first-match implementation would resolve everything to the dashboard. Each href and each
 * `match` prefix is asserted individually in the tests.
 *
 * This replaces the hand-written `isActive` in `admin/layout.tsx`, which special-cased three
 * routes and forgot three others — `/admin/requests`, `/admin/sources` and `/admin/billing`
 * highlighted nothing at all.
 */
export function activeItem(pathname: string): NavItem | undefined {
  let best: NavItem | undefined
  let bestLen = -1
  for (const item of NAV_ITEMS) {
    // A reserved slot has no page, so nothing can be "inside" it.
    if (item.placeholder) continue
    for (const href of [item.href, ...(item.match ?? [])]) {
      const hit = item.exact ? pathname === href : under(pathname, href)
      if (hit && href.length > bestLen) {
        best = item
        bestLen = href.length
      }
    }
  }
  return best
}

/**
 * May this role open this route at all? Replaces the `isSuper` / `allowed` / `canManage`
 * expression each admin page derived for itself.
 *
 * Route-level only. Anything finer than "can you open the page" — `canCreate` on Payments,
 * `canManage` on Administration, `canWrite` / `canQc` / `canAssign` in `officerCockpit.ts` —
 * stays where it is. This registry is not a permission engine.
 *
 * An unknown route returns true: absence from the registry must never invent a new block.
 */
export function canAccess(href: string, role: AdminRoleName, permissions?: readonly string[] | null,
                          mentoring?: boolean, tables?: readonly string[] | null, pageKeys?: readonly string[] | null): boolean {
  const item = activeItem(href)
  return item ? admitsRow(item, role, permissions, mentoring, tables, pageKeys) : true
}

/** An item paired with its already-translated label, which is all the palette needs. */
export interface LabelledNavItem { item: NavItem; label: string }

// The palette ranking and the chord jump live in a leaf beside this file (#39 S3, moves only).
export { searchNav, chordTarget, CHORD_PREFIX } from './navigationJump'

/**
 * Where an authenticated admin lands after sign-in. THE one home for the rule — `adminLanding()`
 * delegates here.
 *
 * ⚠⚠ THIS USED TO SEND EVERY NON-REVIEWER TO `/admin`, AND FOUR ROLES WERE THEN BOUNCED OFF IT.
 * `/admin` is `roles: ['super', 'partner']` — the platform dashboard — so org_admin, admin, qc and
 * finance each landed on a page they may not open and were redirected by `admin/page.tsx`. The old
 * docstring called that "a double hop worth removing later" and it was worse than a hop:
 *
 *   · **`finance` was bounced onto Applications, which `finance` may not see.** The registry omits
 *     it from `applications` deliberately (`_b40_scope` → 'none', so it can only 403), and the
 *     scholarship page had no client guard to catch the contradiction. A finance user's first
 *     screen was a page built for somebody else.
 *   · **org_admin and admin never reached their own Overview**, which is the front door the owner
 *     designed and the only place the gifts are listed (2026-09-08).
 *
 * The fix is to stop naming a destination and DERIVE one: the first route in the registry this
 * role may actually open, in the registry's own order — Platform, then Organisation, then
 * Programme, then Utility. Same answer as before for super and partner; the right answer for the
 * other four. This is exactly the lesson from 2026-06-16, when the reviewer role was added and
 * "post-login landing" was not revisited: adding a role is not done until every place that
 * branches on "is this user an admin?" has been re-checked.
 *
 * ⚠ `NO_PROBES` ON PURPOSE. A dark-shipped page is not a landing page: with nothing probed,
 * `canSee` reports 'soon'/'hide' for Billing and Requests, and only a 'show' is a candidate. A
 * placeholder is skipped for the older reason — there is no page there.
 *
 * ⚠ NOT `programmeChosen: false`. Landing happens before the shell has fetched anything, so the
 * question "which gift" has not been asked yet; answering it here would send an org_admin
 * somewhere different depending on a race. The field is omitted, which means show — see
 * `NavContext`.
 *
 * The Utility group is last and holds Profile, which every role may open, so this always returns
 * something. `/admin/profile` is the honest floor for an account that can reach nothing else.
 */
export function defaultRoute(role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null } | null | undefined,
                             reviewerProfileComplete?: boolean): string {
  // A newly-invited reviewer is held on their profile until the compulsory fields are filled.
  // Checked as `=== false` so an OLD payload that omits the field never traps anyone.
  if (role?.role === 'reviewer' && reviewerProfileComplete === false) return '/admin/profile'

  const r = effectiveRole(role)
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.placeholder) continue
      // ⚠ NO `tables` (T1, owner 2026-11-03): a person lands by their FIRST hat, never on a page a key seat added.
      if (canSee(item, { role: r, probes: NO_PROBES, permissions: role?.permissions }) === 'show') return item.href
    }
  }
  return '/admin/profile'
}
