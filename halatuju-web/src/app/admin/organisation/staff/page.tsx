'use client'

import { useCallback, useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  getInvitations, inviteSponsor,
  type AdminItem, type InvitationKind, type InvitationRow, type InvitationsPayload,
} from '@/lib/admin-api'
import {
  MessageBanner, PageHeader, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'
import InvitationsTable from '@/components/admin/InvitationsTable'
import ReviewerEmailsCard from '@/components/reviewers/ReviewerEmailsCard'

const KINDS: InvitationKind[] = ['admins', 'reviewers', 'source', 'sponsors']

/** The staff roles this page can grant. The SERVER decides which apply to the selected kind
 *  (`invitable_roles`); this type only keeps the invite client honest. */
type StaffRole = 'reviewer' | 'admin' | 'qc' | 'finance'

/** The staff row behind an invitation, for the two actions that act on the ACCOUNT rather than on
 *  the invitation. Only `id` and `is_active` are read; guarded by `admin_id` at every call site. */
const asStaffRow = (row: InvitationRow) =>
  ({ id: row.admin_id as number, is_active: row.is_active ?? true } as AdminItem)

/**
 * Organisation → **Invitations**. Who has been asked to join this organisation.
 *
 * Owner's shape, 2026-08-03. FOUR kinds — admins, reviewers, source, sponsors — with **one table
 * on screen at a time**, chosen by the same buttons that decide what you are inviting.
 *
 * ⚠ **THE WAITING COUNT ON EACH BUTTON IS LOAD-BEARING, not decoration.** Only one table is
 * visible, so an unanswered invitation under a kind you are not looking at would be invisible —
 * which is the exact failure this page exists to end.
 *
 * ⚠ **INVITABLE HERE ≠ LISTED HERE.** `org_admin` appears in the Admins table (an organisation
 * admin is an admin) but is never offered in the selector: appointing one is a platform act a super
 * performs. The server sends `invitable_roles`; this page does not keep its own copy.
 *
 * ⚠ **A SPONSOR INVITATION CREATES NOTHING.** It emails a link to the ordinary public registration,
 * where they consent, sign the terms and are vetted like anybody else — the owner's constraint,
 * "invite, but nothing is skipped". The peer-to-peer route (a sponsor inviting a sponsor) is
 * deliberately NOT shown here; it lives on the sponsor's own account page.
 *
 * ⚠ Sponsors never see any of this. They sign in through their own stack and see `/sponsor/*`.
 */
export default function OrganisationInvitationsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const canManage = r === 'super' || r === 'org_admin'
  const mayView = canAccess('/admin/organisation/staff', r)

  const { message, busy, busyId, invite, resend, toggle } = useStaffAdmin(token)

  const [panel, setPanel] = useState<'invitations' | 'emails'>('invitations')
  const [kind, setKind] = useState<InvitationKind>('admins')
  const [data, setData] = useState<InvitationsPayload | null>(null)
  const [subRole, setSubRole] = useState('')
  const [sName, setSName] = useState('')
  const [sEmail, setSEmail] = useState('')
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    try {
      const payload = await getInvitations(kind, { token })
      setData(payload)
      setSubRole((cur) => (payload.invitable_roles.includes(cur)
        ? cur : (payload.invitable_roles[0] || '')))
    } catch { setData(null) }
  }, [token, kind])

  useEffect(() => { void load() }, [load])

  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    let ok = false
    if (kind === 'sponsors') {
      try {
        await inviteSponsor({ email: sEmail, name: sName, note }, { token: token! })
        ok = true
      } catch { ok = false }
    } else {
      ok = await invite({ email: sEmail, name: sName, role: subRole as StaffRole })
    }
    if (ok) { setSName(''); setSEmail(''); setNote('') }
    void load()
  }

  const rows = data?.invitations ?? []
  const waiting = data?.waiting
  const invitable = data?.invitable_roles ?? []
  const canInviteHere = canManage && (kind === 'sponsors' || invitable.length > 0)

  return (
    <div className="max-w-4xl">
      <PageHeader title={t('admin.invitations.title')} subtitle={t('admin.invitations.subtitle')} />

      {/* Tabs first, mirroring Organisation → Reviewers, so the console has one shape. */}
      <div role="tablist" aria-label={t('admin.invitations.tabsAria')}
        className="mb-6 flex items-center gap-2">
        {(['invitations', 'emails'] as const).map((key) => {
          const on = panel === key
          return (
            <button key={key} type="button" role="tab" aria-selected={on}
              onClick={() => setPanel(key)}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                on ? 'border-blue-600 bg-blue-600 text-white'
                   : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}`}>
              {t(`admin.invitations.tab.${key}`)}
            </button>
          )
        })}
      </div>

      <MessageBanner message={message} />

      {panel === 'emails' && <ReviewerEmailsCard token={token} t={t} />}

      {panel === 'invitations' && (<>
        <div className="mb-6 rounded-xl border bg-white p-6 shadow-sm">
          <p className="mb-2 text-sm font-semibold text-gray-900">{t('admin.inviteAs')}</p>
          <div className="grid max-w-xl grid-cols-2 gap-2 sm:grid-cols-4">
            {KINDS.map((k) => {
              const n = waiting?.[k] ?? 0
              return (
                <button key={k} type="button" onClick={() => setKind(k)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    kind === k ? 'border-primary-600 bg-primary-600 text-white'
                               : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                  {t(`admin.invitations.kind.${k}`)}
                  {/* The waiting badge — see the ⚠ in the docblock. */}
                  {n > 0 && (
                    <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[11px] ${
                      kind === k ? 'bg-white/25 text-white' : 'bg-blue-100 text-blue-700'}`}>
                      {n}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {kind === 'source' ? (
            <p className="mt-4 text-sm text-gray-500">{t('admin.invitations.sourceComingSoon')}</p>
          ) : canInviteHere ? (
            <form onSubmit={submit} className="mt-4 space-y-4">
              {invitable.length > 1 && (
                <div className="flex flex-wrap gap-2">
                  {invitable.map((role_) => (
                    <button key={role_} type="button" onClick={() => setSubRole(role_)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium ${
                        subRole === role_ ? 'border-primary-600 bg-primary-50 text-primary-700'
                                          : 'border-gray-300 bg-white text-gray-600'}`}>
                      {t(`admin.administration.staffRole.${role_}`)}
                    </button>
                  ))}
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <input className={inputCls} placeholder={t('admin.name')} value={sName}
                  onChange={(e) => setSName(e.target.value)} required />
                <input className={inputCls} type="email" placeholder={t('admin.emailLabel')}
                  value={sEmail} onChange={(e) => setSEmail(e.target.value)} required />
              </div>
              {kind === 'sponsors' && (
                <input className={inputCls} placeholder={t('admin.invitations.notePlaceholder')}
                  value={note} onChange={(e) => setNote(e.target.value)} />
              )}
              <button type="submit" disabled={busy}
                className="rounded-lg bg-primary-600 px-6 py-2.5 font-medium text-white hover:bg-primary-700 disabled:opacity-50">
                {t('admin.sendInvite')}
              </button>
            </form>
          ) : null}
        </div>

        <h2 className="mb-2 text-sm font-semibold text-gray-900">
          {t(`admin.invitations.kind.${kind}`)}{' '}
          <span className="font-normal text-gray-400">({rows.length})</span>
        </h2>
        {kind === 'source' ? (
          <div className="rounded-lg border border-dashed bg-white p-6 text-center text-sm text-gray-500">
            {t('admin.invitations.sourceComingSoon')}
          </div>
        ) : (
          <InvitationsTable
            rows={rows} canAct={canManage} busyId={busyId}
            /* `resend` and `toggle` act on the ACCOUNT, so they take the staff row behind the
               invitation. Both read only `id` and `is_active`; a sponsor invitation has no
               account, and the table never offers these for one. */
            onResend={canManage ? (row: InvitationRow) => {
              if (row.admin_id) void resend(asStaffRow(row)).then(load)
            } : undefined}
            onRevoke={canManage ? (row: InvitationRow) => {
              if (row.admin_id) void toggle(asStaffRow(row)).then(load)
            } : undefined}
          />
        )}
        {!canManage && (
          <p className="mt-3 text-sm text-gray-500">{t('admin.administration.viewOnlyNote')}</p>
        )}
      </>)}
    </div>
  )
}
