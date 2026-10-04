/**
 * @jest-environment jsdom
 *
 * THE CONSOLE'S 404 SENDS EVERY ROLE SOMEWHERE IT CAN ACTUALLY GO.
 *
 * ⚠ **`lib/navigation` AND `lib/adminLanding` ARE DELIBERATELY NOT MOCKED.** The claim is that
 * the destination is DERIVED from the route registry, and a mocked `adminLanding` would prove
 * only that this page calls a function. docs/decisions.md 2026-09-08 and docs/lessons.md both
 * record what a hard-coded landing cost: four roles bounced off a page they cannot see, and
 * `finance` sent to one it can only ever be refused. So the href is compared against the real
 * `adminLanding(role)` for every role, and `finance` is asserted again on its own.
 */
import { render, screen } from '@testing-library/react'

import AdminNotFound from './not-found'
import { adminLanding } from '@/lib/adminLanding'
import { canAccess, effectiveRole } from '@/lib/navigation'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

let viewerRole: { role: string; is_super_admin?: boolean } | null = { role: 'admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))

const wayOut = () => screen.getByRole('link', { name: 'errors.backToConsole' })

const ROLES = ['super', 'org_admin', 'admin', 'finance', 'reviewer', 'qc'] as const

describe('the way out', () => {
  it.each(ROLES)('sends %s to the landing the registry derives for them', (role) => {
    viewerRole = { role }
    render(<AdminNotFound />)
    const href = wayOut().getAttribute('href')
    expect(href).toBe(adminLanding({ role }))
    // …and it is a console address, never the public site, which is the defect being fixed:
    // the root 404's button goes to `/`, so a signed-in officer was dumped out of the console
    // although their session had not ended.
    expect(href?.startsWith('/admin')).toBe(true)
  })

  it('⚠ never sends FINANCE to a page it can only be refused on', () => {
    // The named casualty of the hard-coded landing. `/admin` is the PLATFORM dashboard; finance
    // cannot see it, so a literal here would 403 the one role least able to work around it.
    viewerRole = { role: 'finance' }
    render(<AdminNotFound />)
    const href = wayOut().getAttribute('href') as string
    expect(href).not.toBe('/admin')
    expect(canAccess(href, effectiveRole({ role: 'finance' }))).toBe(true)
  })

  it('every role is sent somewhere its own role may open', () => {
    for (const role of ROLES) {
      viewerRole = { role }
      const view = render(<AdminNotFound />)
      const href = wayOut().getAttribute('href') as string
      expect({ role, allowed: canAccess(href, effectiveRole({ role })) })
        .toEqual({ role, allowed: true })
      view.unmount()
    }
  })

  it('still offers a way out when the role call has not answered yet', () => {
    // `role` is null only while /admin/role/ is in flight; the layout holds its own loading
    // state in front of this page, so it is a belt. It must not crash, and it must not invent a
    // literal — the least-privileged reading is the safe direction to be wrong.
    viewerRole = null
    render(<AdminNotFound />)
    expect(wayOut().getAttribute('href')).toBe(adminLanding({}))
  })
})

describe('what it says', () => {
  it('names the 404 and the page copy, not a record', () => {
    viewerRole = { role: 'admin' }
    render(<AdminNotFound />)
    expect(screen.getByTestId('admin-not-found')).toBeTruthy()
    expect(screen.getByText('404')).toBeTruthy()
    expect(screen.getByText('errors.pageNotFound')).toBeTruthy()
    expect(screen.getByText('errors.pageNotFoundDesc')).toBeTruthy()
  })
})
