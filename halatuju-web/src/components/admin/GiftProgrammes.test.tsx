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
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import GiftProgrammes from './GiftProgrammes'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }))
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeScope: () => ({ select: jest.fn(), reload: jest.fn().mockResolvedValue(undefined) }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const programme = (over: Partial<api.AdminProgramme> = {}): api.AdminProgramme => ({
  id: 7, code: 'test3', name_en: 'Test Three', name_ms: '', name_ta: '',
  is_active: false, intake_years: 0, applications: 0, open_year: null,
  delete_blocked_by: null, delete_blocked_count: 0, ...over,
})

const show = async (p: api.AdminProgramme) => {
  mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [p] })
  render(<GiftProgrammes token="tok" />)
  await waitFor(() => expect(screen.getByTestId('programme-test3')).toBeTruthy())
}

beforeEach(() => jest.clearAllMocks())

describe('deleting a gift', () => {
  it('leaves Delete LIVE for a gift that has intake years but no students', async () => {
    // The production shape of the owner's own case: a gift created by mistake, given one year,
    // nobody has applied. Before the ruling this button was grey and stayed grey for ever.
    await show(programme({ intake_years: 2, delete_blocked_by: null }))
    const del = screen.getByTestId('delete-test3') as HTMLButtonElement
    expect(del.disabled).toBe(false)
    expect(screen.queryByTestId('delete-blocked-test3')).toBeNull()
  })

  it('still greys Delete, with the reason, when the SERVER says students hold it', async () => {
    await show(programme({
      intake_years: 1, applications: 41,
      delete_blocked_by: 'has_applications', delete_blocked_count: 41,
    }))
    expect((screen.getByTestId('delete-test3') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByTestId('delete-blocked-test3').textContent)
      .toContain('admin.programmes.error.hasApplications')
  })

  it('warns in the dialog that the years go too, and names how many', async () => {
    await show(programme({ intake_years: 3 }))
    fireEvent.click(screen.getByTestId('delete-test3'))
    // The count is interpolated, so the mocked `t` prints it after the pipe.
    expect(screen.getByTestId('delete-years-note').textContent)
      .toBe('admin.programmes.deleteYears|3')
  })

  it('says nothing about years when the gift has none', async () => {
    await show(programme({ intake_years: 0 }))
    fireEvent.click(screen.getByTestId('delete-test3'))
    // A sentence about zero years is noise on the one dialog that must be read carefully.
    expect(screen.queryByTestId('delete-years-note')).toBeNull()
  })

  it('sends the typed phrase, and only wakes the confirm button once it matches', async () => {
    mockApi.deleteAdminProgramme.mockResolvedValue(undefined as never)
    await show(programme({ intake_years: 2 }))
    fireEvent.click(screen.getByTestId('delete-test3'))

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
