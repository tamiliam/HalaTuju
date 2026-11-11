/**
 * The staff of an organisation: who they are, inviting one, revoking one, resending an
 * invitation, and setting a password.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (168-218, 284-352, 821-862). The invitation READER
 * (`./invitations`) was written in the middle of them, and `inviteAdmin` 500 lines later.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Admin management ────────────────────────────────────────────────

export interface AdminItem {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  role: 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance' | 'member'
  is_active: boolean
  org_name: string | null
  owning_org_id?: number | null
  owning_org_name?: string | null
  created_at: string
  /** A reviewer who has stepped back. Serialised here as well as on the Reviewers table, so the
   *  two screens showing the same people can no longer disagree about it. */
  paused?: boolean
  paused_at?: string | null
  /** NULL means NOT RECORDED, never "never signed in" — everyone predating 2026-08-03 is empty. */
  first_seen_at?: string | null
  last_seen_at?: string | null
  /** ⚠ MAY THIS VIEWER ACT ON THIS ROW? Everybody in the tenant is LISTED; only some may be
   *  revoked — an org_admin sees their fellow organisation admins and may not touch them. Served
   *  by the same check the write endpoints enforce, so the screen cannot draw a refused button. */
  manageable?: boolean
  /** Common profile S2: a ~1-hour signed URL of their photo, or null. Staff screens only. */
  photo_url?: string | null
  /** M1a (owner O16): no group table shows a phone, so the list serves one ONLY to a super's platform
   *  screens (Organisations, Partners: `getAdmins(options, true)`, `?phones=1`), and then only when the
   *  person shows it to the team. Absent otherwise; the person page has it. */
  phone?: string | null
  /** Whether this account may be DELETED outright rather than only revoked: a programme-staff role
   *  with NO recorded work. Reviewers and QC too since D6 (Sprint T2, 2026-11-08), which reversed
   *  2026-09-09's "never a reviewer". */
  deletable?: boolean
  /** T2 review N2: nobody may ever delete this row here — draw no Delete. */
  delete_never?: boolean
  /** T2 review N3: Revoke / Restore may be offered (false: a super, yourself, the sole org admin). */
  revocable?: boolean
  /** What this person has DONE, `{what: count}`, empty when nothing. The reason a delete is
   *  refused, so the screen can name it instead of greying a button for no visible cause. */
  work?: Record<string, number>
  /** Request #39 Sprint 4 — People's permission chips. `custom` = a set saved on the editor; the two
   *  lists are what differs from the preset (both empty on it), decided by the server. */
  custom?: boolean
  permissions_added?: string[]
  permissions_removed?: string[]
  /** THIS row's dormancy threshold, resolved for the person's own organisation on the server
   *  (Org Config Sprint C). `standingOf` reads it; the old constant is only its fallback. */
  dormant_days?: number
  /** Team tables T2 (served on both Team lists): see `TeamSeat`. */
  tables?: string[]
  lead?: boolean
  admin_keys?: string[]
  reviewer_keys?: string[]
  remove?: TeamRemove
  /** M1b (TD-606): their unfinished payment runs, served on the Admins list only; the tip of a Remove greyed
   *  `run_in_progress` names it. */
  runs_in_progress?: number
  /** The invitation behind this person. Null when they predate the record. */
  invitation?: {
    /** Decided by the server (`invitations.status_of`); never re-derived on this side. */
    status: 'invited' | 'expired' | 'no_reply' | 'accepted' | 'revoked'
    sent_at: string | null
    send_count: number
    /** Tri-state: true sent, false a real failure, **null not recorded** (every backfilled row). */
    last_send_ok: boolean | null
    last_send_error: string
    expires_at: string | null
    credential_issued: boolean
  } | null
}

// ── Team tables T2: Team -> Admins / Reviewers -> Add, and Remove from ──────────────────────────────

export type TeamTableName = 'admins' | 'reviewers'

/** Per table the person sits in AND the viewer may act on: `null` = Remove is accepted; a code = why not
 *  (`last_table`, `mentors_only`, `has_open_cases`, `lead_fixed`, …). Absent = no link at all. Served by
 *  the same rules the endpoint applies (`staff_tables_admin.row_fields`). */
export type TeamRemove = Partial<Record<TeamTableName, string | null>>

/** One person the Add sheet offers (`admin/team/<table>/candidates/`). */
export interface TeamCandidate {
  id: number
  name: string
  email: string
  /** The organisation admin (only ever offered for Reviewers, and only to themselves or a super). */
  lead: boolean
  /** A mentor's own login: added, they join the team as staff. */
  mentor_only: boolean
  tables: string[]
  consequences: string[]
}

