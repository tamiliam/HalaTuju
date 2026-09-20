/**
 * Gift programmes and their intake years (Sabah S2b): what a programme asks for, the apply
 * copy a student reads, and the cohort years it runs.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Gift programmes and their intake years (Sabah S2b, 2026-09-02) ──────────────────────────────
//
// The screens an `org_admin` uses to stand up a gift without an engineer. Every endpoint is fenced
// server-side on the programme's own organisation; cross-tenant is 404, never 403. Nothing here is
// an access check — it is the org fence's own answer, rendered.

/** The requirement columns the tick boxes write. `null` means the test is NOT APPLIED (S2a) —
 *  the value IS the switch, so unticking is writing null and there is no companion boolean. */
export interface ProgrammeRequirements {
  min_spm_a_count: number | null
  /** The TOTAL strong count, not the extra beyond the A's: "4 A− plus 1 more at B+" is stored 5.
   *  The screen shows the difference, because that is how the rule is set and read. */
  min_spm_bplus_count: number | null
  min_stpm_pngk: number | null
  min_merit_score: number | null
  income_ceiling: number | null
  per_capita_ceiling: number | null
}

/** One language's block of the gift's public apply-page copy. */
export interface AdminApplyCopyBlock {
  title: string
  intro: string
  criteria: string[]
}

/** The gift's copy as STORED — an absent locale means that box is blank, not English. */
export type AdminApplyCopy = Partial<Record<'en' | 'ms' | 'ta', AdminApplyCopyBlock>>

export interface AdminProgramme {
  id: number
  code: string
  name_en: string
  name_ms: string
  name_ta: string
  is_active: boolean
  /**
   * What the PUBLIC apply page says about this gift. `{}` = the platform's own wording.
   *
   * ⚠ THE STORED MAP, VERBATIM — the reader-facing endpoint folds ms/ta onto English, this does
   * NOT. The tab is an editor: a blank Malay box must render blank, or the first save would
   * silently promote the English text into a field nobody typed.
   */
  apply_copy: AdminApplyCopy
  /**
   * Race / ethnicity / religion words found in that copy. ADVISORY — nothing refuses on it.
   *
   * ⚠ `decisions.md` 2026-05-25 removed ethnicity from the public copy because MyNadi's s44(6)
   * tax status requires the programme not to discriminate by race. The owner ruled 2026-09-09
   * that this WARNS rather than refuses: an ethnicity-scoped gift is lawful in Malaysia and the
   * constraint is our funder's, not the platform's.
   */
  apply_copy_sensitive: string[]
  /**
   * Where the gift is in its life — the badge on its card.
   *
   * ⚠ SERVED, NOT DERIVED HERE (owner ruling, 2026-09-07). `draft` and `archived` are BOTH
   * `is_active: false`; the server splits them on whether anybody has ever applied. The card
   * carries an `applications` count, so this COULD be worked out in the browser — do not. It is
   * the same rule the Delete control reads, and two copies of it would put a **Draft** badge
   * beside a Delete button greyed because students applied.
   *
   * `is_active` stays beside it because it is what the PATCH writes; `lifecycle` is how it READS.
   */
  lifecycle: 'draft' | 'active' | 'archived'
  intake_years: number
  /**
   * Everyone who has ever applied to this gift.
   *
   * ⚠ COUNTED THROUGH THE ROUND AS WELL AS THE COLUMN, server-side. An application's gift is
   * denormalised and set once, so a round moved between gifts leaves its applications on the old
   * one — and this number has to agree with the Applications list, which narrows the same way.
   */
  applications: number
  /**
   * How many of them have EVER been awarded — not how many sit at `awarded` right now.
   *
   * ⚠ `awarded` is one stage in awarded → active → maintenance → closed, so a live status count
   * would FALL as students progress. Served from the never-cleared `awarded_at` stamp; do not
   * re-derive it here from anything on this card.
   */
  awarded: number
  /** The year currently taking applications, or null. A PROGRAMME is never open — a year is. */
  open_year: number | null
  /**
   * What is holding this gift, so the Delete control can be DISABLED with the reason showing —
   * or `null` when nothing is and it may be deleted.
   *
   * ⚠ SERVED, NEVER DERIVED HERE. This payload carries `intake_years` and `applications`; it has
   * never carried benefactors, money or payment runs. A button disabled on what the client happens
   * to know would go green for a gift held by a donation and refuse only after the phrase was
   * typed — rarer than the bug it replaces, and more surprising. The delete endpoint refuses from
   * the SAME function that fills this, so the two cannot disagree.
   *
   * ⚠ AN INTAKE YEAR IS NOT ON THIS LIST, and its absence is the owner's ruling (2026-09-07):
   * students hold a gift, a year on its own does not. An EMPTY year is deleted along with the
   * gift. Do not add `has_intake_years` back by reading `intake_years > 0` here — that is exactly
   * the derived-from-the-card mistake the paragraph above refuses.
   */
  delete_blocked_by:
    | 'has_applications' | 'has_benefactors'
    | 'has_money' | 'has_payment_runs' | null
  delete_blocked_count: number
  /**
   * The whole link a student follows to apply to THIS gift.
   *
   * ⚠ SERVED WHOLE — do not rebuild it from `code` and `window.location.origin`. The console and
   * the student site share an origin today, so that would be right, and would go silently wrong
   * the day a tenant is served from its own domain; the server already answers that per
   * organisation. It is also the one string somebody copies onto a poster.
   *
   * ⚠ PER GIFT, NOT PER YEAR (owner ruling). The code is the gift's permanent identifier, so a
   * printed link survives every intake; the server picks whichever round is open.
   */
  apply_url: string
}

