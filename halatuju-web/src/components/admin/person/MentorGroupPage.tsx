'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import MentorOnlyPermissions from './MentorOnlyPermissions'
import PersonShell, { personStop } from './PersonShell'
import { usePersonPage } from './useTeamPerson'

/**
 * Sprint M2a (owner U2): a person's MENTOR page, `/admin/organisation/team/mentors/<id>` — the id is the
 * MENTOR record's, not the sign-in's. It reads the mentor detail alone: the header with the mentor's
 * figures and gifts, About with the area and "mentoring since" rows, and their scholars (`MentorWork`).
 *   * A PURE mentor keeps the Permissions tab: read-only, with the Add-to-a-group path for a viewer who may
 *     add them (`MentorOnlyPermissions`, D8).
 *   * A STAFF mentor's mentor page has NO Permissions tab — mentoring is not a permission; their admin or
 *     reviewer permissions are on those pages. It offers Remove from Mentors (the Mentors table's `stop`),
 *     except on a fellow organisation admin's page, which is read-only (O10).
 *   * The background profile fields follow the server (`profile_full`, T3 review fix 1).
 *
 * The mentor parts are the Mentors table's own chunk, loaded by its literal specifier — no new chunk.
 * ⚠ WHO SEES IT: exactly who reads the Mentors table (`mayReadMentors`); `GET admin/mentors/<id>/` is the
 * fence (403, and 404 for another organisation's mentor).
 */
type MentorsModule = typeof import('@/components/mentors/MentorsAdmin')

export default function MentorGroupPage({ id }: { id: number }) {
  const { t } = useT()
  const page = usePersonPage('mentors', id)
  const [mentors, setMentors] = useState<MentorsModule | null>(null)
  const needsMentors = !!page.data?.mentor
  useEffect(() => {
    if (!needsMentors || mentors) return
    let live = true
    import('@/components/mentors/MentorsAdmin').then((m) => { if (live) setMentors(m) }).catch(() => {})
    return () => { live = false }
  }, [needsMentors, mentors])

  const stop = personStop(page, t)
  if (stop) return stop
  const data = page.data!
  const p = data.person
  const mentor = data.mentor
  // O10: a fellow organisation admin is read-only for another organisation admin. The mentor row's
  // `manageable` is the Mentors table's rule (an org_admin manages their own organisation's mentors), so
  // the page knows the lead by the person block and the mentor row's staff role.
  const readOnly = page.viewerRole !== 'super' && (p.lead || mentor?.mentor.staff_role === 'org_admin')
  const actions = !readOnly && !p.mentor_only && mentors && mentor && mentor.mentor.manageable
    && mentor.mentor.status === 'active'
    ? <mentors.StaffMentorRemove mentor={mentor.mentor} onRemoved={page.reload} /> : null
  return (
    <PersonShell group="mentors" page={page} data={data} mayManage={page.mayManage && !readOnly} actions={actions}
      mentorFigures={mentors && mentor ? <mentors.MentorFigures data={mentor} /> : null}
      mentorGifts={mentors && mentor ? (
        <mentors.MentorGifts data={mentor} onSaved={(gifts) => page.patch((d) => ({ ...d,
          mentor: d.mentor && { ...d.mentor, mentor: { ...d.mentor.mentor, gifts, every_gift: gifts.length === 0 } } }))} />
      ) : null}
      mentorWork={mentors && mentor ? <mentors.MentorWork data={mentor} /> : null}
      permissions={p.mentor_only ? (
        <MentorOnlyPermissions adminId={p.admin_id} name={p.name || p.email} mayAdd={mentor?.may_add ?? []}
          token={page.token} onAdded={page.reload} />
      ) : null} />
  )
}
