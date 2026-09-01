/**
 * @jest-environment jsdom
 *
 * Layer 1 A1 — a tenant's STORED colours actually reach the page, and follow the mode.
 *
 * The fence and the ramp maths are pure and pinned in `branding.test.ts`. What is tested HERE is
 * the half a pure test cannot see, and it is the half that has bitten before:
 *
 *  - the override writes INLINE styles, which outrank `globals.css` INCLUDING its dark block — so
 *    without the mode watcher a tenant would sit in dark mode wearing the light ramp (the exact
 *    defect F3 raised, and unfixable from CSS because an inline style wins);
 *  - the watcher is a MutationObserver on one attribute, because `applyTheme` sets an attribute and
 *    deliberately fires no event — there is nothing else to subscribe to;
 *  - a STORED set must beat the derivation, or the freeze A1 exists for is not a freeze.
 *
 * `NEXT_PUBLIC_ORG_CODE` is read lazily by the provider precisely so these cases can each set a
 * different one. Re-importing under `jest.resetModules()` would hand the provider a second copy of
 * React, which has no hooks — so the env read moved into a function instead.
 */
import { act, render, waitFor } from '@testing-library/react'

import { BrandingProvider } from '@/lib/branding-context'

const LIGHT_500 = '162 28 175'
const DARK_50 = '24 24 46'
const LIGHT_50 = '250 244 251'

/** A stored set — the shape the endpoint serves. Deliberately NOT what `brandRamp` would produce
 *  for the same colour, so a test that passes proves the STORED values were used. */
const STORED = {
  light: { 'brand-50': '1 2 3', 'brand-500': LIGHT_500 },
  dark: { 'brand-50': '4 5 6', 'brand-500': LIGHT_500 },
}

function setMode(mode: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', mode)
}

function readVar(name: string) {
  return document.documentElement.style.getPropertyValue(name)
}

/** Mount the provider for one org code with one branding payload. */
async function mount(orgCode: string, payload: unknown) {
  process.env.NEXT_PUBLIC_ORG_CODE = orgCode
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => payload }) as never
  await act(async () => {
    render(<BrandingProvider>hello</BrandingProvider>)
  })
}

beforeEach(() => {
  document.documentElement.removeAttribute('style')
  setMode('light')
})

afterEach(() => {
  delete process.env.NEXT_PUBLIC_ORG_CODE
  jest.restoreAllMocks()
})

describe('a tenant with STORED colours', () => {
  it('paints the stored values, not a re-derivation', async () => {
    await mount('inspire', { brand_colour: '#a21caf', theme: STORED })
    await waitFor(() => expect(readVar('--brand-500')).toBe(LIGHT_500))
    // `brandRamp('#a21caf','light')[50]` is '250 244 251'. The stored set says '1 2 3'. If the
    // derivation had won, this would read the ramp value — which is the whole point of storing.
    expect(readVar('--brand-50')).toBe('1 2 3')
    expect(readVar('--brand-50')).not.toBe(LIGHT_50)
  })

  it('follows a mode change, because an inline style beats the dark block', async () => {
    await mount('inspire', { brand_colour: '#a21caf', theme: STORED })
    await waitFor(() => expect(readVar('--brand-50')).toBe('1 2 3'))
    await act(async () => setMode('dark'))
    await waitFor(() => expect(readVar('--brand-50')).toBe('4 5 6'))
    // The identity stop does not move. A mode may not change whose product you are looking at.
    expect(readVar('--brand-500')).toBe(LIGHT_500)
  })

  it('never paints a platform tone, even if the server sends one', async () => {
    await mount('inspire', {
      brand_colour: '#a21caf',
      theme: {
        light: { ...STORED.light, 'critical-500': '0 255 0' },
        dark: { ...STORED.dark, 'critical-500': '0 255 0' },
      },
    })
    await waitFor(() => expect(readVar('--brand-500')).toBe(LIGHT_500))
    expect(readVar('--critical-500')).toBe('')
  })
})

describe('a tenant with NO stored colours', () => {
  it('still derives from the colour column, exactly as before A1', async () => {
    await mount('inspire', { brand_colour: '#a21caf', theme: null })
    await waitFor(() => expect(readVar('--brand-500')).toBe(LIGHT_500))
    expect(readVar('--brand-50')).toBe(LIGHT_50) // the derived value, not a stored one
  })

  it('derives the DARK ramp when the mode flips', async () => {
    await mount('inspire', { brand_colour: '#a21caf', theme: null })
    await waitFor(() => expect(readVar('--brand-50')).toBe(LIGHT_50))
    await act(async () => setMode('dark'))
    await waitFor(() => expect(readVar('--brand-50')).toBe(DARK_50))
  })
})

describe('the platform', () => {
  it('never fetches and never writes an inline colour', async () => {
    await mount('brightpath', { brand_colour: '#a21caf', theme: STORED })
    expect(global.fetch).not.toHaveBeenCalled()
    expect(readVar('--brand-500')).toBe('')
  })

  it('a failed fetch leaves the stylesheet alone rather than half a theme', async () => {
    process.env.NEXT_PUBLIC_ORG_CODE = 'inspire'
    global.fetch = jest.fn().mockRejectedValue(new Error('offline')) as never
    await act(async () => {
      render(<BrandingProvider>hello</BrandingProvider>)
    })
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(readVar('--brand-500')).toBe('')
  })
})
