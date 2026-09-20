/**
 * Organisation → Invitations: every invitation this organisation has sent, of every kind,
 * and inviting a sponsor.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Invitations (Organisation → Invitations) ─────────────────────────────────

/** The four kinds the page is organised by. `source` is reserved and empty today. */
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

