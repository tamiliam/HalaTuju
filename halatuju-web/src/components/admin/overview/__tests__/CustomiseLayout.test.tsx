/**
 * @jest-environment jsdom
 *
 * The Overview's customise editor — and what this file guards is the SHAPE OF THE SAVE.
 *
 * ⚠⚠ **THE FULL ORDERED LIST GOES OUT, NEVER A DIFF.** The server validates `sections` as a
 * permutation of the five customisable widgets, and the order is half of what the screen records;
 * a save that posted only the row somebody touched would pass its own unit test and lose every
 * arrangement in production. That is asserted on the CALL, from the outside.
 *
 * ⚠ **SAVE IS ASLEEP UNTIL SOMETHING ACTUALLY DIFFERS** (the platform's nothing-to-save standard),
 * and the reason is one hover away rather than a sentence in the bar.
 *
 * ⚠ No jest-dom matchers exist in this project: `toBeNull` / `not.toBeNull` / `toEqual`.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import CustomiseLayout from '../CustomiseLayout'
import * as api from '@/lib/admin-api'
import { SECTION_KEYS, type LayoutRow } from '@/lib/overviewLayout'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    (vars ? `${k}|${Object.values(vars).join(',')}` : k), locale: 'en' }),
}))

jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const NAME = (key: string) => `admin.programmeOverview.sections.${key}`

const LAYOUT = (): LayoutRow[] => SECTION_KEYS.map((key) => ({ key, on: true }))

const STORED = {
  organisation: { code: 'mynadi', name: 'MyNadi' },
  sections: LAYOUT(),
  updated_by_email: 'admin@example.com',
  updated_at: '2026-09-18T10:00:00+08:00',
}

let onSaved: jest.Mock
let onCancel: jest.Mock

beforeEach(() => {
  jest.clearAllMocks()
  onSaved = jest.fn()
  onCancel = jest.fn()
  mockApi.saveOverviewLayout.mockResolvedValue(STORED)
})

const draw = (initial: LayoutRow[] = LAYOUT()) =>
  render(<CustomiseLayout initial={initial} onSaved={onSaved} onCancel={onCancel} />)

const saveButton = () => screen.getByTestId('save-layout') as HTMLButtonElement

describe('the cards', () => {
  it('gives every customisable widget a switch, named by the panel it controls', () => {
    draw()
    for (const key of SECTION_KEYS) {
      expect(screen.getByRole('switch', { name: NAME(key) })).not.toBeNull()
      expect(screen.queryByTestId(`customise-card-${key}`)).not.toBeNull()
    }
  })

  /* ⚠ `mine` and `qc` are a reviewer's and a checker's whole page, not a widget on somebody
   * else's — they are outside the catalogue and must not appear here at all. */
  it('offers no card for mine or qc', () => {
    draw()
    expect(screen.queryByTestId('customise-card-mine')).toBeNull()
    expect(screen.queryByTestId('customise-card-qc')).toBeNull()
  })

  /* ⚠ THE WHOLE CARD FADES, not just a badge — what a person scans is the block. */
  it('fades a hidden card and says it is hidden', () => {
    draw(LAYOUT().map((r) => (r.key === 'money' ? { ...r, on: false } : r)))
    const hidden = screen.getByTestId('customise-card-money')
    expect(hidden.getAttribute('class')).toContain('opacity-50')
    expect(hidden.textContent).toContain('admin.programmeOverview.customise.hidden')
    const shown = screen.getByTestId('customise-card-funnel')
    expect((shown.getAttribute('class') ?? '').indexOf('opacity-50')).toBe(-1)
    expect(shown.textContent).toContain('admin.programmeOverview.customise.visible')
  })
})

/* ⚠⚠ THE ARROWS ARE THE WHOLE REORDER (Sprint B) — there is no drag-and-drop, on purpose. What
 * this block guards is the part a page-level test cannot see: where the KEYBOARD ends up. */
