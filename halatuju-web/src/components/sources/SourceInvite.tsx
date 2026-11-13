'use client'

import { useState } from 'react'

import {
  inviteSource, resendSourceUser,
  type InvitationRow, type InvitationsPayload, type SourceUserRow,
} from '@/lib/admin-api'
import InvitationsTable from '@/components/admin/InvitationsTable'
import { FIELD_LABEL as LABEL, InviteField, InviteFoot } from '@/components/admin/InviteForm'
import { inputCls, type Banner } from '@/components/admin/StaffAdmin'

// ⚠ THE MENTOR TAB RIDES THIS CHUNK (S7b follow-up review fix 5): Invitations loads its Mentor form and
// roster through THIS module, so they share the Source tab's lazy chunk instead of adding one. Every
// lazy chunk is an entry in the webpack runtime that EVERY route downloads — a chunk of its own put
// ~0.05 kB on `/scholarship/application`, a student route under its first-load line.
export { MentorInviteForm, MentorRoster } from '@/components/mentors/MentorInvite'

/**
 * Invitations → **Source** (source sign-in S2, 2026-10-30). Design of record: the owner-approved
 * mock-up of that tab ("Looks good. Proceed", 2026-10-30).
 *
 * ⚠ INVITING IS HOW A SOURCE IS ADDED NOW. The Sources page's own Add form is gone (its POST answers
 * 410): you either pick a source already on the list or add a new one here (name + short code, the
 * old Add source's rules, checked by the server), and name the person who will sign in for it.
 * ⚠ SUPER AND ORG_ADMIN ONLY (owner ruling: Admin does not invite sources). The page passes
 * `canManage`; the server refuses everyone else 403 regardless.
 * ⚠ Every refusal arrives as a code and is shown in plain words — `already_staff` deliberately says
 * nothing about WHOSE account the address holds (the server's own rule).
 * ⚠ ONE PERSON PER SOURCE (owner ruling 2026-11-08, Invitations I2; revises 2026-10-30): a source
 * someone has joined is not offered, and one with an invitation still waiting is offered greyed
 * (resend or cancel it in the waiting table below). The server refuses both, `source_has_person`.
 * The person who has joined is shown — and removed — on the Sources page, not here.
 */

type T = (k: string, vars?: Record<string, string>) => string
const K = 'admin.invitations.source'
const REFUSALS = ['already_staff', 'source_has_person', 'code_taken', 'code_reserved', 'code_and_name_required',
  'source_inactive', 'bad_email', 'name_required', 'not_found', 'organisation_required',
  'not_configured', 'create_failed']
const refusal = (t: T, err: unknown) => {
  const code = (err as { code?: string })?.code
  return t(`${K}.error.${code && REFUSALS.includes(code) ? code : 'generic'}`)
}
const slugify = (v: string) => v.toLowerCase().replace(/[^a-z0-9-]/g, '')