export interface AdminIntakeYear {
  id: number
  code: string
  name: string
  year: number
  is_open: boolean
  is_active: boolean
  applications: number
  requirements: ProgrammeRequirements
  /** ⚠ THE ROUND'S STATED WINDOW, AND IT DESCRIBES — IT OPENS NOTHING (owner, 2026-09-06).
   *  `is_open` is the switch and stays the switch; these two say when the round is MEANT to run.
   *  `null` means no window was stated, which is a normal round — render a dash, not an error. */
  opens_on: string | null
  closes_on: string | null
  /**
   * Where the round is in its life — **SERVED, never derived here** (`views_admin.round_state`).
   *
   * ⚠⚠ FOUR STATES, THREE BEHAVIOURS, AND THE MIDDLE ONE IS LOAD-BEARING:
   *   · `open`     — anyone may start and submit.
   *   · `closed`   — no NEW applications; **anyone already started may still finish**. That grace
   *                  period is real: the 2026 round closed on 1 July and thirty students who were
   *                  part-way through submitted between then and the 7th.
   *   · `finished` — nobody may submit. **TERMINAL** — the server refuses to reopen one.
   *   · `draft`    — never opened, nobody has applied.
   */
  state: 'draft' | 'open' | 'closed' | 'finished'
  /** When the round was closed for good, and by whom. Null while it can still be reopened. */
  finished_at: string | null
  finished_by: string
  /** How many applicants have STARTED and not yet submitted — the people a finish would shut out.
   *  ⚠ Counted as `status='shortlisted'` server-side; `submitted_at` is `auto_now_add` and never
   *  null, so it cannot answer this. */
  unsubmitted: number
}

export async function getAdminProgrammes(options?: ApiOptions) {
  return adminFetch<{ programmes: AdminProgramme[] }>(
    '/api/v1/admin/scholarship/programmes/', options)
}

/** Create a gift. It arrives INACTIVE whatever is sent — switching it on is a separate press,
 *  because an active second programme changes live behaviour the moment it exists. */
