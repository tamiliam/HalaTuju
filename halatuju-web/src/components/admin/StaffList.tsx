'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { COUNTED, refusalOf, refusalWords } from '@/lib/staffRefusals'
import { firstGroupPage } from '@/lib/teamPaths'
import {
  DEFAULT_MEMBER_SORT, MEMBER_FILTERS, MEMBER_SORT_LABEL, filterMembers, sortMembers,
  type MemberFilter, type MemberSortKey,
} from '@/lib/memberTable'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import {
  deleteAdmin, deleteMentor, getStaffList, mentorAction, revokeAdmin, type StaffRow,
} from '@/lib/admin-api'
import StaffAvatar from '@/components/admin/StaffAvatar'
import StaffActions from '@/components/admin/StaffActions'
import TableChips from '@/components/admin/TableChips'
import TypedConfirmDialog from '@/components/admin/TypedConfirmDialog'
import SortHeader from '@/components/admin/SortHeader'
import TableFrame from '@/components/admin/TableFrame'
import { Pagination } from '@/components/Pagination'
import { MessageBanner } from '@/components/admin/StaffAdmin'

/**
 * Sprint M1b: Team -> **Staff**, the first tab and the default (`?tab=staff`). One row per accepted member
 * of the team (`GET admin/staff/`), with their group chips — "No group" when they sit in none.
 * Sprint M2c (owner R4): the tab reads **Members** (`?tab=members` too) and the list is a table like the
 * console's others — sortable Name / Groups / Status (`lib/memberTable`), a name search, a status filter,
 * pages; below md the SAME table restacks as rows (`TableFrame phoneRows`), so every control exists once.
 * R1: whoever manages the team sees how many open cases suspended members still hold (`suspended_cases`, a
 * banner here — the Overview card would have cost a query the ledger does not have), with a button that
 * filters the table to the suspended.
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

/** The never-rules Delete is GREYED for, with a reason, rather than left out: both pass once the person acts
 *  (M2c, owner R2: `in_a_group` until they are in No group; `has_unfinished_work` until it is handed on). */
const GREYED: ReadonlySet<string> = new Set(['in_a_group', 'has_unfinished_work'])
export const deleteReason = (row: StaffRow, t: T) =>
  row.delete_never === 'in_a_group' ? refusalWords('in_a_group', t)
    : row.delete_never === 'has_unfinished_work' ? unfinishedReason(row, t) : null

/** The person page, for a row in a group — read-only for a fellow organisation admin (O10). Sprint M2a
 *  (U5): the FIRST group page they have, in the order Admins, Reviewers, Mentors (a pure mentor's is the
 *  mentor page, by their mentor record); in no group, or suspended, no link. */
