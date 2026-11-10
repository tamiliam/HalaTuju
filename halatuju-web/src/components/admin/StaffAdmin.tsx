'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'

import {
  changeAdminRole, getAdmins, getOrgs, inviteAdmin, resendAdminInvite, revokeAdmin,
  type AdminItem, type OrgItem,
} from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { formatDate } from '@/lib/formatDate'
import PermissionChips from '@/components/admin/PermissionChips'
import StaffAvatar from '@/components/admin/StaffAvatar'
import { roleBadgeClass } from '@/lib/roleBadge'
import { switchableTo } from '@/lib/staffRole'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'
import { AlsoIn, RemoveControl } from '@/components/admin/TeamTables'
import StaffActions from '@/components/admin/StaffActions'

/**
 * Everything the four staff-facing pages share, in one place.
 *
 * The Administration hub used to be a single 414-line component doing five jobs; N3b split it
 * into real pages (Organisation overview, Staff, Organisations, Referral partners). This module
 * is what stops that split turning one copy of the staff table into four.
 *
 * ⚠ Every component here is at MODULE scope, deliberately. A sub-component declared inside its
 * parent is a new type on every render, so React unmounts and remounts the subtree — which in
 * this exact file previously stole focus from the invite inputs after each keystroke (see the
 * hoist comment the old page carried). Do not move these inside a component.
 */

export const inputCls =
  'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-brand-shape focus:border-brand-shape'

export type Banner = { type: 'success' | 'warning' | 'error'; text: string } | null

export function MessageBanner({ message }: { message: Banner }) {
  if (!message) return null
  return (
    <div className={`rounded-lg p-4 mb-6 ${
      message.type === 'success' ? 'bg-positive-50 border border-positive-200 text-positive-700'
      : message.type === 'warning' ? 'bg-caution-50 border border-caution-200 text-caution-700'
      : 'bg-critical-50 border border-critical-200 text-critical-600'}`}>{message.text}</div>
  )
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-ground-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-ground-500">{subtitle}</p>}
    </div>
  )
}

function roleBadge(rl: string) {
  return roleBadgeClass(rl)
}

