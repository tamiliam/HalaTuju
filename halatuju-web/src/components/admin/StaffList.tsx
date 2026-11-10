'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { COUNTED, refusalOf, refusalWords } from '@/lib/staffRefusals'
import {
  deleteAdmin, deleteMentor, getStaffList, mentorAction, revokeAdmin, type StaffRow,
} from '@/lib/admin-api'
import StaffAvatar from '@/components/admin/StaffAvatar'
import StaffActions from '@/components/admin/StaffActions'
import TableChips from '@/components/admin/TableChips'
import TypedConfirmDialog from '@/components/admin/TypedConfirmDialog'
import { MessageBanner } from '@/components/admin/StaffAdmin'

/**
 * Sprint M1b: Team -> **Staff**, the first tab and the default (`?tab=staff`). One row per accepted member
 * of the team (`GET admin/staff/`), with their group chips — "No group" when they sit in none.
 *
 * ⚠ SUSPEND / RESTORE AND DELETE LIVE HERE ONLY (owner O3). The group tables keep Add and Remove (O4).
 * ⚠ NO PHONE, NO EMAIL (O16): the row carries neither.
 * ⚠ THE SERVER DECIDES. `revocable`, `deletable`, `delete_never`, `delete_outcome` and `work` are served;
 * this draws them:
 *   - Suspend is greyed, with the reason, while they still mentor scholars (O18) — for a mentor login
 *     too, whose own switch-off would END that mentoring rather than refuse;
 *   - Delete is live when `deletable`, greyed with what is unfinished (O7, reason in the tip: O17), and
 *     absent for yourself, the sole organisation admin, or a row you may not manage;
 *   - Delete's confirm names the outcome — Archive (their name stays on past records) or Erase — and an
 *     archive is sent as `{archive: true}`.
 * A staff row acts through `admin/admins/<id>/`; a mentor's own login through `admin/mentors/<mentor_id>/`.
 */
type T = (k: string, vars?: Record<string, string>) => string
type Banner = { type: 'success' | 'error' | 'warning'; text: string } | null

/** What is unfinished, each in the reader's words with its count — from a row's `work`, or a 409
 *  `has_unfinished_work` body's (the same shape). Missing parts read as none. */
export function unfinishedWords(work: Partial<StaffRow['work']> | undefined, t: T): string {
  const counts: Record<string, number> = {
    ...work?.admins, open_cases: work?.reviewers?.open_cases ?? 0, scholars_now: work?.mentors?.scholars_now ?? 0,
  }
  const said = Object.entries(COUNTED)
    .filter(([, field]) => (counts[field] ?? 0) > 0)
    .map(([code]) => refusalWords(code, t, counts))
    .filter((x): x is string => !!x)
  return said.length > 0 ? said.join(' ') : t('admin.refusal.has_unfinished_work')
}

/** The greyed Delete's tip. */
export const unfinishedReason = (row: StaffRow, t: T) => unfinishedWords(row.work, t)

/** The person page, for a row in a group — read-only for a fellow organisation admin (O10). */
const pageOf = (row: StaffRow) => {
  if (row.suspended || row.groups.length === 0) return null
  if (row.kind === 'mentor') return row.mentor_id ? `/admin/organisation/reviewers/mentors/${row.mentor_id}` : null
  return `/admin/organisation/reviewers/admins/${row.id}`
}

