/**
 * Test fixtures for the source console — each one is the EXACT shape the backend serves
 * (`halatuju_api/apps/scholarship/source_console.py`: `profile_dict`, the overview view,
 * `application_row` / `application_detail` / `witness_only_detail`, `agreement_dict`,
 * `scholar_row` / `scholar_detail`, and the `FlexiblePageNumberPagination` envelope). Every key the
 * server writes is here and nothing else, so a component that reads a key the server never sends
 * fails its test. Imported by the `*.test.tsx` files beside it only.
 */
import type {
  SourceAgreement, SourceApplication, SourceApplicationList, SourceContract, SourceOverview,
  SourceProfile, SourceScholar, SourceScholarList,
} from '@/lib/admin-api'

const GIFT = { code: 'flag', name: 'Harapan Bursary' }

export const PROFILE: SourceProfile = {
  user: { name: 'Audrey Koh Sui Ean', email: 'muetmyway@example.org' },
  source: { name: 'MUETMyWay', code: 'muet', contact_person: 'Audrey Koh Sui Ean',
            contact_email: 'muetmyway@example.org', phone: '016-845 1270', organisation: 'Harapan' },
}

export const OVERVIEW: SourceOverview = {
  programme: GIFT,
  counts: { not_shortlisted: 6, shortlisted: 2, awaiting_review: 3, under_review: 21, awarded: 5,
            rejected: 7, closed: 1, total: 45 },
  scholars: 3,
  witness_waiting: [{ application_id: 104, student_name: 'Harish A/L Kumar' }],
  missing_items: [{ application_id: 101, student_name: 'Priya Devi', applied: '2026-10-12T02:00:00Z',
                    last_activity: '2026-10-20T02:00:00Z' }],
}

export const WAITING_CONTRACT: SourceContract = {
  status: 'binds', student_signed_at: '2026-10-24T02:00:00Z', guarantor_signed_at: '2026-10-25T02:00:00Z',
  witness_signed_at: null, foundation_signed_at: null, witness_is_you: true, can_witness: true,
}

export const APPLICATIONS: SourceApplicationList = {
  count: 2, total_pages: 1, page: 1, page_size: 25, next: null, previous: null,
  applications: [
    { id: 101, student_name: 'Priya Devi', school: 'SMK Seri Garing', state: 'Selangor', level: 'spm',
      programme: GIFT, submitted_at: '2026-10-12T02:00:00Z', stage: 'shortlisted' },
    { id: 104, student_name: 'Harish A/L Kumar', school: 'SMK Taman Melawati', state: 'Selangor',
      level: 'stpm', programme: GIFT, submitted_at: '2026-09-03T02:00:00Z', stage: 'awarded' },
  ],
}

export const LISTED: SourceApplication = {
  ...APPLICATIONS.applications[1], kind: 'listed', phone: '012-345 6789', email: 'harish.k@example.com',
  told_at: '2026-10-20T02:00:00Z', missing_items: [], contract: WAITING_CONTRACT,
}

export const LISTED_MISSING: SourceApplication = {
  ...APPLICATIONS.applications[0], kind: 'listed', phone: '', email: 'priya@example.com',
  told_at: '2026-10-13T02:00:00Z', missing_items: ['documents', 'guardian_documents'], contract: null,
}

export const WITNESS_ONLY: SourceApplication = {
  id: 207, kind: 'witness_only', student_name: 'Kavin Selvam', programme: GIFT, contract: WAITING_CONTRACT,
}

export const AGREEMENT: SourceAgreement = {
  ...WAITING_CONTRACT, application_id: 104, student_name: 'Harish A/L Kumar', pdf_url: null,
  pdf_expires_in: 300, rendered: false,
}

export const SCHOLARS: SourceScholarList = {
  count: 2, total_pages: 1, page: 1, page_size: 25, next: null, previous: null,
  scholars: [
    { id: 104, student_name: 'Harish A/L Kumar', programme: GIFT, institution: 'Universiti Malaya',
      course: 'Bachelor of Engineering', status: 'awarded', contract_stage: 'binds' },
    { id: 105, student_name: 'Janani Muthu', programme: GIFT, institution: 'Politeknik Ungku Omar',
      course: 'Diploma in Accountancy', status: 'active', contract_stage: 'executed' },
  ],
}

export const SCHOLAR: SourceScholar = {
  ...SCHOLARS.scholars[1], phone: '011-222 3333', email: 'janani@example.com',
  contract: { status: 'executed', student_signed_at: '2026-06-01T02:00:00Z',
              guarantor_signed_at: '2026-06-01T02:00:00Z', witness_signed_at: '2026-06-03T02:00:00Z',
              foundation_signed_at: '2026-06-05T02:00:00Z', witness_is_you: true, can_witness: false },
}
