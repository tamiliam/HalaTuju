/**
 * An address bar for "the URL carries the gift" tests (TD-296, 2026-09-28).
 *
 * The router here MOVES jsdom's real address bar: `push` adds a history entry, `replace` rewrites
 * the current one. That is what lets a test assert the thing the person would notice — what the
 * address bar says, and whether Back has grown a gift-switcher (`history.length`) — rather than
 * only which mock was called.
 *
 * Use it from a `jest.mock` factory, which may not close over imports:
 *   jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
 * and import `urlRouter` / `openAt` / `address` normally — the registry hands both the same module.
 */
import { fireEvent, screen } from '@testing-library/react'

export const urlRouter = {
  push: jest.fn((href: string) => { window.history.pushState({}, '', href) }),
  replace: jest.fn((href: string) => { window.history.replaceState({}, '', href) }),
}

export const navigationMock = { useRouter: () => urlRouter }

/** Arrive at `url` as a fresh load would: the address bar says it, and no entry is added. */
export function openAt(url: string): void {
  window.history.replaceState({}, '', url)
}

/** What the address bar says now, path and query. */
export const address = (): string => window.location.pathname + window.location.search

/** Switch gift the way a person does: open the crumb's menu (`GiftScope`'s crumb) and pick one. */
export function switchCrumbTo(giftName: string): void {
  fireEvent.click(screen.getByRole('button', { name: 'admin.shell.switchProgramme' }))
  fireEvent.click(screen.getByRole('menuitem', { name: new RegExp(giftName) }))
}

/** Open the crumb's menu and say whether it offers "All gifts" (TD-302). Leaves the menu open. */
export function crumbOffersAll(): boolean {
  fireEvent.click(screen.getByRole('button', { name: 'admin.shell.switchProgramme' }))
  return screen.queryByRole('menuitem', { name: 'admin.shell.allGifts' }) !== null
}

/** Choose "All gifts" from the crumb's menu, the way a person does. */
export function switchCrumbToAll(): void {
  fireEvent.click(screen.getByRole('button', { name: 'admin.shell.switchProgramme' }))
  fireEvent.click(screen.getByRole('menuitem', { name: 'admin.shell.allGifts' }))
}

/** A promise the test resolves by hand, for replies that must arrive in a chosen order. */
export function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}
