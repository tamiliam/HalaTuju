'use client'

import { Pagination } from '@/components/Pagination'
import { formatDate } from '@/lib/formatDate'
import { usePagedRows } from '@/lib/usePagedRows'
import { useT } from '@/lib/i18n'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import type { InvitationRow } from '@/lib/admin-api'
import { teamLabelRole } from '@/lib/staffRole'

/**
 * One kind's invitations. Same five columns as every other table on the console —
 * Name · Email · Role · Status · Action (owner's shape, 2026-08-03).
 *
 * ⚠ THE STATUS CARRIES ITS DATE: "No reply yet (21/07/2026)". A status without one is a fact you
 * cannot act on — knowing somebody has not replied is only useful beside how long it has been.
 *
 * ⚠ **THE ONLY ACTION IS RESEND (2026-09-09).** It used to be contextual — Resend while waiting,
 * Revoke once somebody had arrived — because the table listed accepted invitations too. It no
 * longer does: the endpoint serves the WAITING ones only, so the Revoke branch could never have
 * fired again and is deleted rather than left as a dead arm. **Revoke and Restore now live on the
 * person**, in Organisation → People, beside Pause — one screen decides whether somebody is in.
 * A sponsor invitation still gets nothing but Resend: it provisions no account.
 * **TD-214 (2026-10-05) adds Cancel beside it** — the invitation's own verb, for one sent by
 * mistake: the row is kept as `revoked` and leaves this waiting list (the server decides; a staff
 * invitation's never-used account is switched off with it).
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
 *
 * ⚠ **ONE WAITING TABLE ON EVERY TAB (I1, 2026-11-08).** Source and Mentor used to draw their own
 * (own columns, a bare date, no Action heading, a blue Cancel, no pages). They render through this
 * table now: Source adds its `lead` column (the source's name), and each tab passes its own Resend /
 * Cancel handlers and its own "may act on this row" rule. Headings are `TH`, and below md the rows
 * restack as cards (`TableFrame phoneRows`, each cell named by its `data-label`). ⚠ A MENTOR row's
 * Cancel is the MENTOR revoke (`admin/mentors/<id>/revoke/`) passed in by `MentorRoster` — the
 * generic Cancel refuses a mentor invitation by design; only the word on the link is shared.
 */
