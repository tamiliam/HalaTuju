'use client'

import { useT } from '@/lib/i18n'

/**
 * People's permission chips (request #39 Sprint 4): beside a person's role, what their set adds to
 * the role's preset (`+ Spending`) and what it takes away (struck through). Nothing on a preset row,
 * so a settled team reads exactly as before.
 *
 * ⚠ THE SERVER DECIDES THE DIFFERENCE (`permissions_added` / `permissions_removed`, served on both
 * People lists). This file holds no copy of the presets — `lib/staffPermissions.ts` says why.
 */
export default function PermissionChips({ row }: {
  row: { custom?: boolean; permissions_added?: string[]; permissions_removed?: string[] }
}) {
  const { t } = useT()
  if (!row.custom) return null
  const added = row.permissions_added ?? []
  const removed = row.permissions_removed ?? []
  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-testid="permission-chips">
      <span className="rounded-full bg-caution-100 px-2 py-0.5 text-[11px] font-semibold text-caution-700">
        {t('admin.permEditor.custom')}
      </span>
      {added.map((k) => (
        <span key={`+${k}`} className="rounded-full bg-info-100 px-2 py-0.5 text-[11px] text-info-700">
          + {t(`admin.perm.${k}.name`)}
        </span>
      ))}
      {removed.map((k) => (
        <span key={`-${k}`}
          className="rounded-full bg-ground-100 px-2 py-0.5 text-[11px] text-ground-500 line-through">
          {t(`admin.perm.${k}.name`)}
        </span>
      ))}
    </span>
  )
}
