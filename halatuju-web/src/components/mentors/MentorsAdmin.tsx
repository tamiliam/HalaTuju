'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getMentors, inviteMentor, mentorAction,
  type MentorAction, type MentorRow, type MentorStatus, type MentorsPayload,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'

/**
 * Organisation → Mentors (student maintenance S7a, 2026-10-31). Design of record: the MentorsAdmin
 * board (owner-approved). Mirrors the source invite (`components/sources/SourceInvite.tsx`): an
 * invite form of name + email, the server's refusal codes in plain words, and per-row actions
 * offered only where the row's `manageable` says the endpoint would take them.
 *
 * ⚠ STAFF NEVER EDIT A MENTOR'S PROFILE. Area and languages are the mentor's own (their Profile);
 * blank shows "Not filled in yet". ⚠ A MENTOR IS NEVER DELETED: Deactivate, and Reactivate.
 * ⚠ NO "SCHOLARS NOW" COLUMN until mentors can be assigned (Sprint 7b).
 */

type T = (k: string, vars?: Record<string, string>) => string
type Banner = { ok: boolean; text: string } | null

const K = 'admin.mentors'
const STATUSES: MentorStatus[] = ['active', 'invited', 'inactive']
const INVITE_REFUSALS = ['already_staff', 'bad_email', 'name_required', 'organisation_required',
  'not_configured', 'create_failed']
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active']
const INPUT = 'w-full rounded-lg border border-ground-300 px-3 py-2 focus:border-info-500 focus:ring-2 focus:ring-info-500'
const LINK = 'text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50'
const CHIP_TONE: Record<MentorStatus, string> = {
  active: 'bg-positive-50 text-positive-800',
  invited: 'bg-caution-50 text-caution-800',
  inactive: 'bg-ground-100 text-ground-600',
}

const codeOf = (err: unknown) => (err as { code?: string })?.code ?? ''

/** "EN · MS · TA (+ Mandarin)" — the languages spoken conversationally or better; '' when none. */
export function languagesLine(m: MentorRow): string {
  const codes = (['en', 'ms', 'ta'] as const).filter((k) => m.languages[k] === 'conversational'
    || m.languages[k] === 'fluent').map((k) => k.toUpperCase())
  return [...codes, ...(m.other_language ? [m.other_language] : [])].join(' · ')
}

function statusText(t: T, m: MentorRow): string {
  if (m.status === 'active') {
    return m.last_seen_at ? t(`${K}.activeSeen`, { date: formatDate(m.last_seen_at) }) : t(`${K}.status.active`)
  }
  if (m.status === 'invited') return t(`${K}.invitedOn`, { date: formatDate(m.invited_at) })
  return t(`${K}.inactiveOn`, { date: formatDate(m.deactivated_at) })
}

function InviteForm({ t, token, onDone, onClose }: {
  t: T; token: string; onDone: (b: Banner) => void; onClose: () => void
}) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const sent = await inviteMentor({ name: name.trim(), email: email.trim() }, { token })
      onDone(sent.emailed
        ? { ok: true, text: t(`${K}.invite.sent`, { name: name.trim(), email: email.trim() }) }
        : { ok: false, text: t(`${K}.invite.notEmailed`, { name: name.trim() }) })
      onClose()
    } catch (err) {
      const code = codeOf(err)
      setError(t(`${K}.error.${INVITE_REFUSALS.includes(code) ? code : 'generic'}`))
    } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} data-testid="mentor-invite-form" aria-label={t(`${K}.invite.title`)}
      className="max-w-3xl space-y-4 rounded-xl border-2 border-info-500 bg-ground-0 p-5">
      <h2 className="font-semibold text-ground-900">{t(`${K}.invite.title`)}</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-ground-700">{t(`${K}.invite.name`)}</span>
          <input className={INPUT} value={name} required maxLength={200} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-ground-700">{t(`${K}.invite.email`)}</span>
          <input className={INPUT} type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
        </label>
      </div>
      <p className="text-sm text-ground-600">{t(`${K}.invite.note`)}</p>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy}
          className="rounded-lg bg-brand-fill px-5 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t(busy ? `${K}.invite.sending` : `${K}.invite.send`)}
        </button>
        <button type="button" onClick={onClose}
          className="rounded-lg border border-ground-300 bg-ground-0 px-5 py-2.5 text-ground-800 hover:bg-ground-50">
          {t(`${K}.invite.cancel`)}
        </button>
      </div>
    </form>
  )
}

