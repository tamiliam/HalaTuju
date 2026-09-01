/**
 * @jest-environment jsdom
 *
 * "Colours" — rendered (Layer 1 A2).
 *
 * The maths is pure and pinned in `lib/__tests__/contrast.test.ts`. What is tested HERE is what a
 * pure test cannot see, and it is the whole point of the screen:
 *
 *  - **Save never wakes for a colour that cannot be read**, and the reason is on screen beside it.
 *    A person is never invited to press something that will be refused.
 *  - **A refusal from the SERVER is rendered even when the browser disagreed.** The two disagreeing
 *    is a real bug; showing our own optimistic answer over the server's would hide it.
 *  - **Reset really calls reset**, because "you can always get back" is what makes trying safe.
 *  - **Every pair the check can report has a label in all three languages** — a refusal that
 *    rendered a raw dotted key would do it at the exact moment somebody is being told no.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProgrammeColoursTab, { PAIR_KEYS } from './ProgrammeColoursTab'
import * as api from '@/lib/admin-api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, vars?: Record<string, string>) =>
      (vars ? `${k}|${Object.values(vars).join(',')}` : k),
  }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const READABLE = '#a21caf'    // purple — passes every pair
const UNREADABLE = '#facc15'  // yellow — fails the text pairs

function theme(over: Partial<api.OrganisationTheme> = {}): api.OrganisationTheme {
  return {
    organisation: { code: 'alpha', name: 'Alpha Foundation' },
    colour: '',
    is_default: true,
    tokens: null,
    checks: [],
    ...over,
  }
}

async function mount() {
  render(<ProgrammeColoursTab />)
  await waitFor(() => expect(screen.getByTestId('palette')).toBeTruthy())
}

function typeColour(value: string) {
  fireEvent.change(screen.getByLabelText('admin.programme.colours.hexLabel'), { target: { value } })
}

const saveButton = () => screen.getByTestId('save-colours') as HTMLButtonElement

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getOrganisationTheme.mockResolvedValue(theme())
})

describe('the palette', () => {
  it('always shows the ten shades', async () => {
    await mount()
    expect(screen.getByTestId('palette').children).toHaveLength(10)
  })
})

describe('Save, and when it may be pressed', () => {
  it('is asleep with nothing changed', async () => {
    await mount()
    expect(saveButton().disabled).toBe(true)
    expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.usingDefault')
  })

  it('wakes on a readable change', async () => {
    await mount()
    typeColour(READABLE)
    expect(saveButton().disabled).toBe(false)
    expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.changed')
  })

  it('⚠ STAYS ASLEEP for a colour nobody could read, and says why', async () => {
    await mount()
    typeColour(UNREADABLE)
    expect(saveButton().disabled).toBe(true)
    expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.cannotSave')
    expect(screen.getByTestId('unreadable-note')).toBeTruthy()
    // And it names the failing pairs rather than saying only that something is wrong.
    expect(screen.getByTestId('check-filled_button').getAttribute('data-passes')).toBe('no')
    expect(mockApi.saveOrganisationTheme).not.toHaveBeenCalled()
  })

  it('goes back to sleep when the colour is put back', async () => {
    await mount()
    typeColour(READABLE)
    expect(saveButton().disabled).toBe(false)
    typeColour(UNREADABLE)
    expect(saveButton().disabled).toBe(true)
    typeColour(READABLE)
    expect(saveButton().disabled).toBe(false)
  })

  it('is asleep while the text is not yet a colour, without shouting about it', async () => {
    await mount()
    typeColour('#a21c')
    expect(saveButton().disabled).toBe(true)
    expect(screen.getByTestId('bad-hex')).toBeTruthy()
  })
})

describe('saving', () => {
  it('sends the colour and reports success', async () => {
    mockApi.saveOrganisationTheme.mockResolvedValue(
      theme({ colour: READABLE, is_default: false }))
    await mount()
    typeColour(READABLE)
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveOrganisationTheme)
      .toHaveBeenCalledWith(READABLE, undefined, { token: 'tok' }))
    await waitFor(() => expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.saved'))
  })

  it('⚠ renders the SERVER refusal even though the browser thought it fine', async () => {
    // The gate is the server. If the two ever disagree, the person must see the server's answer —
    // showing our optimistic one would hide a real bug behind a cheerful screen.
    const err = new Error('unreadable') as Error & { body?: Record<string, unknown> }
    err.body = { code: 'unreadable', failing: ['filled_button', 'link_on_card'] }
    mockApi.saveOrganisationTheme.mockRejectedValue(err)
    await mount()
    typeColour(READABLE)
    fireEvent.click(saveButton())
    await waitFor(() => expect(screen.getByTestId('colours-outcome').textContent)
      .toContain('admin.programme.colours.refused'))
  })

  it('has a line on screen for a plain failure too', async () => {
    mockApi.saveOrganisationTheme.mockRejectedValue(new Error('boom'))
    await mount()
    typeColour(READABLE)
    fireEvent.click(saveButton())
    await waitFor(() => expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.errorGeneric'))
  })
})

describe('reset', () => {
  it('is offered only once a colour has been set', async () => {
    await mount()
    expect((screen.getByTestId('reset-colour') as HTMLButtonElement).disabled).toBe(true)
  })

  it('calls reset and returns to the default', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(theme({ colour: READABLE, is_default: false }))
    mockApi.resetOrganisationTheme.mockResolvedValue(theme())
    await mount()
    fireEvent.click(screen.getByTestId('reset-colour'))
    await waitFor(() => expect(mockApi.resetOrganisationTheme).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByTestId('colours-outcome').textContent)
      .toBe('admin.programme.colours.wasReset'))
  })
})

describe('a super with more than one tenant', () => {
  it('is asked which, never given a silent pick', async () => {
    const err = new Error('organisation_required') as Error & { body?: Record<string, unknown> }
    err.body = { code: 'organisation_required', organisations: ['alpha', 'beta'] }
    mockApi.getOrganisationTheme.mockRejectedValueOnce(err)
    render(<ProgrammeColoursTab />)
    await waitFor(() =>
      expect(screen.getByText('admin.programme.colours.organisationRequired')).toBeTruthy())
    expect(screen.getByText('alpha')).toBeTruthy()
    expect(screen.getByText('beta')).toBeTruthy()
  })
})

describe('every pair the check can report has words behind it', () => {
  // A refusal renders `pair.<key>` and `pairShort.<key>`. A missing one shows a raw dotted key at
  // the exact moment somebody is being told no — the "UI asserts what nothing checks" cluster.
  type PairLabels = {
    admin: { programme: { colours: { pair: Record<string, string>; pairShort: Record<string, string> } } }
  }

  it.each([['en', en], ['ms', ms], ['ta', ta]])('%s', (_locale, messages) => {
    const colours = (messages as unknown as PairLabels).admin.programme.colours
    for (const key of PAIR_KEYS) {
      expect(typeof colours.pair[key]).toBe('string')
      expect(colours.pair[key].length).toBeGreaterThan(0)
      expect(typeof colours.pairShort[key]).toBe('string')
      expect(colours.pairShort[key].length).toBeGreaterThan(0)
    }
  })
})