export default function InvitationsTable({ rows, canAct, busyId, onResend, onCancel, canCancel,
                                           canResend, showRole = true, lead, rowTestId, empty }: {
  rows: InvitationRow[]
  canAct?: boolean
  busyId?: number | null
  onResend?: (r: InvitationRow) => void
  /** TD-214: withdraw an unanswered invitation. Offered on the same rows as Resend. */
  onCancel?: (r: InvitationRow) => void
  /** Which rows THIS viewer may cancel (default: all). An org_admin never gets it on an
   *  organisation-admin row — one they could not have sent; the server 404s it anyway. */
  canCancel?: (r: InvitationRow) => boolean
  /** Which rows THIS viewer may resend (default: all). Source and Mentor pass the server's
   *  `manageable` rule for the account behind the row. */
  canResend?: (r: InvitationRow) => boolean
  /** Whether this kind's invitations carry a staff role. False for sponsors, sources and mentors. */
  showRole?: boolean
  /** An optional FIRST column (I1: the Source tab's source name). Its heading is already in words. */
  lead?: { header: string; cell: (r: InvitationRow) => React.ReactNode }
  /** The row's test id (default `invitation-row-<id>`). */
  rowTestId?: (r: InvitationRow) => string
  /** What to say when there is nothing to list. ⚠ **THE EMPTY STATE IS NOW THE USUAL STATE** —
   *  the table holds only unanswered invitations, and on a settled organisation that is nothing at
   *  all. The PAGE supplies these words because only the page knows which of the two empties this
   *  is (nobody asked yet vs everybody arrived) and where the directory lives. */
  empty?: React.ReactNode
}) {
  const { t } = useT()
  const paged = usePagedRows(rows)

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">
        {empty ?? t('admin.invitations.noneInKind')}
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
  const headers = ['nameHeader', 'emailHeader', ...(showRole ? ['roleHeader'] : []), 'statusHeader', 'actionHeader']
  const word = (h: string) => t(`admin.${h}`)

  return (
    // On a phone the rows become cards (`phoneRows`), so this wrapper drops its own card there too.
    <div className="overflow-hidden rounded-lg border bg-ground-0 shadow-sm max-md:overflow-visible max-md:rounded-none max-md:border-0 max-md:bg-transparent max-md:shadow-none"
      data-testid="invitations-table">
      {/* bare: the card, and the pagination beneath it, belong to THIS component — so the frame
          contributes only the scroll floor and the more-to-the-right cue, not a second card. */}
      <TableFrame bare phoneRows minWidth={lead ? 720 : 640} label={t('admin.invitations.title')}>
        <table className="w-full text-sm">
          <thead className="border-b bg-ground-50">
            <tr>
              {lead && <th className={TH}>{lead.header}</th>}
              {headers.map((h) => (
                <th key={h} className={TH}>{word(h)}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {paged.rows.map((r) => {
              const waiting = r.status === 'invited' || r.status === 'expired' || r.status === 'no_reply'
              return (
                <tr key={r.id} data-testid={rowTestId ? rowTestId(r) : `invitation-row-${r.id}`}>
                  {lead && <td className="px-4 py-3 font-medium text-ground-900">{lead.cell(r)}</td>}
                  {/* The first cell is the card's title on a phone; under a lead column it is named. */}
                  <td className={`px-4 py-3 ${lead ? 'text-ground-900' : 'font-medium text-ground-900'}`}
                    data-label={lead ? word('nameHeader') : undefined}>
                    {r.name || '—'}
                    {/* Which gift this invitation was for (S-ASSIGN). Rendered only when the row
                        HAS one: a blank means every gift, and printing an empty line under a
                        staff invitation would read as a missing value rather than as "n/a". */}
                    {r.programme_name && (
                      <div className="text-xs font-normal text-ground-500">{r.programme_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ground-500 max-md:break-all" data-label={word('emailHeader')}>{r.email}</td>
                  {showRole && (
                    <td className="px-4 py-3" data-label={word('roleHeader')}>
                      {/* A staff row always has a role; the dash is the "we hold no answer" case,
                          which is why the whole column goes when the kind never has one. */}
                      {r.role ? t(`admin.role.${teamLabelRole(r.role)}`) : '—'}
                    </td>
                  )}
                  <td className="px-4 py-3" data-label={word('statusHeader')}>
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
                  <td className="whitespace-nowrap px-4 py-3">
                    {canAct && waiting && onResend && (canResend?.(r) ?? true) && (
                      <button type="button" disabled={busyId === r.id} onClick={() => onResend(r)}
                        className="text-xs font-medium text-primary-600 hover:text-primary-800 disabled:opacity-50">
                        {t('admin.resend')}
                      </button>
                    )}
                    {canAct && waiting && onCancel && (canCancel?.(r) ?? true) && (
                      <button type="button" disabled={busyId === r.id} onClick={() => onCancel(r)}
                        className="ml-3 text-xs font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
                        {t('admin.invitations.cancel')}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </TableFrame>
      {/* ⚠ The padding belongs HERE, not inside `Pagination` — it is the table's inset, and the
          component is dropped onto surfaces with different insets (the sponsors page uses the same
          wrapper). Rendered bare it sat flush against the card edge, out of line with the `px-4`
          cells above it and with nothing beneath the border. */}
      {paged.visible && (
        <div className="px-4 pb-4 max-md:px-0">
          <Pagination page={paged.page} totalPages={paged.totalPages} total={rows.length}
            pageSize={paged.pageSize} onPageChange={paged.setPage}
            pageSizeOptions={[10, 25, 50]} onPageSizeChange={paged.setPageSize} />
        </div>
      )}
    </div>
  )
}
