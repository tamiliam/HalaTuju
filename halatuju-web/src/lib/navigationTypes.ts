/**
 * The admin route registry's TYPES (T5c P5, moved verbatim out of `navigation.ts`, a moves-only commit,
 * because that file sat at its size line and P5 adds the Programmes row). Every name is re-exported from
 * `navigation.ts`, so every importer is unchanged. `NavItem` is `NavItemOf<AdminRoleName>` there: the role
 * type stays beside the list it is held to, and this leaf imports nothing back (`importCycles.test.ts`).
 */
import type { DoorName, StaffPermission } from './staffPermissions'

/** The scope a page belongs to. Platform → Organisation → Programme is the platform hierarchy
 *  (`apps/scholarship/models.py` Programme docstring); `utility` is "yours, not any scope's". */
export type NavScope = 'platform' | 'organisation' | 'programme' | 'mentoring' | 'utility'

/** Scopes the sidebar renders as groups (N2). `utility` lives in the help/account menus.
 *  `mentoring` (student maintenance S7c) is the MENTOR's own group: My students, nobody else's. */
export const SIDEBAR_SCOPES: readonly NavScope[] = ['platform', 'organisation', 'programme', 'mentoring']

/** Dark-shipped features. One key per probe the shell runs; see `NavGate`. */
export type ProbeKey = 'requests' | 'billing'

/**
 * Counts the sidebar may render on an item, and the bell may repeat.
 *
 * A UNION rather than a second hardcoded prop (TD-205): the shell used to thread
 * `pendingSponsors: number` through three components and test `i.badge === 'pendingSponsors'` at
 * the render site, so a second badge meant a fourth place to remember. The shell now passes one
 * `Partial<Record<BadgeKey, number>>` and the row looks its own key up.
 */
export type BadgeKey = 'pendingSponsors' | 'requestsWaiting' | 'paymentsWaiting'  // last: #39 S2
/** 'unknown' = not yet loaded, 'dark' = the endpoint 404d (flag off), 'live' = it answered. */
export type ProbeState = 'unknown' | 'live' | 'dark'

export type NavGate =
  | { mode: 'always' }
  /**
   * Dark-shipped: availability is inferred from the API answering, never from a client flag
   * (`REQUESTS_ENABLED` / `BILLING_USAGE_ENABLED` stay server-side env vars). `dark` says how
   * to render while not-live — 'hide' reproduces today's hidden Requests card, 'soon' the
   * disabled "Coming soon" Billing card (`admin/administration/page.tsx`).
   */
  | { mode: 'probe'; probe: ProbeKey; dark: 'hide' | 'soon' }

