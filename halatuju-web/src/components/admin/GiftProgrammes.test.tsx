/**
 * @jest-environment jsdom
 *
 * Organisation → Overview → the gifts, DELETE only (owner ruling, 2026-09-07).
 *
 * ⚠⚠ THE RULING THIS PINS: *"I don't [want] the ability to delete a gift programme that has
 * students, and not merely intake years."* A year on its own is the rules somebody typed a minute
 * ago; students are what hold a gift. It shipped the other way round on 2026-09-07 — the year was
 * checked FIRST — which made a gift created by mistake and given one stray year permanent, because
 * a year cannot be deleted on its own either (TD-232).
 *
 * Two things are pinned here and neither is visible to a source-shape guard:
 *
 *  1. THE BUTTON IS LIVE FOR A GIFT THAT HAS YEARS BUT NO STUDENTS. This is the whole ruling, seen
 *     from the owner's side of the screen. `delete_blocked_by` is SERVED, so the assertion is that
 *     nothing here re-derives a block from the `intake_years` count sitting on the same card.
 *  2. THE DIALOG SAYS THE YEARS GO, AND SAYS HOW MANY. The years are the one thing being removed
 *     that a person cannot see from the dialog, and they no longer stop the delete — so silence
 *     would mean pressing Delete and quietly losing rules they had set up.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import GiftProgrammes from './GiftProgrammes'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
// Stable spies: the card-is-the-door tests assert BOTH halves of stepping into a gift — the
// selection the breadcrumb reads, and the navigation — so a fresh jest.fn() per render would lose
// the call being asserted.
const mockPush = jest.fn()
const mockSelect = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }) }))
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeScope: () => ({ select: mockSelect, reload: jest.fn().mockResolvedValue(undefined) }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const programme = (over: Partial<api.AdminProgramme> = {}): api.AdminProgramme => ({
  id: 7, code: 'test3', name_en: 'Test Three', name_ms: '', name_ta: '',
  is_active: false, lifecycle: 'draft', intake_years: 0, applications: 0, awarded: 0,
  open_year: null, delete_blocked_by: null, delete_blocked_count: 0, ...over,
})

/** A gift that has finished: switched off, and students applied to it. */
const archived = () => programme({
  lifecycle: 'archived', applications: 41, intake_years: 1,
  delete_blocked_by: 'has_applications', delete_blocked_count: 41,
})

const show = async (p: api.AdminProgramme) => {
  mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [p] })
  render(<GiftProgrammes token="tok" />)
  await waitFor(() => expect(screen.getByTestId('programme-test3')).toBeTruthy())
}

/** Open the card's ⋮ menu. Settings and Delete live in there now (owner, 2026-09-08). */
const openMore = () => fireEvent.click(screen.getByTestId('more-test3'))

/** The Delete row inside that menu — a <button> when live, an aria-disabled <span> when asleep. */
const deleteItem = () =>
  screen.getByText('admin.programmes.delete').closest('[data-menuitem]') as HTMLElement

const isAsleep = (el: HTMLElement) => el.getAttribute('aria-disabled') === 'true'

beforeEach(() => jest.clearAllMocks())

