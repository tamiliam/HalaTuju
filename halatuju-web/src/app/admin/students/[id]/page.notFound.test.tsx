/**
 * @jest-environment jsdom
 *
 * A STUDENT RECORD THAT IS NOT THERE — and the sentence this screen used to put on screen.
 *
 * It said `apiErrors.studentNotFound` ("Student not found") for ANY failed GET. That is a claim
 * we cannot make: the same rejection is a dropped connection, and it is a student belonging to
 * another organisation, which the admin fence answers 404 for precisely so that the record's
 * existence is never leaked. The record exists; saying it does not is simply false, and saying
 * "you may not see it" would leak it. The shared state says neither.
 *
 * The second test is the one that keeps the fix from costing something: a failed DELETE still
 * reports itself, and it must not be swallowed by the not-found state now sitting above it.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import AdminStudentDetail from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '999999' }),
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'super', is_super_admin: true } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const gone = () => {
  const err = new Error('Not found') as Error & { status?: number; code?: string }
  err.status = 404
  err.code = 'not_found'
  return err
}

const STUDENT = {
  supabase_user_id: 'uid-1', name: 'Test Student 07', email: 's@example.test',
  nric: '081119-05-0548', phone: null, grades: {}, stpm_grades: {}, student_signals: {},
  created_at: '2026-01-01T00:00:00Z',
} as unknown as api.StudentDetailData

beforeEach(() => {
  jest.clearAllMocks()
})

it('draws the not-found state, says nothing about why, and STOPS loading', async () => {
  mockApi.getPartnerStudent.mockRejectedValue(gone())
  render(<AdminStudentDetail />)
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByText('common.loading')).toBeNull()
  // ⚠ The old sentence must not come back on this path.
  expect(screen.queryByText('apiErrors.studentNotFound')).toBeNull()
})

it('keeps loading while the record has genuinely not answered', async () => {
  mockApi.getPartnerStudent.mockReturnValue(new Promise(() => {}))
  render(<AdminStudentDetail />)
  await waitFor(() => expect(screen.getByText('common.loading')).toBeTruthy())
  expect(screen.queryByTestId('record-not-found')).toBeNull()
})

it('a FAILED DELETE still reports itself — the record loaded, so this is not a not-found', async () => {
  // ⚠ This page shares ONE `error` string between the load and the delete, which is why the
  // order of the two early returns had to change rather than one of them being deleted. If the
  // not-found state swallowed a delete failure, the officer would type `delete`, press the
  // button, and watch the whole record be replaced by "we could not find that".
  mockApi.getPartnerStudent.mockResolvedValue(STUDENT)
  mockApi.deleteStudent.mockRejectedValue(new Error('Refused by the server'))
  render(<AdminStudentDetail />)
  // By role: the name is drawn twice (the heading and the Full name row), so a bare text query
  // would report "multiple elements" rather than a loaded record.
  await screen.findByRole('heading', { name: 'Test Student 07' })
  fireEvent.change(screen.getByPlaceholderText('admin.typeDeleteConfirm'),
                   { target: { value: 'delete' } })
  fireEvent.click(screen.getByRole('button', { name: 'admin.deleteStudent' }))
  await waitFor(() => expect(screen.getByText('Refused by the server')).toBeTruthy())
  expect(screen.queryByTestId('record-not-found')).toBeNull()
})
