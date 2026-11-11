/**
 * @jest-environment jsdom
 *
 * TD-341: the dashboard banner reads the same rule as /scholarship/application (`applicationScreen`),
 * not `applications[0]`: one live application is the one it speaks about, several say nothing.
 */
import { render, screen, waitFor } from '@testing-library/react'
import ScholarshipBanner from './ScholarshipBanner'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ status: 'ready', token: 'tok' }) }))
const mockGet = jest.fn()
jest.mock('@/lib/api', () => ({ getMyScholarshipApplications: (...a: unknown[]) => mockGet(...a) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }))

const app = (status: string) => ({ id: Math.random(), status, has_file: false })

it('one shortlisted application: the banner shows', async () => {
  mockGet.mockResolvedValue({ applications: [app('shortlisted')] })
  render(<ScholarshipBanner />)
  expect(await screen.findByText('scholarship.banner.shortlistedTitle')).toBeTruthy()
})

it('a shortlisted one first in the list but two live: says nothing (not whichever sorts first)', async () => {
  mockGet.mockResolvedValue({ applications: [app('shortlisted'), app('profile_complete')] })
  const { container } = render(<ScholarshipBanner />)
  await waitFor(() => expect(mockGet).toHaveBeenCalled())
  await new Promise((r) => setTimeout(r, 0))
  expect(container.innerHTML).toBe('')
})

it('a finished application listed first beside a shortlisted one: speaks about the shortlisted one', async () => {
  mockGet.mockResolvedValue({ applications: [app('rejected'), app('shortlisted')] })
  render(<ScholarshipBanner />)
  expect(await screen.findByText('scholarship.banner.shortlistedTitle')).toBeTruthy()
})
