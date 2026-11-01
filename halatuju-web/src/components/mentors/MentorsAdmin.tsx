'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState, type ComponentType } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import {
  getInvitations, getMentors, mentorAction,
  type MentorAction, type MentorRow, type MentorStatus, type MentorsPayload,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
/** The Emails tab's card — the Invitations page's own `InvitationEmailsCard` (one template, one editor).
 *  ⚠ HANDED IN BY THE ROUTE (`app/admin/organisation/mentors/page.tsx`), never imported here: this
 *  screen is a lazy chunk, and a lazy chunk that needs the shared template editor puts that editor's
 *  chunk into the webpack runtime EVERY route downloads — +0.02 kB on `/scholarship/application`, a
 *  student route at its first-load line (review fix 5). Imported by the route, it stays initial. */
export type EmailsCard = ComponentType<{
  token: string | null; t: (k: string, p?: Record<string, string>) => string
  only?: readonly string[]; note?: string
}>

/**
 * Organisation → Mentors (student maintenance S7a, 2026-10-31; reshaped by the S7b follow-up,
 * 2026-11-01, owner rulings). A MANAGEMENT page, like Organisation → People: Invitations invites;
 * this is where you look at the mentors who have ARRIVED.
 *
 * ⚠ ARRIVED ONLY (signed in): chips Active and Inactive; Reactivate sends nothing. A mentor switched off
 * before arriving is not listed — a re-invite on Invitations → Mentor brings them back (review fix 4). A mentor invited and not signed in yet lives on
 * Invitations → Mentor, with its Resend and Revoke; this page says how many are waiting there (the
 * Invitations payload's own count — the chip's — never a subtraction) and links to it.
 * ⚠ "Invite a mentor →" is a LINK to `/admin/organisation/staff?kind=mentor`, like the Sources
 * page's "Invite a source →". There is no invite form here.
 * ⚠ The tab bar is People's and Sources': Mentors · Emails · Terms (disabled — shown so the surfaces
 * look alike). Emails (super / org_admin) is the mentor's invitation, the only email a mentor gets.
 * ⚠ STAFF NEVER EDIT A MENTOR'S PROFILE. Area and languages are the mentor's own; blank shows
 * "Not filled in yet". ⚠ A MENTOR IS NEVER DELETED: Deactivate, and Reactivate.
 */

type T = (k: string, vars?: Record<string, string>) => string
type Banner = { ok: boolean; text: string } | null
type Panel = 'mentors' | 'emails' | 'terms'

const K = 'admin.mentors'
const STATUSES = ['active', 'inactive'] as const
type Arrived = typeof STATUSES[number]
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active', 'not_arrived']
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
  return t(`${K}.inactiveOn`, { date: formatDate(m.deactivated_at) })
}

