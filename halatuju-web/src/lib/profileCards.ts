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
 * Visibility, never the fence: every card's endpoint re-checks on the server.
 */

export type ProfileCardId =
  | 'you' | 'contact' | 'access' | 'qualifications' | 'address' | 'takingPart' | 'organisation' | 'signin'

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

export const PROFILE_CARDS: readonly ProfileCard[] = [
  { id: 'you', order: 10, show: everyone },
  // S1: phone + "share with students I interview" — review holders only. S2 widens it to everyone.
  { id: 'contact', order: 20, show: reviewsCases },
  { id: 'access', order: 30, show: everyone },
  { id: 'qualifications', order: 40, show: reviewsCases },
  { id: 'address', order: 50, show: reviewsCases },
  { id: 'takingPart', order: 60, show: reviewsCases },
  { id: 'organisation', order: 70,
    show: (ctx) => !ctx.isSuper && (ctx.role === 'partner' || ctx.role === 'source_partner') },
  { id: 'signin', order: 80, show: everyone },
]

/** The cards this person sees, in page order. */
export function cardsFor(ctx: ProfileCardContext): ProfileCardId[] {
  return [...PROFILE_CARDS].sort((a, b) => a.order - b.order).filter((c) => c.show(ctx)).map((c) => c.id)
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
  for (const key of NAMED_PERMS) {
    if (ctx.permissions?.includes(key)) lines.push(`admin.perm.${key}.name`)
  }
  if (!lines.length) lines.push('admin.myProfile.can.profileOnly')
  return lines
}
