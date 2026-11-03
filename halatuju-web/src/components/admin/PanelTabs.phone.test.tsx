/**
 * @jest-environment jsdom
 *
 * Mobile M7a (owner, 2026-11-03): on a phone (below md BY WIDTH) up to four tabs stay 44 px chips; MORE become one
 * chooser above the content (the Guide's pattern), replacing the bar rather than sitting beside a hidden copy.
 * From md — and wherever the width is unknown (the server, a browser without matchMedia) — the bar is unchanged.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import PanelTabs, { PHONE_CHIPS_MAX, type PanelTab } from './PanelTabs'
import { PHONE_WIDTH_QUERY } from '@/lib/phoneWidth'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

const tabs = (n: number): PanelTab<string>[] =>
  Array.from({ length: n }, (_, i) => ({ key: `k${i}`, labelKey: `tab.${i}`, count: i, disabled: i === n - 1 && n > 2 }))

/** A window of the given width class: matchMedia answers the phone query only. */
function widthIs(phone: boolean | null) {
  if (phone === null) { delete (window as { matchMedia?: unknown }).matchMedia; return }
  window.matchMedia = ((q: string) => ({
    matches: q === PHONE_WIDTH_QUERY && phone, media: q, addEventListener: () => {}, removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}
afterEach(() => widthIs(null))

it('the line is four', () => expect(PHONE_CHIPS_MAX).toBe(4))

it('a phone with more than four tabs gets ONE chooser and no tab bar; it selects by the same keys', async () => {
  widthIs(true)
  const onSelect = jest.fn()
  render(<PanelTabs tabs={tabs(5)} active="k0" onSelect={onSelect} ariaLabelKey="aria" />)
  await act(async () => {})
  const chooser = document.querySelector('[data-panel-chooser]') as HTMLSelectElement
  expect(chooser).not.toBeNull()
  expect(chooser.className.split(' ')).toContain('min-h-11')
  expect(screen.queryByRole('tablist')).toBeNull()
  expect(Array.from(chooser.options).map((o) => o.value)).toEqual(['k0', 'k1', 'k2', 'k3', 'k4'])
  expect(chooser.options[4].disabled).toBe(true)   // a "soon" tab stays unpickable, as in the bar
  expect(chooser.options[2].textContent).toBe('tab.2 (2)')
  fireEvent.change(chooser, { target: { value: 'k3' } })
  expect(onSelect).toHaveBeenCalledWith('k3')
})

it('a phone with four tabs keeps the chips, each 44 px tall', async () => {
  widthIs(true)
  render(<PanelTabs tabs={tabs(4)} active="k0" onSelect={jest.fn()} ariaLabelKey="aria" />)
  await act(async () => {})
  expect(document.querySelector('[data-panel-chooser]')).toBeNull()
  for (const tab of screen.getAllByRole('tab')) expect(tab.className.split(' ')).toContain('max-md:min-h-11')
})

it('from md, and with no matchMedia, nine tabs are the bar they always were', async () => {
  for (const w of [false, null] as const) {
    widthIs(w)
    const { unmount } = render(<PanelTabs tabs={tabs(9)} active="k0" onSelect={jest.fn()} ariaLabelKey="aria" />)
    await act(async () => {})
    expect(document.querySelector('[data-panel-chooser]')).toBeNull()
    expect(screen.getAllByRole('tab')).toHaveLength(9)
    unmount()
  }
})
