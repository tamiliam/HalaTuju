'use client'

/**
 * The case list's assignment dropdown parts, shared by the phone rows and the desktop table (T1-e,
 * owner D7 2026-11-09; lifted out of `app/admin/scholarship/page.tsx`, which sits at the 600-line
 * standard). Who is offered is `listAssignees`; the `<select>` itself stays in the page, because the
 * two layouts disable and title it differently.
 */
import { useT } from '@/lib/i18n'
import { listAssignees, orderReviewersFor, SPECIFIC_CALL_LANGS, type AssignRow, type Reviewer } from '@/lib/assignOptions'

/** The id a row's `<select>` names in `aria-describedby`: the legend's, but only when the student
 *  named a single language, because otherwise no option carries ✓ or ⚠. */
export function legendIdFor(lang: string, legendId: string): string | undefined {
  return SPECIFIC_CALL_LANGS.has(lang) ? legendId : undefined
}

/** What ✓ and ⚠ mean, once. The desktop table shows it under the table; every select points at it. */
export function AssignLegend({ id, className }: { id: string; className: string }) {
  const { t } = useT()
  return <p id={id} className={className} data-assign-legend>{t('admin.scholarship.assignLangLegend')}</p>
}

/** "Prefers <language>" and, with `legendId` (the phone rows), the legend under it. Nothing when the
 *  student named no single language ('mixed' / unset), because then no option carries either mark. */
export function AssignLangNote({ lang, className, legendId }: { lang: string; className: string; legendId?: string }) {
  const { t } = useT()
  if (!SPECIFIC_CALL_LANGS.has(lang)) return null
  return (
    <p className={className}>
      {t('admin.scholarship.prefersLang', { lang: t(`scholarship.apply.callLang.${lang}`) })}
      {legendId && <span id={legendId} className="block" data-assign-legend>{t('admin.scholarship.assignLangLegend')}</span>}
    </p>
  )
}

/** The `<option>`s for one case: Unassigned, the current holder even when the list does not name
 *  them, then the offered people, those who speak the student's language first. TD-613 (review F2):
 *  Unassigned is disabled exactly when the server says it does not take it (`may_unassign` false). */
export function AssigneeOptions({ reviewers, row, isSuper }: {
  reviewers: Reviewer[]
  row: AssignRow & { assigned_to_name: string | null; call_language: string; may_unassign?: boolean }
  isSuper: boolean
}) {
  const { t } = useT()
  return (
    <>
      <option value="" disabled={row.may_unassign === false}>{t('admin.scholarship.unassigned')}</option>
      {row.assigned_to_id != null && !reviewers.some((rv) => rv.id === row.assigned_to_id) && (
        <option value={row.assigned_to_id}>{row.assigned_to_name || row.assigned_to_id}</option>
      )}
      {orderReviewersFor(listAssignees(reviewers, row, isSuper), row.call_language).map(({ rv, match, specific }) => (
        <option key={rv.id} value={rv.id}>
          {specific ? (match ? '✓ ' : '⚠ ') : ''}{rv.name}
        </option>
      ))}
    </>
  )
}

/** Request #75: at Awaiting review the list offers no picker. It names who holds the case
 *  ("Unassigned" or the reviewer); the choice between assigning and rejecting before interview is
 *  made on the case's own page, where both are offered side by side. */
export const assignsInCockpitOnly = (status: string) => status === 'profile_complete'

export function AssignedPlain({ name, className }: { name: string | null; className: string }) {
  const { t } = useT()
  return <p className={className} data-assigned-plain>{name || t('admin.scholarship.unassigned')}</p>
}
