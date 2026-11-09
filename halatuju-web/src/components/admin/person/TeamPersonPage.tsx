'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import { mayOpen, mayReadMentors } from '@/lib/pageGuard'
import RecordState from '@/components/admin/RecordState'
import PanelTabs from '@/components/admin/PanelTabs'
import PermissionEditor from '@/components/admin/PermissionEditor'
import StaffPersonActions from '@/components/admin/StaffPersonActions'
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
 *   * the Permissions tab: whoever may manage, and for a PURE mentor anybody who opens the page (it is
 *     read-only, D8). With one tab there is no bar: an `admin` or `finance` reader of a staff
 *     person's page sees the Profile exactly as before.
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
  const router = useRouter()
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
  if (!data) return <RecordState loading={!failed} />

  const { person: p, reviewer, staff, mentor } = data
  const who = p.name || p.email
  const backHref = `/admin/organisation/reviewers?tab=${backTable}`
  const leave = () => router.push(backHref)
  const staffRow = reviewer ?? staff
  // M5: the same actions, in the same place, on every page — a staff person's or a pure mentor's.
  const actions = !p.mentor_only
    ? (mayManage && token && staffRow ? (
      <StaffPersonActions token={token} viewerSuper={viewerRole === 'super'} onDeleted={leave}
        person={{ ...staffRow, name: who, email: staffRow.email ?? p.email }} openNow={reviewer?.open_now}
        onChanged={(on) => patch((d) => ({ ...d, person: { ...d.person, is_active: on },
          reviewer: d.reviewer && { ...d.reviewer, is_active: on }, staff: d.staff && { ...d.staff, is_active: on } }))} />
    ) : null)
    : (mentors && mentor && mentor.mentor.manageable ? (
      <mentors.MentorActions mentor={mentor.mentor} onDeleted={leave}
        onChanged={(row) => patch((d) => ({ ...d, person: { ...d.person, is_active: row.status !== 'inactive' },
          mentor: d.mentor && { ...d.mentor, mentor: { ...d.mentor.mentor, ...row } } }))} />
    ) : null)
  const tabbed = mayManage || p.mentor_only
  const shown = tabbed ? tab : 'profile'

  return (
    <div className="space-y-3.5" data-testid="team-person">
      <Link href={backHref} data-testid="person-back"
        className="text-sm text-primary-600 hover:text-primary-800 max-md:inline-flex max-md:min-h-11 max-md:items-center">
        ← {t(`admin.person.backTo.${backTable}`)}
      </Link>
      <PersonHeader data={data} token={token} mayManage={mayManage} actions={actions} onPatch={patch}
        mentorFigures={mentors && mentor ? <mentors.MentorFigures data={mentor} /> : null} />
      {tabbed && (
        <PanelTabs ariaLabelKey="admin.person.tabsAria" active={shown}
          onSelect={(k) => selectTab(k as 'profile' | 'permissions')}
          tabs={[
            { key: 'profile', labelKey: 'admin.person.tabProfile' },
            { key: 'permissions', labelKey: 'admin.person.tabPermissions' },
          ]} />
      )}
      {shown === 'permissions' && (p.mentor_only ? (
        <MentorOnlyPermissions adminId={p.admin_id} name={who} mayAdd={mentor?.may_add ?? []} token={token}
          onAdded={reload} />
      ) : token && (
        <PermissionEditor adminId={p.admin_id} name={who} token={token} initial={staff ?? undefined} onSaved={reload} />
      ))}
      {shown === 'profile' && (
        <PersonProfile data={data} mentorWork={mentors && mentor ? <mentors.MentorWork data={mentor} /> : null} />
      )}
    </div>
  )
}
