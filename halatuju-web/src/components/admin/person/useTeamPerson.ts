'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getReviewerDetail, type AdminReviewerDetail, type TeamPersonBlock } from '@/lib/admin-api'
import { getStaffPermissions, type StaffPermissionsView } from '@/lib/admin-api/admins'
import { getMentorDetail, type MentorDetail } from '@/lib/admin-api/mentors'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { effectiveRole } from '@/lib/navigation'
import { mayOpen, mayReadMentors } from '@/lib/pageGuard'
import { TEAM_PATH, wrongGroupTarget, type TeamGroup } from '@/lib/teamPaths'

/**
 * Sprint M2a (owner U2, 2026-11-11): ONE group page reads ONE detail — the admin page the permissions
 * view, the reviewer page the reviewer detail, the mentor page the mentor detail. T3's cross-reads are
 * gone: the other groups' parts live on their own pages (the header chips link there, U4).
 *
 * ⚠ `failed` says which way the read failed (T3 review): `'missing'` — a 404 or an id that names nobody,
 * and `RecordState` says "We could not find that", never why (the fence answers 404 across organisations);
 * `'error'` — anything else (offline, a 500, an api with no `person` block), worded as a load failure.
 */
export interface TeamPersonData {
  person: TeamPersonBlock
  reviewer: AdminReviewerDetail | null
  staff: StaffPermissionsView | null
  mentor: MentorDetail | null
}

export type PersonLoadFailure = false | 'missing' | 'error'

export interface TeamPersonState {
  data: TeamPersonData | null
  failed: PersonLoadFailure
  reload: () => void
  patch: (next: (d: TeamPersonData) => TeamPersonData) => void
}

async function readOne(group: TeamGroup, id: number, token: string): Promise<TeamPersonData> {
  const opts = { token }
  const got: Omit<TeamPersonData, 'person'> & { person?: TeamPersonBlock } =
    group === 'reviewers' ? await getReviewerDetail(id, opts).then((r) => ({ person: r.person, reviewer: r, staff: null, mentor: null }))
      : group === 'admins' ? await getStaffPermissions(id, opts).then((s) => ({ person: s.person, reviewer: null, staff: s, mentor: null }))
        : await getMentorDetail(id, opts).then((m) => ({ person: m.person, reviewer: null, staff: null, mentor: m }))
  if (!got.person) throw new Error('no person block')   // an api older than this page
  return got as TeamPersonData
}

export function useTeamPerson({ group, id, token }: {
  group: TeamGroup
  id: number
  token: string | null
}): TeamPersonState {
  const [data, setData] = useState<TeamPersonData | null>(null)
  const [failed, setFailed] = useState<PersonLoadFailure>(false)
  const [round, setRound] = useState(0)

  useEffect(() => {
    // A segment that is not a number can name nobody: "not found", never loading for ever.
    if (!Number.isInteger(id) || id <= 0) { setFailed('missing'); return }
    if (!token) return
    let live = true
    readOne(group, id, token)
      .then((d) => { if (live) { setData(d); setFailed(false) } })
      .catch((e: { status?: number }) => { if (live) setFailed(e?.status === 404 ? 'missing' : 'error') })
    return () => { live = false }
  }, [group, id, token, round])

  const reload = useCallback(() => setRound((n) => n + 1), [])
  const patch = useCallback((next: (d: TeamPersonData) => TeamPersonData) => {
    setData((d) => (d ? next(d) : d))
  }, [])
  return { data, failed, reload, patch }
}

export interface PersonPage extends TeamPersonState {
  token: string | null
  viewerRole: ReturnType<typeof effectiveRole>
  /** A super or an organisation admin: may change a team member's permissions (and open the admin page). */
  mayManage: boolean
  /** Which group pages this viewer may open — the header chips link only those (U4). */
  may: Record<TeamGroup, boolean>
  /** The message key that refuses this viewer the page, or null. */
  refusal: string | null
  /** True while the wrong-group rule sends the viewer on (nothing is drawn meanwhile). */
  moving: boolean
}

/**
 * Everything a group page decides before it draws (M2a): who may open it, its one read, and the
 * wrong-group replace (`lib/teamPaths.wrongGroupTarget`).
 *   * the admin page: whoever opens Team, and then only a super or an organisation admin
 *     (`admin.person.notAllowed` otherwise) — the permissions GET is narrower than Team;
 *   * the reviewer page: whoever opens Team; the mentor page: whoever reads the Mentors table.
 * A refused viewer's page asks nothing (UX only — every GET is its own fence).
 */
export function usePersonPage(group: TeamGroup, id: number): PersonPage {
  const { token, role } = useAdminAuth()
  const router = useRouter()
  const viewerRole = effectiveRole(role)
  const mayManage = viewerRole === 'super' || viewerRole === 'org_admin'
  const mayTeam = mayOpen(TEAM_PATH, role)
  const may = { admins: mayTeam && mayManage, reviewers: mayTeam, mentors: mayReadMentors(role) }
  const refusal = !role ? null
    : group === 'mentors' ? (may.mentors ? null : 'apiErrors.superAdminRequired')
      : !mayTeam ? 'apiErrors.superAdminRequired'
        : group === 'admins' && !mayManage ? 'admin.person.notAllowed' : null
  const state = useTeamPerson({ group, id, token: refusal ? null : token })
  const person = state.data?.person
  const target = person
    ? wrongGroupTarget(group, person, typeof window !== 'undefined' ? window.location.hash : '') : null
  useEffect(() => { if (target) router.replace(target) }, [target, router])
  return { ...state, token, viewerRole, mayManage, may, refusal, moving: !!target }
}
