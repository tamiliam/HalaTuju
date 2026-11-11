'use client'

import { useT } from '@/lib/i18n'
import PermissionEditor from '@/components/admin/PermissionEditor'
import PersonShell, { personStop } from './PersonShell'
import { usePersonPage } from './useTeamPerson'

/**
 * Sprint M2a (owner U2): a person's REVIEWER page, `/admin/organisation/team/reviewers/<id>`. It reads the
 * reviewer detail alone: the header with the reviewer's figures, Covers and Pause; the About tab with
 * Outcomes, About and Reopens (the reviewer layout since request #10); Permissions with ONLY the Reviewers
 * section (O12) for a viewer who may manage, the "only an organisation admin" line for anybody else
 * (nothing fetched, architect Q1).
 *
 * A fellow organisation admin's page is READ-ONLY for another organisation admin (O10): no Pause, no
 * Covers edit. The reviewer detail carries no `manageable`, so the page knows them by role.
 * ⚠ WHO SEES IT: whoever opens Team; the endpoint is the fence. ⚠ `ReviewerProfile` also holds a HOME
 * ADDRESS: it is in no payload and never shown.
 */
export default function ReviewerGroupPage({ id }: { id: number }) {
  const { t } = useT()
  const page = usePersonPage('reviewers', id)
  const stop = personStop(page, t)
  if (stop) return stop
  const data = page.data!
  const p = data.person
  const readOnly = page.viewerRole !== 'super' && data.reviewer?.role === 'org_admin'
  return (
    <PersonShell group="reviewers" page={page} data={data} mayManage={page.mayManage && !readOnly} actions={null}
      permissions={!page.mayManage ? (
        <p className="text-sm text-ground-500" data-testid="person-perm-not-allowed">{t('admin.person.notAllowed')}</p>
      ) : page.token ? (
        <PermissionEditor adminId={p.admin_id} name={p.name || p.email} token={page.token} onSaved={page.reload}
          table="reviewers" />
      ) : <></>} />
  )
}
