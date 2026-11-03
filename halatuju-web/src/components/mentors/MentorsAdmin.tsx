'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState, type ComponentType } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import { STANDING_TONE } from '@/lib/scholars'
import {
  getInvitations, getMentorDetail, getMentors, mentorAction,
  type MentorAction, type MentorDetail as MentorDetailPayload, type MentorRow, type MentorScholarRow,
  type MentorsPayload, type ScholarStanding,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import Sheet from '@/components/Sheet'
import StaffMentorSheet from './StaffMentorSheet'

/**
 * Team → **Mentors** and the **mentor detail** page (Team tables T3, 2026-11-03; the TeamMentors board the
 * owner approved; roadmap ruling 6). Before T3 this file was the Organisation → Mentors page (S7a–S7d); that
 * route now redirects here. ONE CHUNK for both screens: the Team page and the detail route each load it
 * through their own `lazySource` loader with this literal specifier, so no new chunk joins the webpack
 * runtime every route downloads (the S7b follow-up review's lesson).
 *
 * ⚠ WHAT THE TABLE LISTS IS THE OLD PAGE'S LIST, UNCHANGED: the mentors who have ARRIVED (signed in) plus
 * every staff member who mentors (their sign-in is People's), split Active · n / Inactive · n. A mentor
 * invited and not signed in yet is on Invitations → Mentor; this table says how many ("n waiting to
 * accept: see Invitations" — the Invitations payload's own count, for the roles who see that tab).
 * ⚠ "INVITE A MENTOR" IS GONE (ruling 6): new mentors are invited on Invitations → Mentor. **Add Mentor**
 * is 7d's "Add a staff member as mentor" (`StaffMentorSheet`, the shared Sheet): an existing team member,
 * no email, their sign-in untouched.
 * ⚠ REMOVE IS 7d's, UNCHANGED: a staff member's **Stop mentoring** (assignments end, the sign-in
 * untouched; under Inactive, **Mentor again**) and a pure mentor's **Deactivate** (their sign-in is
 * switched off; under Inactive, **Reactivate**). Offered only where the row's `manageable` says the
 * endpoint will take it; the confirm is the shared Sheet.
 * ⚠ STAFF NEVER EDIT A MENTOR'S PROFILE. Area and languages are the mentor's own.
 * ⚠ THE DETAIL PAGE IS STAFF ONLY AND SHOWS NO MEETING NOTE: figures, scholars, dates, standing, concern
 * state. Notes stay on each scholar's file. Who reads it = who reads this table (`GET admin/mentors/<id>/`).
 * ⚠ `superRole` (a leaf), never `lib/navigation`: importing the route registry here split it into a shared
 * chunk once — one more runtime entry every route pays for (S7b follow-up review fix 5). The Team page
 * decides who sees the tab (`pageGuard.mayReadMentors`) and hands in its own "Also in" chips.
 */

type T = (k: string, vars?: Record<string, string>) => string
type Banner = { ok: boolean; text: string } | null

const K = 'admin.mentors'
const STATUSES = ['active', 'inactive'] as const
type Arrived = typeof STATUSES[number]
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active', 'not_arrived', 'not_eligible', 'staff_mentor',
  'not_staff']
const LINK = 'text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50'
/** The two actions that take a mentor OUT (the Sheet confirms them); the two that bring one back are direct. */
const REMOVES: readonly MentorAction[] = ['stop', 'deactivate']

const codeOf = (err: unknown) => (err as { code?: string })?.code ?? ''

/** "EN · MS · TA (+ Mandarin)" — the languages spoken conversationally or better; '' when none. */
export function languagesLine(m: MentorRow): string {
  const codes = (['en', 'ms', 'ta'] as const).filter((k) => m.languages[k] === 'conversational'
    || m.languages[k] === 'fluent').map((k) => k.toUpperCase())
  return [...codes, ...(m.other_language ? [m.other_language] : [])].join(' · ')
}

