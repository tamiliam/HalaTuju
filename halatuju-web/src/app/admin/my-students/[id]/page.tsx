'use client'
// One of a MENTOR's students (student maintenance S7c, 2026-11-01). Its own route chunk, like My students
// (no `import()` layer — see that page); the server answers 404 for anyone who is not this mentor's
// CURRENT student, and the screen says so.

import { useParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import MyStudentFile from '@/components/mentor/MyStudentFile'

export default function MyStudentPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)
  if (!role) return null
  if (!canAccess('/admin/my-students', effectiveRole(role), role.permissions, role.mentoring)) {
    return <p className="text-critical-600">{t('admin.myStudents.mentorsOnly')}</p>
  }
  if (!Number.isInteger(id) || id <= 0) return <p className="text-sm text-ground-700">{t('admin.myStudents.notYours')}</p>
  return <MyStudentFile id={id} />
}
