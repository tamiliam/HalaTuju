'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import { mayOpen, mayReadMentors } from '@/lib/pageGuard'
import RecordState from '@/components/admin/RecordState'
import PanelTabs from '@/components/admin/PanelTabs'
import PermissionEditor from '@/components/admin/PermissionEditor'
import PersonHeader from './PersonHeader'
import PersonProfile from './PersonProfile'
import MentorOnlyPermissions from './MentorOnlyPermissions'
import { useTeamPerson, type PersonEntry } from './useTeamPerson'

/**
 * Sprint T3 (owner 2026-11-09; D8, D9, M1–M6): ONE person page for every team member.
 *
 * Three routes stay — `reviewers/[id]`, `reviewers/admins/[id]`, `reviewers/mentors/[id]` — so every
 * link keeps working; each renders this, its own chunk (`'ad'`, with the permission editor), so a
 * route's entry carries one loader line. The header (`PersonHeader`) and the two tabs are the same for
 * everybody; the parts each table brings (a reviewer's figures, outcomes and reopens; a mentor's
 * figures and scholars) appear for whoever sits in it (M6).
 *
 * WHO SEES WHAT (UX only — every GET is its own fence, and answers 404 across organisations):
 *   * the reviewer route: whoever opens Team; the admin route: a super or an organisation admin
 *     (`admin.person.notAllowed` otherwise); the mentor route: whoever reads the Mentors table;
 *   * the Permissions tab: for everybody. A PURE mentor's is read-only (D8); a staff person's is the
 *     editor for whoever may manage, and for an `admin` or `finance` reader only the line "Only an
 *     organisation admin can open a team member's permissions." — nothing fetched (architect, Q1);
 *   * the background profile fields: as the server serves them (`profile_full`, T3 review fix 1).
 *
 * A STAFF MENTOR's page also offers Remove from Mentors (the Mentors table's `stop`). Suspend and Delete
 * are on Team -> Staff only (M1b, O3). A fellow organisation admin's page is READ-ONLY (O10): no
 * buttons, and the permissions are shown, not edited. Permissions draw only the section for the table
 * the page was opened from (O12, `table`).
 *
 * `#permissions` opens the tab directly, read after mount (the hash does not exist on the server pass).
 */
type MentorsModule = typeof import('@/components/mentors/MentorsAdmin')

export default function TeamPersonPage({ entry, id, backTable }: {
  entry: PersonEntry
  id: number
  /** The Team tab Back returns to (`?tab=`). */
  backTable: 'admins' | 'reviewers' | 'mentors'
}) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const viewerRole = effectiveRole(role)
  const mayManage = viewerRole === 'super' || viewerRole === 'org_admin'
  const mayMentors = mayReadMentors(role)
  const mayView = entry === 'mentor' ? mayMentors : mayOpen('/admin/organisation/reviewers', role)
  const fenced = !!role && (!mayView || (entry === 'admin' && !mayManage))
  const { data, failed, reload, patch } = useTeamPerson({
    entry, id, token: fenced ? null : token, mayManage, mayMentors,
  })

  // The mentor parts are the Mentors table's own chunk, by its literal specifier — no new chunk.
  const [mentors, setMentors] = useState<MentorsModule | null>(null)
  const needsMentors = !!data?.mentor
  useEffect(() => {
    if (!needsMentors || mentors) return
    let live = true
    import('@/components/mentors/MentorsAdmin').then((m) => { if (live) setMentors(m) }).catch(() => {})
    return () => { live = false }
  }, [needsMentors, mentors])

  const [tab, setTab] = useState<'profile' | 'permissions'>('profile')
  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash === '#permissions') setTab('permissions')
  }, [])
  const selectTab = (k: 'profile' | 'permissions') => {
    setTab(k)
    // Keep the address in step, so a reload or a copied link lands on the same tab.
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '',
        `${window.location.pathname}${window.location.search}${k === 'permissions' ? '#permissions' : ''}`)
    }
  }

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (role && entry === 'admin' && !mayManage) return <p className="text-critical-600">{t('admin.person.notAllowed')}</p>
  if (!data && failed === 'error') return <p className="text-sm text-critical-600" role="alert">{t('admin.person.loadFailed')}</p>
  if (!data) return <RecordState loading={!failed} />

  const { person: p, reviewer, staff, mentor } = data
  const who = p.name || p.email
  const backHref = `/admin/organisation/reviewers?tab=${backTable}`
  // M1b (O3, O10): Suspend and Delete live on Team -> Staff only. A staff mentor keeps Remove from
  // Mentors here; a fellow organisation admin's page is read-only — no buttons at all.
  // The staff GET says it (`manageable`); the reviewer route, which skips that GET, knows them by role.
  const readOnly = staff ? staff.manageable === false : viewerRole !== 'super' && reviewer?.role === 'org_admin'
  const actions = !readOnly && !p.mentor_only && mentors && mentor && mentor.mentor.manageable
    && mentor.mentor.status === 'active'
    ? <mentors.StaffMentorRemove mentor={mentor.mentor} onRemoved={reload} /> : null

  return (
    <div className="space-y-3.5" data-testid="team-person">
      <Link href={backHref} data-testid="person-back"
        className="text-sm text-primary-600 hover:text-primary-800 max-md:inline-flex max-md:min-h-11 max-md:items-center">
        ← {t(`admin.person.backTo.${backTable}`)}
      </Link>
      <PersonHeader data={data} token={token} mayManage={mayManage && !readOnly} actions={actions} onPatch={patch}
        mentorFigures={mentors && mentor ? <mentors.MentorFigures data={mentor} /> : null}
        mentorGifts={mentors && mentor ? (
          <mentors.MentorGifts data={mentor} onSaved={(gifts) => patch((d) => ({ ...d,
            mentor: d.mentor && { ...d.mentor, mentor: { ...d.mentor.mentor, gifts, every_gift: gifts.length === 0 } } }))} />
        ) : null} />
      <PanelTabs ariaLabelKey="admin.person.tabsAria" active={tab}
        onSelect={(k) => selectTab(k as 'profile' | 'permissions')}
        tabs={[
          { key: 'profile', labelKey: 'admin.person.tabProfile' },
          { key: 'permissions', labelKey: 'admin.person.tabPermissions' },
        ]} />
      {tab === 'permissions' && (p.mentor_only ? (
        <MentorOnlyPermissions adminId={p.admin_id} name={who} mayAdd={mentor?.may_add ?? []} token={token}
          onAdded={reload} />
      ) : !mayManage ? (
        <p className="text-sm text-ground-500" data-testid="person-perm-not-allowed">{t('admin.person.notAllowed')}</p>
      ) : token && (
        <PermissionEditor adminId={p.admin_id} name={who} token={token} initial={staff ?? undefined} onSaved={reload}
          table={backTable === 'mentors' ? undefined : backTable} />
      ))}
      {tab === 'profile' && (
        <PersonProfile data={data} mentorWork={mentors && mentor ? <mentors.MentorWork data={mentor} /> : null} />
      )}
    </div>
  )
}