export function StaffTable({ rows, showOrg = false, canAct = true, busyId, onResend, onToggle,
                             onDelete, onChangeRole, nameHref, soleOrgAdmin, team, showPhone = false, viewerSuper = false }: {
  rows: AdminItem[]
  showOrg?: boolean
  canAct?: boolean
  busyId?: number | null
  onResend?: (a: AdminItem) => void
  onToggle?: (a: AdminItem) => void
  /** Delete outright. Only ever called for a row the SERVER marked `deletable`. */
  onDelete?: (a: AdminItem) => void
  /** Is the viewer a super? Only a super is offered an organisation admin's Delete (Sprint T2). */
  viewerSuper?: boolean
  /** Switch within the pair (`lib/staffRole`). Offered only where a switch exists. */
  onChangeRole?: (a: AdminItem) => void
  /** Where the row's NAME links to, or null for plain text (2026-10-22: a team member's permissions
   *  live on their own page, so the name opens it). Absent = every name is plain text, which is
   *  what the platform's staff screens draw. The page decides which rows qualify. */
  nameHref?: (a: AdminItem) => string | null
  /** The sole active org_admin of a tenant cannot be revoked — the backend enforces it; this
   *  just keeps a dead affordance off the screen. */
  soleOrgAdmin?: (a: AdminItem) => boolean
  /** Team tables T2: this is Team -> ADMINS. The Role column becomes "Also in" (the organisation admin
   *  reads "Organisation admin (lead)"), and a row gains "Remove from Admins" where the server says the
   *  endpoint accepts it (`remove`). T3 (owner): no permission column — permissions are set only on the
   *  person's own page, Permissions tab (the name opens it). */
  team?: { onRemove: (a: AdminItem) => void }
  /** Draw each person's phone. Off unless a screen asks (fail closed): only the platform's staff screens do. */
  showPhone?: boolean
}) {
  const { t } = useT()
  // Team (owner 2026-11-08): read like Reviewers and Mentors — the email under the name, a Last seen
  // column after Status, the shared header style. The platform's staff screens keep their layout.
  // Four base columns either way: Name, Email (Team: Last seen instead), Role / Also in, Status.
  const cols = 4 + (showOrg ? 1 : 0) + (canAct ? 1 : 0)
  const th = team ? TH : 'px-4 py-3 text-left font-medium text-ground-600'
  const lastSeen = (a: AdminItem) => a.last_seen_at ? formatDate(a.last_seen_at)
    : <span className="text-ground-400">{t('admin.reviewers.lastSeenUnknown')}</span>
  /** T2: the organisation admin reads "Organisation admin (lead)" on the Admins table (T3: no permission
   *  column any more; the lead's fixed tier is still said, beside "Also in"). */
  const leadCell = (a: AdminItem) => a.lead ? (
    <span className="block" data-testid="team-lead">
      <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${roleBadge('org_admin')}`}>
        {t('admin.team.leadChip')}
      </span>
      <span className="mt-0.5 block text-[11px] text-ground-500">{t('admin.team.leadNote')}</span>
    </span>
  ) : null

  /** The status a row shows. ⚠ THE RULE ITSELF NOW LIVES IN `lib/staffStatus` (2026-09-09) —
   *  the Reviewers table needed the same one the moment Revoke arrived on it, and this file
   *  having its own copy is exactly how those two screens came to disagree twice before. */
  const statusOf = (a: AdminItem) => {
    const key = staffStatusKey(a)
    return {
      tone: STAFF_STATUS_TONE[key],
      label: t(key === 'revoked' ? 'admin.revoked'
        : key === 'paused' ? 'admin.reviewers.status.paused' : 'admin.active'),
    }
  }

  /** The row's actions, or none. Same conditions as the table — a super is never actionable,
   *  and the sole active org_admin of a tenant keeps no Revoke (the backend enforces it; this
   *  only keeps a dead affordance off the screen). */
  const actionsFor = (a: AdminItem) => {
    // ⚠ `manageable === false` MEANS THE SERVER WILL REFUSE. An org_admin sees their fellow
    // organisation admins and may not act on them, so the row draws no controls rather than
    // controls that 404. Undefined = a payload predating the field; treat it as manageable, which
    // is what the screen assumed before it existed.
    if (!canAct || a.is_super_admin || a.role === 'super' || a.manageable === false) return null
    return (
      <div className="flex items-center gap-3">
        {/* ⚠ RESEND IS FOR SOMEBODY WHO HAS NOT ARRIVED — AND IT USED TO BE THE OPPOSITE.
            The condition was `a.is_active`, so it appeared beside every working colleague, and
            pressing it OVERWRITES THEIR PASSWORD with a temporary one and mails it to them
            (`AdminResendView` rotates the Supabase password and sets must_change_password). One
            click locked a signed-in admin out of their own account. It is a re-send of sign-in
            details, so it belongs only to somebody whose invitation is still open — and who can
            still sign in: a revoked or cancelled account is refused by the server (2026-10-09). */}
        {a.is_active && a.invitation && a.invitation.status !== 'accepted' && onResend && (
          <button disabled={busyId === a.id} onClick={() => onResend(a)}
            className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
            {busyId === a.id ? t('admin.resending') : t('admin.resend')}
          </button>
        )}
        {/* Sprint T2: Revoke / Restore, then Delete — the one pair every Team table and person page
            draws (`StaffActions`). DELETE IS THE SERVER'S CALL (`deletable`); somebody with work on
            record gets it greyed, with the reason on hover, tap and focus. An organisation admin's
            Delete is drawn for a super viewer only. */}
        <StaffActions active={a.is_active} busy={busyId === a.id}
          onToggle={onToggle && a.revocable !== false && !(a.is_active && soleOrgAdmin?.(a))
            ? () => onToggle(a) : undefined}
          onDelete={onDelete ? () => onDelete(a) : undefined}
          deletable={a.deletable} deleteNever={a.delete_never} work={a.work} orgAdmin={a.role === 'org_admin'} viewerSuper={viewerSuper} />
        {team && <RemoveControl remove={a.remove} table="admins" busy={busyId === a.id}
          onRemove={() => team.onRemove(a)} />}
        {onChangeRole && switchableTo(a) && (
          <button disabled={busyId === a.id} onClick={() => onChangeRole(a)}
            className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
            {t('admin.changeRole')}
          </button>
        )}
      </div>
    )
  }

  /** O9 (owner, 2026-11-10): a phone number never shows on Team -> Admins; it shows on the person's own
   *  page (still only when they switched "Show my phone to my team" on). The Reviewers table draws its
   *  own rows and keeps its phone line; the platform's staff screens ask for theirs (`showPhone`); the default is no phone. */
  const phoneOf = (a: AdminItem) => showPhone && a.phone
    ? <span className="block text-xs text-ground-600" data-testid={`team-phone-${a.id}`}><span className="sr-only">{t('admin.reviewer.phone')}: </span>{a.phone}</span>
    : null

  /** The name, as a link to the person's page when the page offers one for this row; otherwise
   *  exactly what the row drew before (`plain`). */
  const nameOf = (a: AdminItem, link: string, plain: React.ReactNode) => {
    const href = nameHref?.(a)
    return href
      ? <Link href={href} className={`${link} text-primary-600 hover:text-primary-800`}>{a.name}</Link>
      : plain
  }

  return (
    <>
    {/* ── PHONE: one card per person (owner, 2026-09-08). Name and STATUS lead — this list is
        read to find out who still has access — with the role beside the email. The actions come
        too: revoking somebody is the one thing on this screen that might not wait for a desk. */}
    <div className="space-y-2.5 md:hidden" data-testid="staff-cards">
      {rows.map((a) => {
        const status = statusOf(a)
        const actions = actionsFor(a)
        return (
          <div key={a.id} className="rounded-xl border border-ground-200 bg-ground-0 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-2">
                <StaffAvatar name={a.name} photoUrl={a.photo_url} size={32} />
                <div className="min-w-0">
                {nameOf(a, 'block text-sm font-semibold',
                  <span className="block text-sm font-semibold text-ground-900">{a.name}</span>)}
                <span className="block truncate text-[11px] text-ground-500">{a.email}</span>
                {phoneOf(a)}
                {team && <span className="block text-[11px] text-ground-500">{t('admin.reviewers.colLastSeen')}: {lastSeen(a)}</span>}
                </div>
                {showOrg && (
                  <span className="block text-[11px] text-ground-400">{a.owning_org_name || '—'}</span>
                )}
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${status.tone}`}>
                {status.label}
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3">
              {team ? (
                <span className="flex min-w-0 flex-col gap-1">
                  {leadCell(a)}
                  <AlsoIn row={a} here="admins" />
                </span>
              ) : (
              <span className="flex flex-wrap items-center gap-1">
                <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] ${roleBadge(a.role)}`}>
                  {t(`admin.role.${a.role}`)}
                </span>
                <PermissionChips row={a} />
              </span>
              )}
              {actions}
            </div>
          </div>
        )
      })}
      {rows.length === 0 && (
        <p className="rounded-xl border border-dashed border-ground-200 px-4 py-6 text-center text-sm text-ground-400">
          {t('admin.noAdmins')}
        </p>
      )}
    </div>

    <TableFrame className="hidden md:block" minWidth={560} label={t('admin.invitations.title')}>
      <table className="w-full text-sm">
        <thead className="border-b bg-ground-50">
          <tr>
            <th className={th}>{t('admin.nameHeader')}</th>
            {!team && <th className={th}>{t('admin.emailHeader')}</th>}
            {showOrg && <th className={th}>{t('admin.orgHeader')}</th>}
            <th className={th}>{t(team ? 'admin.team.colAlsoIn' : 'admin.roleHeader')}</th>
            <th className={th}>{t('admin.statusHeader')}</th>
            {team && <th className={th}>{t('admin.reviewers.colLastSeen')}</th>}
            {canAct && <th className={th}>{t('admin.actionHeader')}</th>}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((a) => (
            <tr key={a.id}>
              <td className="px-4 py-3">
                <span className="flex items-start gap-2">
                  <StaffAvatar name={a.name} photoUrl={a.photo_url} size={28} />
                  <span className="min-w-0">{nameOf(a, 'font-medium', a.name)}{team && <span className="block text-xs text-ground-500" data-testid={`team-email-${a.id}`}>{a.email}</span>}{phoneOf(a)}</span>
                </span>
              </td>
              {!team && <td className="px-4 py-3 text-ground-500">{a.email}</td>}
              {showOrg && <td className="px-4 py-3 text-ground-500">{a.owning_org_name || '—'}</td>}
              {team ? (<>
                <td className="px-4 py-3"><span className="flex flex-col gap-1">{leadCell(a)}<AlsoIn row={a} here="admins" /></span></td>
              </>) : (
              <td className="px-4 py-3">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${roleBadge(a.role)}`}>
                  {t(`admin.role.${a.role}`)}
                </span>
                {/* #39 S4: what this person's set adds to (or takes from) the role. */}
                {a.custom && <div className="mt-1"><PermissionChips row={a} /></div>}
              </td>
              )}
              {/* Revoked beats paused: a revoked account cannot be brought back by un-pausing,
                  so showing "Paused" over it would name the smaller of two facts. Pause is
                  rendered HERE as well as on the Reviewers table because both screens list the
                  same people, and until 2026-08-03 they disagreed — one said Active while the
                  other said Paused. */}
              <td className="px-4 py-3">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusOf(a).tone}`}>
                  {statusOf(a).label}
                </span>
              </td>
              {team && <td className="px-4 py-3 whitespace-nowrap" data-testid={`team-last-seen-${a.id}`}>{lastSeen(a)}</td>}
              {/* ⚠ `actionsFor`, NOT A SECOND COPY. This cell held its own inline duplicate of the
                  buttons until 2026-09-09 — the phone cards called the helper and the desktop
                  table did not — so fixing the Resend rule in one place fixed exactly half the
                  screen, and the half the owner was looking at kept the bug. Two renderings, one
                  source of actions. */}
              {canAct && <td className="px-4 py-3">{actionsFor(a)}</td>}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={cols} className="px-4 py-6 text-center text-ground-400">{t('admin.noAdmins')}</td></tr>
          )}
        </tbody>
      </table>
    </TableFrame>
    </>
  )
}

/** Loads the staff list and owns the invite / resend / revoke actions the pages share. */
export function useStaffAdmin(token: string | null | undefined, wantOrgs = false) {
  const { t } = useT()
  const [admins, setAdmins] = useState<AdminItem[]>([])
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [message, setMessage] = useState<Banner>(null)
  const [busy, setBusy] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getAdmins({ token }).then((d) => setAdmins(d.admins)).catch(() => {})
  }, [token])

  useEffect(() => {
    load()
    if (token && wantOrgs) getOrgs({ token }).then((d) => setOrgs(d.orgs)).catch(() => {})
  }, [load, token, wantOrgs])

  const onError = useCallback((err: unknown) => {
    const code = (err as { code?: string })?.code
    // `already_on_team` (#39) is a pointer to People, not a failure: shown as a warning.
    setMessage({ type: code === 'already_on_team' ? 'warning' : 'error', text: code === 'last_org_admin'
      ? t('admin.administration.lastOrgAdmin')
      : err instanceof Error ? err.message : t('admin.actionFailed') })
  }, [t])

  const invite = useCallback(async (data: Parameters<typeof inviteAdmin>[0]) => {
    if (!token) return false
    setBusy(true); setMessage(null)
    try {
      const r = await inviteAdmin(data, { token })
      setMessage({ type: r.emailed === false ? 'warning' : 'success', text: r.message })
      load()
      if (wantOrgs) getOrgs({ token }).then((d) => setOrgs(d.orgs)).catch(() => {})
      return true
    } catch (err) { onError(err); return false } finally { setBusy(false) }
  }, [token, load, onError, wantOrgs])

  const resend = useCallback(async (a: AdminItem) => {
    if (!token) return
    setBusyId(a.id)
    try { setMessage({ type: 'success', text: (await resendAdminInvite(a.id, { token })).message }) }
    catch (err) { onError(err) } finally { setBusyId(null) }
  }, [token, onError])

  // ⚠ CONFIRMED, like the reviewers' Revoke (2026-10-09): it used to fire on the first click. The
  // reviewers' sentences are reused — they say exactly what happens to an admin too.
  const toggle = useCallback(async (a: AdminItem) => {
    if (!token) return
    if (!window.confirm(t(a.is_active ? 'admin.reviewers.revokeConfirm'
      : 'admin.reviewers.restoreConfirm', { name: a.name }))) return
    setBusyId(a.id)
    try { await revokeAdmin(a.id, a.is_active ? 'revoke' : 'restore', { token }); load() }
    catch (err) { onError(err) } finally { setBusyId(null) }
  }, [token, load, onError, t])

  /** Change role (2026-10-09). A DRY RUN first, so the question can name what the switch does to
   *  the payment finance check — answered by the server's own rule, never re-derived here. A
   *  refusal (open cases, a run in progress) arrives as the server's sentence. True on success,
   *  so a page keeping its own list (the reviewers table) knows to re-read it. */
  const changeRole = useCallback(async (a: { id: number; name: string; role: string;
                                             is_active: boolean; is_super_admin?: boolean }) => {
    const to = switchableTo(a)
    if (!token || !to) return false
    setBusyId(a.id); setMessage(null)
    try {
      const plan = await changeAdminRole(a.id, to, true, { token })
      const note = [
        plan.consequence === 'finance_check_on' ? t('admin.financeCheckOn')
          : plan.consequence === 'finance_check_off' ? t('admin.financeCheckOff') : '',
        // #39 S4: a saved custom set goes back to the new role's preset — said BEFORE the click.
        plan.permissions_reset ? t('admin.permissionsReset') : '',
        // #39 S4 review fix 4: what the switch does to the payment chain and to files, from the
        // editor's own rule (the approval fallback, the check step) — worded as the editor words it.
        ...(plan.consequences ?? []).map((c) => t(`admin.permEditor.effect.${c}`, { name: a.name })),
        // S7d: a staff member who also mentors stops mentoring with a switch to Finance.
        plan.stops_mentoring ? t('admin.stopsMentoring') : '',
      ].filter(Boolean).join(' ')
      const ask = t('admin.roleChangeConfirm', { name: a.name, role: t(`admin.role.${to}`) })
      if (!window.confirm(note ? `${ask} ${note}` : ask)) return false
      await changeAdminRole(a.id, to, false, { token })
      load()
      return true
    } catch (err) { onError(err); return false } finally { setBusyId(null) }
  }, [token, load, onError, t])

  const soleOrgAdmin = useCallback((a: AdminItem) =>
    a.role === 'org_admin' && a.is_active && a.owning_org_id != null
    && admins.filter((x) => x.role === 'org_admin' && x.is_active
      && x.owning_org_id === a.owning_org_id).length <= 1, [admins])

  // `reload` is exported so a page that DELETES a row can re-read the list — the hook's own
  // actions all reload themselves, but a delete lives on the page that owns the confirmation.
  return { admins, orgs, message, setMessage, busy, busyId, invite, resend, toggle, changeRole,
           soleOrgAdmin, reload: load }
}