/** The row's one action: a staff mentor's Stop / Mentor again, a mentor login's Deactivate / Reactivate. */
export function actionOf(m: MentorRow): MentorAction {
  return m.staff_role
    ? (m.status === 'active' ? 'stop' : 'resume')
    : (m.status === 'active' ? 'deactivate' : 'reactivate')
}

/** The Team page's own "Also in" chips (`components/admin/TeamTables`), handed in by the route. */
export type AlsoInChips = ComponentType<{ row: { tables?: string[]; lead?: boolean }; here: 'mentors' }>

export const mentorHref = (id: number) => `/admin/organisation/reviewers/mentors/${id}`

export default function TeamMentors({ AlsoIn }: { AlsoIn: AlsoInChips }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const mayManage = ['super', 'org_admin'].includes(r)
  const [data, setData] = useState<MentorsPayload | null>(null)
  const [waiting, setWaiting] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)
  const [filter, setFilter] = useState<Arrived>('active')
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<MentorRow | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    try {
      const d = await getMentors({ token })
      setData(d); setFailed(false)
    } catch { setFailed(true) }
    // The waiting count is the Invitations page's own (its Mentor chip), for the roles who see it.
    if (mayManage) {
      getInvitations('mentor', { token }).then((p) => setWaiting(p.waiting?.mentor ?? 0)).catch(() => setWaiting(null))
    }
  }, [token, mayManage])
  useEffect(() => { void load() }, [load])

  const act = async (m: MentorRow, action: MentorAction) => {
    if (!token) return
    setBusyId(m.id); setBanner(null)
    try {
      await mentorAction(m.id, action, { token })
      setBanner({ ok: true, text: t(`${K}.done.${action}`, { name: m.name, email: m.email }) })
    } catch (err) {
      const code = codeOf(err)
      setBanner({ ok: false, text: t(`${K}.error.${ACTION_REFUSALS.includes(code) ? code : 'generic'}`) })
    } finally {
      setBusyId(null); setRemoving(null)
      void load()
    }
  }

  // ARRIVED = has signed in (`mentor_invite.has_signed_in`, the server's `signed_in`). A mentor switched
  // off before arriving is not listed: a re-invite on Invitations brings them back. A staff mentor is
  // listed either way (their sign-in is People's business). THE OLD MENTORS PAGE'S RULE, unchanged.
  const arrived = (data?.mentors ?? []).filter((m) => (m.staff_role || m.signed_in) && m.status !== 'invited')
  const rows = arrived.filter((m) => m.status === filter)
  const counts: Record<Arrived, number> = {
    active: arrived.filter((m) => m.status === 'active').length,
    inactive: arrived.filter((m) => m.status === 'inactive').length,
  }
  const removingAction = removing ? actionOf(removing) : null

  return (
    <div className="space-y-4" data-testid="team-mentors">
      {mayManage && (
        <div className="flex justify-end">
          <button type="button" onClick={() => setAdding(true)} data-testid="team-add-mentors-open"
            className="min-h-11 rounded-lg bg-brand-fill px-4 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {t(`${K}.addMentor`)}
          </button>
        </div>
      )}
      {mayManage && (
        <StaffMentorSheet open={adding} token={token} t={t} onClose={() => setAdding(false)}
          onAdded={(row) => {
            setAdding(false); setFilter('active')
            setBanner({ ok: true, text: t(`${K}.done.added`, { name: row.name }) })
            void load()
          }} />
      )}
      <Sheet open={!!removing} onClose={() => setRemoving(null)} busy={busyId !== null} tone="critical"
        role="alertdialog" testId="mentor-remove"
        title={removing && removingAction ? t(`${K}.removeTitle.${removingAction}`, { name: removing.name }) : ''}
        footer={(
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busyId !== null} data-testid="mentor-remove-confirm"
              onClick={() => { if (removing && removingAction) void act(removing, removingAction) }}
              className="min-h-11 rounded-lg bg-critical-fill px-4 font-medium text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
              {removingAction ? t(`${K}.action.${removingAction}`) : ''}
            </button>
            <button type="button" onClick={() => setRemoving(null)} disabled={busyId !== null}
              className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-700 hover:bg-ground-50">
              {t('common.cancel')}
            </button>
          </div>
        )}>
        <p className="text-sm text-ground-700">
          {removing && removingAction ? t(`${K}.confirm.${removingAction}`, { name: removing.name }) : ''}
        </p>
      </Sheet>

      {banner && (
        <p role={banner.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
            : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
      )}
      {failed && <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>}
      {!data && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

      {mayManage && !!waiting && (
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
              {arrived.length === 0 ? t(mayManage ? `${K}.emptyNone` : `${K}.emptyNoneRead`) : t(`${K}.empty`)}
            </div>
          ) : (
            <TableFrame minWidth={1100} label={t(`${K}.title`)} phoneRows>
              <table className="w-full text-sm">
                <thead className="border-b bg-ground-50">
                  <tr>
                    <th className={TH}>{t(`${K}.col.mentor`)}</th>
                    <th className={TH}>{t('admin.team.colAlsoIn')}</th>
                    {['area', 'languages', 'scholarsNow', 'meetings90', 'lastMeeting', 'concernsOpen'].map((c) => (
                      <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>
                    ))}
                    <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {rows.map((m) => {
                    const langs = languagesLine(m)
                    const action = actionOf(m)
                    return (
                      <tr key={m.id} data-testid={`mentor-row-${m.id}`} className="align-top">
                        <td className="px-4 py-3">
                          <Link href={mentorHref(m.id)} data-testid={`mentor-link-${m.id}`}
                            className="font-medium text-primary-600 hover:text-primary-800">{m.name}</Link>
                          <span className="block text-xs text-ground-500">
                            {m.email}{m.phone ? ` · ${m.phone}` : ''}
                          </span>
                        </td>
                        <td className="px-4 py-3" data-label={t('admin.team.colAlsoIn')}><AlsoIn row={m} here="mentors" /></td>
                        <td className={`px-4 py-3 ${m.area ? '' : 'text-ground-500'}`} data-label={t(`${K}.col.area`)}>{m.area || t(`${K}.notFilled`)}</td>
                        <td className={`px-4 py-3 ${langs ? '' : 'text-ground-500'}`} data-label={t(`${K}.col.languages`)}>{langs || t(`${K}.notFilled`)}</td>
                        <td className="px-4 py-3 tabular-nums" data-label={t(`${K}.col.scholarsNow`)} data-testid={`mentor-scholars-${m.id}`}>{m.scholars_now ?? 0}</td>
                        <td className="px-4 py-3 tabular-nums" data-label={t(`${K}.col.meetings90`)} data-testid={`mentor-meetings-${m.id}`}>{m.meetings_90 ?? 0}</td>
                        <td className="px-4 py-3 whitespace-nowrap" data-label={t(`${K}.col.lastMeeting`)}>
                          {m.last_meeting ? formatDate(m.last_meeting) : <span className="text-ground-400">-</span>}
                        </td>
                        {/* T3 review: null for a caller without `see_all` (no scholar data) — a dash. */}
                        <td className={`px-4 py-3 tabular-nums ${m.concerns_open ? 'font-semibold text-caution-700' : ''}`} data-label={t(`${K}.col.concernsOpen`)}
                          data-testid={`mentor-concerns-${m.id}`}>
                          {m.concerns_open === null ? <span className="text-ground-400">-</span> : (m.concerns_open ?? 0)}</td>
                        <td className="whitespace-nowrap px-4 py-3">
                          {m.manageable && (
                            <button type="button" disabled={busyId === m.id} data-testid={`mentor-action-${m.id}`}
                              className={REMOVES.includes(action)
                                ? 'text-sm font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50' : LINK}
                              onClick={() => (REMOVES.includes(action) ? setRemoving(m) : void act(m, action))}>
                              {t(`${K}.action.${action}`)}
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
          <p className="text-xs text-ground-500">{t(`${K}.staffNote`)}</p>
        </>
      )}
    </div>
  )
}

// ── The mentor detail page ───────────────────────────────────────────────────────────────────────────

const CONCERN_TONE: Record<string, string> = {
  open: 'bg-caution-100 text-caution-800',
  handled: 'bg-ground-100 text-ground-600',
  closed: 'bg-ground-100 text-ground-600',
}

function Tile({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div className="rounded-xl border bg-ground-0 px-4 py-3" data-testid={testId}>
      <div className="text-xs text-ground-500">{label}</div>
      <strong className="text-xl tabular-nums text-ground-900">{value}</strong>
    </div>
  )
}

function ScholarTable({ t, rows, past, testId }: { t: T; rows: MentorScholarRow[]; past: boolean; testId: string }) {
  const cols = ['scholar', 'since', ...(past ? ['ended'] : []), 'meetings', 'lastMeeting', 'standing', 'concern']
  return (
    <TableFrame minWidth={760} label={t(`${K}.detail.${past ? 'pastTitle' : 'currentTitle'}`)} phoneRows>
      <table className="w-full text-sm" data-testid={testId}>
        <thead className="border-b bg-ground-50">
          <tr>{cols.map((c) => <th key={c} className={TH}>{t(`${K}.detail.col.${c}`)}</th>)}</tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((s) => (
            <tr key={`${s.application_id}-${s.since}`} data-testid={`mentor-scholar-${s.application_id}`}>
              <td className="px-4 py-3">
                {s.has_file
                  ? <Link href={`/admin/scholars/${s.application_id}`}
                      className="font-medium text-primary-600 hover:text-primary-800">{s.name || `#${s.application_id}`}</Link>
                  : <span>{s.name || `#${s.application_id}`}</span>}
              </td>
              <td className="px-4 py-3 whitespace-nowrap" data-label={t(`${K}.detail.col.since`)}>{formatDate(s.since)}</td>
              {past && <td className="px-4 py-3 whitespace-nowrap" data-label={t(`${K}.detail.col.ended`)}>{formatDate(s.ended)}</td>}
              <td className="px-4 py-3 tabular-nums" data-label={t(`${K}.detail.col.meetings`)}>{s.meetings}</td>
              <td className="px-4 py-3 whitespace-nowrap" data-label={t(`${K}.detail.col.lastMeeting`)}>
                {s.last_meeting ? formatDate(s.last_meeting) : <span className="text-ground-400">-</span>}
              </td>
              <td className="px-4 py-3" data-label={t(`${K}.detail.col.standing`)}>
                {s.standing
                  ? <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      STANDING_TONE[s.standing as ScholarStanding] ?? STANDING_TONE.no_result_yet}`}>
                      {t(`admin.scholars.standing.${s.standing}`)}</span>
                  : <span className="text-ground-400">-</span>}
              </td>
              <td className="px-4 py-3" data-label={t(`${K}.detail.col.concern`)}>
                {s.concern
                  ? <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${CONCERN_TONE[s.concern]}`}
                      data-testid={`mentor-concern-${s.application_id}`}>{t(`${K}.detail.concern.${s.concern}`)}</span>
                  : <span className="text-ground-400">-</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
  )
}

/** Team → Mentors → a mentor: their work and how it is going (staff only; no meeting notes). */
export function MentorDetail({ id }: { id: number }) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<MentorDetailPayload | null>(null)
  const [failed, setFailed] = useState<'missing' | 'error' | null>(null)

  useEffect(() => {
    if (!token || !id) return
    let live = true
    setData(null); setFailed(null)
    getMentorDetail(id, { token })
      .then((d) => { if (live) setData(d) })
      .catch((e: { status?: number }) => { if (live) setFailed(e?.status === 404 ? 'missing' : 'error') })
    return () => { live = false }
  }, [token, id])

  const back = (
    <Link href="/admin/organisation/reviewers?tab=mentors" data-testid="mentor-back"
      className="text-sm font-medium text-primary-600 hover:text-primary-800">← {t(`${K}.detail.back`)}</Link>
  )
  if (failed) {
    return (
      <div className="space-y-3">{back}
        <p className="text-sm text-critical-600" role="alert">
          {t(failed === 'missing' ? `${K}.detail.notFound` : `${K}.loadError`)}</p>
      </div>
    )
  }
  if (!data) return <div className="space-y-3">{back}<p className="text-sm text-ground-500">{t('common.loading')}</p></div>

  const m = data.mentor
  const f = data.figures
  const langs = languagesLine(m)
  const sees = data.sees_scholars !== false && f !== null
  const facts = [
    m.area || t(`${K}.notFilled`),
    ...(langs ? [langs] : []),
    ...(data.mentoring_since ? [t(`${K}.detail.since`, { date: formatDate(data.mentoring_since) })] : []),
    m.last_seen_at ? t(`${K}.detail.lastSeen`, { date: formatDate(m.last_seen_at) }) : t(`${K}.detail.lastSeenUnknown`),
  ]
  const gap = !f || f.average_gap_days === null ? '-'
    : t(f.average_gap_days === 1 ? `${K}.detail.oneDay` : `${K}.detail.days`, { n: String(f.average_gap_days) })

  return (
    <div className="space-y-5" data-testid="mentor-detail">
      {back}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ground-900 sm:text-2xl">{m.name}</h1>
          <p className="mt-1 text-sm text-ground-600" data-testid="mentor-facts">{facts.join(' · ')}</p>
          {(m.staff_role || m.status === 'inactive') && (
            <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
              {m.staff_role && <span className="rounded-full bg-info-50 px-2 py-0.5 text-info-800">
                {t(`${K}.staffTag`, { role: t(`admin.role.${m.staff_role}`) })}</span>}
              {m.status === 'inactive' && <span className="rounded-full bg-ground-100 px-2 py-0.5 text-ground-600">
                {t(`${K}.status.inactive`)}</span>}
            </p>
          )}
        </div>
      </div>
      {/* T3 review: the scholar side needs the Scholars list's read key (`see_all`). */}
      {!sees || !f ? (
        <p className="rounded-lg border bg-ground-0 p-4 text-sm text-ground-700" data-testid="mentor-needs-see-all">
          {t(`${K}.detail.needSeeAll`)}</p>
      ) : (<>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile testId="tile-scholars" label={t(`${K}.detail.tile.scholarsNow`)} value={String(f.scholars_now)} />
        <Tile testId="tile-meetings" label={t(`${K}.detail.tile.meetings90`)} value={String(f.meetings_90)} />
        <Tile testId="tile-gap" label={t(`${K}.detail.tile.averageGap`)} value={gap} />
        <Tile testId="tile-concerns" label={t(`${K}.detail.tile.concerns`)}
          value={`${f.concerns_raised} / ${f.concerns_open}`} />
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.detail.currentTitle`)}</h2>
        {data.current.length === 0
          ? <p className="text-sm text-ground-500" data-testid="mentor-current-none">{t(`${K}.detail.noneNow`)}</p>
          : <ScholarTable t={t} rows={data.current} past={false} testId="mentor-current" />}
      </section>
      {data.past.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.detail.pastTitle`)}</h2>
          <ScholarTable t={t} rows={data.past} past testId="mentor-past" />
        </section>
      )}
      <p className="text-xs text-ground-500">{t(`${K}.detail.note`)}</p>
      </>)}
    </div>
  )
}
