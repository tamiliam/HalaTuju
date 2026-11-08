'use client'

import { useState } from 'react'

import {
  inviteMentor, mentorAction,
  type InvitationRow, type InvitationsPayload, type MentorRow,
} from '@/lib/admin-api'
import InvitationsTable from '@/components/admin/InvitationsTable'
import { InviteField, InviteFoot } from '@/components/admin/InviteForm'
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
 * ⚠ I1 (2026-11-08): the form wears the one invite layout (`admin/InviteForm`) and the roster draws the
 * one waiting table (`admin/InvitationsTable`). Its red link reads "Cancel invitation" like every other
 * tab's, but STILL calls the mentor revoke, with its confirm — only the word changed.
 */

type T = (k: string, vars?: Record<string, string>) => string
const K = 'admin.mentors'
const INVITE_REFUSALS = ['already_staff', 'already_team', 'bad_email', 'name_required', 'organisation_required',
  'not_configured', 'create_failed']
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active']
const codeOf = (err: unknown) => (err as { code?: string })?.code ?? ''

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
        <InviteField label={t(`${K}.invite.name`)}>
          <input className={inputCls} value={name} required maxLength={200} onChange={(e) => setName(e.target.value)} />
        </InviteField>
        <InviteField label={t('admin.emailLabel')}>
          <input className={inputCls} type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
        </InviteField>
      </div>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <InviteFoot note={t(`${K}.invite.note`)} busy={busy} label={t('admin.sendInvite')} />
    </form>
  )
}

/** The Mentor tab's table: the mentors invited and not signed in yet, with Resend and Cancel (= revoke). */
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

  return (
    <div data-testid="mentor-roster">
      <h2 className="mb-2 text-sm font-semibold text-ground-900">
        {t('admin.invitations.waitingHeading')} <span className="font-normal text-ground-400">({waiting.length})</span>
      </h2>
      {/* ⚠ Cancel here is the MENTOR revoke (`act(row, 'revoke')`), never the generic Cancel. */}
      <InvitationsTable rows={waiting} canAct={canManage} busyId={busyId} showRole={false}
        rowTestId={(row) => `mentor-waiting-${row.id}`}
        onResend={(row) => { void act(row, 'resend') }} onCancel={(row) => { void act(row, 'revoke') }}
        canResend={(row) => !!mentorOf(row)?.manageable} canCancel={(row) => !!mentorOf(row)?.manageable}
        empty={t('admin.invitations.mentor.noneWaiting')} />
    </div>
  )
}
