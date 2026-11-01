'use client'
// My students — a MENTOR's own students (student maintenance S7c, 2026-11-01). The route is its own chunk
// and only a mentor's menu links here, so no staff or student route carries a byte of it. No `import()`
// layer on top: the route is mentor-only already, and every extra async chunk is one more entry in the
// webpack runtime EVERY route downloads (the S7b follow-up's lesson). The server is the fence
// (`admin/mentor/students/` serves the caller's CURRENT students only); this page only declines to draw
// for anyone who is not a mentor.

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import MyStudents from '@/components/mentor/MyStudents'

export default function MyStudentsPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  if (!role) return null
  // S7d: a staff member who also mentors now (`role.mentoring`) opens it too, keeping their own menu.
  if (!canAccess('/admin/my-students', effectiveRole(role), role.permissions, role.mentoring)) {
    return <p className="text-critical-600">{t('admin.myStudents.mentorsOnly')}</p>
  }
  return <MyStudents />
}
