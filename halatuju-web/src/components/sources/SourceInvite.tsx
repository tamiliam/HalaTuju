'use client'

import { useState } from 'react'

import { formatDate } from '@/lib/formatDate'
import {
  inviteSource, resendSourceUser, revokeSourceUser,
  type InvitationRow, type InvitationsPayload, type SourceUserRow,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { inputCls, type Banner } from '@/components/admin/StaffAdmin'
import { SignInBadge } from '@/components/sources/shared'

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
 */

type T = (k: string, vars?: Record<string, string>) => string
const K = 'admin.invitations.source'
const REFUSALS = ['already_staff', 'code_taken', 'code_reserved', 'code_and_name_required',
  'source_inactive', 'bad_email', 'name_required', 'not_found', 'organisation_required',
  'not_configured', 'create_failed']
const refusal = (t: T, err: unknown) => {
  const code = (err as { code?: string })?.code
  return t(`${K}.error.${code && REFUSALS.includes(code) ? code : 'generic'}`)
}
const slugify = (v: string) => v.toLowerCase().replace(/[^a-z0-9-]/g, '')
const LABEL = 'mb-1 block text-sm font-medium text-ground-700'

export function SourceInviteForm({ data, token, t, onDone }: {
  data: InvitationsPayload | null
  token: string | null
  t: T
  /** The banner to show, then reload the tab. */
  onDone: (message: Banner) => void
}) {
  const sources = data?.sources ?? []
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
            <label className="block text-sm">
              <span className={LABEL}>{t(`${K}.newName`)}</span>
              <input className={inputCls} value={newSource.name} required
                onChange={(e) => setNewSource({ ...newSource, name: e.target.value })} />
            </label>
            <div className="text-sm">
              <label htmlFor="source-invite-code" className={LABEL}>{t(`${K}.newCode`)}</label>
              <input id="source-invite-code" className={inputCls} value={newSource.code} required
                onChange={(e) => setNewSource({ ...newSource, code: slugify(e.target.value) })} />
              <span className="mt-1 block text-xs text-ground-500">{t('admin.sources.codeHelp')}</span>
            </div>
            <label className="block text-sm">
              <span className={LABEL}>{t(`${K}.contactPerson`)}</span>
              <input className={inputCls} value={newSource.contact_person}
                onChange={(e) => setNewSource({ ...newSource, contact_person: e.target.value })} />
            </label>
            <label className="block text-sm">
              <span className={LABEL}>{t(`${K}.contactPhone`)}</span>
              {/* Plain on purpose: the phone helpers live in `lib/scholarship`, whose words are a slice
                  this route does not load (TD-416). The source keeps its own phone, checked, in its
                  console Profile. */}
              <input className={inputCls} inputMode="tel" type="tel" value={newSource.phone}
                onChange={(e) => setNewSource({ ...newSource, phone: e.target.value })} />
            </label>
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
                  <option key={s.id} value={s.id}>
                    {/* Every active source stays on offer — a source may sign in more than one
                        person — but one that has joined says so (review L3). */}
                    {s.sign_in === 'joined'
                      ? t(`${K}.optionJoined`, { name: s.name, code: s.code })
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
        <label className="block text-sm">
          <span className={LABEL}>{t(`${K}.personName`)}</span>
          <input className={inputCls} value={person.name} required
            onChange={(e) => setPerson({ ...person, name: e.target.value })} />
        </label>
        <label className="block text-sm">
          <span className={LABEL}>{t('admin.emailLabel')}</span>
          <input className={inputCls} type="email" value={person.email} required
            onChange={(e) => setPerson({ ...person, email: e.target.value })} />
        </label>
      </div>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ground-500">{t(`${K}.note`)}</span>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-brand-fill px-6 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.sendInvite')}
        </button>
      </div>
    </form>
  )
}

/** The Source tab's two tables: who has not replied yet, and who has signed in. */
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
  const joined = users.filter((u) => u.is_active && u.first_seen_at)
  const mayAct = (adminId: number | null | undefined) =>
    canManage && adminId != null && (byId.get(adminId)?.manageable ?? false)

  /** `known`: the refusal codes with words of their own (review L6) — the server's `already_joined`
   *  and `not_active` say what to do next; anything else is the generic failure. */
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
  const remove = (u: SourceUserRow) => {
    if (!token || !window.confirm(t(`${K}.removeConfirm`, { name: u.name, source: u.source_name }))) return
    void act(u.id, () => revokeSourceUser(u.id, { token }), `${K}.removed`, `${K}.removeFailed`, u,
      ['not_active'])
  }

  const link = 'text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50'
  const heading = (key: string, n: number) => (
    <h2 className="mb-2 mt-6 text-sm font-semibold text-ground-900 first:mt-0">
      {t(key)} <span className="font-normal text-ground-400">({n})</span>
    </h2>
  )
  const empty = (key: string) => (
    <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">{t(key)}</div>
  )

  return (
    <div data-testid="source-roster">
      {heading('admin.invitations.waitingHeading', waiting.length)}
      {waiting.length === 0 ? empty(`${K}.noneWaiting`) : (
        <TableFrame minWidth={720} label={t('admin.invitations.waitingHeading')}>
          <table className="w-full text-sm">
            <thead className="border-b bg-ground-50">
              <tr>{['source', 'person', 'email', 'sent'].map((c) => <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>)}<th className={TH} /></tr>
            </thead>
            <tbody className="divide-y">
              {waiting.map((row) => (
                <tr key={row.id} data-testid={`source-waiting-${row.id}`}>
                  <td className="px-4 py-3 font-medium text-ground-900">{row.source_name || '—'}</td>
                  <td className="px-4 py-3">{row.name || '—'}</td>
                  <td className="px-4 py-3 text-ground-500">{row.email}</td>
                  <td className="px-4 py-3 text-ground-500 whitespace-nowrap">{row.sent_at ? formatDate(row.sent_at) : '—'}
                    {row.last_send_ok === false && <div className="text-xs text-critical-600">{t('admin.invitations.send.failed')}</div>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {mayAct(row.admin_id) && (<>
                      <button type="button" className={link} disabled={busyId === row.id} onClick={() => resend(row)}>{t('admin.resend')}</button>
                      <button type="button" className={`ml-3 ${link}`} disabled={busyId === row.id} onClick={() => onCancel(row)}>{t('admin.invitations.cancel')}</button>
                    </>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
      )}

      {heading(`${K}.signedIn`, joined.length)}
      {joined.length === 0 ? empty(`${K}.noneSignedIn`) : (
        <TableFrame minWidth={720} label={t(`${K}.signedIn`)}>
          <table className="w-full text-sm">
            <thead className="border-b bg-ground-50">
              <tr>{['source', 'person', 'email', 'lastSeen'].map((c) => <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>)}<th className={TH} /></tr>
            </thead>
            <tbody className="divide-y">
              {joined.map((u) => (
                <tr key={u.id} data-testid={`source-user-${u.id}`}>
                  <td className="px-4 py-3 font-medium text-ground-900">{u.source_name}
                    <span className="ml-2"><SignInBadge state="joined" t={t} /></span></td>
                  <td className="px-4 py-3">{u.name || '—'}</td>
                  <td className="px-4 py-3 text-ground-500">{u.email}</td>
                  <td className="px-4 py-3 text-ground-500 whitespace-nowrap">{formatDate(u.last_seen_at ?? u.first_seen_at)}</td>
                  <td className="px-4 py-3">
                    {mayAct(u.id) && (
                      <button type="button" className="text-xs font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50"
                        disabled={busyId === u.id} onClick={() => remove(u)}>{t(`${K}.remove`)}</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
      )}
    </div>
  )
}