describe('the lifecycle badge', () => {
  it('shows the state, and never paints a draft RED', async () => {
    // ⚠ The owner's sketch asked for green/red/blue. Red in this product means something is
    // WRONG — a blocked delete, a failed check on a student's file — and a gift being set up is
    // the normal state of every gift on its first day. Grey says "not live yet", not "broken".
    await show(programme())
    const badge = screen.getByTestId('lifecycle-test3')
    expect(badge.textContent).toContain('admin.programmes.lifecycle.draft')
    expect(badge.className).toContain('bg-ground-100')
    expect(badge.className).not.toContain('critical')
  })

  it('tells a retired gift apart from one still being set up', async () => {
    // The whole reason the third state exists: both are `is_active: false` and used to render
    // identically, so "still being built" and "finished, holding 41 students" looked the same.
    await show(archived())
    const badge = screen.getByTestId('lifecycle-test3')
    expect(badge.textContent).toContain('admin.programmes.lifecycle.archived')
    expect(badge.className).toContain('bg-info-100')
  })

  it('IS the control — pressing it offers the one move that makes sense', async () => {
    // ⚠ A rendered test, not a source scan: this is a click, and a scan cannot see one.
    mockApi.updateAdminProgramme.mockResolvedValue(undefined as never)
    await show(programme())
    fireEvent.click(screen.getByTestId('lifecycle-test3'))

    const item = screen.getByText('admin.programmes.lifecycle.makeLive')
    fireEvent.click(item)
    await waitFor(() => expect(mockApi.updateAdminProgramme)
      .toHaveBeenCalledWith(7, { is_active: true }, { token: 'tok' }))
  })

  it('names where a live gift will LAND, which depends on whether anybody applied', async () => {
    // Switching off is one PATCH, but it lands in a different state depending on history — so
    // the menu says which before it is pressed rather than after.
    await show(programme({ is_active: true, lifecycle: 'active', applications: 41 }))
    fireEvent.click(screen.getByTestId('lifecycle-test3'))
    expect(screen.queryByText('admin.programmes.lifecycle.archive')).toBeTruthy()
    expect(screen.queryByText('admin.programmes.lifecycle.toDraft')).toBeNull()
  })

  it('offers a return to DRAFT for a live gift nobody has applied to', async () => {
    await show(programme({ is_active: true, lifecycle: 'active', applications: 0 }))
    fireEvent.click(screen.getByTestId('lifecycle-test3'))
    expect(screen.queryByText('admin.programmes.lifecycle.toDraft')).toBeTruthy()
    expect(screen.queryByText('admin.programmes.lifecycle.archive')).toBeNull()
  })

  it('keeps the state OUT of the verb menu — the badge is the only state control', async () => {
    // ⚠ THE OWNER'S ORIGINAL REPORT (2026-09-07). "Switch off" used to sit in a row of verbs one
    // line under a column headed "Taking applications", and read as a duplicate of the intake
    // year's Open/Close. It moved into the badge, and it must not follow Settings and Delete into
    // the ⋮ menu on the way past.
    await show(programme())
    openMore()
    expect(screen.queryByText('admin.programmes.switchOn')).toBeNull()
    expect(screen.queryByText('admin.programmes.switchOff')).toBeNull()
    expect(screen.getByText('admin.programmes.openSettings')).toBeTruthy()
    expect(deleteItem()).toBeTruthy()
  })
})

/*
 * ── The card is the door (owner, 2026-09-08) ──────────────────────────────────────────────────
 *
 * *"In supabase, the project card is clickable… we could change the entire gift card to button."*
 * The old door was the word "Settings" in a row of verbs at the foot of the card, and the owner
 * never found it — they reached a gift through Applications and the breadcrumb instead.
 */
describe('the card is the door', () => {
  it('opens the gift when the card itself is pressed', async () => {
    await show(programme())
    fireEvent.click(screen.getByTestId('open-test3'))
    expect(mockSelect).toHaveBeenCalledWith('test3')
    expect(mockPush).toHaveBeenCalledWith('/admin/programme')
  })

  it('KEEPS Settings in the menu as well', async () => {
    // The card is a shortcut, not a replacement. Somebody looking for "where do I configure this"
    // should find the word, and both routes must land in the same place.
    await show(programme())
    openMore()
    fireEvent.click(screen.getByText('admin.programmes.openSettings'))
    expect(mockSelect).toHaveBeenCalledWith('test3')
    expect(mockPush).toHaveBeenCalledWith('/admin/programme')
  })

  it('never nests a button inside the card button', async () => {
    // ⚠ THE ACCESSIBILITY TRAP THIS CARD WAS BUILT AROUND. A <button> inside a <button> is invalid
    // HTML and the inner control becomes unreachable by keyboard — so the state badge and the ⋮
    // menu are SIBLINGS of the door, never children of it. Asserted structurally because a browser
    // recovers from the mistake quietly, which is exactly why it survives review.
    await show(programme())
    const door = screen.getByTestId('open-test3')
    expect(door.querySelector('button')).toBeNull()
    expect(door.contains(screen.getByTestId('lifecycle-test3'))).toBe(false)
    expect(door.contains(screen.getByTestId('more-test3'))).toBe(false)
  })

  it('still lets the badge be pressed without opening the gift', async () => {
    mockApi.updateAdminProgramme.mockResolvedValue(undefined as never)
    await show(programme())
    fireEvent.click(screen.getByTestId('lifecycle-test3'))
    expect(mockPush).not.toHaveBeenCalled()
    expect(screen.getByText('admin.programmes.lifecycle.makeLive')).toBeTruthy()
  })
})

