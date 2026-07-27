/**
 * @jest-environment jsdom
 *
 * The Menu primitive is used three times (help, notifications, account), so its keyboard and
 * dismissal behaviour is worth pinning once. These are exactly the behaviours that a pure test
 * cannot reach and that a user notices immediately when they are missing.
 *
 * NB the frontend jest config runs in `node` by default; this file opts into jsdom with the
 * docblock above, the same way AwardComprehensionQuiz.test.tsx does.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import { Menu, MenuItem } from './Menu'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const setup = () => render(
  <Menu label="Account" trigger={<span>avatar</span>}>
    <MenuItem onClick={() => {}}>Profile</MenuItem>
    <MenuItem onClick={() => {}}>Settings</MenuItem>
    <MenuItem onClick={() => {}}>Sign out</MenuItem>
  </Menu>,
)

const trigger = () => screen.getByRole('button', { name: 'Account' })

describe('Menu', () => {
  it('is closed until asked, and says so to a screen reader', () => {
    setup()
    expect(screen.queryByRole('menu')).toBeNull()
    expect(trigger().getAttribute('aria-expanded')).toBe('false')
  })

  it('opens on click and closes again on a second click', () => {
    setup()
    fireEvent.click(trigger())
    expect(screen.getByRole('menu')).toBeTruthy()
    expect(trigger().getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(trigger())
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('closes on a click outside — not only on the trigger', () => {
    setup()
    fireEvent.click(trigger())
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('closes on Escape AND hands focus back to the trigger', () => {
    // A keyboard user who dismisses a menu must not be dumped at the top of the document.
    setup()
    fireEvent.click(trigger())
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(trigger())
  })

  it('opens with ArrowDown from the trigger and lands on the first item', async () => {
    setup()
    fireEvent.keyDown(trigger(), { key: 'ArrowDown' })
    const items = await screen.findAllByRole('menuitem')
    // The panel focuses asynchronously (it must exist first), so give the timeout a turn.
    await new Promise((r) => setTimeout(r, 0))
    expect(document.activeElement).toBe(items[0])
  })

  it('wraps with the arrow keys rather than dead-ending', async () => {
    setup()
    fireEvent.click(trigger())
    const menu = screen.getByRole('menu')
    const items = screen.getAllByRole('menuitem')
    items[0].focus()
    fireEvent.keyDown(menu, { key: 'ArrowUp' })
    expect(document.activeElement).toBe(items[items.length - 1])
    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(items[0])
  })

  it('closes after an item is chosen', () => {
    setup()
    fireEvent.click(trigger())
    fireEvent.click(screen.getAllByRole('menuitem')[0])
    expect(screen.queryByRole('menu')).toBeNull()
  })
})
