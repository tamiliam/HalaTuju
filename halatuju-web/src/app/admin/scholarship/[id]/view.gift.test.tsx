/**
 * @jest-environment jsdom
 *
 * An application tells the breadcrumb which gift it belongs to (2026-09-28).
 *
 * ⚠ THE NEW-TAB CASE IS THE ONE THAT MATTERS. A payment run opens each student in a NEW TAB —
 * deliberately, so the run stays open beside them — and a new tab is a fresh app with no choice
 * in it. So this mounts the cockpit with NO prior choice and asserts the crumb names the case's
 * own gift, with no switch.
 *
 * ⚠ AND THE TRAP: `chosen_programme` is the student's COURSE, not the gift. The fixture below
 * gives the course a field that reads exactly like one of the gift codes, so a pin wired to the
 * wrong field names the wrong gift here and fails.
 */
import { screen, waitFor, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import * as adminApi from '@/lib/admin-api'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'
import { GiftScope, crumbSwitch, crumbText, scopeChosen, scopePinned } from '@/test/giftScope'

installCockpitConsoleGuard()

const SABAH = { id: 2, code: 'bpb-sabah-2026', name: 'Sabah Bursary 2026' }

/** The gift is Sabah; the COURSE carries the flagship's code in every field a careless read of
 *  "programme" might reach for. */
const app = () => buildApplicationDetail('interviewing', {
  programme_id: SABAH.id,
  programme: SABAH,
  chosen_programme: {
    code: 'brightpath-flagship', programme: 'brightpath-flagship',
    course_id: 'test-course', course_name: 'Test Engineering Degree',
  },
})

/** The payload has arrived and been drawn — the fixture's applicant is on screen. */
const mounted = () => screen.findAllByText(/Test Student 07/)

describe('a fresh mount of the application page, with no prior choice', () => {
  it('names the CASE’s gift in the crumb, with no switch', async () => {
    renderCockpit({ role: 'org_admin', app: app(), wrapper: GiftScope })
    await mounted()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    expect(crumbText()).toContain('Sabah Bursary 2026')
    expect(crumbSwitch()).toBeNull()
    expect(scopeChosen()).toBe('bpb-sabah-2026')
  })

  it('⚠ pins `programme` (the GIFT), never `chosen_programme` (the course)', async () => {
    renderCockpit({ role: 'org_admin', app: app(), wrapper: GiftScope })
    await mounted()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    // The course names the flagship in three places; the crumb must not.
    expect(crumbText()).not.toContain('Flagship Bursary')
    expect(scopeChosen()).not.toBe('brightpath-flagship')
  })

  it('pins nothing for a case with no gift, and the crumb still asks', async () => {
    renderCockpit({ role: 'org_admin', app: { ...app(), programme: null, programme_id: null },
                    wrapper: GiftScope })
    await mounted()
    expect(scopePinned()).toBe('false')
    expect(crumbText()).toContain('admin.shell.chooseProgramme')
  })

  it('releases the pin when the page goes, and leaves the all-gifts list all-gifts', async () => {
    // ⚠ F2 (adversarial review): the pin used to SELECT, which narrowed the Applications list —
    // a reviewer's only door, and a list of EVERY gift — to this one, with no way back but a
    // reload. Nobody chose a gift, so after the page goes nobody has one.
    const view = renderCockpit({ role: 'org_admin', app: app(), wrapper: GiftScope })
    await mounted()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    // `rerender` keeps the WRAPPER (the scope and the crumb) and swaps the page out — which is
    // what navigating to a list page does inside the shell.
    view.rerender(<></>)
    expect(scopePinned()).toBe('false')
    expect(scopeChosen()).toBe('(none)')
    expect(crumbSwitch()).not.toBeNull()
  })

  it('⚠ the way back to Applications does NOT name the case’s gift (TD-296, by decision)', async () => {
    // Unlike a payment run's way back (Payments has no all-gifts mode), this list IS the all-gifts
    // list. Naming the applicant's gift here would narrow it on the way back — F2 by another road.
    renderCockpit({ role: 'org_admin', app: app(), wrapper: GiftScope })
    await mounted()
    const back = screen.getByRole('link', { name: /admin.scholarship.back/ })
    expect(back.getAttribute('href')).toBe('/admin/scholarship')
  })
})

/**
 * The assign picker and MULTI-GIFT reviewers (owner design, 2026-11-06). A reviewer who covers
 * none of this case's gift is GREYED, "Does not cover <gift>" — never removed. One who covers
 * every gift (`[]`), or several gifts including this one, stays open.
 */
describe('the assign picker greys a reviewer who does not cover the case’s gift', () => {
  const FLAGSHIP = { id: 1, code: 'brightpath-flagship', name: 'Flagship Bursary' }
  const row = (id: number, name: string, gifts: typeof FLAGSHIP[]) => ({
    id, name, role: 'reviewer', email: `r${id}@example.test`, languages: ['en'], corrections: 0,
    paused: false, gifts,
  })

  it('greys only the reviewer whose gifts leave this case out', async () => {
    const getAdmins = adminApi.getAssignableAdmins as jest.Mock
    // Queued BEFORE the mount: a once-value wins over the default `primeCockpitApi` sets.
    getAdmins.mockResolvedValueOnce({ admins: [
      row(60, 'Flagship Only', [FLAGSHIP]),
      row(61, 'Every Gift', []),
      row(62, 'Both Gifts', [FLAGSHIP, SABAH]),
    ] })
    renderCockpit({ role: 'org_admin', stage: 'profile_complete', build: { programme_id: SABAH.id, programme: SABAH } })
    await mounted()
    const card = screen.getByText('admin.scholarship.assignTitle').closest('div') as HTMLElement
    const picker = within(card).getByRole('combobox')
    const opt = (name: RegExp) => within(picker).getByRole('option', { name }) as HTMLOptionElement
    await waitFor(() => expect(opt(/Flagship Only/).disabled).toBe(true))
    expect(opt(/Flagship Only/).textContent).toContain('admin.scholarship.assign.doesNotCover')
    expect(opt(/Every Gift/).disabled).toBe(false)
    expect(opt(/Both Gifts/).disabled).toBe(false)
    expect(opt(/Both Gifts/).textContent).not.toContain('doesNotCover')
  })
})
