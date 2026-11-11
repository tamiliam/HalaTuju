'use client'

import { useT } from '@/lib/i18n'
import PermissionEditor from '@/components/admin/PermissionEditor'
import PersonShell, { personStop } from './PersonShell'
import { usePersonPage } from './useTeamPerson'

/**
 * Sprint M2a (owner U2): a person's ADMIN page, `/admin/organisation/team/admins/<id>` — admin work only.
 * It reads the permissions view alone (`GET admin/admins/<id>/permissions/`): the header (no figures, no
 * Covers, no Pause — those are the reviewer page's), About, and Permissions with ONLY the Admins section
 * (O12). A fellow organisation admin's page is read-only (O10): the view says so (`manageable: false`,
 * `editable: false`) and the editor locks its switches.
 *
 * ⚠ WHO SEES IT: whoever opens Team, and then only a super or an organisation admin — the GET is the fence
 * (an org_admin reads only their own organisation's team; 404 otherwise).
 */
export default function AdminGroupPage({ id }: { id: number }) {
  const { t } = useT()
  const page = usePersonPage('admins', id)
  const stop = personStop(page, t)
  if (stop) return stop
  const data = page.data!
  const p = data.person
  const staff = data.staff
  return (
    <PersonShell group="admins" page={page} data={data} mayManage={page.mayManage && staff?.manageable !== false}
      actions={null}
      permissions={page.token ? (
        <PermissionEditor adminId={p.admin_id} name={p.name || p.email} token={page.token}
          initial={staff ?? undefined} onSaved={page.reload} table="admins" />
      ) : <></>} />
  )
}
