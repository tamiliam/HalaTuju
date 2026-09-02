/**
 * @jest-environment jsdom
 *
 * "Colours" — rendered (Layer 1 A2, with A3's lifecycle).
 *
 * The maths is pure and pinned in `lib/__tests__/contrast.test.ts`; the server's rules are pinned in
 * `test_theme_draft_publish.py`. What is tested HERE is what a pure test cannot see, and after A3
 * the top item is not the gate — it is that **nobody can confuse "live" with "draft"**:
 *
 *  - the screen SAYS what applicants are seeing, rather than leaving it to be inferred;
 *  - saving a draft does not change that, and the screen says so;
 *  - Publish is asleep while there are unsaved edits, because publishing would ship the SAVED
 *    draft rather than what is in the box;
 *  - Save never wakes for a colour nobody could read, and the reason sits beside it;
 *  - a refusal from the SERVER is rendered even when the browser disagreed;
 *  - every pair the check can report has words behind it, in all three languages.
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
const TEAL = '#0f766e'
const UNREADABLE = '#facc15'  // yellow — fails the text pairs

function version(colour: string): api.ThemeVersion {
  return { colour, checks: [] }
}

function theme(over: Partial<api.OrganisationTheme> = {}): api.OrganisationTheme {
  return {
    organisation: { code: 'alpha', name: 'Alpha Foundation' },
    live: null,
    draft: null,
    previous_colour: '',
    can_revert: false,
    published_at: '',
    published_by: '',
    tokens: null,
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

const btn = (id: string) => screen.getByTestId(id) as HTMLButtonElement
const outcome = () => screen.getByTestId('colours-outcome').textContent

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getOrganisationTheme.mockResolvedValue(theme())
})

describe('the screen says what applicants are seeing', () => {
  it('names the default when nothing has been published', async () => {
    await mount()
    expect(screen.getByTestId('live-state').textContent)
      .toContain('admin.programme.colours.liveIsDefault')
  })

  it('names the live colour, and flags an unpublished draft beside it', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(
      theme({ live: version(READABLE), draft: version(TEAL), can_revert: true }))
    await mount()
    const banner = screen.getByTestId('live-state').textContent
    expect(banner).toContain('admin.programme.colours.liveIs')
    expect(banner).toContain(READABLE)
    expect(banner).toContain('admin.programme.colours.draftPending')
  })

  it('shows the DRAFT in the box when there is one, not the live colour', async () => {
    // The box is where the work happens, so it holds the unpublished work. The banner is what
    // says which colour is actually reaching people.
    mockApi.getOrganisationTheme.mockResolvedValue(
      theme({ live: version(READABLE), draft: version(TEAL) }))
    await mount()
    expect((screen.getByLabelText('admin.programme.colours.hexLabel') as HTMLInputElement).value)
      .toBe(TEAL)
  })
})

describe('saving a draft', () => {
  it('is asleep with nothing changed', async () => {
    await mount()
    expect(btn('save-draft').disabled).toBe(true)
    expect(outcome()).toBe('admin.programme.colours.nothingToDo')
  })

  it('wakes on a readable change and sends the colour', async () => {
    mockApi.saveOrganisationThemeDraft.mockResolvedValue(theme({ draft: version(READABLE) }))
    await mount()
    typeColour(READABLE)
    expect(btn('save-draft').disabled).toBe(false)
    fireEvent.click(btn('save-draft'))
    await waitFor(() => expect(mockApi.saveOrganisationThemeDraft)
      .toHaveBeenCalledWith(READABLE, undefined, { token: 'tok' }))
  })

  it('⚠ SAYS OUT LOUD that applicants still see the published colour', async () => {
    // The whole of A3 in one line of copy. A "Saved" that did not say this would read exactly like
    // the old behaviour, which DID change what everyone saw.
    mockApi.saveOrganisationThemeDraft.mockResolvedValue(
      theme({ live: version(READABLE), draft: version(TEAL), can_revert: true }))
    mockApi.getOrganisationTheme.mockResolvedValue(theme({ live: version(READABLE), can_revert: true }))
    await mount()
    typeColour(TEAL)
    fireEvent.click(btn('save-draft'))
    await waitFor(() => expect(outcome()).toBe('admin.programme.colours.draftSaved'))
    expect(screen.getByTestId('live-state').textContent).toContain(READABLE)
  })

  it('⚠ STAYS ASLEEP for a colour nobody could read, and says why', async () => {
    await mount()
    typeColour(UNREADABLE)
    expect(btn('save-draft').disabled).toBe(true)
    expect(outcome()).toBe('admin.programme.colours.cannotSave')
    expect(screen.getByTestId('unreadable-note')).toBeTruthy()
    // ⚠ THE ROW IS NAMED PER MODE since F7a, because the same pair now appears twice with
    // different numbers. Asserting the LIGHT row specifically also keeps this test about the
    // colour being unreadable rather than about which mode happened to notice first.
    expect(screen.getByTestId('check-light-filled_button').getAttribute('data-passes')).toBe('no')
    expect(mockApi.saveOrganisationThemeDraft).not.toHaveBeenCalled()
  })

  it('is asleep while the text is not yet a colour, without shouting', async () => {
    await mount()
    typeColour('#a21c')
    expect(btn('save-draft').disabled).toBe(true)
    expect(screen.getByTestId('bad-hex')).toBeTruthy()
  })
})

describe('publishing', () => {
  it('is asleep when there is no draft', async () => {
    await mount()
    expect(btn('publish-colours').disabled).toBe(true)
  })

  it('⚠ IS ASLEEP WHILE THERE ARE UNSAVED EDITS, and says to save first', async () => {
    // Publishing ships the SAVED draft, not what is in the box. Offering it mid-edit would publish
    // something other than the colour the person is looking at.
    mockApi.getOrganisationTheme.mockResolvedValue(theme({ draft: version(TEAL) }))
    await mount()
    expect(btn('publish-colours').disabled).toBe(false)
    typeColour(READABLE)
    expect(btn('publish-colours').disabled).toBe(true)
    expect(btn('publish-colours').getAttribute('title'))
      .toBe('admin.programme.colours.saveFirst')
  })

  it('publishes and says applicants can see it now', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(theme({ draft: version(TEAL) }))
    mockApi.publishOrganisationTheme.mockResolvedValue(
      theme({ live: version(TEAL), can_revert: true }))
    await mount()
    fireEvent.click(btn('publish-colours'))
    await waitFor(() => expect(mockApi.publishOrganisationTheme).toHaveBeenCalled())
    await waitFor(() => expect(outcome()).toBe('admin.programme.colours.published'))
    expect(screen.getByTestId('live-state').textContent).toContain(TEAL)
  })
})

describe('discarding and reverting', () => {
  it('discarding a SAVED draft asks the server; discarding an unsaved edit just resets the box', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(theme({ live: version(READABLE), can_revert: true }))
    await mount()

    typeColour(TEAL)                       // an unsaved edit — no server call needed
    fireEvent.click(btn('discard-draft'))
    expect(mockApi.discardOrganisationThemeDraft).not.toHaveBeenCalled()
    expect((screen.getByLabelText('admin.programme.colours.hexLabel') as HTMLInputElement).value)
      .toBe(READABLE)
  })

  it('discards a saved draft through the server and leaves the live colour alone', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(
      theme({ live: version(READABLE), draft: version(TEAL), can_revert: true }))
    mockApi.discardOrganisationThemeDraft.mockResolvedValue(
      theme({ live: version(READABLE), can_revert: true }))
    await mount()
    fireEvent.click(btn('discard-draft'))
    await waitFor(() => expect(mockApi.discardOrganisationThemeDraft).toHaveBeenCalled())
    await waitFor(() => expect(outcome()).toBe('admin.programme.colours.draftDiscarded'))
    expect(screen.getByTestId('live-state').textContent).toContain(READABLE)
  })

  it('offers Revert only once something is live, and names where it goes back to', async () => {
    await mount()
    expect(btn('revert-colours').disabled).toBe(true)
    // With no previous version, reverting lands on the platform default — said plainly.
    expect(btn('revert-colours').textContent).toBe('admin.programme.colours.revertToDefault')
  })

  it('names the previous colour when there is one', async () => {
    mockApi.getOrganisationTheme.mockResolvedValue(
      theme({ live: version(TEAL), previous_colour: READABLE, can_revert: true }))
    mockApi.revertOrganisationTheme.mockResolvedValue(
      theme({ live: version(READABLE), can_revert: true }))
    await mount()
    expect(btn('revert-colours').textContent).toContain(READABLE)
    fireEvent.click(btn('revert-colours'))
    await waitFor(() => expect(outcome()).toBe('admin.programme.colours.reverted'))
  })
})

describe('when the server disagrees', () => {
  it('⚠ renders the SERVER refusal even though the browser thought it fine', async () => {
    const err = new Error('unreadable') as Error & { body?: Record<string, unknown> }
    err.body = { code: 'unreadable', failing: ['filled_button', 'link_on_card'] }
    mockApi.saveOrganisationThemeDraft.mockRejectedValue(err)
    await mount()
    typeColour(READABLE)
    fireEvent.click(btn('save-draft'))
    await waitFor(() => expect(outcome()).toContain('admin.programme.colours.refused'))
  })

  it('has a line on screen for a plain failure too', async () => {
    mockApi.saveOrganisationThemeDraft.mockRejectedValue(new Error('boom'))
    await mount()
    typeColour(READABLE)
    fireEvent.click(btn('save-draft'))
    await waitFor(() => expect(outcome()).toBe('admin.programme.colours.errorGeneric'))
  })
})

describe('the palette', () => {
  it('always shows the ten shades', async () => {
    await mount()
    expect(screen.getByTestId('palette').children).toHaveLength(10)
  })

  it('marks the identity stop — the shade they actually chose', async () => {
    // Every other shade is DERIVED from 500, so a palette that does not say which one is theirs
    // reads as ten arbitrary blues. It was in the approved mock, lost in the build, and spotted
    // on the live screen rather than by any test — hence this one.
    await mount()
    expect(screen.getByTestId('identity-stop')).toBeTruthy()
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
