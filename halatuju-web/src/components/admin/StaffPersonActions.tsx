'use client'

import { useState } from 'react'

import { deleteAdmin, revokeAdmin } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import StaffActions from '@/components/admin/StaffActions'
import TypedConfirmDialog from '@/components/admin/TypedConfirmDialog'

/**
 * Sprint T2: Revoke / Restore and Delete on a STAFF person's own page (a reviewer's, an admin's) —
 * the table's pair (`StaffActions`), with the table's confirmations: `window.confirm` for Revoke (the
 * open-cases warning when they hold some) and the typed confirmation for Delete. After a delete the
 * page sends the viewer back to the Team tab they came from (`onDeleted`); a refusal (409 `has_work`
 * when somebody did work since the page loaded, the sole organisation admin's revoke…) shows the
 * server's own sentence.
 *
 * ⚠ AN ORGANISATION ADMIN'S PAGE OFFERS NO REVOKE (the Reviewers table's rule: a super revokes them on
 * the Admins table) AND A DELETE ONLY TO A SUPER (owner, 2026-11-08). The server refuses either way.
 * ⚠ T2 review N3: nor is Revoke offered where the server says `revocable: false` — a super's page, your
 * own, the sole organisation admin's — and N2: no Delete where it says `delete_never`.
 */
export default function StaffPersonActions({ person, token, viewerSuper, onDeleted, openNow = 0, onChanged }: {
  person: {
    id: number; name: string; email: string; role: string; is_active: boolean
    lead?: boolean; deletable?: boolean; delete_never?: boolean; revocable?: boolean
    work?: Record<string, number>
  }
  token: string
  viewerSuper: boolean
  /** After a delete: the page leaves (the person is gone). */
  onDeleted: () => void
  /** Their open cases, for the revoke warning (a reviewer's page). */
  openNow?: number
  /** After a revoke or restore: their new `is_active`. */
  onChanged: (active: boolean) => void
}) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const orgAdmin = !!person.lead || person.role === 'org_admin'
  const failed = (e: unknown) => setError(e instanceof Error && e.message ? e.message : t('admin.actionFailed'))

  const toggle = async () => {
    const going = person.is_active
    const warn = going && openNow > 0
      ? t('admin.reviewers.revokeConfirmOpen', { name: person.name, n: String(openNow) })
      : t(going ? 'admin.reviewers.revokeConfirm' : 'admin.reviewers.restoreConfirm', { name: person.name })
    if (!window.confirm(warn)) return
    setBusy(true); setError('')
    try {
      await revokeAdmin(person.id, going ? 'revoke' : 'restore', { token })
      onChanged(!going)
    } catch (e) { failed(e) } finally { setBusy(false) }
  }

  const remove = async () => {
    setBusy(true); setError('')
    try {
      await deleteAdmin(person.id, { token })
      onDeleted()
    } catch (e) { failed(e); setBusy(false); setDeleting(false) }
  }

  return (
    <div data-testid="person-actions">
      <div className="flex flex-wrap items-center gap-4">
        <StaffActions size="sm" active={person.is_active} busy={busy}
          onToggle={orgAdmin || person.revocable === false ? undefined : () => void toggle()}
          onDelete={() => setDeleting(true)} deletable={person.deletable} deleteNever={person.delete_never}
          work={person.work} orgAdmin={orgAdmin} viewerSuper={viewerSuper} />
      </div>
      {error && <p className="mt-1.5 text-sm text-critical-600" role="alert">{error}</p>}
      {deleting && (
        <TypedConfirmDialog busy={busy} phrase={person.email}
          title={t('admin.programmes.deleteTitle', { name: person.name })}
          body={t('admin.deleteStaffBody')} cta={t('admin.delete')}
          onCancel={() => setDeleting(false)} onConfirm={() => void remove()} />
      )}
    </div>
  )
}