export interface TeamTablePlan {
  id: number
  table: TeamTableName
  action: 'add' | 'remove'
  dry_run: boolean
  role: string
  role_changed: boolean
  added: string[]
  removed: string[]
  consequences: string[]
  finance_check_off: boolean
  /** The change makes them role `admin`, which OPENS the admin work pages (Announcements, Surveys,
   *  Development, Sources, Mentors): a Remove from Reviewers (lead ruling Q2b) or a mentor login added to
   *  Admins. Said in plain words on the confirm (review 2026-11-03). */
  opens_admin_pages: boolean
  /** T3: leaving their last staff table, they stay on as a mentor login (My students, their own students on Scholars read-only, and Profile; S1). */
  becomes_mentor?: boolean
  /** M1b: leaving their last group (sent with `to_no_group`), they stay on as a member in No group. */
  becomes_member?: boolean
}

export async function getTeamCandidates(table: TeamTableName, options?: ApiOptions) {
  return adminFetch<{ table: TeamTableName; candidates: TeamCandidate[] }>(
    `/api/v1/admin/team/${table}/candidates/`, options)
}

/** Add a person to a table, or remove them from it; with `dryRun`, what it WOULD do. A refusal throws
 *  with the server's sentence and its `code` (the whole body on `.body`, counts included). Never touches
 *  a sign-in; never emails. `toNoGroup` (M1b): a Remove from their LAST group, which leaves them a member
 *  in No group — without it the server refuses `last_table`. */
export async function changeTeamTable(table: TeamTableName, adminId: number, action: 'add' | 'remove',
                                      dryRun: boolean, options?: ApiOptions, toNoGroup = false) {
  return adminMutate<TeamTablePlan>(`/api/v1/admin/team/${table}/`, 'POST',
    { admin_id: adminId, action, dry_run: dryRun, ...(toNoGroup ? { to_no_group: true } : {}) }, options)
}

/** M1b: one accepted member of the team on the Staff list (`GET admin/staff/`). No phone, no email
 *  (owner O16). `groups` empty = No group; a suspended row's groups are what a Restore gives back. */
export interface StaffRow {
  id: number
  kind: 'staff' | 'mentor'
  /** Their Mentors record (a mentor login's own door for Suspend and Delete). */
  mentor_id: number | null
  name: string
  photo_url: string | null
  last_seen_at: string | null
  groups: ('admins' | 'reviewers' | 'mentors')[]
  lead: boolean
  suspended: boolean
  manageable: boolean
  /** What is still waiting on them, per group: `admins` the registry fields (`runs_in_progress`, …),
   *  `reviewers.open_cases`, `mentors.scholars_now`. Always all three groups. */
  work: { admins: Record<string, number>; reviewers: { open_cases: number }; mentors: { scholars_now: number } }
  deletable: boolean
  delete_never: null | 'self' | 'not_manageable' | 'sole_org_admin' | 'has_unfinished_work'
  /** What a Delete does: `archive` keeps their name on past records; `erase` removes the row. */
  delete_outcome: 'erase' | 'archive' | null
  revocable: boolean
}

/** The Staff list. A super may name an `organisation`; everybody else reads their own. */
export async function getStaffList(options?: ApiOptions, organisation?: number) {
  const q = organisation === undefined ? '' : `?organisation=${organisation}`
  return adminFetch<{ staff: StaffRow[] }>(`/api/v1/admin/staff/${q}`, options)
}

export async function getAdmins(options?: ApiOptions, phones = false) {
  return adminFetch<{ admins: AdminItem[] }>(`/api/v1/admin/admins/${phones ? '?phones=1' : ''}`, options)
}

/** Delete a staff account outright. ⚠ Only ever offered for a programme-staff role with NO recorded
 *  work; the server refuses everything else — 409 `has_work` carries the counts that stopped it,
 *  400 `not_deletable` means the role can never be deleted (a super, a partner), 400 `last_org_admin`
 *  the organisation's only active admin, and 404 a row this caller may not manage (another
 *  organisation's, a mentor or a source login — those have their own doors). */
export async function deleteAdmin(adminId: number, options?: ApiOptions, archive = false) {
  // M1b: `archive` when the Staff list says the outcome is archive — their name stays on past records.
  // `login: 'failed'` = the row is gone but their sign-in could not be removed; the message says so.
  return adminMutate<{ message: string; login?: string; archived?: boolean }>(
    `/api/v1/admin/admins/${adminId}/`, 'DELETE', archive ? { archive: true } : undefined, options)
}

