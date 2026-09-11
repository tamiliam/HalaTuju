'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import { listReviewers, type AdminItem, type AdminReviewer } from '@/lib/admin-api'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { isFree, orderedLanguages, turnaroundBand } from '@/lib/reviewerDetail'
import {
  DEFAULT_SORT, REVIEWER_SORT_LABEL, firstDirFor, sortReviewers,
  type ReviewerSortKey,
} from '@/lib/reviewerTable'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import SortHeader from '@/components/admin/SortHeader'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import { Pagination } from '@/components/Pagination'
import ReviewerEmailsCard from '@/components/reviewers/ReviewerEmailsCard'
import { roleBadgeClass } from '@/lib/roleBadge'
import { formatDate } from '@/lib/formatDate'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'
import { revokeAdmin, deleteAdmin } from '@/lib/admin-api'
import { byCategory } from '@/lib/adminStaff'
import { MessageBanner, StaffTable, useStaffAdmin } from '@/components/admin/StaffAdmin'

// Organisation → **People**: the directory of everybody who is already in.
//
// It began as the reviewers directory (request #10) — "Invitations invites; this is where you LOOK
// at somebody before handing them the next case" — and on 2026-09-09 it took the **Admins** tab as
// well, closing the two faults the owner reported:
//   * the 13 reviewers were listed HERE and on Invitations, identically, and
//   * the 5 admins had no directory at all, so their only home was a page about asking.
// The two tabs are the owner's own split, recorded in `adminStaff.ts` on 2026-08-03: *"There are
// two categories of people here: reviewers and admins. QC is a reviewer as well. And finance is
// also an admin."* Same two categories the Invitations page groups by, so nobody has to learn a
// second vocabulary.
//
// ⚠ **REVOKE AND RESTORE LIVE HERE NOW, not on Invitations.** Revoking is something you do to
// somebody who has ARRIVED, and Invitations no longer lists anybody who has. They sit beside Pause
// (on a reviewer's detail page) so one place decides whether a person is in — the two controls
// used to be on different screens.
//
// The reviewers tab is the default and stays sorted by open caseload, because "who can take this
// case?" is asked daily and "who still has access?" is not.
//
// A corrections count is deliberately absent and must stay absent unless the owner says
// otherwise: it reads as a competence score, and the reopens live on the detail page WITH their
// reasons.
//
// ⚠ THE GIFT WAS ABSENT FOR THE SAME KIND OF REASON AND IS NOW CONDITIONAL (S-ASSIGN,
// 2026-09-04). Owner, 2026-08-02: "with one programme it could only ever say one thing". That
// is still true of a one-gift organisation, so it renders only above one gift — the ruling is
// honoured rather than reversed. It is a line under the name, not a column: inventing a sort
// key and a header for a fact most organisations never see is furniture.

const roleBadge = (r: string) => roleBadgeClass(r)


