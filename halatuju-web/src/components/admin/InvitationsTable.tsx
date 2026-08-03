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
 */
export default function InvitationsTable({ rows, canAct, busyId, onResend, onRevoke }: {
  rows: InvitationRow[]
  canAct?: boolean
  busyId?: number | null
  onResend?: (r: InvitationRow) => void
  onRevoke?: (r: InvitationRow) => void
}) {
  const { t } = useT()
  const paged = usePagedRows(rows)

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-white p-6 text-center text-sm text-gray-500">
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
    <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              {['nameHeader', 'emailHeader', 'roleHeader', 'statusHeader', 'actionHeader'].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium text-gray-600">
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
                  <td className="px-4 py-3 font-medium text-gray-900">{r.name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{r.email}</td>
                  <td className="px-4 py-3">
                    {r.role ? t(`admin.role.${r.role}`) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                      r.status === 'expired' ? 'bg-amber-100 text-amber-700'
                        : r.status === 'revoked' ? 'bg-red-100 text-red-600'
                        : waiting ? 'bg-blue-100 text-blue-700'
                        : 'bg-green-100 text-green-700'}`}>
                      {statusText(r)}
                    </span>
                    {r.last_send_ok === false && (
                      <div className="mt-1 max-w-[18rem] break-words text-xs text-red-500">
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
                            className="text-xs font-medium text-red-600 hover:text-red-800 disabled:opacity-50">
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
      {paged.visible && (
        <Pagination page={paged.page} totalPages={paged.totalPages} total={rows.length}
          pageSize={paged.pageSize} onPageChange={paged.setPage}
          pageSizeOptions={[10, 25, 50]} onPageSizeChange={paged.setPageSize} />
      )}
    </div>
  )
}
