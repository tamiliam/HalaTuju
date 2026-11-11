/**
 * Sprint M2a: the person fixtures the group pages' tests share (`components/admin/person/GroupPages*.test.tsx`),
 * moved here from T3's `TeamPersonPage.test.tsx` unchanged. Invented names and `example.org` addresses only.
 */
import type * as admins from '@/lib/admin-api/admins'
import type * as mentors from '@/lib/admin-api/mentors'
import type * as reviewers from '@/lib/admin-api/reviewers'

export const TWO_DAYS_AGO = new Date(Date.now() - 2 * 24 * 3600 * 1000 - 60_000).toISOString()

export const person = (over: Partial<admins.TeamPersonBlock> = {}): admins.TeamPersonBlock => ({
  admin_id: 5, mentor_id: null, name: 'Kavitha Raman', email: 'kavitha@example.org', tables: ['reviewers'],
  lead: false, mentor_only: false, is_active: true, paused: false, joined_at: '2026-03-01T00:00:00Z',
  signed_in: true, last_seen_at: TWO_DAYS_AGO,
  profile: { job_title: 'Lecturer', about: '', qualification: 'MSc', university: '', graduation_year: null,
    field_of_study: '', phone: '', languages: ['en', 'ta'], other_language: '' },
  ...over,
})

export const reviewerDetail = (p: admins.TeamPersonBlock, over: Record<string, unknown> = {}) => ({
  id: p.admin_id, name: p.name, email: p.email, role: 'reviewer', languages: ['ta', 'en'], open_now: 1,
  awaiting_review: 1, interviewing: 0, completed: 4, turnaround_days: 3, paused: false, paused_at: null,
  recommended: 3, declined: 1, rejected_after_review: 0, awaiting_qc: 0, created_at: p.joined_at,
  qualification: 'MSc', university: '', graduation_year: null, field_of_study: '', phone: '',
  share_phone_with_students: false, gifts: [], organisation_id: 1, programmes: [], reopens: [],
  is_active: true, deletable: false, work: { assigned_applications: 1 }, pausable: true, person: p, ...over,
}) as unknown as reviewers.AdminReviewerDetail

const KEYS = ['review', 'see_all', 'qc', 'spending']
export const staffView = (p: admins.TeamPersonBlock, over: Partial<admins.StaffPermissionsView> = {}): admins.StaffPermissionsView => ({
  id: p.admin_id, name: p.name, role: 'admin', is_active: true, editable: true, preset: ['see_all'],
  permissions: ['see_all'], custom: false, keys: KEYS, email: p.email, created_at: p.joined_at ?? '',
  signed_in: true, paused: false, history: [], tables: p.tables, deletable: true, work: {}, person: p, ...over,
})

export const mentorRow = (over: Partial<mentors.MentorRow> = {}): mentors.MentorRow => ({
  id: 3, name: 'Ravi Kumar', email: 'ravi@example.org', status: 'active', area: '',
  languages: { en: 'fluent', ms: '', ta: '' }, other_language: '', invited_at: null, signed_in: true,
  last_seen_at: TWO_DAYS_AGO, deactivated_at: null, manageable: true, scholars_now: 1, staff_role: null,
  tables: ['mentors'], lead: false, meetings_90: 2, last_meeting: '2026-10-28', concerns_open: 0,
  deletable: false, work: { mentor_assignments: 1 }, ...over,
})

export const mentorDetail = (p: admins.TeamPersonBlock, over: Partial<mentors.MentorDetail> = {}): mentors.MentorDetail => ({
  mentor: mentorRow(), mentoring_since: '2026-09-02T00:00:00Z', sees_scholars: true,
  figures: { scholars_now: 1, meetings_90: 2, average_gap_days: 14, concerns_raised: 0, concerns_open: 0,
    last_meeting: '2026-10-28' },
  current: [{ application_id: 104, name: 'Nur Aisyah', since: '2026-09-02T00:00:00Z', ended: null, meetings: 2,
    last_meeting: '2026-10-28', standing: 'performing', has_file: true, concern: null }],
  past: [], may_add: [], person: p, ...over,
})