export default function AdminReviewersList() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // UX only — the endpoint is the fence. This just avoids rendering a table that would 403.
  const mayView = canAccess('/admin/organisation/reviewers', effectiveRole(role))
  // The same pill idiom the Sponsors and Sources screens use, so the console has one way of doing
  // this. Reviewers is the default: "who can take this case?" is the daily question, and both
  // "who still has access?" and "what are volunteers told?" are deliberate second clicks.
  // ⚠ THE TAB IS IN THE URL because another page links straight to one. The Invitations empty
  // state says "everyone invited has accepted — see who is in", and under the ADMINS kind that
  // link must land on the Admins tab; without this it dropped you on Reviewers, which is a
  // different answer to the question you asked (owner, 2026-09-09).
  const search = useSearchParams()
  const asked = search?.get('tab')
  const [panel, setPanel] = useState<'reviewers' | 'admins' | 'emails'>(
    asked === 'admins' ? 'admins' : 'reviewers')
  // Editing what every reviewer is told is an editorial power, not a reading one — so the tab is
  // offered to the roles the endpoint admits and not to `finance`, which may read the list. The
  // endpoint is the authority; this only avoids offering a 403.
  const mayEditEmails = ['super', 'org_admin', 'admin'].includes(effectiveRole(role))
  // ⚠ THE SAME GATE REVOKE HAD ON INVITATIONS, moved with the control and not widened: only a
  // super or an organisation admin may switch somebody off. `admin` and `finance` still READ the
  // tab — the endpoint is the authority, and `soleOrgAdmin` keeps the last org_admin's Revoke off
  // the screen because the backend refuses it anyway.
  const canManage = ['super', 'org_admin'].includes(effectiveRole(role))
  const { admins, message: staffMessage, setMessage: setStaffMessage, busyId: staffBusyId,
          resend, toggle, soleOrgAdmin, reload: reloadStaff } = useStaffAdmin(token)
  // Which reviewer row is mid-revoke. The staff actions carry their own busy id from the hook;
  // the reviewers table acts on the same endpoint but keeps its own list, so it needs its own.
  const [busyId, setBusyId] = useState<number | null>(null)

  /**
   * Revoke or restore a REVIEWER, from the reviewers table (owner, 2026-09-09).
   *
   * ⚠ **IT SAYS WHAT IT STRANDS.** Revoke flips one flag and touches nothing else — the cases
   * assigned to this person stay assigned to them, and they will not be able to open one. On
   * production a single reviewer holds twelve. Pause is the tool for somebody stepping back;
   * revoke is for somebody who has gone, and the difference has to be said out loud BEFORE the
   * click, not discovered afterwards by a student whose case stopped moving.
   */
  const toggleReviewer = async (r: AdminReviewer) => {
    if (!token) return
    const going = r.is_active
    const warn = going && r.open_now > 0
      ? t('admin.reviewers.revokeConfirmOpen', { name: r.name, n: String(r.open_now) })
      : t(going ? 'admin.reviewers.revokeConfirm' : 'admin.reviewers.restoreConfirm',
          { name: r.name })
    if (!window.confirm(warn)) return
    setBusyId(r.id)
    try {
      await revokeAdmin(r.id, going ? 'revoke' : 'restore', { token })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.actionFailed'))
    } finally { setBusyId(null) }
  }

  /**
   * Delete an ADMIN outright — offered only where the server said `deletable`.
   *
   * ⚠ The confirmation NAMES THE PERSON rather than asking "are you sure?", because the row it
   * was pressed on is the only thing that distinguishes this action from the Revoke beside it.
   */
  const removeAdmin = async (a: AdminItem) => {
    if (!token) return
    if (!window.confirm(t('admin.deleteConfirm', { name: a.name }))) return
    try {
      const r = await deleteAdmin(a.id, { token })
      setStaffMessage({ type: 'success', text: r.message })
    } catch (e) {
      // 409 `has_work` is the interesting one: somebody did work between the page loading and
      // the click. The server's sentence names them, so it is shown rather than replaced.
      setStaffMessage({ type: 'error', text: e instanceof Error ? e.message : t('admin.actionFailed') })
    } finally { reloadStaff() }
  }
  const [reviewers, setReviewers] = useState<AdminReviewer[]>([])
  // How many gifts the organisation runs. Only the COUNT is used here: with one, every reviewer
  // covers it and the gift would say the same thing on every row — the owner's own 2026-08-02
  // ruling, which still holds for a one-gift organisation.
  const [giftCount, setGiftCount] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const { sort, setSort } = useSort<ReviewerSortKey>(DEFAULT_SORT)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    listReviewers({ token })
      .then((d) => { setReviewers(d.reviewers); setGiftCount((d.programmes ?? []).length) })
      .catch(() => setError(t('admin.reviewers.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => { load() }, [load])

  // Sort the whole list, then page the sorted result — the other order would sort one page at a
  // time and shuffle rows between pages.
  const sorted = sortReviewers(reviewers, sort.key, sort.dir)
  const paged = usePagedRows(sorted)
  const onSort = (col: ReviewerSortKey) => setSort(nextSort(sort, col, firstDirFor(col)))

  // Below every hook on purpose — an early return above them would change the hook order between
  // the signed-out render and the signed-in one.
  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.people.title')}</h1>
      <p className="text-sm text-ground-500 mt-1 mb-4">{t('admin.people.desc')}</p>

      {/* ⚠ THE TAB BAR NOW RENDERS FOR EVERYONE WHO MAY READ THE PAGE. It used to appear only for
          the roles that may edit the emails, which was harmless while Emails was the only other
          panel — but Admins is a READING tab, and hiding the bar would have left `finance` with no
          way to reach it at all. Each tab keeps its own gate instead. */}
      <PanelTabs ariaLabelKey="admin.people.tabsAria" active={panel}
        onSelect={(k) => setPanel(k as 'reviewers' | 'admins' | 'emails')}
        tabs={[
          { key: 'reviewers', labelKey: 'admin.reviewers.tabReviewers' },
          { key: 'admins', labelKey: 'admin.people.tabAdmins' },
          ...(mayEditEmails ? [{ key: 'emails', labelKey: 'admin.reviewers.tabEmails' }] : []),
          // Reviewers sign nothing today. Shown disabled so the surfaces look alike and the panel
          // reads as coming rather than as missing (owner, 2026-08-04).
          { key: 'terms', labelKey: 'admin.reviewers.tabTerms', disabled: true },
        ]} />

      {/* Mounted only while its tab is selected, so each reveal re-reads the templates and an
          emails hiccup can never take the reviewers table down with it. */}
      {panel === 'emails' && mayEditEmails && <ReviewerEmailsCard token={token} t={t} />}

      {panel === 'admins' && (<>
        <MessageBanner message={staffMessage} />
        {/* The SAME table the platform's two staff screens use — one component, so a third copy
            of "who is in, and may I switch them off" cannot drift from the other two. It already
            knows that revoked beats paused, and already draws phone cards. */}
        <StaffTable rows={byCategory(admins).admins} busyId={staffBusyId} canAct={canManage}
          onResend={canManage ? resend : undefined}
          onToggle={canManage ? toggle : undefined}
          onDelete={canManage ? removeAdmin : undefined}
          soleOrgAdmin={soleOrgAdmin} />
        {!canManage && (
          <p className="mt-3 text-sm text-ground-500">{t('admin.administration.viewOnlyNote')}</p>
        )}
      </>)}

      {panel === 'reviewers' && (<>
      {error && <div className="text-critical-600 mb-3">{error}</div>}
      {/* ⚠ `error` is tested BEFORE the empty check, and that is not a style choice. A failed
          fetch also leaves the list empty, so the other order prints "No reviewers yet — invite
          one" underneath the error: it tells an org_admin they have nobody when the truth is we
          could not ask. "We don't know" and "there are none" must never render the same. */}
      {loading ? (
        <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
      ) : error ? null : reviewers.length === 0 ? (
        <div className="text-center text-ground-500 mt-8">{t('admin.reviewers.empty')}</div>
      ) : (
        <>
        {/* ── PHONE: one card per reviewer (owner, 2026-09-08) ────────────────────────────────
            Seven columns do not fit. The name and the STATUS lead — a paused volunteer is the
            thing you scan this list for — and **open now** is the large figure, because "who is
            free" is the question this page answers. Completed and turnaround follow it as
            context, on one line, in the same order as the table's columns.

            ⚠ THE TWO "NORMAL EMPTY" READINGS SURVIVE, and they are the reason this page has
            careful greys: an empty caseload is a volunteer between assignments (greyed, never
            flagged), and a blank gift means EVERY gift, which is the live default for all 17
            org-scoped staff. Both must read as answers, not as missing data. */}
        <div className="space-y-2.5 md:hidden" data-testid="reviewer-cards">
          {paged.rows.map((r) => {
            const band = turnaroundBand(r.turnaround_days)
            return (
              <div key={r.id}
                className="rounded-xl border border-ground-200 border-l-[3px] border-l-blue-500 bg-ground-0 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link href={`/admin/organisation/reviewers/${r.id}`}
                      className="text-sm font-semibold text-primary-600 hover:text-primary-800">
                      {r.name || '—'}
                    </Link>
                    <div className="mt-0.5 truncate text-[11px] text-ground-500">{r.email || '—'}</div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    STAFF_STATUS_TONE[staffStatusKey(r)]}`}>
                    {t(`admin.reviewers.status.${staffStatusKey(r)}`)}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-ground-600">
                  <span className="flex items-baseline gap-1.5">
                    <span className="text-ground-500">{t('admin.reviewers.colOpen')}</span>
                    <span className={`text-base tabular-nums ${
                      isFree(r) ? 'text-ground-400' : 'font-semibold text-ground-900'}`}>{r.open_now}</span>
                  </span>
                  <span>
                    <span className="text-ground-500">{t('admin.reviewers.colCompleted')}</span>{' '}
                    <span className="tabular-nums">{r.completed > 0 ? r.completed : '—'}</span>
                  </span>
                  <span className={band === 'waiting' ? 'font-semibold text-caution-700' : ''}>
                    <span className="font-normal text-ground-500">{t('admin.reviewers.colTurnaround')}</span>{' '}
                    {band === 'unknown'
                      ? t('admin.reviewers.noTurnaround')
                      : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${roleBadge(r.role)}`}>
                    {t(`admin.reviewers.role.${r.role}`)}
                  </span>
                  {orderedLanguages(r).map((code) => (
                    <span key={code} className="rounded bg-ground-100 px-1.5 py-0.5 text-[11px] text-ground-600">
                      {t(`admin.reviewers.lang.${code}`)}
                    </span>
                  ))}
                  {giftCount > 1 && (
                    <span className="text-[11px] text-ground-400">
                      {r.programme_name || t('admin.reviewers.detail.giftEvery')}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <TableFrame className="hidden md:block" minWidth={1120} label={t('admin.reviewers.title')}>
          <table className="w-full text-sm">
            <thead className="bg-ground-50/80 border-b">
              <tr>
                <SortHeader col="name" label={t(REVIEWER_SORT_LABEL.name)} sort={sort} onSort={onSort} />
                <SortHeader col="role" label={t(REVIEWER_SORT_LABEL.role)} sort={sort} onSort={onSort} />
                {/* Languages is the one unsortable column — a set has no order to put it in. */}
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  {t('admin.reviewers.colLanguages')}
                </th>
                <SortHeader col="openNow" label={t(REVIEWER_SORT_LABEL.openNow)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="completed" label={t(REVIEWER_SORT_LABEL.completed)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="turnaround" label={t(REVIEWER_SORT_LABEL.turnaround)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="status" label={t(REVIEWER_SORT_LABEL.status)} sort={sort} onSort={onSort} />
                {/* Plain headers, not sortable: "last seen" sorts by a column that is empty for
                    anybody predating it, which would bunch "not recorded" at one end and read as
                    an ordering of people. The action column has nothing to sort by at all. */}
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-ground-600">
                  {t('admin.reviewers.colLastSeen')}
                </th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-ground-600">
                  {t('admin.actionHeader')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ground-100">
              {paged.rows.map((r) => {
                const band = turnaroundBand(r.turnaround_days)
                return (
                  <tr key={r.id} className="hover:bg-info-50/40 transition-colors align-top">
                    <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                      {/* The name opens the whole record — credentials, outcomes, reopens. */}
                      <Link href={`/admin/organisation/reviewers/${r.id}`}
                        className="font-medium text-primary-600 hover:text-primary-800">
                        {r.name || '—'}
                      </Link>
                      <div className="text-xs text-ground-500 mt-0.5">{r.email || '—'}</div>
                      {/* Which gift they cover (S-ASSIGN). Under the name rather than as a
                          column, so no sort key or header has to be invented for a fact that
                          most organisations will never see; and shown only when there is more
                          than one gift, per the ruling in the comment at the top of this file.
                          ⚠ BLANK MEANS EVERY GIFT — it is the live default for all 17
                          org-scoped staff and must read as an answer, not as missing data. */}
                      {giftCount > 1 && (
                        <div className="text-xs text-ground-400 mt-0.5">
                          {r.programme_name || t('admin.reviewers.detail.giftEvery')}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${roleBadge(r.role)}`}>
                        {t(`admin.reviewers.role.${r.role}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ground-700">
                      {orderedLanguages(r).length === 0
                        ? <span className="text-ground-400">—</span>
                        : (
                          <span className="flex flex-wrap gap-1">
                            {orderedLanguages(r).map((code) => (
                              <span key={code}
                                className="px-1.5 py-0.5 rounded bg-ground-100 text-ground-600 text-xs">
                                {t(`admin.reviewers.lang.${code}`)}
                              </span>
                            ))}
                          </span>
                        )}
                    </td>
                    {/* An empty caseload is the normal state of a volunteer between assignments —
                        it is greyed, never flagged. */}
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      isFree(r) ? 'text-ground-400' : 'text-ground-900 font-semibold'}`}>
                      {r.open_now}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-700">
                      {r.completed > 0 ? r.completed : <span className="text-ground-400">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      band === 'waiting' ? 'text-caution-700 font-semibold' : 'text-ground-700'}`}
                      title={band === 'unknown' ? t('admin.reviewers.noTurnaroundHint')
                        : t('admin.reviewers.turnaroundHint')}>
                      {band === 'unknown'
                        ? <span className="text-ground-400">{t('admin.reviewers.noTurnaround')}</span>
                        : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                    </td>
                    {/* ⚠ NOT `r.paused` ANY MORE. Revoked beats paused, and the rule lives in
                        `lib/staffStatus` so this table and the staff table cannot disagree —
                        which they have done twice. */}
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        STAFF_STATUS_TONE[staffStatusKey(r)]}`}>
                        {t(`admin.reviewers.status.${staffStatusKey(r)}`)}
                      </span>
                    </td>
                    {/* ⚠ "NOT RECORDED" IS NOT "NEVER SIGNED IN". The column is best-effort and
                        empty for everybody predating it, so a blank must never read as an
                        accusation. 20 of 21 staff carry a value. */}
                    <td className="px-4 py-3 text-ground-700">
                      {r.last_seen_at
                        ? formatDate(r.last_seen_at)
                        : <span className="text-ground-400">{t('admin.reviewers.lastSeenUnknown')}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {canManage && (
                        <button disabled={busyId === r.id} onClick={() => toggleReviewer(r)}
                          className={`text-xs font-medium disabled:opacity-50 ${
                            r.is_active ? 'text-critical-600 hover:text-critical-800'
                                        : 'text-primary-600 hover:text-primary-800'}`}>
                          {t(r.is_active ? 'admin.revoke' : 'admin.restore')}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {paged.visible && (
            <div className="px-4 sm:px-5 pb-4">
              <Pagination
                page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
                onPageChange={paged.setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize}
              />
            </div>
          )}
        </TableFrame>
        </>
      )}
      <p className="text-xs text-ground-500 mt-4 max-w-3xl">{t('admin.reviewers.footnote')}</p>
      </>)}
    </div>
  )
}
