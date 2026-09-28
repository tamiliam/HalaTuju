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
import { screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
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
})
