'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import type { TeamTableName } from '@/lib/admin-api/admins'
import { TeamAddSheet } from '@/components/admin/TeamTables'

/**
 * Sprint T3 (D8, owner 2026-11-09): a PURE mentor's **Permissions** tab — read-only. A mentor holds no
 * permission keys; they see My students, their current scholars' files on Scholars (read-only, sprint
 * S1) and their Profile, and nothing here changes that. What gives
 * them more is a Team table, so the tab offers the Team page's own Add-to-table path (`TeamAddSheet`,
 * narrowed to this one person), and only for the tables the server says this viewer may add them to
 * (`may_add` — the Add endpoint's own rule: a super or their organisation admin, once they have signed
 * in). Everybody else reads the lines and no button.
 */
export default function MentorOnlyPermissions({ adminId, name, mayAdd, token, onAdded }: {
  adminId: number
  name: string
  mayAdd: TeamTableName[]
  token: string | null
  onAdded: () => void
}) {
  const { t } = useT()
  const [adding, setAdding] = useState<TeamTableName | null>(null)
  const [done, setDone] = useState('')
  return (
    <section className="bg-ground-0 rounded-xl shadow-sm border px-4 sm:px-5 py-4 space-y-3" data-testid="mentor-only-permissions">
      <h2 className="text-base font-semibold text-ground-900">{t('admin.permEditor.title', { name })}</h2>
      <div className="text-sm text-ground-700 space-y-1.5">
        <p>{t('admin.person.mentorOnly.intro', { name })}</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>{t('admin.person.mentorOnly.students')}</li>
          <li>{t('admin.person.mentorOnly.scholars')}</li>
          <li>{t('admin.person.mentorOnly.profile')}</li>
        </ul>
        <p className="text-ground-500">{t('admin.person.mentorOnly.none')}</p>
      </div>
      {mayAdd.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-sm text-ground-700">{t('admin.person.mentorOnly.more', { name })}</p>
          <div className="flex flex-wrap gap-2">
            {mayAdd.map((table) => (
              <button key={table} type="button" onClick={() => { setDone(''); setAdding(table) }}
                data-testid={`mentor-add-${table}`}
                className="min-h-11 rounded-lg border border-primary-600 px-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
                {t(`admin.team.add.${table}`)}
              </button>
            ))}
          </div>
        </div>
      )}
      {done && <p className="text-sm text-positive-700" role="status">{done}</p>}
      <TeamAddSheet open={adding !== null} table={adding ?? 'admins'} token={token} only={adminId}
        onClose={() => setAdding(null)}
        onDone={(text) => { setAdding(null); setDone(text); onAdded() }} />
    </section>
  )
}
