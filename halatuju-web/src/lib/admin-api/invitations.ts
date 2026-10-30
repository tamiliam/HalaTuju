/**
 * Organisation → Invitations: every invitation this organisation has sent, of every kind,
 * and inviting a sponsor.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Invitations (Organisation → Invitations) ─────────────────────────────────

/** The four kinds the page is organised by. `source` invites a source's person (source sign-in S2). */
export type InvitationKind = 'admins' | 'reviewers' | 'source' | 'sponsors'

export interface InvitationRow {
  id: number
  name: string
  email: string
  role: string
  status: 'invited' | 'expired' | 'no_reply' | 'accepted' | 'revoked'
  sent_at: string | null
  send_count: number
  /** Tri-state: true sent, false a real failure, **null not recorded** (every backfilled row). */
  last_send_ok: boolean | null
  last_send_error: string
  accepted_at: string | null
  /** The staff account behind this invitation. **Null for a sponsor**, which creates none. */
  admin_id: number | null
  is_active: boolean | null
  paused: boolean | null
  /** Which gift this invitation was for. **Empty means EVERY gift** — the honest reading for
   *  a staff invitation and for every row written before the column existed. Never render a
   *  blank as a gift name. */
  programme: string
  programme_name: string
  /** Which SOURCE a source invitation signs somebody in for (source sign-in S2); null otherwise,
   *  and absent on a payload from before S2. */
  source_id?: number | null
  source_name?: string | null
  source_code?: string | null
}

/** A source's sign-in state on the Sources list and the invite form (`source_invite.sign_in_states`):
 *  `joined` — an active user has signed in; `invited` — active users, none signed in yet. */
export type SourceSignIn = 'none' | 'invited' | 'joined'

/** One source user on the Source tab's roster (`source_users.source_kind_extras`). */
export interface SourceUserRow {
  id: number
  name: string
  email: string
  source_id: number
  source_name: string
  source_code: string
  organisation: string | null
  is_active: boolean
  /** Null = not signed in yet (never "not recorded" for a source user). */
  first_seen_at: string | null
  last_seen_at: string | null
  /** May THIS caller Resend / Remove — the server's own rule, so no button is offered it refuses. */
  manageable: boolean
  invitation: { status: string; sent_at: string | null; send_count: number
                last_send_ok: boolean | null; last_send_error: string } | null
}

/** An ACTIVE source the invite form may pick. */
export interface InvitableSource {
  id: number; code: string; name: string; organisation: string
  sign_in: SourceSignIn; user_count: number
}

export interface InvitationsPayload {
  kind: InvitationKind
  invitations: InvitationRow[]
  /** Unanswered count for EVERY kind, not just the one on screen — only one table is visible at a
   *  time, so a waiting invitation elsewhere would otherwise be invisible. */
  waiting: Record<InvitationKind, number>
  /** EVERY invitation ever sent, per kind. ⚠ `invitations` holds the WAITING ones only, so an
   *  empty table has two meanings — nobody asked yet, or everybody asked has arrived — and this is
   *  the only thing that tells them apart. Without it the empty state would have claimed "nobody
   *  has been invited" over thirteen reviewers who had all accepted. */
  totals: Record<InvitationKind, number>
  /** Roles this caller may grant in this kind. ⚠ NOT the roles LISTED: `org_admin` appears in the
   *  admins table but is appointed at platform level by a super, never from here. */
  invitable_roles: string[]
  /** Gift choices for the sponsor invite form. ACTIVE only, matching what the POST accepts —
   *  an invitation is a prompt to register TODAY, so a gift that is not open yet would be an
   *  invitation through a door that does not open. */
  programmes: Array<{ id: number; code: string; name: string }>
  /** `?kind=source` only (source sign-in S2): every source user, and the sources to pick from. */
  source_users?: SourceUserRow[]
  sources?: InvitableSource[]
}

export async function getInvitations(kind: InvitationKind, options?: ApiOptions) {
  return adminFetch<InvitationsPayload>(`/api/v1/admin/invitations/?kind=${kind}`, options)
}

/** Invite a SPONSOR. Creates no account: the link goes to the ordinary public registration, where
 *  they consent, sign the terms and are vetted exactly as anybody else.
 *
 *  `programme_id` records WHICH GIFT the organisation meant (S-ASSIGN). Omit it and the server
 *  takes the organisation's sole active gift, or refuses `programme_required` when there are
 *  several — it never picks silently. */
export async function inviteSponsor(
  data: { email: string; name?: string; note?: string; programme_id?: number }, options?: ApiOptions,
) {
  return adminMutate<{ id: number; emailed: boolean }>(
    '/api/v1/admin/invitations/', 'POST', { audience: 'sponsor', ...data }, options)
}


/** TD-214: withdraw an invitation nobody has answered. The row is kept and reads `revoked`; a
 *  staff invitation's never-used account is switched off with it. 400 `not_open` once answered. */
export async function cancelInvitation(id: number, options?: ApiOptions) {
  return adminMutate<{ id: number; status: 'revoked' }>(
    `/api/v1/admin/invitations/${id}/cancel/`, 'POST', {}, options)
}

/**
 * Invite a SOURCE's person (source sign-in S2). Either an existing source (`source_id`) or a NEW
 * one (`source_name` + `source_code`, optional contact details). Super or org_admin only.
 * Refusals arrive as `code`: `already_staff`, `code_taken`, `code_reserved`,
 * `code_and_name_required`, `source_inactive`, `bad_email`, `name_required`, `not_found`,
 * `organisation_required`, `not_configured`, `create_failed`.
 */
export async function inviteSource(
  data: {
    name: string; email: string; source_id?: number
    source_name?: string; source_code?: string
    contact_person?: string; contact_email?: string; phone?: string
  },
  options?: ApiOptions,
) {
  return adminMutate<{ id: number; admin_id: number; emailed: boolean; message: string }>(
    '/api/v1/admin/invitations/', 'POST', { audience: 'source_partner', ...data }, options)
}

/** Re-send a waiting source user's invitation (a fresh temporary password where we issued one). */
export async function resendSourceUser(id: number, options?: ApiOptions) {
  return adminMutate<{ message: string; emailed: boolean }>(
    `/api/v1/admin/source-users/${id}/resend/`, 'POST', {}, options)
}

/** Switch a source user off. The way back is to invite the same address for the same source. */
export async function revokeSourceUser(id: number, options?: ApiOptions) {
  return adminMutate<{ id: number; is_active: false; message: string }>(
    `/api/v1/admin/source-users/${id}/revoke/`, 'POST', {}, options)
}