describe('the arrows', () => {
  const up = (key: string) => screen.getByTestId(`move-up-${key}`) as HTMLButtonElement
  const down = (key: string) => screen.getByTestId(`move-down-${key}`) as HTMLButtonElement
  const order = () => Array.from(document.querySelectorAll('[data-testid^="customise-card-"]'))
    .map((card) => (card.getAttribute('data-testid') ?? '').replace('customise-card-', ''))

  /* ⚠ 44px SQUARE. An arrow is the smallest control on this screen and the likeliest to be used
   * with a thumb; below the platform minimum it is the one thing here a phone cannot hit. */
  it('is a 44px touch target', () => {
    draw()
    expect(up('money').getAttribute('class')).toContain('h-11')
    expect(up('money').getAttribute('class')).toContain('w-11')
    expect(down('money').getAttribute('class')).toContain('h-11')
  })

  it('moves a row up, through the pure helper', () => {
    draw()
    fireEvent.click(up('attention'))
    expect(order())
      .toEqual(['funnel', 'attention', 'money', 'applications_series', 'money_series'])
  })

  /* ⚠⚠ **THE MOVED ROW KEEPS THE KEYBOARD.** Pressing Up three times must move one panel three
   * places; if the focus is dropped after the first press the person is back at the top of the
   * page with no idea which row they were on. */
  it('leaves the keyboard on the button that moved', () => {
    draw()
    up('attention').focus()
    fireEvent.click(up('attention'))
    expect(document.activeElement).toBe(up('attention'))
  })

  /* ⚠ THE ONE CASE THAT BREAKS BY ITSELF: a row arriving at an end disables the very arrow that
   * was just pressed, and a browser blurs a disabled element to nothing. Focus lands on the arrow
   * still pointing back the way the row came. */
  it('hands focus to the other arrow when the row lands at an end', () => {
    draw()
    up('money').focus()
    fireEvent.click(up('money'))
    expect(order()[0]).toBe('money')
    expect(up('money').disabled).toBe(true)
    expect(document.activeElement).toBe(down('money'))
  })

  /* ⚠ ORDER COUNTS AS A CHANGE — `isDirty` already says so, and this proves the SCREEN asks it.
   * A Save that slept through a reorder would strand the only edit the person came to make. */
  it('wakes Save on a reorder alone, with no switch touched', () => {
    draw()
    expect(saveButton().disabled).toBe(true)
    fireEvent.click(down('funnel'))
    expect(saveButton().disabled).toBe(false)
    expect(saveButton().getAttribute('title')).toBeNull()
  })
})

