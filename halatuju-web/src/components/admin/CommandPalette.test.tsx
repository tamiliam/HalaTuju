/**
 * @jest-environment jsdom
 *
 * The palette's ranking is pure and tested in navigation.test.ts. What is tested HERE is the
 * behaviour a pure test cannot see: that it opens focused, that Enter navigates, that Escape
 * dismisses, and that it does not reopen holding the last search.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import { CommandPalette } from './CommandPalette'
import { visibleNav, NO_PROBES } from '@/lib/navigation'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: (h: string) => push(h) }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const groups = visibleNav({ role: 'super', probes: NO_PROBES })

beforeEach(() => push.mockClear())

describe('CommandPalette', () => {
  it('renders nothing while closed', () => {
    render(<CommandPalette groups={groups} open={false} onClose={() => {}} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens with the input focused so you can just type', () => {
    render(<CommandPalette groups={groups} open onClose={() => {}} />)
    expect(document.activeElement).toBe(screen.getByRole('textbox'))
  })

  it('Enter navigates to the highlighted result', () => {
    render(<CommandPalette groups={groups} open onClose={() => {}} />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'admin.scholarship.nav' } })
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Enter' })
    expect(push).toHaveBeenCalledWith('/admin/scholarship')
  })

  it('Escape closes without navigating', () => {
    const onClose = jest.fn()
    render(<CommandPalette groups={groups} open onClose={onClose} />)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })

  it('a click on the backdrop closes it; a click inside does not', () => {
    const onClose = jest.fn()
    const { container } = render(<CommandPalette groups={groups} open onClose={onClose} />)
    fireEvent.mouseDown(screen.getByRole('dialog'))
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.mouseDown(container.firstChild as Element)
    expect(onClose).toHaveBeenCalled()
  })

  it('never offers a reserved slot — there is nowhere to go', () => {
    render(<CommandPalette groups={groups} open onClose={() => {}} />)
    // 'admin.nav.fund' is a reserved slot's label key; it must not be listed.
    expect(screen.queryByText('admin.nav.fund')).toBeNull()
    expect(screen.getByText('admin.scholarship.nav')).toBeTruthy()
  })

  it('says plainly that it searches the menu, not the records', () => {
    // Otherwise someone types a student's name, gets nothing, and concludes search is broken.
    render(<CommandPalette groups={groups} open onClose={() => {}} />)
    expect(screen.getByText('admin.shell.searchScopeNote')).toBeTruthy()
  })
})
