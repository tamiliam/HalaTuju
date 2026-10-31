/**
 * The Profile page's card registry — ONE list of cards, each with ONE rule saying who sees it
 * (common profile S1, owner ruling 2026-10-31; roadmap docs/plans/2026-10-31-common-profile-roadmap.md).
 *
 * The page (`app/admin/profile/page.tsx`) renders exactly `cardsFor(ctx)`, in `order`, for every
 * role — a source user included. Nothing else on the page decides whether a card appears.
 *
 * ⚠ THE REVIEWER CARDS FOLLOW THE `review` PERMISSION, NOT THE REVIEWER ROLE. An admin given
 * `review` gets them; a reviewer whose `review` was taken away loses them (the saved details are
 * kept on the server, never deleted). A super holds every key but is NEVER shown them — a super is
 * not a reviewer and is not asked for a reviewer's credentials (the 2026-06 bug fix, kept).
 *
 * ⚠ THE FIRST-SIGN-IN HOLD IS NOT HERE AND DOES NOT MOVE. It stays Reviewer-ROLE only
 * (`reviewer_onboarding.reviewer_profile_complete`, `adminLanding.mustCompleteProfile`,
 * `navigation.defaultRoute`); anyone else holding `review` sees a reminder, never a block.
 *
 * ⚠ A MENTOR (student maintenance S7a, 2026-10-31) works with students too: `worksWithStudents` — a
 * holder of `review` or a mentor — drives the qualification and address cards and the "show my phone
 * to my students" switch, the web twin of `staff_contact.works_with_students`. `takingPart` (the
 * pause) stays on `reviewsCases`: a mentor is never handed cases. The `mentoring` card is a mentor's
 * alone. Photo is staff-only, as for everybody (the You card says so).
 *
 * Visibility, never the fence: every card's endpoint re-checks on the server.
 */

export type ProfileCardId =
  | 'you' | 'contact' | 'mentoring' | 'access' | 'qualifications' | 'address' | 'takingPart'
  | 'organisation' | 'signin' | 'activity'

export interface ProfileCardContext {
  role: string | undefined
  permissions: readonly string[] | null | undefined
  isSuper: boolean
}

export interface ProfileCard {
  id: ProfileCardId
  order: number
  show: (ctx: ProfileCardContext) => boolean
}

const everyone = () => true
/** The reviewer cards' rule: holds `review`, and is not a super (who holds every key). */
export const reviewsCases = (ctx: ProfileCardContext): boolean =>
  !ctx.isSuper && !!ctx.permissions?.includes('review')
/** Somebody students meet: a `review` holder or a mentor (S7a); the server decides the same way. */
export const worksWithStudents = (ctx: ProfileCardContext): boolean =>
  reviewsCases(ctx) || (!ctx.isSuper && ctx.role === 'mentor')
const isMentor = (ctx: ProfileCardContext): boolean => !ctx.isSuper && ctx.role === 'mentor'

export const PROFILE_CARDS: readonly ProfileCard[] = [
  { id: 'you', order: 10, show: everyone },
  // S2 (2026-10-31): everyone — the phone and "show my phone to my team"; the "share with students
  // I interview" switch inside it stays a `review` holder's (`ContactCard`).
  { id: 'contact', order: 20, show: everyone },
  // S7a: the mentor's own area of mentoring, under Contact (the MentorProfile board's order).
  { id: 'mentoring', order: 25, show: isMentor },
  { id: 'access', order: 30, show: everyone },
  { id: 'qualifications', order: 40, show: worksWithStudents },
  { id: 'address', order: 50, show: worksWithStudents },
  { id: 'takingPart', order: 60, show: reviewsCases },
  { id: 'organisation', order: 70,
    show: (ctx) => !ctx.isSuper && (ctx.role === 'partner' || ctx.role === 'source_partner') },
  { id: 'signin', order: 80, show: everyone },
  // S5: My activity — everyone, OWN rows only (the server reads `actor = the caller`, every role).
  // It sits in the page's side column (`SIDE_CARDS`), not under Sign-in.
  { id: 'activity', order: 90, show: everyone },
]