/** Switch a person within their pair (Admin ↔ Finance, Reviewer ↔ QC — `lib/staffRole`).
 *  `dryRun` asks what the switch WOULD do without writing: `consequence` says whether the
 *  payment finance check switches on or off, so the confirmation can say so before the click.
 *  A refusal throws with the server's sentence as the message and its `code`. */
export async function changeAdminRole(adminId: number, role: string, dryRun: boolean,
                                      options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/role/`, {
    method: 'PATCH', headers, body: JSON.stringify({ role, dry_run: dryRun }),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(body.error || `Action failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || ''
    throw err
  }
  return body as { id: number; from: string; to: string; dry_run: boolean
                   consequence: 'finance_check_on' | 'finance_check_off' | null
                   /** #39 S4: a saved custom set of permissions goes back to the new preset. */
                   permissions_reset?: boolean
                   /** #39 S4 review fix 4: the editor's consequence codes for this switch. */
                   consequences?: string[]
                   /** S7d: the switch ends this staff member's mentoring (Admin → Finance). */
                   stops_mentoring?: boolean }
}

/**
 * Sprint T3 (2026-11-09): ONE person page for every team member. The admin, reviewer and mentor detail
 * payloads each carry this same block (`apps/scholarship/staff_person.py`), so the page's header and
 * Profile tab read one shape whichever link opened it. Optional on each payload: an api a few minutes
 * behind this page omits it.
 *
 * ⚠ THE HOME ADDRESS IS NEVER IN IT; the phone only under the screen's existing rule (role-matrix.md).
 */
export interface TeamPersonBlock {
  admin_id: number
  /** Their Mentors-table record while they mentor (the mentor detail's id), else null. */
  mentor_id: number | null
  name: string
  email: string
  /** The tables they sit in (`staff_tables.tables`) — the "Also in" chips' own source. */
  tables: string[]
  /** The organisation admin ("Admin (lead)"). */
  lead: boolean
  /** A mentor's own login: no staff role, so no permissions to change (D8). */
  mentor_only: boolean
  is_active: boolean
  paused: boolean
  joined_at: string | null
  /** False = no sign-in RECORDED yet, never proof they have not come. */
  signed_in: boolean
  last_seen_at: string | null
  /** '' / null / [] = not filled in ("Not given"). */
  profile: {
    job_title: string
    about: string
    qualification: string
    university: string
    graduation_year: number | null
    field_of_study: string
    phone: string
    /** Spoken conversationally or better, in en · ms · ta order. */
    languages: string[]
    other_language: string
  }
  /** T3 review fix 1: false = the mentor route withheld the background fields (job title, about,
   *  qualification, university, graduation year, field of study) — this viewer opens the person by no
   *  admin or reviewer route. The page then draws no row for them (not "Not given": they are not shown
   *  to you, which is not the same as not filled in). Missing (an older api) = served. */
  profile_full?: boolean
}

/** What one person may do, as the editor reads it (request #39 Sprint 4). `keys` are the switches
 *  the editor may show, in the server's catalogue order; `editable` is false for a row nobody edits
 *  (an organisation admin, a super, a partner, your own). */
export interface StaffPermissionsView {
  id: number
  name: string
  role: string
  is_active: boolean
  editable: boolean
  preset: string[]
  permissions: string[]
  custom: boolean
  keys: string[]
  /** The person page's header (Team → a person → Permissions, 2026-10-22). Optional: a payload from
   *  an api deployed a few minutes behind this page omits them, and the page must still draw. */
  email?: string
  created_at?: string
  /** False = no sign-in RECORDED yet (an invitee), never proof they have not come. */
  signed_in?: boolean
  paused?: boolean
  /** The latest changes, newest first (the server caps the list). */
  history?: StaffPermissionChangeRow[]
  /** Team tables T3: the tables the person sits in — the Permissions tab shows one section per table. */
  tables?: string[]
  /** Sprint T2 (D6): may this viewer DELETE them outright (no work on record), and the work that
   *  stops it, `{what: count}` — the Admins table's two fields, by the same server rule. */
  deletable?: boolean
  /** T2 review N2: nobody may ever delete this row here — draw no Delete. */
  delete_never?: boolean
  /** T2 review N3: Revoke / Restore may be offered (false: a super, yourself, the sole org admin). */
  revocable?: boolean
  work?: Record<string, number>
  /** M1a: may this viewer change them (false: a fellow organisation admin, yourself — read-only). */
  manageable?: boolean
  /** M1a (O12): each table's preset keys, so a one-table Permissions tab says Custom against its own. */
  table_presets?: Partial<Record<TeamTableName, string[]>>
  /** Sprint T3: the person page's header and Profile tab. */
  person?: TeamPersonBlock
}

