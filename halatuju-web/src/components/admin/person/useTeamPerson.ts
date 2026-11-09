'use client'

import { useCallback, useEffect, useState } from 'react'
import { getReviewerDetail, type AdminReviewerDetail, type TeamPersonBlock } from '@/lib/admin-api'
import { getStaffPermissions, type StaffPermissionsView } from '@/lib/admin-api/admins'
import { getMentorDetail, type MentorDetail } from '@/lib/admin-api/mentors'

/**
 * Sprint T3: everything ONE person page shows, whichever of the three doors the viewer came in by.
 *
 * The route's own detail is read first (`entry`); its `person` block then says which tables the person
 * sits in, and the page reads the other details that apply (M6 — a reviewer who mentors shows both
 * parts). No new endpoint: the three existing details, each still its own fence.
 *   * the reviewer detail when they sit in Reviewers (outcomes, reopens, figures, Pause, gifts);
 *   * the mentor detail when they mentor and the viewer reads the Mentors table (`mayMentors`);
 *   * the permissions view when the viewer may manage (`mayManage`), the person is staff, and no
 *     reviewer detail carries the Revoke / Delete fields already — an admin or finance person.
 *
 * ⚠ A SECONDARY read that fails draws nothing for its part; only the route's own read can fail the
 * page (and then `RecordState` says "We could not find that" — never why: the fence answers 404).
 */
export type PersonEntry = 'reviewer' | 'admin' | 'mentor'

export interface TeamPersonData {
  person: TeamPersonBlock
  reviewer: AdminReviewerDetail | null
  staff: StaffPermissionsView | null
  mentor: MentorDetail | null
}

export interface TeamPersonState {
  data: TeamPersonData | null
  failed: boolean
  reload: () => void
  patch: (next: (d: TeamPersonData) => TeamPersonData) => void
}

const quiet = <T,>(p: Promise<T>) => p.catch(() => null)

export function useTeamPerson({ entry, id, token, mayManage, mayMentors }: {
  entry: PersonEntry
  id: number
  token: string | null
  mayManage: boolean
  mayMentors: boolean
}): TeamPersonState {
  const [data, setData] = useState<TeamPersonData | null>(null)
  const [failed, setFailed] = useState(false)
  const [round, setRound] = useState(0)

  useEffect(() => {
    // A segment that is not a number can name nobody: "not found", never loading for ever.
    if (!Number.isInteger(id) || id <= 0) { setFailed(true); return }
    if (!token) return
    let live = true
    const opts = { token }
    const first = async (): Promise<Omit<TeamPersonData, 'person'> & { person?: TeamPersonBlock }> => {
      if (entry === 'reviewer') {
        const r = await getReviewerDetail(id, opts)
        return { person: r.person, reviewer: r, staff: null, mentor: null }
      }
      if (entry === 'admin') {
        const s = await getStaffPermissions(id, opts)
        return { person: s.person, reviewer: null, staff: s, mentor: null }
      }
      const m = await getMentorDetail(id, opts)
      return { person: m.person, reviewer: null, staff: null, mentor: m }
    }
    first()
      .then(async (got) => {
        const p = got.person
        if (!p) throw new Error('no person block')   // an api older than this page
        const staffSide = !p.mentor_only
        const [reviewer, mentor] = await Promise.all([
          got.reviewer ?? (p.tables.includes('reviewers') ? quiet(getReviewerDetail(p.admin_id, opts)) : null),
          got.mentor ?? (p.mentor_id && mayMentors ? quiet(getMentorDetail(p.mentor_id, opts)) : null),
        ])
        const staff = got.staff ?? (mayManage && staffSide && !reviewer
          ? await quiet(getStaffPermissions(p.admin_id, opts)) : null)
        if (live) { setData({ person: p, reviewer, staff, mentor }); setFailed(false) }
      })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [entry, id, token, mayManage, mayMentors, round])

  const reload = useCallback(() => setRound((n) => n + 1), [])
  const patch = useCallback((next: (d: TeamPersonData) => TeamPersonData) => {
    setData((d) => (d ? next(d) : d))
  }, [])
  return { data, failed, reload, patch }
}
