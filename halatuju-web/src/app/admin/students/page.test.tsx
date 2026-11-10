/**
 * @jest-environment jsdom
 *
 * The students list reads once per page / filter / token (audit A3.15).
 *
 * Its load effect words a failure with `t`, which changes identity on a language switch. It used to
 * carry a lint suppression for that; it now reads the latest `t` through a ref. Pinned: a new `t`
 * does not read the list again, and a read that fails after the switch is worded with the NEW `t`.
 */
import { render, screen, waitFor } from '@testing-library/react'
import AdminStudentList from './page'
import * as api from '@/lib/admin-api'

let tVariant: 'one' | 'two' = 'one'
jest.mock('@/lib/i18n', () => ({
  useT: () => {
    const v = tVariant
    return { t: (k: string) => `${v}:${k}` }
  },
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', is_super_admin: true } }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ replace: jest.fn(), push: jest.fn() }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}))
jest.mock('@/lib/admin-api', () => ({
  ...jest.requireActual('@/lib/admin-api'),
  getPartnerStudents: jest.fn(),
  getExportUrl: jest.fn(() => '#'),
}))
const mockGet = api.getPartnerStudents as jest.Mock

beforeEach(() => { jest.clearAllMocks(); tVariant = 'one' })

describe('the list does not re-read when `t` changes identity (A3.15)', () => {
  it('reads once, and stays at one after more renders with a new `t`', async () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    const view = render(<AdminStudentList />)
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1))
    tVariant = 'two'
    view.rerender(<AdminStudentList />)
    tVariant = 'one'
    view.rerender(<AdminStudentList />)
    expect(mockGet).toHaveBeenCalledTimes(1)
  })

  it('words a failed read with the latest `t`', async () => {
    let fail: (e: Error) => void = () => {}
    mockGet.mockReturnValue(new Promise((_, reject) => { fail = reject }))
    const view = render(<AdminStudentList />)
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1))
    tVariant = 'two'
    view.rerender(<AdminStudentList />)
    fail(new Error('boom'))
    await waitFor(() => expect(screen.getByText('two:admin.loadStudentsFailed')).toBeTruthy())
    expect(mockGet).toHaveBeenCalledTimes(1)
  })
})
