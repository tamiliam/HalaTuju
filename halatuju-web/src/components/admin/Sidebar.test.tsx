/**
 * @jest-environment jsdom
 *
 * The rail's three states (N4). `navigation.test.ts` proves WHICH items a role gets; this
 * proves what the rail does with them at 48px versus 216px.
 *
 * What it cannot prove: whether the open/close feels right, or whether the chip lands where
 * your eye is. That is the browser pass, and it is still owed.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'

import { Sidebar } from './Sidebar'
import { NO_PROBES, visibleNav, type AdminRoleName } from '@/lib/navigation'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    // Echo the key, with any interpolated values appended — the real messages live in
    // en.json and are checked by `check-i18n`, so what matters here is that the chip is
    // built from the DESTINATION'S label rather than a hardcoded string.
    t: (k: string, p?: Record<string, string>) => (p ? `${k}:${Object.values(p).join(',')}` : k),
  }),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) =>
    <a href={href} {...rest}>{children}</a>,
}))

const groupsFor = (role: AdminRoleName) => visibleNav({ role, probes: NO_PROBES })

const renderRail = (role: AdminRoleName = 'org_admin', props = {}) => {
  render(
    <Sidebar
      groups={groupsFor(role)}
      activeId="applications"
      badgeCounts={{ pendingSponsors: 3 }}
      orgName="BrightPath"
      {...props}
    />,
  )
  return screen.getByRole('navigation', { name: 'admin.shell.primaryNav' })
}

describe('the rail opens and closes', () => {
  it('rests at 48px and opens to 216px on hover', () => {
    const nav = renderRail()
    expect(nav.style.width).toBe('48px')
    expect(nav.getAttribute('data-open')).toBe('no')

    fireEvent.mouseEnter(nav)
    expect(nav.style.width).toBe('216px')
    expect(nav.getAttribute('data-open')).toBe('yes')

    fireEvent.mouseLeave(nav)
    expect(nav.style.width).toBe('48px')
  })

  it('opens on keyboard focus, and stays open while focus moves BETWEEN rows', () => {
    const nav = renderRail()
    const links = within(nav).getAllByRole('link')

    fireEvent.focus(nav)
    expect(nav.getAttribute('data-open')).toBe('yes')

    // Tabbing from one row to the next: relatedTarget is still inside the rail.
    fireEvent.blur(nav, { relatedTarget: links[1] })
    expect(nav.getAttribute('data-open')).toBe('yes')

    // Leaving the rail entirely closes it.
    fireEvent.blur(nav, { relatedTarget: document.body })
    expect(nav.getAttribute('data-open')).toBe('no')
  })

  it('stays open when pinned, with no hover involved', () => {
    const nav = renderRail('org_admin', { pinned: true })
    expect(nav.style.width).toBe('216px')
    fireEvent.mouseLeave(nav)
    expect(nav.style.width).toBe('216px')
  })
})

describe('what survives the collapse', () => {
  it('keeps every label in the DOM so it can FADE rather than pop', () => {
    const nav = renderRail()
    // Present while collapsed...
    const label = within(nav).getByText('admin.nav.invitations')
    expect(label.className).toContain('opacity-0')
    // ...and revealed, not mounted, on open.
    fireEvent.mouseEnter(nav)
    expect(within(nav).getByText('admin.nav.invitations').className).toContain('opacity-100')
  })

  it('keeps the group heading readable to a screen reader at both widths', () => {
    const nav = renderRail()
    expect(within(nav).getByText('BrightPath')).toBeTruthy()
    fireEvent.mouseEnter(nav)
    expect(within(nav).getByText('BrightPath')).toBeTruthy()
  })

  it('shows a waiting count as a dot when collapsed and a number when open', () => {
    const nav = renderRail()
    const sponsors = within(nav).getByText('admin.sponsors.nav').closest('a') as HTMLElement

    expect(sponsors.querySelector('[data-badge="dot"]')).toBeTruthy()
    expect(within(sponsors).getByText('3').className).toContain('opacity-0')

    fireEvent.mouseEnter(nav)
    const openSponsors = within(nav).getByText('admin.sponsors.nav').closest('a') as HTMLElement
    expect(openSponsors.querySelector('[data-badge="dot"]')).toBeNull()
    expect(within(openSponsors).getByText('3').className).toContain('opacity-100')
  })

  it('never renders a badge for a count of zero', () => {
    const nav = renderRail('org_admin', { badgeCounts: { pendingSponsors: 0 } })
    const sponsors = within(nav).getByText('admin.sponsors.nav').closest('a') as HTMLElement
    expect(within(sponsors).queryByText('0')).toBeNull()
  })
})

describe('the Go-to chip', () => {
  it('names the destination and shows its chord', () => {
    const nav = renderRail()
    const staff = within(nav).getByText('admin.nav.invitations').closest('a') as HTMLElement
    const chip = within(staff).getByText(/admin.shell.goTo/)
    expect(chip.textContent).toContain('admin.nav.invitations')
    expect(within(chip).getByText('T')).toBeTruthy()
    expect(within(chip).getByText('g')).toBeTruthy()
  })

  it('drops the chord where nothing is listening for it (the mobile drawer)', () => {
    const nav = renderRail('org_admin', { chords: false, pinned: true })
    const staff = within(nav).getByText('admin.nav.invitations').closest('a') as HTMLElement
    expect(within(staff).getByText(/admin.shell.goTo/).querySelector('kbd')).toBeNull()
  })

  it('is hidden from assistive tech — the link already carries its own name', () => {
    const nav = renderRail()
    const staff = within(nav).getByText('admin.nav.invitations').closest('a') as HTMLElement
    expect(within(staff).getByText(/admin.shell.goTo/).getAttribute('aria-hidden')).toBe('true')
  })

  it('offers no chip on a reserved slot', () => {
    const nav = renderRail('org_admin')
    const fund = within(nav).getByText('admin.nav.fund').closest('[aria-disabled]') as HTMLElement
    expect(within(fund).queryByText(/admin.shell.goTo/)).toBeNull()
  })
})

describe('what the rail refuses to do', () => {
  it('marks exactly one row as the current page', () => {
    const nav = renderRail()
    const current = within(nav).getAllByRole('link')
      .filter((a) => a.getAttribute('aria-current') === 'page')
    expect(current).toHaveLength(1)
    expect(current[0].getAttribute('href')).toBe('/admin/scholarship')
  })

  it('still refuses to render the utility scope — that lives in the account menu', () => {
    const nav = renderRail('super')
    expect(within(nav).queryByText('admin.nav.group.utility')).toBeNull()
  })
})