export default function MentorsAdmin() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<MentorsPayload | null>(null)
  const [failed, setFailed] = useState(false)
  const [filter, setFilter] = useState<MentorStatus | null>(null)
  const [inviting, setInviting] = useState(false)
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    try {
      const d = await getMentors({ token })
      setData(d); setFailed(false)
      // The board opens on Active; on a list with no active mentor yet, the first status that has any.
      setFilter((f) => f ?? (d.counts.active ? 'active' : STATUSES.find((s) => d.counts[s]) ?? 'active'))
    } catch { setFailed(true) }
  }, [token])
  useEffect(() => { void load() }, [load])

  const act = async (m: MentorRow, action: MentorAction) => {
    if (!token) return
    if ((action === 'deactivate' || action === 'revoke')
        && !window.confirm(t(`${K}.confirm.${action}`, { name: m.name }))) return
    setBusyId(m.id); setBanner(null)
    try {
      const row = await mentorAction(m.id, action, { token })
      const reInvited = action === 'reactivate' && row.status === 'invited'
      setBanner(row.emailed === false && (action === 'resend' || reInvited)
        ? { ok: false, text: t(`${K}.done.notEmailed`) }
        : { ok: true, text: t(`${K}.done.${reInvited ? 'reactivateInvited' : action}`,
          { name: m.name, email: m.email }) })
    } catch (err) {
      const code = codeOf(err)
      setBanner({ ok: false, text: t(`${K}.error.${ACTION_REFUSALS.includes(code) ? code : 'generic'}`) })
    } finally {
      setBusyId(null)
      void load()
    }
  }

  const rows = (data?.mentors ?? []).filter((m) => m.status === filter)
  const action = (m: MentorRow, a: MentorAction) => (
    <button type="button" className={LINK} disabled={busyId === m.id} onClick={() => act(m, a)}>
      {t(`${K}.action.${a}`)}
    </button>
  )

  return (
    <div className="space-y-5" data-testid="mentors-admin">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
          <p className="text-sm text-ground-600">{t(`${K}.intro`)}</p>
        </div>
        {data?.can_invite && !inviting && token && (
          <button type="button" onClick={() => { setInviting(true); setBanner(null) }}
            className="rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            {t(`${K}.inviteOpen`)}
          </button>
        )}
      </div>

      {banner && (
        <p role={banner.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
            : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
      )}

      {inviting && token && (
        <InviteForm t={t} token={token} onClose={() => setInviting(false)}
          onDone={(b) => { setBanner(b); void load() }} />
      )}

      {failed && <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>}
      {!data && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

      {data && (
        <>
          <div className="flex flex-wrap gap-2" role="group" aria-label={t(`${K}.col.status`)}>
            {STATUSES.map((s) => (
              <button key={s} type="button" aria-pressed={filter === s} onClick={() => setFilter(s)}
                data-testid={`mentor-chip-${s}`}
                className={`h-9 rounded-full border px-4 text-sm ${filter === s
                  ? 'border-info-500 bg-info-50 font-medium text-info-900' : 'border-ground-300 bg-ground-0 text-ground-700'}`}>
                {t(`${K}.status.${s}`)} · {data.counts[s]}
              </button>
            ))}
          </div>

          {rows.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">
              {t(`${K}.empty`)}
            </div>
          ) : (
            <TableFrame minWidth={760} label={t(`${K}.title`)}>
              <table className="w-full text-sm">
                <thead className="border-b bg-ground-50">
                  <tr>
                    {['mentor', 'area', 'languages', 'status'].map((c) => (
                      <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>
                    ))}
                    <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {rows.map((m) => {
                    const langs = languagesLine(m)
                    return (
                      <tr key={m.id} data-testid={`mentor-row-${m.id}`}>
                        <td className="px-4 py-3">
                          <span className="font-medium text-ground-900">{m.name}</span>
                          <span className="block text-xs text-ground-500">
                            {m.email}{m.phone ? ` · ${m.phone}` : ''}
                          </span>
                        </td>
                        <td className={`px-4 py-3 ${m.area ? '' : 'text-ground-500'}`}>{m.area || t(`${K}.notFilled`)}</td>
                        <td className={`px-4 py-3 ${langs ? '' : 'text-ground-500'}`}>{langs || t(`${K}.notFilled`)}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2.5 py-0.5 text-xs ${CHIP_TONE[m.status]}`}>{statusText(t, m)}</span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          {m.manageable && m.status === 'active' && action(m, 'deactivate')}
                          {m.manageable && m.status === 'inactive' && action(m, 'reactivate')}
                          {m.manageable && m.status === 'invited' && (
                            <>{action(m, 'resend')}<span aria-hidden className="mx-1 text-ground-400">·</span>{action(m, 'revoke')}</>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </TableFrame>
          )}
          <p className="text-xs text-ground-500">{t(`${K}.note`)}</p>
        </>
      )}
    </div>
  )
}
