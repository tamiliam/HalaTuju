'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState, type ComponentType } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import { STANDING_TONE } from '@/lib/scholars'
import { STAFF_STATUS_TONE } from '@/lib/staffStatus'
import { refusalWords, scholarsRefusal } from '@/lib/staffRefusals'
import {
  getMentors, mentorAction, setMentorGifts,
  type MentorAction, type MentorDetail as MentorDetailPayload, type MentorRow, type MentorScholarRow,
  type MentorsPayload, type ReviewerGiftTag, type ScholarStanding,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import Sheet from '@/components/Sheet'
import ReviewerGiftsCell from '@/components/admin/ReviewerGifts'
import StaffMentorSheet from './StaffMentorSheet'
import { Greyed } from '@/components/admin/StaffActions'

/**
 * Team → **Mentors** and the mentor parts of a **person page** (Team tables T3, 2026-11-03; the TeamMentors
 * board the owner approved; roadmap ruling 6). Before T3 this file was the Organisation → Mentors page
 * (S7a–S7d); that route now redirects here. ONE CHUNK for both screens: the Team page and the person page
 * (sprint T3 person page, 2026-11-09: `MentorFigures`, `MentorWork`, `MentorActions`) each load it with this
 * literal specifier, so no new chunk joins the webpack runtime every route downloads (the S7b follow-up
 * review's lesson).
 *
 * ⚠ ONE LIST, READ LIKE ADMINS AND REVIEWERS (owner 2026-11-08): the mentors who have ARRIVED (signed in)
 * plus every staff member who mentors, with a Status (Active / Revoked) and Last seen column. No
 * Active / Inactive chips and no "waiting to accept" line: a mentor invited and not signed in yet is
 * Invitations → Mentor's business, as on the other tabs. A revoked pure mentor stays listed (Revoked,
 * with Restore); a staff member taken off Mentors drops off the list and comes back through Add Mentor.
 * ⚠ "INVITE A MENTOR" IS GONE (ruling 6): new mentors are invited on Invitations → Mentor. **Add Mentor**
 * is 7d's "Add a staff member as mentor" (`StaffMentorSheet`, the shared Sheet): an existing team member,
 * no email, their sign-in untouched. Its button sits on the Team page's tab row (the page owns `adding`).
 * ⚠ ADD AND REMOVE ONLY (M1b, owner O4): **Remove from Mentors** — a staff member's (endpoint `stop`, the
 * sign-in untouched) or a mentor login's (endpoint `remove` with `to_no_group`: they stay on as a member in
 * No group, the confirm says so). Either is GREYED, with the reason in its tip (O17), while they still mentor
 * scholars. Suspend / Restore and Delete live on the Staff tab only (O3). Offered only where the row's
 * `manageable` says the endpoint will take it; the confirm is the shared Sheet.
 * ⚠ STAFF NEVER EDIT A MENTOR'S PROFILE. Area and languages are the mentor's own; they are shown on the
 * mentor's person page (its Profile tab), not as table columns.
 * ⚠ THE MENTOR PARTS OF A PERSON PAGE (Sprint T3: `MentorFigures`, `MentorWork`, drawn by
 * `components/admin/person/MentorGroupPage`) ARE STAFF ONLY AND SHOW NO MEETING NOTE: figures, scholars,
 * dates, standing, concern state. Notes stay on each scholar's file. Who reads them = who reads this table
 * (`GET admin/mentors/<id>/`).
 * ⚠ `superRole` (a leaf), never `lib/navigation`: importing the route registry here split it into a shared
 * chunk once — one more runtime entry every route pays for (S7b follow-up review fix 5). The Team page
 * decides who sees the tab (`pageGuard.mayReadMentors`) and hands in its own "Also in" chips.
 */

type T = (k: string, vars?: Record<string, string>) => string
type Banner = { ok: boolean; text: string } | null

const K = 'admin.mentors'
const ACTION_REFUSALS = ['already_joined', 'not_active', 'active', 'not_arrived', 'not_eligible', 'staff_mentor',
  'not_staff', 'has_work', 'has_scholars', 'last_table']
/** The two Removes (M1b): a staff mentor's `stop`, a mentor login's `remove` (to No group). */
type RemoveAction = Extract<MentorAction, 'stop' | 'remove'>

const codeOf = (err: unknown) => (err as { code?: string })?.code ?? ''

/** A refused action in the reader's language: `has_scholars` (M1a: Remove from Mentors and Delete are
 *  refused while they mentor anyone) names the API's `scholars_now`; a code we do not know is the generic line. */
export function refusalText(err: unknown, t: T): string {
  const code = codeOf(err)
  return scholarsRefusal(err, t, `${K}.error.has_scholars`)
    ?? t(`${K}.error.${ACTION_REFUSALS.includes(code) ? code : 'generic'}`)
}

/** The codes of the languages spoken conversationally or better, in en · ms · ta order. */
function spokenCodes(m: MentorRow): ('en' | 'ms' | 'ta')[] {
  return (['en', 'ms', 'ta'] as const).filter((k) => m.languages[k] === 'conversational'
    || m.languages[k] === 'fluent')
}

/** "EN · MS · TA (+ Mandarin)" — the languages spoken conversationally or better; '' when none. */
export function languagesLine(m: MentorRow): string {
  const codes = spokenCodes(m).map((k) => k.toUpperCase())
  return [...codes, ...(m.other_language ? [m.other_language] : [])].join(' · ')
}

/** Who the table lists: arrived mentors and staff mentors, except a staff member taken off Mentors
 *  (they come back through Add Mentor). A revoked pure mentor stays, marked Revoked. */
export function listed(m: MentorRow): boolean {
  if (m.status === 'invited' || !(m.staff_role || m.signed_in)) return false
  return m.status === 'active' || !m.staff_role
}

/** The row's one action (endpoint names), M1b: "Remove from Mentors" on an active row — a staff mentor's
 *  `stop`, a mentor login's `remove` (they become No group). None on a suspended row: Restore is on Staff. */
export function actionOf(m: MentorRow): RemoveAction | null {
  if (m.status !== 'active') return null
  return m.staff_role ? 'stop' : 'remove'
}

/** The Team page's own "Also in" chips (`components/admin/TeamTables`), handed in by the route. */
export type AlsoInChips = ComponentType<{ row: { tables?: string[]; lead?: boolean }; here: 'mentors' }>

export const mentorHref = (id: number) => `/admin/organisation/team/mentors/${id}`

/** `adding` / `onAddClose`: the Team page's Add Mentor button (on its tab row) opens the sheet here. */
export default function TeamMentors({ AlsoIn, adding = false, onAddClose }: {
  AlsoIn: AlsoInChips
  adding?: boolean
  onAddClose?: () => void
}) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const mayManage = ['super', 'org_admin'].includes(r)
  const [data, setData] = useState<MentorsPayload | null>(null)
  const [failed, setFailed] = useState(false)
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [removing, setRemoving] = useState<MentorRow | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    try {
      const d = await getMentors({ token })
      setData(d); setFailed(false)
    } catch { setFailed(true) }
  }, [token])
  useEffect(() => { void load() }, [load])

  const act = async (m: MentorRow, action: MentorAction) => {
    if (!token) return
    setBusyId(m.id); setBanner(null)
    try {
      await mentorAction(m.id, action, { token }, action === 'remove' ? { to_no_group: true } : {})
      setBanner({ ok: true, text: t(`${K}.done.${action}`, { name: m.name, email: m.email }) })
    } catch (err) {
      setBanner({ ok: false, text: refusalText(err, t) })
    } finally {
      setBusyId(null); setRemoving(null)
      void load()
    }
  }

  // ARRIVED = has signed in (`mentor_invite.has_signed_in`, the server's `signed_in`). A mentor switched
  // off before arriving is not listed: a re-invite on Invitations brings them back. `listed` has the rule.
  const rows = (data?.mentors ?? []).filter(listed)
  // A staff mentor removed from Mentors drops off the list; Add Mentor offers them back (`resume`).
  // M1b: never a member (No group) — Add Mentor brings them back as a mentor through the Team tables' Add.
  const returning = (data?.mentors ?? []).filter((m) => m.staff_role && m.staff_role !== 'member'
    && m.status === 'inactive' && m.manageable)
  const removingAction = removing ? actionOf(removing) : null

  return (
    <div className="space-y-4" data-testid="team-mentors">
      {mayManage && (
        <StaffMentorSheet open={adding} token={token} t={t} onClose={() => onAddClose?.()}
          returning={returning}
          onAdded={(row, back) => {
            onAddClose?.()
            setBanner({ ok: true, text: t(`${K}.done.${back ? 'resume' : 'added'}`, { name: row.name }) })
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

      {data && (
        <>
          {rows.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500"
              data-testid="mentors-empty">
              {t(mayManage ? `${K}.emptyNone` : `${K}.emptyNoneRead`)}
            </div>
          ) : (
            <TableFrame minWidth={1000} label={t(`${K}.title`)} phoneRows>
              <table className="w-full text-sm">
                <thead className="border-b bg-ground-50">
                  <tr>
                    <th className={TH}>{t('admin.nameHeader')}</th>
                    <th className={TH}>{t('admin.team.colAlsoIn')}</th>
                    {['scholarsNow', 'meetings90', 'lastMeeting', 'concernsOpen'].map((c) => (
                      <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>
                    ))}
                    <th className={TH}>{t('admin.statusHeader')}</th>
                    <th className={TH}>{t('admin.reviewers.colLastSeen')}</th>
                    <th className={TH}>{t('admin.actionHeader')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {rows.map((m) => {
                    const action = actionOf(m)
                    const active = m.status === 'active'
                    return (
                      <tr key={m.id} data-testid={`mentor-row-${m.id}`} className="align-top">
                        <td className="px-4 py-3">
                          <Link href={mentorHref(m.id)} data-testid={`mentor-link-${m.id}`}
                            className="font-medium text-primary-600 hover:text-primary-800">{m.name}</Link>
                          <span className="block text-xs text-ground-500">{m.email}</span>
                        </td>
                        <td className="px-4 py-3" data-label={t('admin.team.colAlsoIn')}><AlsoIn row={m} here="mentors" /></td>
                        <td className="px-4 py-3 tabular-nums" data-label={t(`${K}.col.scholarsNow`)} data-testid={`mentor-scholars-${m.id}`}>{m.scholars_now ?? 0}</td>
                        <td className="px-4 py-3 tabular-nums" data-label={t(`${K}.col.meetings90`)} data-testid={`mentor-meetings-${m.id}`}>{m.meetings_90 ?? 0}</td>
                        <td className="px-4 py-3 whitespace-nowrap" data-label={t(`${K}.col.lastMeeting`)}>
                          {m.last_meeting ? formatDate(m.last_meeting) : <span className="text-ground-400">-</span>}
                        </td>
                        {/* T3 review: null for a caller without `scholars` (sprint S1; no scholar data) — a dash. */}
                        <td className={`px-4 py-3 tabular-nums ${m.concerns_open ? 'font-semibold text-caution-700' : ''}`} data-label={t(`${K}.col.concernsOpen`)}
                          data-testid={`mentor-concerns-${m.id}`}>
                          {m.concerns_open === null ? <span className="text-ground-400">-</span> : (m.concerns_open ?? 0)}</td>
                        <td className="px-4 py-3" data-label={t('admin.statusHeader')}>
                          <span data-testid={`mentor-status-${m.id}`}
                            className={`inline-block rounded-full px-2 py-0.5 text-xs ${STAFF_STATUS_TONE[active ? 'active' : 'revoked']}`}>
                            {t(active ? 'admin.active' : 'admin.revoked')}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap" data-label={t('admin.reviewers.colLastSeen')}
                          data-testid={`mentor-last-seen-${m.id}`}>
                          {m.last_seen_at ? formatDate(m.last_seen_at)
                            : <span className="text-ground-400">{t('admin.reviewers.lastSeenUnknown')}</span>}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          {/* M1b (O4): Remove from Mentors only — greyed, with the reason, while they mentor. */}
                          {m.manageable && action && (
                            <MentorRemove m={m} t={t} busy={busyId === m.id} onRemove={() => setRemoving(m)} />
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </TableFrame>
          )}
        </>
      )}
    </div>
  )
}

/** M1b: a row's "Remove from Mentors", greyed with the reason (and the count) while they mentor scholars. */
function MentorRemove({ m, t, busy, onRemove }: { m: MentorRow; t: T; busy: boolean; onRemove: () => void }) {
  const scholars = m.scholars_now ?? 0
  if (scholars > 0) {
    return <Greyed label={t(`${K}.action.stop`)} text="text-sm" testId={`mentor-action-${m.id}-greyed`}
      reason={refusalWords('has_scholars', t, { scholars_now: scholars }) ?? ''} />
  }
  return (
    <button type="button" disabled={busy} data-testid={`mentor-action-${m.id}`} onClick={onRemove}
      className="text-sm font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
      {t(`${K}.action.stop`)}
    </button>
  )
}

// ── The mentor parts of a person page ───────────────────────────────────────────────────────────────────────────

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

/** I4: the words for a refused gift edit — open point D names how many current scholars are outside. */
function giftRefusal(t: T, err: unknown): string {
  const e = err as { code?: string; body?: { count?: number } }
  if (e?.code === 'mentor_has_scholars_outside') {
    return t(`${K}.gifts.outside`, { count: String(e.body?.count ?? '') })
  }
  return t('admin.reviewers.detail.giftFailed')
}

/** Invitations I4 on the person page (merged with Sprint T3, 2026-11-09): the gifts a mentor mentors in
 *  (none named = every gift), in the header card under a reviewer's own gifts — where the old mentor
 *  detail page drew them. The SERVER refuses a narrowing that would leave a current scholar outside (409,
 *  with how many): nothing ends. A pencil only where the row's `manageable` says so and the payload
 *  carries the organisation's `programmes` (an older api offers no edit). */
export function MentorGifts({ data, onSaved }: {
  data: MentorDetailPayload
  onSaved: (gifts: ReviewerGiftTag[]) => void
}) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const m = data.mentor
  return (
    <div className="text-sm text-ground-500 flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="mentor-gifts">
      <span>{t(`${K}.gifts.label`)}</span>
      <ReviewerGiftsCell reviewer={{ id: m.id, name: m.name, gifts: m.gifts ?? [] }}
        options={data.programmes ?? []} token={token}
        canEdit={m.manageable && data.programmes !== undefined}
        save={async (ids, tok) => (await setMentorGifts(m.id, ids, { token: tok })).gifts}
        errorOf={(err) => giftRefusal(t, err)}
        onSaved={onSaved} />
    </div>
  )
}

/** T3 review fix 3: a STAFF mentor's **Remove from Mentors** (`stop`) on their person page — the table's
 *  action and words: refused while they mentor anyone (M1a), the staff sign-in is untouched. Drawn only
 *  while they mentor and the row's `manageable` says the endpoint will take it (their Suspend is on Staff, M1b).
 *  Greyed, with the reason, while they mentor scholars (M1b, O17). */
export function StaffMentorRemove({ mentor: m, onRemoved }: { mentor: MentorRow; onRemoved: () => void }) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  if (!m.manageable || !m.staff_role || m.status !== 'active') return null
  const stop = async () => {
    if (!token || !window.confirm(t(`${K}.confirm.stop`, { name: m.name }))) return
    setBusy(true); setActionError('')
    try {
      await mentorAction(m.id, 'stop', { token })
      onRemoved()
    } catch (err) { setActionError(refusalText(err, t)) } finally { setBusy(false) }
  }
  const scholars = m.scholars_now ?? 0
  return (
    <div>
      {scholars > 0 ? (
        <Greyed label={t(`${K}.action.stop`)} text="text-sm" testId="mentor-person-stop-greyed"
          reason={refusalWords('has_scholars', t, { scholars_now: scholars }) ?? ''} />
      ) : (
        <button type="button" disabled={busy} data-testid="mentor-person-stop" onClick={() => void stop()}
          className="max-md:inline-flex max-md:min-h-11 max-md:items-center text-sm font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
          {t(`${K}.action.stop`)}
        </button>
      )}
      {actionError && <p className="mt-1.5 text-sm text-critical-600" role="alert">{actionError}</p>}
    </div>
  )
}

/** Sprint T3 (M4): a mentor's figures, in the person page's header card. Nothing for a caller without
 *  the Scholars list's read key (`scholars`, sprint S1) — the Profile tab says why. */
export function MentorFigures({ data }: { data: MentorDetailPayload }) {
  const { t } = useT()
  const f = data.figures
  if (data.sees_scholars === false || !f) return null
  const gap = f.average_gap_days === null ? '-'
    : t(f.average_gap_days === 1 ? `${K}.detail.oneDay` : `${K}.detail.days`, { n: String(f.average_gap_days) })
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="mentor-figures">
      <Tile testId="tile-scholars" label={t(`${K}.detail.tile.scholarsNow`)} value={String(f.scholars_now)} />
      <Tile testId="tile-meetings" label={t(`${K}.detail.tile.meetings90`)} value={String(f.meetings_90)} />
      <Tile testId="tile-gap" label={t(`${K}.detail.tile.averageGap`)} value={gap} />
      <Tile testId="tile-concerns" label={t(`${K}.detail.tile.concerns`)}
        value={`${f.concerns_raised} / ${f.concerns_open}`} />
    </div>
  )
}

/** Sprint T3 (M6): the mentor parts of a person's Profile tab — beside the reviewer parts for somebody
 *  in both tables: their scholars now and past. Staff only; never a meeting note. */
export function MentorWork({ data }: { data: MentorDetailPayload }) {
  const { t } = useT()
  // T3 review: the scholar side needs the Scholars list's read key (`scholars`, sprint S1).
  if (data.sees_scholars === false || !data.figures) {
    return (
      <p className="rounded-lg border bg-ground-0 p-4 text-sm text-ground-700" data-testid="mentor-needs-see-all">
        {t(`${K}.detail.needSeeAll`)}</p>
    )
  }
  return (
    <div className="space-y-5" data-testid="mentor-work">
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
    </div>
  )
}
