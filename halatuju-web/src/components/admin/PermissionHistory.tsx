'use client'

import { useT } from '@/lib/i18n'
import { formatDateTime } from '@/lib/formatDate'
import type { StaffPermissionChangeRow } from '@/lib/admin-api/admins'

/**
 * Team → a person → Permissions → **Changes** (2026-10-22): the latest recorded changes of what this
 * person may do, newest first, under the permission card.
 *
 * ⚠ IT READS THE EDITOR'S OWN GET (`history` on `admin/admins/<id>/permissions/`), never a request of
 * its own, and it is imported only by `PermissionEditor` — so it travels in the editor's lazily
 * loaded chunk and adds nothing to the People route.
 *
 * ⚠ "THE HALATUJU TEAM", NOT AN ADDRESS. A change a super made arrives as `by_super` with `by`
 * blank: the server does not hand the platform's addresses to an organisation.
 */
export default function PermissionHistory({ rows, name, role }: {
  rows: readonly StaffPermissionChangeRow[]
  name: string
  role: string
}) {
  const { t } = useT()
  const roleName = (r: string) => t(`admin.role.${r}`)
  const perm = (k: string) => t(`admin.perm.${k}.name`)

  const what = (r: StaffPermissionChangeRow): string => {
    if (r.kind === 'role_change') return t('admin.permHistory.roleReset', { role: roleName(r.role) })
    return [
      ...r.added.map((k) => t('admin.permHistory.on', { perm: perm(k) })),
      ...r.removed.map((k) => t('admin.permHistory.off', { perm: perm(k) })),
    ].join(' · ')
  }

  return (
    <section className="mt-3.5 rounded-xl border bg-ground-0 shadow-sm" data-testid="permission-history"
      aria-labelledby="perm-history-title">
      <h2 id="perm-history-title"
        className="border-b px-4 py-3 text-[11.5px] font-semibold uppercase tracking-wider text-ground-600 sm:px-5">
        {t('admin.permHistory.title')}
      </h2>
      {rows.length === 0 ? (
        <p className="px-4 py-4 text-sm text-ground-500 sm:px-5">
          {t('admin.permHistory.empty', { name, role: roleName(role) })}
        </p>
      ) : (
        <ul className="divide-y divide-ground-100">
          {rows.map((r, i) => (
            <li key={`${r.at}-${i}`} className="px-4 py-3 sm:px-5">
              <p className="text-sm text-ground-900">{what(r)}</p>
              <p className="mt-0.5 text-xs text-ground-500">
                {t('admin.permHistory.byAt', {
                  by: r.by || (r.by_super ? t('admin.permHistory.team') : '—'),
                  at: formatDateTime(r.at),
                })}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