/** One recorded change of somebody's permissions. `kind: 'role_change'` = a Change role put the set
 *  back to the new role's preset. ⚠ `by_super` with a blank `by` is a change made by the HalaTuju
 *  team: the server never hands a super's address to an organisation, so the screen names the team.
 *  `by_migration` = a data migration made it (nobody clicked); `by` is blank and the screen says so. */
export interface StaffPermissionChangeRow {
  kind: 'edit' | 'role_change' | string
  role: string
  before: string[]
  after: string[]
  added: string[]
  removed: string[]
  at: string
  by: string
  by_super: boolean
  /** Absent from an older api. */
  by_migration?: boolean
}

/** The server's answer to a save or a dry run: the set it would hold, what differs from the set it
 *  holds now, and what else the save would do (`consequences`, worded by the screen). */
export interface StaffPermissionsPlan {
  id: number
  role: string
  dry_run: boolean
  changed: boolean
  permissions: string[]
  custom: boolean
  added: string[]
  removed: string[]
  consequences: string[]
}

export async function getStaffPermissions(adminId: number, options?: ApiOptions) {
  return adminFetch<StaffPermissionsView>(`/api/v1/admin/admins/${adminId}/permissions/`, options)
}

/** Save a set, or with `dryRun` ask what saving it would do. A refusal throws with the server's
 *  sentence and its `code` (`has_open_cases`, `would_leave_people`, …). */
export async function saveStaffPermissions(adminId: number, permissions: string[], dryRun: boolean,
                                           options?: ApiOptions) {
  return adminMutate<StaffPermissionsPlan>(`/api/v1/admin/admins/${adminId}/permissions/`, 'PATCH',
    { permissions, dry_run: dryRun }, options)
}

/** Suspend (`revoke`) or restore a staff sign-in. A refusal throws with `code` and the whole body
 *  (`self`, `last_org_admin`, `has_scholars` with `scholars_now`). */
export async function revokeAdmin(adminId: number, action: 'revoke' | 'restore', options?: ApiOptions) {
  return adminMutate<unknown>(`/api/v1/admin/admins/${adminId}/revoke/`, 'PATCH', { action }, options)
}

/** Re-send a partner's sign-in details, rotating their temporary password. The new password goes
 *  ONLY to their inbox — it is never returned here. Safe to call any number of times. */
export async function resendAdminInvite(adminId: number, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/resend/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Resend failed: ${res.status}`)
  }
  return res.json() as Promise<{ message: string; emailed: boolean }>
}

// A temp-password partner sets their OWN password server-side (the service role applies it without
// the re-auth the client updateUser({password}) would demand). Scoped to the caller + must_change_password.
export async function adminSetPassword(password: string, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/set-password/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Set password failed: ${res.status}`)
  }
  return res.json() as Promise<{ ok: boolean }>
}

export async function inviteAdmin(
  data: {
    email: string
    name: string
    role?: 'admin' | 'partner' | 'reviewer' | 'qc' | 'org_admin' | 'finance'
    org_id?: number
    new_org_name?: string
    new_org_code?: string
    contact_person?: string
    org_phone?: string
    /** Multi-gift (owner, 2026-11-06): the gifts a reviewer invite covers. `[]` = every gift,
     *  the default. Each must be the organisation's own (the server refuses another with a 404). */
    programme_ids?: number[]
  },
  options?: ApiOptions
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/invite/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  // A refusal throws with the SERVER'S sentence and its `code`. Request #39: an address already on
  // the caller's team is `already_on_team` (named, with where to go); any other existing account is
  // `not_invitable`, one sentence that says nothing about it. Both are served — no string here.
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.error || `Invite failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || ''
    throw err
  }

  // `emailed` matters: the welcome email is the ONLY carrier of the temporary password, so a
  // failed send leaves the new partner with no way in until the owner presses Resend.
  return res.json() as Promise<{
    message: string
    org: string | null
    role: string
    already_registered: boolean
    emailed: boolean
  }>
}