describe('what the card counts', () => {
  it('shows how many have EVER been awarded', async () => {
    // ⚠ SERVED, NEVER DERIVED HERE. `awarded` is one stage in awarded → active → maintenance →
    // closed, so a count worked out in the browser from a live status would FALL as students
    // progress. The card renders what the server sends and does no arithmetic of its own.
    await show(programme({ applications: 143, awarded: 47 }))
    const card = screen.getByTestId('programme-test3')
    expect(card.textContent).toContain('admin.programmes.col.awarded')
    expect(card.textContent).toContain('47')
  })

  it('says which round is taking applications, or that none is', async () => {
    // A programme is never "open"; one of its years is.
    await show(programme({ open_year: 2026 }))
    expect(screen.getByTestId('programme-test3').textContent)
      .toContain('admin.programmes.takingApplicationsFor|2026')

    cleanup()
    await show(programme({ open_year: null }))
    expect(screen.getByTestId('programme-test3').textContent)
      .toContain('admin.programmes.notTakingApplications')
  })
})

describe('deleting a gift', () => {
  it('leaves Delete LIVE for a gift that has intake years but no students', async () => {
    // The production shape of the owner's own case: a gift created by mistake, given one year,
    // nobody has applied. Before the ruling this control was grey and stayed grey for ever.
    await show(programme({ intake_years: 2, delete_blocked_by: null }))
    openMore()
    expect(isAsleep(deleteItem())).toBe(false)
  })

  it('still asleep, with the reason, when the SERVER says students hold it', async () => {
    // ⚠ THE REASON NOW SHOWS FOR `has_applications` TOO, AND THAT IS A DELIBERATE REVERSAL.
    // The 2026-09-07 ruling (*"REMOVE. Redundant."*) was about ADJACENCY — an APPLICATIONS column
    // reading 41 stood directly above the sentence. Delete lives in the ⋮ menu now, which carries
    // no counts, so in there it is the only explanation a reader gets.
    await show(archived())
    openMore()
    const item = deleteItem()
    expect(isAsleep(item)).toBe(true)
    expect(item.textContent).toContain('admin.programmes.error.hasApplications')
  })

  it('KEEPS the reason for the four causes no count could ever explain', async () => {
    // Money, benefactors and payment runs appear nowhere on this card at all, so this half was
    // never redundant on any surface.
    await show(programme({
      delete_blocked_by: 'has_money', delete_blocked_count: 1, lifecycle: 'archived',
    }))
    openMore()
    const item = deleteItem()
    expect(isAsleep(item)).toBe(true)
    expect(item.textContent).toContain('admin.programmes.error.hasMoney')
  })

  it('keeps the menu OPEN when an asleep Delete is pressed', async () => {
    // ⚠ The panel closes on its own click, so without `stopPropagation` pressing an asleep item
    // would shut the menu — taking the reason off the screen at the moment it was being read.
    await show(archived())
    openMore()
    fireEvent.click(deleteItem())
    expect(screen.getByText('admin.programmes.error.hasApplications')).toBeTruthy()
  })

  it('warns in the dialog that the years go too, and names how many', async () => {
    await show(programme({ intake_years: 3 }))
    openMore()
    fireEvent.click(deleteItem())
    // The count is interpolated, so the mocked `t` prints it after the pipe.
    expect(screen.getByTestId('delete-years-note').textContent)
      .toBe('admin.programmes.deleteYears|3')
  })

  it('says nothing about years when the gift has none', async () => {
    await show(programme({ intake_years: 0 }))
    openMore()
    fireEvent.click(deleteItem())
    // A sentence about zero years is noise on the one dialog that must be read carefully.
    expect(screen.queryByTestId('delete-years-note')).toBeNull()
  })

  it('sends the typed phrase, and only wakes the confirm button once it matches', async () => {
    mockApi.deleteAdminProgramme.mockResolvedValue(undefined as never)
    await show(programme({ intake_years: 2 }))
    openMore()
    fireEvent.click(deleteItem())

    const confirm = screen.getByTestId('delete-confirm') as HTMLButtonElement
    expect(confirm.disabled).toBe(true)          // nothing typed
    const box = document.getElementById('p-confirm') as HTMLInputElement
    fireEvent.change(box, { target: { value: 'test3' } })
    expect(confirm.disabled).toBe(true)          // the bare code is not the phrase
    fireEvent.change(box, { target: { value: '  DELETE   Test3 ' } })
    expect(confirm.disabled).toBe(false)         // case and stray spaces are typing, not intent

    fireEvent.click(confirm)
    await waitFor(() => expect(mockApi.deleteAdminProgramme)
      .toHaveBeenCalledWith(7, 'delete test3', { token: 'tok' }))
  })
})