/** The cards drawn in the page's right-hand column on a wide screen (stacked last on a phone). */
export const SIDE_CARDS: ReadonlySet<ProfileCardId> = new Set<ProfileCardId>(['activity'])

/** The cards this person sees, in page order. */
export function cardsFor(ctx: ProfileCardContext): ProfileCardId[] {
  return [...PROFILE_CARDS].sort((a, b) => a.order - b.order).filter((c) => c.show(ctx)).map((c) => c.id)
}

/** The filters of the My activity card — `?kind=` on `GET admin/me/activity/`. */
export type ActivityFilter = 'all' | 'students' | 'money' | 'profile'

const MONEY_PERMS = ['spending', 'payments_prepare', 'payments_check', 'payments_approve']
const CASE_PERMS = ['review', 'see_all', 'qc']

/**
 * The My activity chips THIS person is offered (common profile S5), in order. All and "Profile and
 * sign-in" are everyone's; Students only for somebody who acts on cases (a case permission, or a role
 * whose work is cases — a source witnesses its students' agreements); Money only for somebody with a
 * money power (a money permission, or a role that signs or records money). A reviewer gets All /
 * Students / Profile and sign-in (the approved mock-up); a mentor and a referral partner All / Profile.
 *
 * ⚠ A CHIP IS A SHORTCUT, NEVER A FENCE. The list holds the person's own rows only; a row of a kind
 * whose chip is not offered (a power taken away since) is still under All. The role OR the
 * permission counts, so a power that is a role's (an admin recording a credit) is not missed.
 */
export function activityFilters(ctx: ProfileCardContext): ActivityFilter[] {
  const has = (keys: readonly string[]) => keys.some((k) => ctx.permissions?.includes(k))
  const role = ctx.role ?? ''
  const out: ActivityFilter[] = ['all']
  if (ctx.isSuper || has(CASE_PERMS) || ['org_admin', 'admin', 'qc', 'reviewer', 'source_partner'].includes(role)) {
    out.push('students')
  }
  if (ctx.isSuper || has(MONEY_PERMS) || ['org_admin', 'admin', 'finance'].includes(role)) out.push('money')
  out.push('profile')
  return out
}

/** The context for the signed-in person, from what `/admin/role/` served. */
export function profileContext(role: {
  role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null
} | null | undefined): ProfileCardContext {
  const isSuper = role?.role === 'super' || !!role?.is_super_admin
  return { role: isSuper ? 'super' : role?.role, permissions: role?.permissions, isSuper }
}

/** The permission keys that have a plain-word name (`admin.perm.<key>.name`). `manage_team` has
 *  none: it is the organisation admin's fixed power and is said by that role's own line. */
const NAMED_PERMS = ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check',
  'payments_approve'] as const

/**
 * "You can" — the i18n keys of the plain-word lines for this person, from role + permissions.
 * A super gets one line (everything); a role with powers that are not catalogue keys gets its
 * role line first (organisation admin, referral partner, source); then one line per named key held.
 */
export function accessLines(ctx: ProfileCardContext): string[] {
  if (ctx.isSuper) return ['admin.myProfile.can.super']
  const lines: string[] = []
  if (ctx.role === 'org_admin') lines.push('admin.myProfile.can.org_admin')
  if (ctx.role === 'partner') lines.push('admin.myProfile.can.partner')
  if (ctx.role === 'source_partner') lines.push('admin.myProfile.can.source_partner')
  if (ctx.role === 'mentor') lines.push('admin.myProfile.can.mentor')
  for (const key of NAMED_PERMS) {
    if (ctx.permissions?.includes(key)) lines.push(`admin.perm.${key}.name`)
  }
  if (!lines.length) lines.push('admin.myProfile.can.profileOnly')
  return lines
}
