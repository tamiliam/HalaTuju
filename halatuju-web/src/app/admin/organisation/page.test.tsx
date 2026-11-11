/**
 * @jest-environment jsdom
 *
 * T5c P5b: the old Organisation Overview and the Administration hub are redirects to the ONE Overview page,
 * in a single hop each. The count tiles that used to live here are the per-person pending cards now.
 */
import { render } from '@testing-library/react'
import OrganisationRedirect from './page'
import AdministrationRedirect from '../administration/page'
import { mayOpen } from '@/lib/pageGuard'
import { activeItem } from '@/lib/navigation'

const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ replace: mockReplace }) }))

beforeEach(() => mockReplace.mockClear())

describe('Overview redirects', () => {
  it('/admin/organisation goes to the Overview page', () => {
    render(<OrganisationRedirect />)
    expect(mockReplace).toHaveBeenCalledWith('/admin/organisation/programmes')
  })
  it('/admin/administration goes there in ONE hop (not via /admin/organisation)', () => {
    render(<AdministrationRedirect />)
    expect(mockReplace).toHaveBeenCalledTimes(1)
    expect(mockReplace).toHaveBeenCalledWith('/admin/organisation/programmes')
  })
})

describe('the folded row does not widen any other route', () => {
  it('the old paths light the Overview row, but its children keep their own rows', () => {
    expect(activeItem('/admin/organisation')?.id).toBe('programmes')
    expect(activeItem('/admin/administration')?.id).toBe('programmes')
    expect(activeItem('/admin/organisation/staff')?.id).toBe('staff')
    expect(activeItem('/admin/organisation/settings')?.id).toBe('orgSettings')
    expect(activeItem('/admin/organisation/team')?.id).toBe('reviewers')
  })
  it('a role that could not open Invitations / People / Settings still cannot', () => {
    for (const role of ['qc', 'reviewer', 'mentor']) {
      for (const path of ['/admin/organisation/staff', '/admin/organisation/team', '/admin/organisation/settings']) {
        expect(mayOpen(path, { role })).toBe(false)
      }
    }
    expect(mayOpen('/admin/organisation/settings', { role: 'finance' })).toBe(false)
  })
})