export interface NavItemOf<R extends string = string> {
  /** Stable id — the snapshot key and the ⌘K palette key. Never derived from the href. */
  id: string
  href: string
  /** Full i18n key. Must resolve in en/ms/ta or `scripts/check-i18n.js` fails the build. */
  labelKey: string
  scope: NavScope
  /** UX visibility only — see the module docstring. */
  roles: readonly R[]
  /** #39 S3: a TEAM MEMBER opens this row by holding any of these keys (`admitsRow`), not by role. */
  perms?: readonly StaffPermission[]
  adminKeys?: readonly StaffPermission[]   // Team tables T1: the Admins table ALSO opens it by a key (`admitsRow`)
  door?: DoorName   // T5c P4: the server door (`pageDoors`): served `page_keys` decide; none = `roles` / `adminKeys`
  gate: NavGate
  /** Extra path prefixes that make this item the active one (sub-pages with no entry). */
  match?: readonly string[]
  /**
   * Match this href EXACTLY, never as a prefix. Set on the index route `/admin`, which is a
   * page rather than a section: its siblings are separate routes, not its children. Without
   * this, `/admin` prefixes every admin path, so an unrecognised route would resolve to the
   * dashboard and silently inherit ITS roles — inventing a block the registry never declared.
   */
  exact?: boolean
  badge?: BadgeKey
  /**
   * This row ACTS ON one particular gift, so it stays hidden until we know which gift that is.
   *
   * ⚠ THE TEST IS CONSEQUENCE, NOT SCOPE. Both Programme rows belong to a gift; only one of them
   * would go WRONG without a choice. `programmeConfig` writes a gift's settings, so opening it
   * with nothing chosen can only ever produce a question (`ChooseProgramme`) — a row whose sole
   * outcome is to ask is noise, and worse, it invites somebody to edit the wrong gift's rules.
   * `applications` is a READ: with nothing chosen it lists every gift under a neutral heading,
   * which is a true answer, just a less specific one. That is the same line the gift-switcher
   * sprint drew inside the pages (2026-09-08); this applies it to the menu.
   * ⚠ `payments`/`spending` carry it since 2026-09-28 — but it hides a row only for a role with a
   * door to the gifts (`hasGiftDoor`); for admin and finance the page's own question IS the door.
   *
   * ⚠ AND IT IS WHY NO ROLE NEEDS AN EXEMPTION. A reviewer's ONLY sidebar group is Programme
   * (`navigation.test.ts` pins it), so hiding the group outright would leave them with an empty
   * sidebar and no way back to their own queue. Marking the CONFIGURE row and not the WORK row
   * means the group can never empty, for anybody — no `if (role === 'reviewer')` anywhere.
   * (The WHOLE group does fold since 2026-09-14 — `programmeGroupFolded` — and that rule has to
   * carry the exemption this one avoids, for exactly the reason given here.)
   *
   * ⚠ STILL VISIBILITY ONLY. See the module docstring: the fence is the endpoint, and a person
   * who types `/admin/programme` reaches exactly what they always did.
   */
  needsProgramme?: boolean
  /**
   * The second key of the `G`-then-X jump, upper-case, e.g. 'A' → Applications.
   *
   * OPTIONAL on purpose, inverting the usual "make a new dimension required" rule: most routes
   * will never earn a chord, and a required field would force a fake letter onto every one of
   * them. The guard is a test instead — `navigation.test.ts` asserts the letters are unique
   * across the WHOLE registry, single upper-case characters, and never on a placeholder.
   *
   * Uniqueness is global rather than per-role deliberately. Two roles seeing different pages
   * under one letter would make the sidebar's own hint wrong for somebody, and "what does G T
   * do" must have exactly one answer.
   */
  chord?: string
  /**
   * A reserved slot: the sidebar renders it disabled with a "soon" pill and it links nowhere.
   *
   * ⚠ **NO SLOT IS RESERVED TODAY.** `billingRates` was the last one and its page shipped on
   * 2026-09-11, so the field is now unused — kept because the rule it encodes is what governs
   * the next request for one, not because anything wears it.
   *
   * ⚠ THE FOUR THAT WENT SHOW WHERE THE LINE IS (owner, 2026-09-03). `billingRates` earned its
   * slot: its endpoint SHIPPED on 2026-07-27, super-only, and what was missing was only the
   * page — a slot for a thing that demonstrably existed, and it was duly filled. The Programme
   * group's three (reviewer scoping, the fund, the rules) each reserved a page for work nobody
   * had scoped, and each guessed its SHAPE wrongly: rules are a section of the programme's own
   * configuration, reviewer scoping is a field on a reviewer's record, and the fund is a report.
   * lessons.md (N4, 2026-07-28) names the cost: "a placeholder for future work encodes an
   * assumption about that work — if the assumption is not yours to make, do not leave the
   * placeholder."
   *
   * The test for a reserved slot is therefore not "will we build it" but "do we already know
   * where it goes". `navigation.test.ts` pins the behaviour and the current population.
   */
  placeholder?: boolean
  /** S7d: a staff member who mentors NOW (`NavContext.mentoring`) sees this row too; their landing never
   *  changes (`defaultRoute` ignores it). Visibility only — `mentor_desk.mentor_of` decides. */
  staffMentors?: boolean
}
