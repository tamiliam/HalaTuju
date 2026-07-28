/**
 * @jest-environment jsdom
 *
 * The breadcrumb switchers (nav/IA N3a).
 *
 * The rule worth pinning is the one a future sprint will be tempted to "simplify": with a single
 * option the crumb renders as PLAIN TEXT, not a dropdown containing one entry. A chevron that
 * opens a menu of one is a promise the data does not keep — and it is the state production is in
 * today, so getting it wrong would be visible immediately and to everyone.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import { ScopeSwitcher } from './ScopeSwitcher'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

const ORG_A = { id: 1, code: 'tenant-a', name: 'BrightPath' }
const ORG_B = { id: 2, code: 'tenant-b', name: 'Inspire' }
const PROG_A = { id: 1, code: 'a-bursary', name: 'BrightPath Bursary' }
const PROG_B = { id: 2, code: 'b-bursary', name: 'Inspire Bursary' }

const renderSwitcher = (props = {}) => {
  const onSelectOrg = jest.fn()
  const onSelectProgramme = jest.fn()
  render(
    <ScopeSwitcher
      organisations={[ORG_A]}
      programmes={[PROG_A]}
      selectedOrg="tenant-a"
      selectedProgramme="a-bursary"
      onSelectOrg={onSelectOrg}
      onSelectProgramme={onSelectProgramme}
      scope="programme"
      {...props}
    />,
  )
  return { onSelectOrg, onSelectProgramme }
}

describe('with one of each — production today', () => {
  it('shows both names', () => {
    renderSwitcher()
    expect(screen.getByText('BrightPath')).toBeTruthy()
    expect(screen.getByText('BrightPath Bursary')).toBeTruthy()
  })

  it('offers NO menu — a dropdown of one is a promise the data does not keep', () => {
    renderSwitcher()
    expect(screen.queryByRole('button', { name: 'admin.shell.switchOrg' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'admin.shell.switchProgramme' })).toBeNull()
  })
})

describe('with two organisations', () => {
  it('becomes a real switcher', () => {
    renderSwitcher({ organisations: [ORG_A, ORG_B] })
    expect(screen.getByRole('button', { name: 'admin.shell.switchOrg' })).toBeTruthy()
  })

  it('reports the chosen code and does not decide anything itself', () => {
    const { onSelectOrg } = renderSwitcher({ organisations: [ORG_A, ORG_B] })
    fireEvent.click(screen.getByRole('button', { name: 'admin.shell.switchOrg' }))
    fireEvent.click(screen.getByText('Inspire'))
    expect(onSelectOrg).toHaveBeenCalledWith('tenant-b')
  })

  it('leaves the programme crumb as text when there is still only one', () => {
    renderSwitcher({ organisations: [ORG_A, ORG_B] })
    expect(screen.queryByRole('button', { name: 'admin.shell.switchProgramme' })).toBeNull()
  })
})

describe('with two programmes', () => {
  it('switches programme independently of organisation', () => {
    const { onSelectProgramme } = renderSwitcher({ programmes: [PROG_A, PROG_B] })
    fireEvent.click(screen.getByRole('button', { name: 'admin.shell.switchProgramme' }))
    fireEvent.click(screen.getByText('Inspire Bursary'))
    expect(onSelectProgramme).toHaveBeenCalledWith('b-bursary')
  })
})

describe('degenerate scopes', () => {
  it('renders nothing at all when the caller has no scope — a partner, or no organisation', () => {
    const { container } = render(
      <ScopeSwitcher
        organisations={[]} programmes={[]}
        selectedOrg="" selectedProgramme=""
        onSelectOrg={jest.fn()} onSelectProgramme={jest.fn()}
      />,
    )
    expect(container.textContent).toBe('')
  })

  it('falls back to the first option when the selection names something absent', () => {
    // e.g. a stored preference for an organisation that has since been deactivated.
    renderSwitcher({ selectedOrg: 'gone', selectedProgramme: 'gone' })
    expect(screen.getByText('BrightPath')).toBeTruthy()
    expect(screen.getByText('BrightPath Bursary')).toBeTruthy()
  })
})

// ── The breadcrumb says WHERE YOU ARE (owner, 2026-07-28) ────────────────────
//
// Not "what exists". A platform page is outside any organisation. The scope comes from the route
// registry — the same NavItem.scope that groups the sidebar — so the breadcrumb and the sidebar
// can never disagree about which level a page belongs to.
describe('breadcrumb depth follows the page scope', () => {
  const at = (scope?: string) => {
    const { container } = render(
      <ScopeSwitcher
        organisations={[ORG_A]} programmes={[PROG_A]}
        selectedOrg="tenant-a" selectedProgramme="a-bursary"
        onSelectOrg={jest.fn()} onSelectProgramme={jest.fn()}
        scope={scope as never}
      />,
    )
    return container.textContent ?? ''
  }

  it('a PLATFORM page shows neither — you are outside any organisation', () => {
    const text = at('platform')
    expect(text).not.toContain('BrightPath')
    expect(text).not.toContain('BrightPath Bursary')
  })

  it('an ORGANISATION page shows the organisation, not the programme', () => {
    const text = at('organisation')
    expect(text).toContain('BrightPath')
    expect(text).not.toContain('BrightPath Bursary')
  })

  it('a PROGRAMME page shows both', () => {
    const text = at('programme')
    expect(text).toContain('BrightPath')
    expect(text).toContain('BrightPath Bursary')
  })

  it('a UTILITY page shows neither — Profile and Guide belong to the person, not a tenant', () => {
    expect(at('utility')).not.toContain('BrightPath')
  })

  it('an unknown route shows neither rather than guessing a scope', () => {
    expect(at(undefined)).not.toContain('BrightPath')
  })
})