export default function MentorsAdmin({ EmailsCard }: { EmailsCard: EmailsCard }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // ⚠ `superRole` (a leaf), never `lib/navigation`'s `effectiveRole`: importing the route registry here
  // split it into a shared chunk — one more runtime entry every route pays for (review fix 5).
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const mayInvite = ['super', 'org_admin'].includes(r)
  // The Emails tab follows the invitation-template editor's own gate (`_sources_admin`: super,
  // org_admin, admin) so it agrees with Invitations → Emails (follow-up review fix 3).
  const mayEditEmails = ['super', 'org_admin', 'admin'].includes(r)
  const [panel, setPanel] = useState<Panel>('mentors')
  const [data, setData] = useState<MentorsPayload | null>(null)
  const [waiting, setWaiting] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)
  const [filter, setFilter] = useState<Arrived>('active')
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    try {
      const d = await getMentors({ token })
      setData(d); setFailed(false)
    } catch { setFailed(true) }
    // The waiting count is the Invitations page's own (its Mentor chip), for the roles who see it.
    if (mayInvite) {
      getInvitations('mentor', { token }).then((p) => setWaiting(p.waiting?.mentor ?? 0)).catch(() => setWaiting(null))
    }
  }, [token, mayInvite])
  useEffect(() => { void load() }, [load])

  const act = async (m: MentorRow, action: MentorAction) => {
    if (!token) return
    if (action === 'deactivate' && !window.confirm(t(`${K}.confirm.deactivate`, { name: m.name }))) return
    setBusyId(m.id); setBanner(null)
    try {
      await mentorAction(m.id, action, { token })
      setBanner({ ok: true, text: t(`${K}.done.${action}`, { name: m.name, email: m.email }) })
    } catch (err) {
      const code = codeOf(err)
      setBanner({ ok: false, text: t(`${K}.error.${ACTION_REFUSALS.includes(code) ? code : 'generic'}`) })
    } finally {
      setBusyId(null)
      void load()
    }
  }

  // ARRIVED = has signed in (`mentor_invite.has_signed_in`, the server's `signed_in`). A mentor
  // switched off before arriving is not listed here: a re-invite on Invitations brings them back.
  const arrived = (data?.mentors ?? []).filter((m) => m.signed_in && m.status !== 'invited')
  const rows = arrived.filter((m) => m.status === filter)
  const counts: Record<Arrived, number> = {
    active: arrived.filter((m) => m.status === 'active').length,
    inactive: arrived.filter((m) => m.status === 'inactive').length,
  }

  return (
    <div className="space-y-5" data-testid="mentors-admin">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
          <p className="text-sm text-ground-600">{t(`${K}.intro`)}</p>
        </div>
        {panel === 'mentors' && mayInvite && (
          <Link href="/admin/organisation/staff?kind=mentor" data-testid="mentor-invite-link"
            className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            {t(`${K}.inviteOpen`)} →
          </Link>
        )}
      </div>

      <PanelTabs ariaLabelKey={`${K}.tabsAria`} active={panel} onSelect={(k) => setPanel(k as Panel)}
        tabs={[
          { key: 'mentors', labelKey: `${K}.tab.mentors` },
          ...(mayEditEmails ? [{ key: 'emails' as const, labelKey: 'admin.reviewers.tabEmails' }] : []),
          // Mentors sign nothing today. Shown disabled so the surfaces look alike (People, Sources).
          { key: 'terms', labelKey: 'admin.reviewers.tabTerms', disabled: true },
        ]} />

      {/* Mounted only while selected: each reveal re-reads the template. */}
      {panel === 'emails' && mayEditEmails && (
        <EmailsCard token={token} t={t} only={['invite_mentor']} note={t(`${K}.emailsNote`)} />
      )}

      {panel === 'mentors' && (<>
        {banner && (
          <p role={banner.ok ? 'status' : 'alert'}
            className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
              : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
        )}
        {failed && <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>}
        {!data && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

        {mayInvite && !!waiting && (
          <p className="text-sm text-ground-700" data-testid="mentors-waiting">
            {t(`${K}.waiting`, { count: String(waiting) })}{' '}
            <Link href="/admin/organisation/staff?kind=mentor" className="font-medium text-primary-600 hover:underline">
              {t(`${K}.seeInvitations`)}
            </Link>
          </p>
        )}

        {data && (
          <>
            <div className="flex flex-wrap gap-2" role="group" aria-label={t(`${K}.col.status`)}>
              {STATUSES.map((s) => (
                <button key={s} type="button" aria-pressed={filter === s} onClick={() => setFilter(s)}
                  data-testid={`mentor-chip-${s}`}
                  className={`h-9 rounded-full border px-4 text-sm ${filter === s
                    ? 'border-info-500 bg-info-50 font-medium text-info-900' : 'border-ground-300 bg-ground-0 text-ground-700'}`}>
                  {t(`${K}.status.${s}`)} · {counts[s]}
                </button>
              ))}
            </div>

            {rows.length === 0 ? (
              <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500"
                data-testid="mentors-empty">
                {arrived.length === 0 ? t(mayInvite ? `${K}.emptyNone` : `${K}.emptyNoneRead`) : t(`${K}.empty`)}
              </div>
            ) : (
              <TableFrame minWidth={760} label={t(`${K}.title`)}>
                <table className="w-full text-sm">
                  <thead className="border-b bg-ground-50">
                    <tr>
                      {['mentor', 'area', 'languages', 'scholarsNow', 'status'].map((c) => (
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
                          <td className="px-4 py-3 tabular-nums" data-testid={`mentor-scholars-${m.id}`}>{m.scholars_now ?? 0}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2.5 py-0.5 text-xs ${CHIP_TONE[m.status]}`}>{statusText(t, m)}</span>
                          </td>
                          <td className="whitespace-nowrap px-4 py-3">
                            {m.manageable && (
                              <button type="button" className={LINK} disabled={busyId === m.id}
                                onClick={() => act(m, m.status === 'active' ? 'deactivate' : 'reactivate')}>
                                {t(`${K}.action.${m.status === 'active' ? 'deactivate' : 'reactivate'}`)}
                              </button>
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
      </>)}
    </div>
  )
}
