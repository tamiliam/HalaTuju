'use client'

import type { AdminItem } from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { sendState } from '@/lib/invitations'
import { useT } from '@/lib/i18n'

/**
 * The invitations still waiting for an answer — a worklist that empties.
 *
 * ⚠ IT IS SEPARATE FROM THE PEOPLE TABLE ON PURPOSE. The two answer different questions and need
 * different columns (Sent · Sends · Outcome vs Role · Last seen) and different actions. One table
 * with a status filter would bury three outstanding invitations among twenty settled colleagues,
 * which is the exact thing this page exists to stop.
 *
 * "Nothing outstanding" is a good screen, not an empty one.
 */
export default function OutstandingInvitations({ rows, canAct, busyId, onResend }: {
  rows: AdminItem[]
  canAct?: boolean
  busyId?: number | null
  onResend?: (a: AdminItem) => void
}) {
  const { t } = useT()

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-white p-6 text-center text-sm text-gray-500">
        {t('admin.invitations.noneOutstanding')}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="border-b bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.nameHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.roleHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.invitations.sentHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.invitations.emailHeader')}</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.statusHeader')}</th>
            {canAct && <th className="px-4 py-3 text-left font-medium text-gray-600">{t('admin.actionHeader')}</th>}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((a) => {
            const inv = a.invitation!
            const send = sendState(a)
            return (
              <tr key={a.id}>
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900">{a.name}</div>
                  <div className="text-gray-500">{a.email}</div>
                </td>
                <td className="px-4 py-3">{t(`admin.role.${a.role}`)}</td>
                <td className="px-4 py-3 text-gray-600">
                  {inv.sent_at ? formatDate(inv.sent_at) : '—'}
                  {inv.send_count > 1 && (
                    <span className="ml-1 text-xs text-gray-400">
                      {t('admin.invitations.resentTimes', { n: String(inv.send_count - 1) })}
                    </span>
                  )}
                </td>
                {/* The owner's third ask: "invitations send email, but that is not shown to
                    anyone". A bounce is usually the whole explanation for silence. */}
                <td className="px-4 py-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                    send === 'failed' ? 'bg-red-100 text-red-600'
                      : send === 'sent' ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'}`}>
                    {t(`admin.invitations.send.${send}`)}
                  </span>
                  {send === 'failed' && inv.last_send_error && (
                    <div className="mt-1 max-w-[16rem] break-words text-xs text-red-500">
                      {inv.last_send_error}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  {/* ⚠ `no_reply` is styled apart from `expired`. Nothing of theirs lapsed — they
                      simply have not come — so it must not read as an error to be repaired. */}
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                    inv.status === 'expired' ? 'bg-amber-100 text-amber-700'
                      : 'bg-blue-100 text-blue-700'}`}>
                    {t(`admin.invitations.status.${inv.status}`)}
                  </span>
                </td>
                {canAct && (
                  <td className="px-4 py-3">
                    {onResend && (
                      <button disabled={busyId === a.id} onClick={() => onResend(a)}
                        className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
                        {t('admin.resend')}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
