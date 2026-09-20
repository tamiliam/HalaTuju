/**
 * What this admin may see (the nav/IA breadcrumb switchers), and the two layers of settings
 * beneath it: what a PROGRAMME asks for, and what the ORGANISATION has tuned.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (3536-3569, 3672-3710, 3795-3840) — the colours
 * module was written between the two configuration layers.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── nav/IA N3a: the breadcrumb switchers ─────────────────────────────────────
/** One organisation or programme the caller may LOOK AT. */
export interface AdminScopeOrg { id: number; code: string; name: string }
export interface AdminScopeProgramme extends AdminScopeOrg {
  organisation_id: number
  /** ⚠ An INACTIVE gift IS offered (2026-09-03): one is created inactive and configured before it
   *  is switched on, so that is the state an org_admin most often stands inside. The flag exists so
   *  the crumb can SAY so rather than naming a draft gift as if it were live. */
  is_active: boolean
}
export interface AdminScopes {
  organisations: AdminScopeOrg[]
  programmes: AdminScopeProgramme[]
}

/**
 * What this admin may look at — feeds the breadcrumb switchers.
 *
 * ⚠ NOT an access check and must never be used as one. The answer is derived server-side from
 * the same `owning_organisation` the org fence uses, so it cannot widen anything; a client that
 * ignores it reaches exactly the same data. The selection it produces is a DISPLAY preference —
 * it must not travel as a header, a cookie, or anything ambient, because that would relocate the
 * fence into the client.
 *
 * Never throws upward in the shell: a switcher is furniture, and a failed fetch must not take
 * the console down. Callers treat a rejection as "no scopes to offer".
 */
export async function getAdminScopes(
  lang: string,
  options?: ApiOptions,
): Promise<AdminScopes> {
  return adminFetch(`/api/v1/admin/scholarship/scopes/?lang=${encodeURIComponent(lang)}`, options)
}

// ── Layer 0 Sprint 5: what the programme asks for ────────────────────────────

export type ProgrammeItemState = 'off' | 'optional' | 'required'

export interface ProgrammeConfigItem {
  kind: 'document' | 'question'
  code: string
  label_key: string
  is_core: boolean
  default_state: ProgrammeItemState
  state: ProgrammeItemState
}

export interface ProgrammeConfiguration {
  programme: { code: string; name: string; organisation: string }
  /** Applications on this programme still inside the submission gate — COUNTED server-side. */
  live_applicants: number
  items: ProgrammeConfigItem[]
}

/** GET the configuration. `programme` is optional for an org_admin (their one programme) and
 *  required for a super when more than one exists (the server answers `programme_required`). */
export async function getProgrammeConfiguration(
  programme?: string, options?: ApiOptions,
): Promise<ProgrammeConfiguration> {
  const q = programme ? `?programme=${encodeURIComponent(programme)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/programme/configuration/${q}`, options)
}

/** PUT only the rows that changed. The server validates all-or-nothing (a core item switched
 *  off refuses the WHOLE save with `core_item`) and returns the re-read configuration. */
export async function saveProgrammeConfiguration(
  items: Pick<ProgrammeConfigItem, 'kind' | 'code' | 'state'>[],
  programme?: string, options?: ApiOptions,
): Promise<ProgrammeConfiguration> {
  const q = programme ? `?programme=${encodeURIComponent(programme)}` : ''
  return adminMutate(`/api/v1/admin/scholarship/programme/configuration/${q}`, 'PUT', { items }, options)
}

// ── Org Config Sprint A: the organisation's tunable values ──────────────────

/** One registry setting, for ONE organisation. */
export interface OrganisationConfigSetting {
  key: string
  group: string
  unit: string
  min: number
  max: number
  /** ⚠ null = FOLLOWING THE PLATFORM DEFAULT. The server never returns a copied default as the
   *  value — a copied default would go stale the day the platform default moves. */
  value: number | null
  /** The platform default, read live from the server's settings. */
  default: number
  /** Present (non-null) when the setting's vocabulary is a short LIST rather than a range —
   *  the row renders a menu of exactly these, not a number box (Org Config Sprint D: a slot
   *  step must divide an hour, so 5/10/15/20/30/60 is the whole vocabulary). */
  allowed?: number[] | null
}

export interface OrganisationConfiguration {
  organisation: { code: string; name: string }
  settings: OrganisationConfigSetting[]
}

/** GET the organisation's tunable values. `org` is optional for an org_admin (their one
 *  organisation) and required for a super when more than one tenant exists
 *  (`organisation_required`). */
export async function getOrganisationConfiguration(
  org?: string, options?: ApiOptions,
): Promise<OrganisationConfiguration> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/organisation/configuration/${q}`, options)
}

/** Save changed values. Send ONLY the keys being changed; `null` clears a key back to the
 *  platform default. The server validates everything before storing anything (all-or-nothing)
 *  and refuses with `out_of_range` / `bad_value` / `unknown_setting` plus the offending `key`. */
export async function saveOrganisationConfiguration(
  values: Record<string, number | null>, org?: string, options?: ApiOptions,
): Promise<OrganisationConfiguration> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(
    `/api/v1/admin/scholarship/organisation/configuration/${q}`, 'PUT', { values }, options)
}

