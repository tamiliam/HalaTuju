'use client'

import Link from 'next/link'
import { useState, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { chipLinks, teamTabHref, type TeamGroup } from '@/lib/teamPaths'
import RecordState from '@/components/admin/RecordState'
import PanelTabs from '@/components/admin/PanelTabs'
import PersonHeader from './PersonHeader'
import PersonProfile from './PersonProfile'
import type { PersonPage, TeamPersonData } from './useTeamPerson'

/**
 * Sprint M2a (owner U2–U4, 2026-11-11): what the three group pages (`AdminGroupPage`, `ReviewerGroupPage`,
 * `MentorGroupPage`) share — Back to the page's own Team tab, the header card (its chips link to the
 * person's OTHER group pages the viewer may open, U4), the About tab (on every group page, U3) and, when
 * the page has one, the Permissions tab. Each page brings only its own group's parts (U2).
 *
 * `#permissions` opens the tab directly, and choosing a tab keeps the address in step.
 */

/** What a group page draws instead of itself: a refusal, a load failure, loading, or nothing while the
 *  wrong-group rule moves the viewer on. Null = draw the page. */
export function personStop(page: PersonPage, t: (k: string) => string): ReactNode | null {
  if (page.refusal) return <p className="text-critical-600">{t(page.refusal)}</p>
  if (!page.data && page.failed === 'error') {
    return <p className="text-sm text-critical-600" role="alert">{t('admin.person.loadFailed')}</p>
  }
  if (!page.data || page.moving) return <RecordState loading={!page.failed} />
  return null
}

type Tab = 'profile' | 'permissions'

export default function PersonShell({ group, page, data, mayManage, actions, mentorFigures, mentorGifts, mentorWork,
  permissions }: {
  group: TeamGroup
  page: PersonPage
  data: TeamPersonData
  /** May change what the header offers (Pause, Covers): false on a read-only page (O10). */
  mayManage: boolean
  actions: ReactNode
  mentorFigures?: ReactNode
  mentorGifts?: ReactNode
  mentorWork?: ReactNode
  /** The Permissions tab's body; null = this page has no Permissions tab (a staff mentor's mentor page). */
  permissions: ReactNode | null
}) {
  const { t } = useT()
  const hasPermissions = permissions !== null
  // The shell is drawn only once the person has loaded — never on the server pass — so the hash is read
  // as the tab starts.
  const [tab, setTab] = useState<Tab>(() =>
    hasPermissions && typeof window !== 'undefined' && window.location.hash === '#permissions' ? 'permissions' : 'profile')
  const selectTab = (k: Tab) => {
    setTab(k)
    // Keep the address in step, so a reload or a copied link lands on the same tab.
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '',
        `${window.location.pathname}${window.location.search}${k === 'permissions' ? '#permissions' : ''}`)
    }
  }

  return (
    <div className="space-y-3.5" data-testid="team-person">
      <Link href={teamTabHref(group)} data-testid="person-back"
        className="text-sm text-primary-600 hover:text-primary-800 max-md:inline-flex max-md:min-h-11 max-md:items-center">
        ← {t(`admin.person.backTo.${group}`)}
      </Link>
      <PersonHeader data={data} token={page.token} mayManage={mayManage} actions={actions} onPatch={page.patch}
        chips={{ current: group, hrefs: chipLinks(data.person, group, page.may) }}
        mentorFigures={mentorFigures ?? null} mentorGifts={mentorGifts} />
      {hasPermissions && (
        <PanelTabs ariaLabelKey="admin.person.tabsAria" active={tab} onSelect={(k) => selectTab(k as Tab)}
          tabs={[
            { key: 'profile', labelKey: 'admin.person.tabProfile' },
            { key: 'permissions', labelKey: 'admin.person.tabPermissions' },
          ]} />
      )}
      {hasPermissions && tab === 'permissions' && permissions}
      {(!hasPermissions || tab === 'profile') && <PersonProfile data={data} mentorWork={mentorWork ?? null} />}
    </div>
  )
}
