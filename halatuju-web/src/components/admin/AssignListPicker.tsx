'use client'

/**
 * The case list's "Assigned" cell, shared by the phone rows and the desktop table. F1 / I-13 (owner
 * option A, 2026-11-21): the list holds NO picker. One line of plain text from one function
 * (`AssignedCell`); every assign and reassign happens on the case page.
 */
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { SPECIFIC_CALL_LANGS } from '@/lib/assignOptions'

/** "Prefers <language>". Nothing when the student named no single language ('mixed' / unset). */
export function AssignLangNote({ lang, className }: { lang: string; className: string }) {
  const { t } = useT()
  if (!SPECIFIC_CALL_LANGS.has(lang)) return null
  return (
    <p className={className}>
      {t('admin.scholarship.prefersLang', { lang: t(`scholarship.apply.callLang.${lang}`) })}
    </p>
  )
}

export type AssignedCellRow = {
  status: string
  assigned_to_name: string | null
  assigned_to_id: number | null
  call_language: string
  ready_for_assignment?: boolean
  ready_on?: string | null
}

/** The "Assigned" cell, from one function: the holder's name at any stage; at Awaiting review with
 *  nobody, "Waiting for a reviewer" (+ "Prefers <language>") when ready, or "Not ready yet" (+ "Ready on
 *  <date>") inside the 5-day window; "—" for any other stage with nobody. */
export function AssignedCell({ row, className, noteClassName }: { row: AssignedCellRow; className: string; noteClassName: string }) {
  const { t } = useT()
  const held = row.assigned_to_name || (row.assigned_to_id != null ? String(row.assigned_to_id) : '')
  if (held) return <p className={className} data-assigned-plain>{held}</p>
  if (row.status !== 'profile_complete') return <p className={className} data-assigned-plain>—</p>
  if (row.ready_for_assignment === false) {
    return (
      <div data-assigned-plain>
        <p className={className}>{t('admin.scholarship.assignedCell.notReady')}</p>
        {row.ready_on && <p className={noteClassName} data-assign-ready-on>{t('admin.scholarship.assignedCell.readyOn', { date: formatDate(row.ready_on) })}</p>}
      </div>
    )
  }
  return (
    <div data-assigned-plain>
      <p className={className}>{t('admin.programmeOverview.attention.unassigned')}</p>
      <AssignLangNote lang={row.call_language} className={noteClassName} />
    </div>
  )
}
