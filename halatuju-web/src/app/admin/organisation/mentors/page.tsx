'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Organisation → Mentors had a page of its own from student maintenance S7a (2026-10-31) until Team
 * tables T3 (2026-11-03, owner ruling 6): mentors are a TEAM table now — Team → Mentors — beside Admins
 * and Reviewers, and the menu row went.
 *
 * This stays as a permanent redirect, the same shape as `/admin/organisation/programmes`: it costs one
 * file, and a dead admin link costs somebody a support message. `navigation.ts` matches this path to
 * the Team row, so a bookmark also lights the right part of the sidebar. "Invite a mentor" went with the
 * page: mentors are invited on Invitations → Mentor; the Mentors emails tab's template is on
 * Invitations → Emails.
 */
export default function MentorsRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/admin/organisation/reviewers?tab=mentors')
  }, [router])
  return null
}
