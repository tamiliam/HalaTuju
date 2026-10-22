'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { getStaffPermissions, type StaffPermissionsView } from '@/lib/admin-api/admins'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'
import RecordState from '@/components/admin/RecordState'
import PanelTabs from '@/components/admin/PanelTabs'
import LazyPermissionEditor from '@/components/admin/LazyPermissionEditor'

/**
 * Team → an ADMIN-side team member (Admin, Finance) → **Permissions** (2026-10-22, the owner's
 * option A): one consistent place for what a person may do — their own page, on a Permissions tab,
 * the same as a reviewer's.
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/reviewers` ON PURPOSE. `canAccess` resolves a path by
 * its longest registered prefix, so this page belongs to the Team row (same roles, same highlight,
 * same ⌘K entry) without a registry row of its own. `admins` is a static segment, so Next prefers it
 * over the reviewer page's `[id]`.
 *
 * ⚠ THE GET IS THE FENCE, and it is narrower than the Team page: only a super or an organisation
 * admin may read anybody's permissions, and an org_admin only their own organisation's team (404
 * otherwise, never 403, so existence does not leak). `admin` and `finance` may open Team but not
 * this; they are told so rather than shown an empty card. The header is drawn from the same GET the
 * card uses — `initial` hands it over, so the page makes one request.
 */
export default function AdminPersonPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)
  const viewerRole = effectiveRole(role)
  const mayView = canAccess('/admin/organisation/reviewers', viewerRole)
  const mayManage = viewerRole === 'super' || viewerRole === 'org_admin'

  const [view, setView] = useState<StaffPermissionsView | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)

  useEffect(() => {
    if (!token || !id || !mayManage) return
    let live = true
    getStaffPermissions(id, { token })
      .then((v) => { if (live) setView(v) })
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [token, id, mayManage])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (role && !mayManage) return <p className="text-critical-600">{t('admin.person.notAllowed')}</p>
  if (!view) return <RecordState loading={!loadFailed && Number.isFinite(id) && id > 0} />

  const status = staffStatusKey(view)
  const who = view.name || view.email || ''

  return (
    <div className="space-y-3.5">
      {/* `?tab=admins` is what the Team page reads, so Back lands on the tab the person came from. */}
      <Link href="/admin/organisation/reviewers?tab=admins"
        className="text-sm text-primary-600 hover:text-primary-800">
        ← {t('admin.person.back')}
      </Link>

      <section className="bg-ground-0 rounded-xl shadow-sm border px-4 sm:px-5 py-4">
        <h1 className="text-lg sm:text-xl font-bold truncate">{who}</h1>
        <p className="text-sm text-ground-500 mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1">
          <span>{t(`admin.role.${view.role}`)}</span>
          <span aria-hidden>·</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${STAFF_STATUS_TONE[status]}`}>
            {t(`admin.reviewers.status.${status}`)}
          </span>
          {/* ⚠ "No sign-in recorded", never "never signed in": the column is empty for anybody who
              predates it (models_staff.py, `first_seen_at`). */}
          {view.signed_in === false && (<>
            <span aria-hidden>·</span>
            <span className="text-caution-700" data-testid="person-invited">{t('admin.person.invited')}</span>
          </>)}
          {view.created_at && (<>
            <span aria-hidden>·</span>
            <span>{t('admin.reviewers.detail.joined', { date: formatDate(view.created_at) })}</span>
          </>)}
        </p>
        {view.email && <p className="text-sm text-ground-500 mt-1 break-all">{view.email}</p>}
      </section>

      {/* One tab today, drawn as a bar so this page and a reviewer's look alike. */}
      <PanelTabs ariaLabelKey="admin.person.tabsAria" active="permissions" onSelect={() => {}}
        tabs={[{ key: 'permissions', labelKey: 'admin.person.tabPermissions' }]} />

      {token && (
        <LazyPermissionEditor adminId={view.id} name={who} token={token} initial={view} />
      )}
    </div>
  )
}