describe('the save bar', () => {
  it('sleeps until a switch is flipped, with the reason on the button', () => {
    draw()
    expect(saveButton().disabled).toBe(true)
    expect(saveButton().getAttribute('title')).toBe('common.nothingToSave')
    fireEvent.click(screen.getByRole('switch', { name: NAME('attention') }))
    expect(saveButton().disabled).toBe(false)
    expect(saveButton().getAttribute('title')).toBeNull()
  })

  /* ⚠⚠ THE FULL ORDERED LIST. Five rows go out, in order, with only the flipped one changed. */
  it('posts every row in order and tells the page to reload', async () => {
    draw()
    fireEvent.click(screen.getByRole('switch', { name: NAME('money') }))
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveOverviewLayout).toHaveBeenCalled())
    expect(mockApi.saveOverviewLayout.mock.calls[0][0]).toEqual([
      { key: 'funnel', on: true },
      { key: 'money', on: false },
      { key: 'attention', on: true },
      { key: 'applications_series', on: true },
      { key: 'money_series', on: true },
    ])
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('discards without saving anything', () => {
    draw()
    fireEvent.click(screen.getByRole('switch', { name: NAME('funnel') }))
    fireEvent.click(screen.getByTestId('discard-layout'))
    expect(onCancel).toHaveBeenCalled()
    expect(mockApi.saveOverviewLayout).not.toHaveBeenCalled()
  })

  /* ⚠ EVERY OUTCOME HAS A LINE ON SCREEN (the #20 rule) — a refusal names the panel the server
   * objected to rather than restating the rule. */
  it('says which panel a refusal was about', async () => {
    const refused = Object.assign(new Error('bad_section'), {
      status: 400, body: { error: 'bad_section', code: 'bad_section', key: 'money' },
    })
    mockApi.saveOverviewLayout.mockRejectedValue(refused)
    draw()
    fireEvent.click(screen.getByRole('switch', { name: NAME('money') }))
    fireEvent.click(saveButton())
    const line = await screen.findByTestId('customise-outcome')
    await waitFor(() => expect(line.textContent)
      .toBe('admin.programmeOverview.customise.refused|admin.programmeOverview.sections.money'))
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('falls back to a generic line when the server says nothing useful', async () => {
    mockApi.saveOverviewLayout.mockRejectedValue(new Error('boom'))
    draw()
    fireEvent.click(screen.getByRole('switch', { name: NAME('money') }))
    fireEvent.click(saveButton())
    const line = await screen.findByTestId('customise-outcome')
    await waitFor(() =>
      expect(line.textContent).toBe('admin.programmeOverview.customise.error'))
  })
})

/* ⚠⚠ REQUEST #42 (2026-10-22): ON A GIFT, THE EDITOR ACTS ON THAT GIFT ONLY. The heading names the
 * gift, Save carries the gift's code, and "Use the organisation layout" appears only when the
 * layout on screen is the gift's own — on the all-gifts page there is no gift and no reset. */
describe('on a gift', () => {
  const GIFT = { code: 'b40-flagship', name: 'Flagship Bursary' }
  const K = 'admin.programmeOverview.customise'

  beforeEach(() => {
    mockApi.resetOverviewLayout.mockResolvedValue({ ...STORED, source: 'organisation' })
  })

  const drawGift = (source: 'gift' | 'organisation' | 'default') => render(
    <CustomiseLayout initial={LAYOUT()} gift={GIFT} source={source}
      onSaved={onSaved} onCancel={onCancel} />)

  it('names the gift in the heading and drops the whole-organisation hint', () => {
    drawGift('organisation')
    expect(screen.getByTestId('customise-title').textContent).toBe(`${K}.titleGift|Flagship Bursary`)
    expect(screen.getByTestId('customise-hint').textContent).toBe(`${K}.hintGift`)
    expect(screen.getByTestId('customise-source').textContent).toBe(`${K}.sourceOrganisation`)
  })

  it('saves for that gift only', async () => {
    drawGift('organisation')
    fireEvent.click(screen.getByRole('switch', { name: NAME('money') }))
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveOverviewLayout).toHaveBeenCalled())
    expect(mockApi.saveOverviewLayout.mock.calls[0][1]).toEqual({ programme: 'b40-flagship' })
  })

  it('hides "Use the organisation layout" when the gift has no layout of its own', () => {
    drawGift('organisation')
    expect(screen.queryByTestId('reset-layout')).toBeNull()
    cleanupAndDraw('default')
    expect(screen.queryByTestId('reset-layout')).toBeNull()
  })

  it('offers it on a gift layout, and the press deletes the gift layout and reloads', async () => {
    drawGift('gift')
    expect(screen.getByTestId('customise-source').textContent).toBe(`${K}.sourceGift`)
    const reset = screen.getByTestId('reset-layout')
    expect(reset.textContent).toBe(`${K}.useOrganisation`)
    fireEvent.click(reset)
    await waitFor(() => expect(mockApi.resetOverviewLayout).toHaveBeenCalled())
    expect(mockApi.resetOverviewLayout.mock.calls[0][0]).toBe('b40-flagship')
    expect(mockApi.saveOverviewLayout).not.toHaveBeenCalled()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('says so on screen when the reset fails', async () => {
    mockApi.resetOverviewLayout.mockRejectedValue(new Error('boom'))
    drawGift('gift')
    fireEvent.click(screen.getByTestId('reset-layout'))
    const line = await screen.findByTestId('customise-outcome')
    await waitFor(() => expect(line.textContent).toBe(`${K}.resetError`))
    expect(onSaved).not.toHaveBeenCalled()
  })

  function cleanupAndDraw(source: 'gift' | 'organisation' | 'default') {
    cleanup()
    drawGift(source)
  }
})

describe('on all gifts (no gift chosen)', () => {
  it('edits the organisation layout, says it is the default, and offers no reset', async () => {
    render(<CustomiseLayout initial={LAYOUT()} source="organisation"
      onSaved={onSaved} onCancel={onCancel} />)
    expect(screen.getByTestId('customise-title').textContent)
      .toBe('admin.programmeOverview.customise.title')
    expect(screen.getByTestId('customise-hint').textContent)
      .toBe('admin.programmeOverview.customise.hint')
    expect(screen.queryByTestId('customise-source')).toBeNull()
    expect(screen.queryByTestId('reset-layout')).toBeNull()
    fireEvent.click(screen.getByRole('switch', { name: NAME('money') }))
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveOverviewLayout).toHaveBeenCalled())
    expect(mockApi.saveOverviewLayout.mock.calls[0][1]).toEqual({ org: undefined })
  })
})