export async function createAdminProgramme(
  body: { code: string; name_en: string; name_ms?: string; name_ta?: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminProgramme>('/api/v1/admin/scholarship/programmes/', 'POST', body, options)
}

export async function updateAdminProgramme(
  id: number,
  // ⚠ `code` IS EDITABLE, AND THE SERVER KEEPS THE OLD ONE AS AN ALIAS. Sending it unchanged is a
  // no-op — no alias is written — so the rename dialog may post the box as it stands.
  // ⚠ `apply_copy` IS ALL-OR-NOTHING PER LANGUAGE and the SERVER validates it — length caps,
  // no markup, and "title + intro + a bullet, or none". Send `{}` to return the gift to the
  // platform's own wording.
  body: Partial<{
    code: string; name_en: string; name_ms: string; name_ta: string; is_active: boolean
    apply_copy: AdminApplyCopy
  }>,
  options?: ApiOptions,
) {
  return adminMutate<AdminProgramme>(
    `/api/v1/admin/scholarship/programmes/${id}/`, 'PATCH', body, options)
}

/**
 * Draft this gift's Malay or Tamil apply-page copy from ITS OWN saved English.
 *
 * ⚠⚠ IT RETURNS A DRAFT AND SAVES NOTHING. The caller puts the block in the boxes; the wording
 * only ever reaches a public page through `updateAdminProgramme`, pressed by a person. That is
 * the same division the document engines keep — the model proposes, a human decides.
 *
 * ⚠ IT READS THE SAVED ENGLISH, not what is on screen, so a caller must not offer it while the
 * English has unsaved edits: the draft would translate wording the reader can no longer see.
 * ⚠ It is BILLABLE — one model call per invocation.
 */
export async function draftApplyCopy(
  id: number, locale: 'ms' | 'ta', options?: ApiOptions,
): Promise<AdminApplyCopyBlock> {
  const r = await adminMutate<{ locale: string; block: AdminApplyCopyBlock }>(
    `/api/v1/admin/scholarship/programmes/${id}/apply-copy/draft/`, 'POST', { locale }, options)
  return r.block
}

/**
 * Delete a gift that never became anything.
 *
 * ⚠ `confirm` MUST BE THE GIFT'S OWN CODE, and the SERVER checks it — this is not a client
 * courtesy. A destructive verb any caller can fire with an empty body is one mis-wired button
 * away from deleting somebody's gift.
 *
 * ⚠ IT REFUSES WITH A NAMED REASON rather than a generic failure: `has_applications`,
 * `has_benefactors`, `has_money`, `has_payment_runs`. Those are the relations the model already
 * protects — a gift that has taken a student or a ringgit cannot be deleted.
 *
 * ⚠ THE GIFT'S EMPTY INTAKE YEARS ARE DELETED WITH IT (owner, 2026-09-07). A year is rules, not
 * students, so it never refuses; one that holds an application is caught as `has_applications`.
 */
export async function deleteAdminProgramme(
  id: number,
  confirm: string,
  options?: ApiOptions,
) {
  return adminMutate<void>(
    `/api/v1/admin/scholarship/programmes/${id}/`, 'DELETE', { confirm }, options)
}

export async function getAdminIntakeYears(programmeId: number, options?: ApiOptions) {
  return adminFetch<{
    programme: { id: number; code: string; name_en: string; is_active: boolean }
    years: AdminIntakeYear[]
  }>(`/api/v1/admin/scholarship/programmes/${programmeId}/years/`, options)
}

/** Create an intake year. It arrives CLOSED — opening is what lets real students in, and gets its
 *  own deliberate press. Requirement keys may be omitted; a `null` unticks that test. */
export async function createAdminIntakeYear(
  programmeId: number,
  body: { code: string; name: string; year: number; opens_on?: string | null; closes_on?: string | null }
    & Partial<ProgrammeRequirements>,
  options?: ApiOptions,
) {
  return adminMutate<AdminIntakeYear>(
    `/api/v1/admin/scholarship/programmes/${programmeId}/years/`, 'POST', body, options)
}

export async function updateAdminIntakeYear(
  id: number,
  body: Partial<{ name: string; is_open: boolean; opens_on: string | null; closes_on: string | null }>
    & Partial<ProgrammeRequirements>,
  options?: ApiOptions,
) {
  return adminMutate<AdminIntakeYear>(
    `/api/v1/admin/scholarship/intake-years/${id}/`, 'PATCH', body, options)
}

/**
 * Close a round FOR GOOD. **Terminal — nothing in the product undoes this.**
 *
 * ⚠ ITS OWN ENDPOINT, and `confirm` must be the round's own code. The server checks it; the typed
 * box is not the guard, it is the pause. The round must already be closed (`still_open` otherwise).
 */
export async function finishAdminIntakeYear(
  id: number, confirm: string, options?: ApiOptions,
) {
  return adminMutate<AdminIntakeYear>(
    `/api/v1/admin/scholarship/intake-years/${id}/finish/`, 'POST', { confirm }, options)
}
