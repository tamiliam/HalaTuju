'use client'

import { useState } from 'react'

import { formatDate } from '@/lib/formatDate'
import {
  inviteMentor, mentorAction,
  type InvitationRow, type InvitationsPayload, type MentorRow,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { inputCls, type Banner } from '@/components/admin/StaffAdmin'

/**
 * Invitations → **Mentor** (student maintenance S7b follow-up, 2026-11-01; owner ruling: mentor
 * inviting follows the SOURCE pattern exactly — `components/sources/SourceInvite.tsx`).
 *
 * ⚠ ONE INVITE PATH: the form posts `POST admin/invitations/` `audience='mentor'` (`mentor_invite`),
 * the same endpoint the Mentors page used before. ⚠ THE ROSTER'S RESEND AND REVOKE ARE THE MENTOR
 * ACTIONS (`admin/mentors/<id>/resend|revoke/`), never the generic Cancel — that refuses a mentor
 * invitation by design (Revoke also stamps the mentor inactive, so the two can never disagree).
 * ⚠ SUPER AND ORG_ADMIN ONLY: the page shows this tab only to them; the server refuses others.
 */

type T = (k: string, vars?: Record<string, string>) => string
const K = 'admin.mentors'
const INVITE_REFUSALS = ['already_staff', 'already_team', 'bad_email', 'name_required', 'organisation_required',
  'not_configured', 'create_failed']
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active']
const codeOf = (err: unknown) => (err as { code?: string })?.code ?? ''
const LABEL = 'mb-1 block text-sm font-medium text-ground-700'

export function MentorInviteForm({ token, t, onDone }: {
  token: string | null
  t: T
  /** The banner to show, then reload the tab. */
  onDone: (message: Banner) => void
}) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setBusy(true); setError('')
    try {
      const sent = await inviteMentor({ name: name.trim(), email: email.trim() }, { token })
      onDone(sent.emailed
        ? { type: 'success', text: t(`${K}.invite.sent`, { name: name.trim(), email: email.trim() }) }
        : { type: 'warning', text: t(`${K}.invite.notEmailed`, { name: name.trim() }) })
      setName(''); setEmail('')
    } catch (err) {
      const code = codeOf(err)
      setError(t(`${K}.error.${INVITE_REFUSALS.includes(code) ? code : 'generic'}`))
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-4" data-testid="mentor-invite-form">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className={LABEL}>{t(`${K}.invite.name`)}</span>
          <input className={inputCls} value={name} required maxLength={200} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className={LABEL}>{t('admin.emailLabel')}</span>
          <input className={inputCls} type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
        </label>
      </div>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ground-500">{t(`${K}.invite.note`)}</span>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-brand-fill px-6 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.sendInvite')}
        </button>
      </div>
    </form>
  )
}

/** The Mentor tab's table: the mentors invited and not signed in yet, with Resend and Revoke. */
export function MentorRoster({ data, token, t, canManage, onDone }: {
  data: InvitationsPayload | null
  token: string | null
  t: T
  canManage: boolean
  onDone: (message: Banner) => void
}) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const waiting = data?.invitations ?? []
  const byId = new Map<number, MentorRow>((data?.mentors ?? []).map((m) => [m.id, m]))
  const mentorOf = (row: InvitationRow) => (row.mentor_id != null ? byId.get(row.mentor_id) : undefined)

  const act = async (row: InvitationRow, action: 'resend' | 'revoke') => {
    const m = mentorOf(row)
    if (!token || !m) return
    if (action === 'revoke' && !window.confirm(t(`${K}.confirm.revoke`, { name: m.name }))) return
    setBusyId(row.id)
    try {
      const done = await mentorAction(m.id, action, { token })
      onDone(action === 'resend' && done.emailed === false
        ? { type: 'warning', text: t(`${K}.done.notEmailed`) }
        : { type: 'success', text: t(`${K}.done.${action}`, { name: m.name, email: m.email }) })
    } catch (err) {
      const code = codeOf(err)
      onDone({ type: 'warning', text: t(`${K}.error.${ACTION_REFUSALS.includes(code) ? code : 'generic'}`) })
    } finally { setBusyId(null) }
  }

  const link = 'text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50'
  return (
    <div data-testid="mentor-roster">
      <h2 className="mb-2 text-sm font-semibold text-ground-900">
        {t('admin.invitations.waitingHeading')} <span className="font-normal text-ground-400">({waiting.length})</span>
      </h2>
      {waiting.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">
          {t('admin.invitations.mentor.noneWaiting')}
        </div>
      ) : (
        <TableFrame minWidth={640} label={t('admin.invitations.waitingHeading')} phoneRows>
          <table className="w-full text-sm">
            <thead className="border-b bg-ground-50">
              <tr>{['name', 'email', 'sent'].map((c) => <th key={c} className={TH}>{t(`admin.invitations.mentor.col.${c}`)}</th>)}<th className={TH} /></tr>
            </thead>
            <tbody className="divide-y">
              {waiting.map((row) => {
                const m = mentorOf(row)
                return (
                  <tr key={row.id} data-testid={`mentor-waiting-${row.id}`}>
                    <td className="px-4 py-3 font-medium text-ground-900">{row.name || '—'}</td>
                    <td className="px-4 py-3 text-ground-500 max-md:break-all" data-label={t('admin.invitations.mentor.col.email')}>{row.email}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-ground-500" data-label={t('admin.invitations.mentor.col.sent')}>{row.sent_at ? formatDate(row.sent_at) : '—'}
                      {row.last_send_ok === false && <div className="text-xs text-critical-600">{t('admin.invitations.send.failed')}</div>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      {canManage && m?.manageable && (<>
                        <button type="button" className={link} disabled={busyId === row.id}
                          onClick={() => { void act(row, 'resend') }}>{t(`${K}.action.resend`)}</button>
                        <button type="button" className={`ml-3 ${link}`} disabled={busyId === row.id}
                          onClick={() => { void act(row, 'revoke') }}>{t(`${K}.action.revoke`)}</button>
                      </>)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </TableFrame>
      )}
    </div>
  )
}