export function SourceInviteForm({ data, token, t, onDone }: {
  data: InvitationsPayload | null
  token: string | null
  t: T
  /** The banner to show, then reload the tab. */
  onDone: (message: Banner) => void
}) {
  // I2: a joined source is not offered at all; a waiting one is, greyed (see the docblock).
  const sources = (data?.sources ?? []).filter((s) => s.sign_in !== 'joined')
  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const adding = mode === 'new' || (data !== null && sources.length === 0)
  const [sourceId, setSourceId] = useState('')
  const [newSource, setNewSource] = useState({ name: '', code: '', contact_person: '', phone: '' })
  const [person, setPerson] = useState({ name: '', email: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    if (!adding && !sourceId) { setError(t(`${K}.chooseFirst`)); return }
    setBusy(true); setError('')
    try {
      const sent = await inviteSource({
        name: person.name.trim(), email: person.email.trim(),
        ...(adding
          ? { source_name: newSource.name.trim(), source_code: newSource.code,
              contact_person: newSource.contact_person.trim(), phone: newSource.phone.trim() }
          : { source_id: Number(sourceId) }),
      }, { token })
      setPerson({ name: '', email: '' }); setSourceId('')
      setNewSource({ name: '', code: '', contact_person: '', phone: '' }); setMode('existing')
      // The account exists either way; only the letter may have failed (review M4) — then say so,
      // with the way out, rather than "Invitation sent".
      onDone(sent.emailed === false
        ? { type: 'warning', text: t(`${K}.notEmailed`, { name: person.name.trim() }) }
        : { type: 'success', text: t(`${K}.sent`) })
    } catch (err) {
      setError(refusal(t, err))
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-4" data-testid="source-invite-form">
      <div className="grid gap-4 sm:grid-cols-2">
        {adding ? (
          <>
            <InviteField label={t(`${K}.newName`)}>
              <input className={inputCls} value={newSource.name} required
                onChange={(e) => setNewSource({ ...newSource, name: e.target.value })} />
            </InviteField>
            <div className="text-sm">
              <label htmlFor="source-invite-code" className={LABEL}>{t(`${K}.newCode`)}</label>
              <input id="source-invite-code" className={inputCls} value={newSource.code} required
                onChange={(e) => setNewSource({ ...newSource, code: slugify(e.target.value) })} />
              <span className="mt-1 block text-xs text-ground-500">{t('admin.sources.codeHelp')}</span>
            </div>
            <InviteField label={t(`${K}.contactPerson`)}>
              <input className={inputCls} value={newSource.contact_person}
                onChange={(e) => setNewSource({ ...newSource, contact_person: e.target.value })} />
            </InviteField>
            <InviteField label={t(`${K}.contactPhone`)}>
              {/* Plain on purpose: the phone helpers live in `lib/scholarship`, whose words are a slice
                  this route does not load (TD-416). The source keeps its own phone, checked, in its
                  console Profile. */}
              <input className={inputCls} inputMode="tel" type="tel" autoComplete="off" value={newSource.phone}
                onChange={(e) => setNewSource({ ...newSource, phone: e.target.value })} />
            </InviteField>
            {sources.length > 0 && (
              <p className="text-xs text-ground-500 sm:col-span-2">
                <button type="button" onClick={() => setMode('existing')}
                  className="font-medium text-primary-600 hover:underline">{t(`${K}.pickExisting`)}</button>
              </p>
            )}
          </>
        ) : (
          <>
            <div className="text-sm">
              <label htmlFor="source-invite-which" className={LABEL}>{t(`${K}.which`)}</label>
              <select id="source-invite-which" className={inputCls} value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}>
                <option value="">{t(`${K}.choose`)}</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id} disabled={s.sign_in === 'invited'}>
                    {s.sign_in === 'invited'
                      ? t(`${K}.optionWaiting`, { name: s.name, code: s.code })
                      : t(`${K}.option`, { name: s.name, code: s.code,
                                           state: t(`admin.sources.signIn.${s.sign_in}`) })}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-ground-500">
                {t(`${K}.help`)}{' '}
                <button type="button" onClick={() => setMode('new')}
                  className="font-medium text-primary-600 hover:underline">{t(`${K}.addNew`)}</button>
              </span>
            </div>
            <div className="hidden sm:block" />
          </>
        )}
        <InviteField label={t(`${K}.personName`)}>
          <input className={inputCls} value={person.name} required
            onChange={(e) => setPerson({ ...person, name: e.target.value })} />
        </InviteField>
        <InviteField label={t('admin.emailLabel')}>
          <input className={inputCls} type="email" value={person.email} required
            onChange={(e) => setPerson({ ...person, email: e.target.value })} />
        </InviteField>
      </div>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      {/* I1: the one invite foot — note under the fields, Send Invite at the left. */}
      <InviteFoot note={t(`${K}.note`)} busy={busy} label={t('admin.sendInvite')} />
    </form>
  )
}

/** The Source tab's table: who has not replied yet — the one waiting table, as on every tab
 *  (I2: the "Signed in" table and its Remove moved to the Sources page). */
export function SourceRoster({ data, token, t, canManage, onCancel, onDone }: {
  data: InvitationsPayload | null
  token: string | null
  t: T
  canManage: boolean
  /** The page's own Cancel (the invitation's verb, shared with every other kind). */
  onCancel: (row: InvitationRow) => void
  onDone: (message: Banner) => void
}) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const users = data?.source_users ?? []
  const byId = new Map(users.map((u) => [u.id, u]))
  const waiting = data?.invitations ?? []
  const mayAct = (adminId: number | null | undefined) =>
    canManage && adminId != null && (byId.get(adminId)?.manageable ?? false)

  /** `known`: the refusal codes with words of their own (review L6) — the server's `already_joined`
   *  and `not_active` say what to do next; anything else is the generic failure. Resend only now:
   *  Remove moved to the Sources page (I2). */
  const act = async (id: number, run: () => Promise<unknown>, ok: string, failed: string,
                     who: SourceUserRow | undefined, known: string[]) => {
    setBusyId(id)
    try {
      await run()
      onDone({ type: 'success', text: t(ok) })
    } catch (err) {
      const code = (err as { code?: string })?.code ?? ''
      onDone({ type: 'warning', text: known.includes(code)
        ? t(`${K}.refused.${code}`, { name: who?.name ?? '' }) : t(failed) })
    } finally { setBusyId(null) }
  }
  const resend = (row: InvitationRow) => {
    const adminId = row.admin_id
    if (!token || adminId == null) return
    void act(row.id, () => resendSourceUser(adminId, { token }),
      'admin.invitations.resent', 'admin.invitations.resendFailed', byId.get(adminId),
      ['already_joined', 'not_active'])
  }

  return (
    <div data-testid="source-roster">
      <h2 className="mb-2 text-sm font-semibold text-ground-900">
        {t('admin.invitations.waitingHeading')}{' '}
        <span className="font-normal text-ground-400">({waiting.length})</span>
      </h2>
      {/* I1: the one waiting table every tab draws, with the source's name as its lead column.
          Resend is the source-user resend, Cancel the page's own; both only where `mayAct`. */}
      <InvitationsTable rows={waiting} canAct={canManage} busyId={busyId} showRole={false}
        lead={{ header: t(`${K}.col.source`), cell: (row) => row.source_name || '—', sortText: (row) => row.source_name || '' }}
        rowTestId={(row) => `source-waiting-${row.id}`}
        onResend={resend} onCancel={onCancel}
        canResend={(row) => mayAct(row.admin_id)} canCancel={(row) => mayAct(row.admin_id)}
        empty={t(`${K}.noneWaiting`)} />
    </div>
  )
}
