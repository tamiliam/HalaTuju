'use client'

import { useCallback, useEffect, useState } from 'react'

import {
  getAdmins, getOrgs, inviteAdmin, resendAdminInvite, revokeAdmin,
  type AdminItem, type OrgItem,
} from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { roleBadgeClass } from '@/lib/roleBadge'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'

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
                             onDelete, soleOrgAdmin }: {
  rows: AdminItem[]
  showOrg?: boolean
  canAct?: boolean
  busyId?: number | null
  onResend?: (a: AdminItem) => void
  onToggle?: (a: AdminItem) => void
  /** Delete outright. Only ever called for a row the SERVER marked `deletable`. */
  onDelete?: (a: AdminItem) => void
  /** The sole active org_admin of a tenant cannot be revoked — the backend enforces it; this
   *  just keeps a dead affordance off the screen. */
  soleOrgAdmin?: (a: AdminItem) => boolean
}) {
  const { t } = useT()
  const cols = 3 + (showOrg ? 1 : 0) + (canAct ? 1 : 0)

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
            details, so it belongs only to somebody whose invitation is still open. */}
        {a.invitation && a.invitation.status !== 'accepted' && onResend && (
          <button disabled={busyId === a.id} onClick={() => onResend(a)}
            className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
            {busyId === a.id ? t('admin.resending') : t('admin.resend')}
          </button>
        )}
        {onToggle && !(a.is_active && soleOrgAdmin?.(a)) && (
          <button disabled={busyId === a.id} onClick={() => onToggle(a)}
            className={`text-xs font-medium disabled:opacity-50 ${
              a.is_active ? 'text-critical-600 hover:text-critical-800'
                          : 'text-primary-600 hover:text-primary-800'}`}>
            {a.is_active ? t('admin.revoke') : t('admin.restore')}
          </button>
        )}
        {/* ⚠ DELETE IS THE NARROW ACTION AND THE SERVER DECIDES. `deletable` is true only for an
            admin-shaped role with NO recorded work — never a reviewer. It is not offered with a
            reason attached because the reason is absence: somebody who has done anything keeps
            Revoke instead. See `staff_footprint`. */}
        {a.deletable && onDelete && (
          <button disabled={busyId === a.id} onClick={() => onDelete(a)}
            className="text-xs font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
            {t('admin.delete')}
          </button>
        )}
      </div>
    )
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
              <div className="min-w-0">
                <span className="block text-sm font-semibold text-ground-900">{a.name}</span>
                <span className="block truncate text-[11px] text-ground-500">{a.email}</span>
                {showOrg && (
                  <span className="block text-[11px] text-ground-400">{a.owning_org_name || '—'}</span>
                )}
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${status.tone}`}>
                {status.label}
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] ${roleBadge(a.role)}`}>
                {t(`admin.role.${a.role}`)}
              </span>
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
            <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.nameHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.emailHeader')}</th>
            {showOrg && <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.orgHeader')}</th>}
            <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.roleHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.statusHeader')}</th>
            {canAct && <th className="px-4 py-3 text-left font-medium text-ground-600">{t('admin.actionHeader')}</th>}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((a) => (
            <tr key={a.id}>
              <td className="px-4 py-3">{a.name}</td>
              <td className="px-4 py-3 text-ground-500">{a.email}</td>
              {showOrg && <td className="px-4 py-3 text-ground-500">{a.owning_org_name || '—'}</td>}
              <td className="px-4 py-3">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${roleBadge(a.role)}`}>
                  {t(`admin.role.${a.role}`)}
                </span>
              </td>
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
    setMessage({ type: 'error', text: code === 'last_org_admin'
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

  const toggle = useCallback(async (a: AdminItem) => {
    if (!token) return
    setBusyId(a.id)
    try { await revokeAdmin(a.id, a.is_active ? 'revoke' : 'restore', { token }); load() }
    catch (err) { onError(err) } finally { setBusyId(null) }
  }, [token, load, onError])

  const soleOrgAdmin = useCallback((a: AdminItem) =>
    a.role === 'org_admin' && a.is_active && a.owning_org_id != null
    && admins.filter((x) => x.role === 'org_admin' && x.is_active
      && x.owning_org_id === a.owning_org_id).length <= 1, [admins])

  // `reload` is exported so a page that DELETES a row can re-read the list — the hook's own
  // actions all reload themselves, but a delete lives on the page that owns the confirmation.
  return { admins, orgs, message, setMessage, busy, busyId, invite, resend, toggle,
           soleOrgAdmin, reload: load }
}
