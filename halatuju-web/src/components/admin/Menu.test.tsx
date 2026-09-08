/**
 * @jest-environment jsdom
 *
 * The Menu primitive carries the help, notification and account menus in the topbar, the gift
 * card's menu and the intake round's state badge, so its keyboard, dismissal and PLACEMENT
 * behaviour is worth pinning once. These are exactly the behaviours that a pure test cannot reach
 * and that a user notices immediately when they are missing.
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

  // ⚠ THE OWNER SAW THIS ONE (2026-09-08): *"Clicking the close opens something, but it is
  // hidden."* The panel was `absolute` inside the trigger's own box, so an ancestor with
  // `overflow-hidden` — the rounded wrapper round the intake-round table — sliced it off. It
  // opened, it rendered, and only a sliver of it reached the screen.
  //
  // The panel is a PORTAL on document.body now, which is the only placement no ancestor can clip.
  // Pinning it here rather than on the one table is deliberate: the trap was in the primitive.
  it('escapes a clipping ancestor — the panel is a portal on the body', () => {
    render(
      <div style={{ overflow: 'hidden' }} data-testid="clipper">
        <Menu label="Account" trigger={<span>avatar</span>}>
          <MenuItem onClick={() => {}}>Profile</MenuItem>
        </Menu>
      </div>,
    )
    fireEvent.click(trigger())
    const panel = screen.getByRole('menu')
    expect(panel.parentElement).toBe(document.body)
    expect(screen.getByTestId('clipper').contains(panel)).toBe(false)
  })

  // The portal put the panel outside the wrapper, and the click-outside guard watched only the
  // wrapper. Left alone, the mousedown on an item would close the menu BEFORE its click fired —
  // every menu item in the console would have become a no-op.
  it('still runs an item that is pressed, mousedown first', () => {
    const chosen = jest.fn()
    render(
      <Menu label="Account" trigger={<span>avatar</span>}>
        <MenuItem onClick={chosen}>Profile</MenuItem>
      </Menu>,
    )
    fireEvent.click(trigger())
    const item = screen.getByRole('menuitem')
    fireEvent.mouseDown(item)
    expect(screen.queryByRole('menu')).toBeTruthy()
    fireEvent.click(item)
    expect(chosen).toHaveBeenCalledTimes(1)
  })
})
