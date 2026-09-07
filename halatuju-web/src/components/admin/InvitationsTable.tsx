'use client'

import { Pagination } from '@/components/Pagination'
import { formatDate } from '@/lib/formatDate'
import { usePagedRows } from '@/lib/usePagedRows'
import { useT } from '@/lib/i18n'
import type { InvitationRow } from '@/lib/admin-api'

/**
 * One kind's invitations. Same five columns as every other table on the console —
 * Name · Email · Role · Status · Action (owner's shape, 2026-08-03).
 *
 * ⚠ THE STATUS CARRIES ITS DATE: "No reply yet (21/07/2026)". A status without one is a fact you
 * cannot act on — knowing somebody has not replied is only useful beside how long it has been.
 *
 * ⚠ THE ACTION IS CONTEXTUAL, and that is what lets one table serve both purposes. Somebody still
 * waiting gets **Resend**; somebody who has arrived gets **Revoke**. A sponsor invitation gets
 * neither — it provisions no account, so there is nothing of theirs for us to revoke.
 *
 * ⚠ **ROLE IS THE SAME STORY, AND THE COLUMN IS DROPPED RATHER THAN DASHED** (owner, 2026-09-08,
 * on seeing a live sponsors table). The two staff tables each hold several roles — Admin · Finance ·
 * Org admin, and Reviewer · QC — so there the column separates things. A SPONSOR invitation carries
 * no role because it creates no account: it emails a link to the ordinary public registration. So
 * that column could only ever print "—", for every row, for ever. A permanent column of dashes is
 * not neutral: it reads as a value we failed to fetch, and it invited exactly that question.
 *
 * ⚠ **`showRole` IS PASSED, NOT DERIVED FROM THE ROWS.** "Do these invitations have roles" is a
 * fact about the KIND, and reading it off whichever rows happen to be loaded would hide the column
 * on a staff table the day one arrives with a blank role — a real value gone missing, reported as
 * nothing at all.
 */
export default function InvitationsTable({ rows, canAct, busyId, onResend, onRevoke,
                                           showRole = true }: {
  rows: InvitationRow[]
  canAct?: boolean
  busyId?: number | null
  onResend?: (r: InvitationRow) => void
  onRevoke?: (r: InvitationRow) => void
  /** Whether this kind's invitations carry a staff role. False for sponsors and sources. */
  showRole?: boolean
}) {
  const { t } = useT()
  const paged = usePagedRows(rows)

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">
        {t('admin.invitations.noneInKind')}
      </div>
    )
  }

  const statusText = (r: InvitationRow) => {
    const label = t(`admin.invitations.status.${r.status}`)
    // Which date explains which status: when it was sent for one still waiting, when they arrived
    // for one that is settled. Showing the wrong one reads as noise.
    const when = r.status === 'accepted' ? r.accepted_at : r.sent_at
    return when ? `${label} (${formatDate(when)})` : label
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-ground-0 shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b bg-ground-50">
            <tr>
              {['nameHeader', 'emailHeader', ...(showRole ? ['roleHeader'] : []),
                'statusHeader', 'actionHeader'].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium text-ground-600">
                  {t(`admin.${h}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {paged.rows.map((r) => {
              const waiting = r.status === 'invited' || r.status === 'expired' || r.status === 'no_reply'
              return (
                <tr key={r.id}>
                  <td className="px-4 py-3 font-medium text-ground-900">
                    {r.name || '—'}
                    {/* Which gift this invitation was for (S-ASSIGN). Rendered only when the row
                        HAS one: a blank means every gift, and printing an empty line under a
                        staff invitation would read as a missing value rather than as "n/a". */}
                    {r.programme_name && (
                      <div className="text-xs font-normal text-ground-500">{r.programme_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ground-500">{r.email}</td>
                  {showRole && (
                    <td className="px-4 py-3">
                      {/* A staff row always has a role; the dash is the "we hold no answer" case,
                          which is why the whole column goes when the kind never has one. */}
                      {r.role ? t(`admin.role.${r.role}`) : '—'}
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                      r.status === 'expired' ? 'bg-caution-100 text-caution-700'
                        : r.status === 'revoked' ? 'bg-critical-100 text-critical-600'
                        : waiting ? 'bg-info-100 text-info-700'
                        : 'bg-positive-100 text-positive-700'}`}>
                      {statusText(r)}
                    </span>
                    {r.last_send_ok === false && (
                      <div className="mt-1 max-w-[18rem] break-words text-xs text-critical-600">
                        {t('admin.invitations.send.failed')}
                        {r.last_send_error ? ` — ${r.last_send_error}` : ''}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {canAct && (
                      <div className="flex items-center gap-3">
                        {waiting && onResend && (
                          <button disabled={busyId === r.id} onClick={() => onResend(r)}
                            className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
                            {t('admin.resend')}
                          </button>
                        )}
                        {/* A sponsor invitation has no account behind it (`admin_id` null), so
                            there is nothing to revoke — the control is absent, not disabled. */}
                        {!waiting && r.admin_id && onRevoke && (
                          <button disabled={busyId === r.id} onClick={() => onRevoke(r)}
                            className="text-xs font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
                            {t(r.is_active === false ? 'admin.restore' : 'admin.revoke')}
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {/* ⚠ The padding belongs HERE, not inside `Pagination` — it is the table's inset, and the
          component is dropped onto surfaces with different insets (the sponsors page uses the same
          wrapper). Rendered bare it sat flush against the card edge, out of line with the `px-4`
          cells above it and with nothing beneath the border. */}
      {paged.visible && (
        <div className="px-4 pb-4">
          <Pagination page={paged.page} totalPages={paged.totalPages} total={rows.length}
            pageSize={paged.pageSize} onPageChange={paged.setPage}
            pageSizeOptions={[10, 25, 50]} onPageSizeChange={paged.setPageSize} />
        </div>
      )}
    </div>
  )
}