export default function StaffList({ token, canManage, viewerSuper, onChanged }: {
  token: string | null
  /** May this viewer suspend and delete (a super, an organisation admin)? The server re-checks. */
  canManage: boolean
  viewerSuper: boolean
  /** The group tables read their lists again after a change here. */
  onChanged?: () => void
}) {
  const { t } = useT()
  const [rows, setRows] = useState<StaffRow[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [message, setMessage] = useState<Banner>(null)
  // Per row: a second row's action may start while the first is still in flight.
  const [busy, setBusy] = useState<ReadonlySet<number>>(new Set())
  const [deleting, setDeleting] = useState<StaffRow | null>(null)
  const mark = (id: number, on: boolean) => setBusy((b) => {
    const next = new Set(b)
    if (on) next.add(id); else next.delete(id)
    return next
  })

  // Only the LATEST read lands, and none after unmount. A failed RE-read keeps the rows on screen (a
  // stale list beats none) and says so inline, with a Retry; only a first read that fails replaces the list.
  const seq = useRef(0)
  useEffect(() => () => { seq.current += 1 }, [])
  const load = useCallback(() => {
    if (!token) return
    const mine = ++seq.current
    setFailed(false)
    getStaffList({ token })
      .then((d) => { if (mine === seq.current) { setRows(d.staff); setFailed(false) } })
      .catch(() => { if (mine === seq.current) setFailed(true) })
  }, [token])
  useEffect(() => { load() }, [load])

  const refused = (e: unknown) => {
    const err = e as { code?: string; body?: { work?: Partial<StaffRow['work']> } } | null
    const text = err?.code === 'has_unfinished_work' && err.body?.work ? unfinishedWords(err.body.work, t)
      : refusalOf(e, t) ?? (e instanceof Error ? e.message : t('admin.actionFailed'))
    setMessage({ type: 'error', text })
  }
  // Every outcome reads the list again — a refusal too (`has_work`: the row now archives, not erases).
  const after = (id: number) => { mark(id, false); load(); onChanged?.() }

  const toggle = async (row: StaffRow) => {
    if (!token) return
    const going = !row.suspended
    // Suspending a reviewer with open cases: say how many wait on them (the Reviewers table's own confirm).
    const open = row.work.reviewers.open_cases
    const ask = going && open > 0 ? t('admin.staff.suspendConfirmOpen', { name: row.name, n: String(open) })
      : t(going ? 'admin.staff.suspendConfirm' : 'admin.staff.restoreConfirm', { name: row.name })
    if (!window.confirm(ask)) return
    mark(row.id, true); setMessage(null)
    try {
      if (row.kind === 'mentor' && row.mentor_id) {
        await mentorAction(row.mentor_id, going ? 'deactivate' : 'reactivate', { token })
      } else {
        await revokeAdmin(row.id, going ? 'revoke' : 'restore', { token })
      }
      setMessage({ type: 'success', text: t(going ? 'admin.staff.suspended' : 'admin.staff.restored', { name: row.name }) })
    } catch (e) { refused(e) } finally { after(row.id) }
  }

  const remove = async (row: StaffRow) => {
    if (!token) return
    const archive = row.delete_outcome === 'archive'
    mark(row.id, true); setMessage(null)
    try {
      const r = row.kind === 'mentor' && row.mentor_id
        ? await deleteMentor(row.mentor_id, { token }, archive)
        : await deleteAdmin(row.id, { token }, archive)
      setMessage({ type: r?.login === 'failed' ? 'warning' : 'success',
                   text: t(archive ? 'admin.staff.archived' : 'admin.staff.erased', { name: row.name }) })
    } catch (e) { refused(e) } finally { setDeleting(null); after(row.id) }
  }

  if (failed && !rows) return <p className="text-critical-600" role="alert">{t('admin.staff.loadFailed')}</p>
  if (!rows) return <p className="mt-8 text-center text-ground-500">{t('common.loading')}</p>
  return (
    <div data-testid="staff-list">
      <MessageBanner message={message} />
      {failed && (
        <div className="mb-3 flex flex-wrap items-center gap-3" data-testid="staff-reload-failed">
          <p className="text-sm text-critical-600" role="alert">{t('admin.staff.loadFailed')}</p>
          <button type="button" onClick={load} className="text-sm font-medium text-primary-600 hover:text-primary-800">
            {t('common.retry')}</button>
        </div>
      )}
      {rows.length === 0 ? (
        <p className="mt-8 text-center text-ground-500">{t('admin.staff.empty')}</p>
      ) : (
        <ul className="divide-y divide-ground-100 rounded-xl border border-ground-200 bg-ground-0">
          {rows.map((row) => (
            <StaffLine key={row.id} row={row} t={t} canManage={canManage} viewerSuper={viewerSuper}
              busy={busy.has(row.id)} onToggle={() => toggle(row)} onDelete={() => setDeleting(row)} />
          ))}
        </ul>
      )}
      {deleting && (
        <TypedConfirmDialog busy={busy.has(deleting.id)} phrase={deleting.name.trim() || t('admin.delete')}
          title={t('admin.programmes.deleteTitle', { name: deleting.name })}
          body={<span data-testid="staff-delete-outcome">
            {t(`admin.staff.outcome.${deleting.delete_outcome === 'archive' ? 'archive' : 'erase'}`)}</span>}
          cta={t('admin.delete')} onCancel={() => setDeleting(null)} onConfirm={() => remove(deleting)} />
      )}
    </div>
  )
}

/** One member: photo, name, group chips (or "No group"), status, last seen, and — for a manager — the pair. */
function StaffLine({ row, t, canManage, viewerSuper, busy, onToggle, onDelete }: {
  row: StaffRow
  t: T
  canManage: boolean
  viewerSuper: boolean
  busy: boolean
  onToggle: () => void
  onDelete: () => void
}) {
  const href = canManage ? pageOf(row) : null   // the person page's own fence (super, organisation admin)
  const acts = canManage && row.manageable
  const scholars = row.work.mentors.scholars_now
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3" data-testid={`staff-row-${row.id}`}>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <StaffAvatar name={row.name} photoUrl={row.photo_url} size={32} />
        <div className="min-w-0">
          {href ? (
            <Link href={href} className="font-medium text-primary-600 hover:text-primary-800">{row.name || '—'}</Link>
          ) : <span className="font-medium text-ground-900">{row.name || '—'}</span>}
          <div className="mt-0.5 flex flex-wrap items-center gap-1">
            {row.groups.length > 0
              ? <TableChips tables={row.groups} lead={row.lead} testId={`staff-groups-${row.id}`} />
              : <span className="rounded-full bg-ground-100 px-2 py-0.5 text-[11px] font-medium text-ground-600"
                  data-testid={`staff-no-group-${row.id}`}>{t('admin.staff.noGroup')}</span>}
          </div>
        </div>
      </div>
      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${row.suspended
        ? 'bg-critical-50 text-critical-700' : 'bg-positive-50 text-positive-700'}`}>
        {t(row.suspended ? 'admin.staff.statusSuspended' : 'admin.staff.statusActive')}
      </span>
      <span className="text-xs text-ground-500">
        {row.last_seen_at ? t('admin.staff.lastSeen', { date: formatDate(row.last_seen_at) }) : t('admin.reviewers.lastSeenUnknown')}
      </span>
      {acts && (
        <span className="flex flex-wrap items-center gap-3">
          <StaffActions active={!row.suspended} busy={busy} size="xs"
            revokeKey="admin.staff.suspend" restoreKey="admin.restore" toggleTestId={`staff-toggle-${row.id}`}
            onToggle={row.revocable ? onToggle : undefined}
            toggleBlocked={!row.suspended && scholars > 0 ? refusalWords('has_scholars', t, { scholars_now: scholars }) : null}
            onDelete={onDelete} deletable={row.deletable}
            deleteNever={row.delete_never !== null && row.delete_never !== 'has_unfinished_work'}
            deleteBlocked={row.delete_never === 'has_unfinished_work' ? unfinishedReason(row, t) : null}
            orgAdmin={row.lead} viewerSuper={viewerSuper} />
        </span>
      )}
    </li>
  )
}
