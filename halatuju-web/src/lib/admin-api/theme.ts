/**
 * Layer 1 A2: the organisation's own colours — the draft, its contrast checks, publishing
 * it, and reverting to a previous version.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Layer 1 A2: the organisation's colours ───────────────────────────────────

/** One contrast pair, measured. `key` is shared with `lib/contrast.ts` and with the server, so a
 *  `400 unreadable` names rows the screen has already drawn. */
export interface ThemeCheck {
  key: string
  ratio: number
  min_ratio: number
  passes: boolean
}

/** One version of an organisation's colours — either what is live, or the unpublished draft. */
export interface ThemeVersion {
  /** The hex the stored shades were derived from. */
  colour: string
  /** The readability check for THIS version's shades, so a number is never orphaned from its
   *  colour. Every pair is reported, passing ones included. */
  checks: ThemeCheck[]
}

export interface OrganisationTheme {
  organisation: { code: string; name: string }
  /** ⚠ WHAT VISITORS SEE. null = the platform stylesheet is in charge. */
  live: ThemeVersion | null
  /** ⚠ BEING WORKED ON, and served to nobody. null = there is no unpublished work. Kept SEPARATE
   *  from `live` on purpose: folding them into one "colour" invites a screen that cannot say which
   *  one an applicant is looking at, which is the whole thing A3 exists to make clear. */
  draft: ThemeVersion | null
  /** What Revert would put back. '' means the platform colours — a real answer, because reverting
   *  the first colour an organisation ever published lands them there. */
  previous_colour: string
  can_revert: boolean
  published_at: string
  published_by: string
  /** The LIVE shades, both modes, or null. Never the draft's. */
  tokens: { light: Record<string, string>; dark: Record<string, string> } | null
}

/** GET the organisation's colours. `org` is optional for an org_admin (their one organisation) and
 *  required for a super when more than one tenant exists (`organisation_required`). */
export async function getOrganisationTheme(
  org?: string, options?: ApiOptions,
): Promise<OrganisationTheme> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/organisation/theme/${q}`, options)
}

/** Save the DRAFT. **What visitors see is untouched.** The SERVER derives the shades and refuses an
 *  unreadable colour with `unreadable` plus the failing pair keys — the browser's own check is a
 *  courtesy, never the gate. */
export async function saveOrganisationThemeDraft(
  colour: string, org?: string, options?: ApiOptions,
): Promise<OrganisationTheme> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(`/api/v1/admin/scholarship/organisation/theme/${q}`, 'PUT', { colour }, options)
}

/** Throw the draft away. What is live stays live — that is what makes trying a colour safe. */
export async function discardOrganisationThemeDraft(
  org?: string, options?: ApiOptions,
): Promise<OrganisationTheme> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(`/api/v1/admin/scholarship/organisation/theme/${q}`, 'DELETE', null, options)
}

/** The draft becomes what visitors see. Refuses `no_draft` when there is nothing to publish. */
export async function publishOrganisationTheme(
  org?: string, options?: ApiOptions,
): Promise<OrganisationTheme> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(
    `/api/v1/admin/scholarship/organisation/theme/publish/${q}`, 'POST', {}, options)
}

/** Put back the colour that was live before. Reverting the FIRST colour ever published lands the
 *  organisation on the platform stylesheet — a correct outcome, not an error. */
export async function revertOrganisationTheme(
  org?: string, options?: ApiOptions,
): Promise<OrganisationTheme> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(
    `/api/v1/admin/scholarship/organisation/theme/revert/${q}`, 'POST', {}, options)
}

