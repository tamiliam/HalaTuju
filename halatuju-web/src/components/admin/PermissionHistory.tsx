'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { permName } from './permName'
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
 * blank: the server does not hand the platform's addresses to an organisation. A change a data
 * migration made (`by_migration`, nobody clicked: sprint S1's Scholars grant) says so in words.
 *
 * Sprint M2d (D9): a change naming more than three keys reads as a summary ("5 switched on · 2 switched
 * off") with Show / Hide for the full list; three or fewer stay listed inline. A role reset reads as one.
 */

/** More keys than this in one change, and the row reads as a summary until shown. */
const INLINE_KEYS = 3
export default function PermissionHistory({ rows, name, role }: {
  rows: readonly StaffPermissionChangeRow[]
  name: string
  role: string
}) {
  const { t } = useT()
  const roleName = (r: string) => t(`admin.role.${r}`)
  const perm = (k: string) => permName(t, k)          // M2b: a v2 page key reads "<page>: <level>"

  const what = (r: StaffPermissionChangeRow): string => {
    if (r.kind === 'role_change') return t('admin.permHistory.roleReset', { role: roleName(r.role) })
    return [
      ...r.added.map((k) => t('admin.permHistory.on', { perm: perm(k) })),
      ...r.removed.map((k) => t('admin.permHistory.off', { perm: perm(k) })),
    ].join(' · ')
  }
  const summary = (r: StaffPermissionChangeRow): string | null => {
    if (r.kind === 'role_change' || r.added.length + r.removed.length <= INLINE_KEYS) return null
    return [
      ...(r.added.length ? [t('admin.permHistory.countOn', { n: String(r.added.length) })] : []),
      ...(r.removed.length ? [t('admin.permHistory.countOff', { n: String(r.removed.length) })] : []),
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
            <ChangeRow key={`${r.at}-${i}`} full={what(r)} summary={summary(r)}
              byAt={t('admin.permHistory.byAt', {
                by: r.by || (r.by_super ? t('admin.permHistory.team')
                  : r.by_migration ? t('admin.permHistory.migration') : '—'),
                at: formatDateTime(r.at),
              })} />
          ))}
        </ul>
      )}
    </section>
  )
}

/** One change: the full list, or (D9) its summary with Show / Hide. */
function ChangeRow({ full, summary, byAt }: { full: string; summary: string | null; byAt: string }) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  return (
    <li className="px-4 py-3 sm:px-5" data-testid="perm-history-row">
      {summary === null ? <p className="text-sm text-ground-900">{full}</p> : (
        <>
          <p className="flex flex-wrap items-center gap-x-2 text-sm text-ground-900">
            <span>{summary}</span>
            <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="-my-2 min-h-11 px-1 text-sm font-medium text-primary-700 underline-offset-2 hover:underline">
              {t(open ? 'admin.permHistory.hide' : 'admin.permHistory.show')}
            </button>
          </p>
          {open && <p className="mt-1 text-sm text-ground-700" data-testid="perm-history-full">{full}</p>}
        </>
      )}
      <p className="mt-0.5 text-xs text-ground-500">{byAt}</p>
    </li>
  )
}