export const pageOf = (row: StaffRow) => {
  if (row.suspended) return null
  return firstGroupPage(row.groups, { admin_id: row.kind === 'staff' ? row.id : null, mentor_id: row.mentor_id })
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
  const [held, setHeld] = useState(0)   // open cases suspended members hold (R1); 0 = no banner
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<MemberFilter>('all')
  const { sort, setSort } = useSort<MemberSortKey>(DEFAULT_MEMBER_SORT)
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
      .then((d) => {
        if (mine !== seq.current) return
        setRows(d.staff); setHeld(d.suspended_cases ?? 0); setFailed(false)
      })
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

  // Filter, then sort the whole list, then page the result — sorting one page at a time would shuffle rows
  // between pages. Above the early returns: hooks keep their order.
  const shown = sortMembers(filterMembers(rows ?? [], query, status), sort.key, sort.dir)
  const paged = usePagedRows(shown)
  const onSort = (col: MemberSortKey) => setSort(nextSort(sort, col))

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
      {held > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3"
          data-testid="staff-suspended-cases">
          <p className="text-sm text-caution-700">
            {t(`admin.staff.suspendedCases.${held === 1 ? 'one' : 'many'}`, { n: String(held) })}</p>
          {status !== 'suspended' && (
            <button type="button" onClick={() => setStatus('suspended')} data-testid="staff-show-suspended"
              className="text-sm font-medium text-primary-600 hover:text-primary-800">
              {t('admin.staff.showSuspended')}</button>
          )}
        </div>
      )}
      {rows.length === 0 ? (
        <p className="mt-8 text-center text-ground-500">{t('admin.staff.empty')}</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <label className="block min-w-0 flex-1 text-sm text-ground-600">{t('admin.staff.search')}
              <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} data-testid="staff-search"
                className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 text-base focus:border-info-500 focus:ring-2 focus:ring-info-500" />
            </label>
            <label className="block text-sm text-ground-600">{t('admin.reviewers.colStatus')}
              <select value={status} onChange={(e) => setStatus(e.target.value as MemberFilter)} data-testid="staff-filter"
                className="mt-1 block rounded-lg border border-ground-300 px-3 py-2 text-base">
                {MEMBER_FILTERS.map((f) => <option key={f} value={f}>{t(FILTER_LABEL[f])}</option>)}
              </select>
            </label>
          </div>
          {shown.length === 0 ? (
            <p className="mt-8 text-center text-ground-500" data-testid="staff-no-match">{t('admin.staff.noMatch')}</p>
          ) : (
            <TableFrame phoneRows minWidth={canManage ? 900 : 640} label={t('admin.staff.tab')}>
              <table className="w-full text-sm">
                <thead className="border-b bg-ground-50/80">
                  <tr>
                    <SortHeader col="name" label={t(MEMBER_SORT_LABEL.name)} sort={sort} onSort={onSort} />
                    <SortHeader col="groups" label={t(MEMBER_SORT_LABEL.groups)} sort={sort} onSort={onSort} />
                    <SortHeader col="status" label={t(MEMBER_SORT_LABEL.status)} sort={sort} onSort={onSort} />
                    <th className={TH}>{t('admin.reviewers.colLastSeen')}</th>
                    {canManage && <th className={TH}>{t('admin.actionHeader')}</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ground-100">
                  {paged.rows.map((row) => (
                    <StaffLine key={row.id} row={row} t={t} canManage={canManage} viewerSuper={viewerSuper}
                      busy={busy.has(row.id)} onToggle={() => toggle(row)} onDelete={() => setDeleting(row)} />
                  ))}
                </tbody>
              </table>
            </TableFrame>
          )}
          {paged.visible && (
            <div className="mt-3">
              <Pagination page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
                onPageChange={paged.setPage} pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize} />
            </div>
          )}
        </>
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

const TH = 'px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-ground-600'
const FILTER_LABEL: Record<MemberFilter, string> = {
  all: 'admin.staff.filterAll', active: 'admin.staff.statusActive', suspended: 'admin.staff.statusSuspended',
}

/** One member's row: photo and name, group chips (or "No group"), status, last seen, and — for a manager —
 *  the pair. Each cell names itself (`data-label`) for the phone's restacked rows. */
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
    <tr data-testid={`staff-row-${row.id}`}>
      <td className="px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <StaffAvatar name={row.name} photoUrl={row.photo_url} size={32} />
          {href ? (
            <Link href={href} className="font-medium text-primary-600 hover:text-primary-800">{row.name || '—'}</Link>
          ) : <span className="font-medium text-ground-900">{row.name || '—'}</span>}
        </div>
      </td>
      <td className="px-4 py-3" data-label={t(MEMBER_SORT_LABEL.groups)}>
        <span className="inline-flex flex-wrap items-center gap-1">
          {row.groups.length > 0
            ? <TableChips tables={row.groups} lead={row.lead} testId={`staff-groups-${row.id}`} />
            : <span className="rounded-full bg-ground-100 px-2 py-0.5 text-[11px] font-medium text-ground-600"
                data-testid={`staff-no-group-${row.id}`}>{t('admin.staff.noGroup')}</span>}
        </span>
      </td>
      <td className="px-4 py-3" data-label={t(MEMBER_SORT_LABEL.status)}>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${row.suspended
          ? 'bg-critical-50 text-critical-700' : 'bg-positive-50 text-positive-700'}`}>
          {t(row.suspended ? 'admin.staff.statusSuspended' : 'admin.staff.statusActive')}
        </span>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-xs text-ground-500" data-label={t('admin.reviewers.colLastSeen')}>
        {row.last_seen_at ? formatDate(row.last_seen_at) : t('admin.reviewers.lastSeenUnknown')}
      </td>
      {canManage && (
        <td className="px-4 py-3">
          {acts && (
            <span className="flex flex-wrap items-center gap-3">
              <StaffActions active={!row.suspended} busy={busy} size="xs"
                revokeKey="admin.staff.suspend" restoreKey="admin.restore" toggleTestId={`staff-toggle-${row.id}`}
                onToggle={row.revocable ? onToggle : undefined}
                toggleBlocked={!row.suspended && scholars > 0 ? refusalWords('has_scholars', t, { scholars_now: scholars }) : null}
                onDelete={onDelete} deletable={row.deletable}
                deleteNever={row.delete_never !== null && !GREYED.has(row.delete_never)}
                deleteBlocked={deleteReason(row, t)}
                orgAdmin={row.lead} viewerSuper={viewerSuper} />
            </span>
          )}
        </td>
      )}
    </tr>
  )
}
