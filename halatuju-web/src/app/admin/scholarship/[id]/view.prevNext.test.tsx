/**
 * @jest-environment jsdom
 *
 * PREVIOUS / NEXT ON THE CASE HEADER, ON THE SHARED LIST-NAV RECORD (audit A3.3, TD-477).
 *
 * The Applications list leaves the page's ids with `writeListNav` (the one record every list uses),
 * and the cockpit reads them with `useListNav`: the same steps it always had, now with "n of m".
 * A case that is not in the record (a direct link) shows no steps at all.
 */
import { fireEvent, screen } from '@testing-library/react'

import { cockpitRouterPush, installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { writeListNav } from '@/lib/listNav'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

beforeEach(() => { sessionStorage.clear(); cockpitRouterPush.mockClear() })

describe('the cockpit header steps through the list it came from', () => {
  it('offers both steps and where the case sits (id 7 is the middle of 5, 7, 9)', async () => {
    writeListNav('scholarship', { ids: [5, 7, 9], backHref: '/admin/scholarship', labelKey: 'x' })
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    const nav = await screen.findByTestId('cockpit-prev-next')
    const links = Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(links).toEqual(['/admin/scholarship/5', '/admin/scholarship/9'])
    // The harness's `t` echoes the key, so the "2 of 3" figures are proven where they are computed
    // (listNav.test.ts); here the position is drawn between the two steps.
    expect(screen.getByTestId('cockpit-position').textContent).toBe('admin.requests.detail.position')
  })

  it('greys the step at either end', async () => {
    writeListNav('scholarship', { ids: [7, 9], backHref: '/admin/scholarship', labelKey: 'x' })
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    const nav = await screen.findByTestId('cockpit-prev-next')
    expect(Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href')))
      .toEqual(['/admin/scholarship/9'])
  })

  it('shows no steps for a case that is not in the record (a direct link)', async () => {
    writeListNav('scholarship', { ids: [1, 2, 3], backHref: '/admin/scholarship', labelKey: 'x' })
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    expect(screen.queryByTestId('cockpit-prev-next')).toBeNull()
  })

  it('shows no steps when nothing was left behind', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    expect(screen.queryByTestId('cockpit-prev-next')).toBeNull()
  })
})

describe('the arrow keys step through the same list', () => {
  const key = (k: string) => fireEvent.keyDown(document, { key: k })
  const seed = () => writeListNav('scholarship', { ids: [5, 7, 9], backHref: '/admin/scholarship', labelKey: 'x' })

  it('ArrowRight goes to the next case and ArrowLeft to the previous one', async () => {
    seed()
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    await screen.findByTestId('cockpit-prev-next')
    key('ArrowRight')
    expect(cockpitRouterPush).toHaveBeenLastCalledWith('/admin/scholarship/9')
    key('ArrowLeft')
    expect(cockpitRouterPush).toHaveBeenLastCalledWith('/admin/scholarship/5')
    expect(cockpitRouterPush).toHaveBeenCalledTimes(2)
  })

  it('does nothing while the officer is typing in a box', async () => {
    seed()
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    await screen.findByTestId('cockpit-prev-next')
    const box = document.querySelector('textarea, input:not([type="hidden"])') as HTMLElement
    expect(box).not.toBeNull()
    box.focus()
    expect(document.activeElement).toBe(box)
    fireEvent.keyDown(box, { key: 'ArrowRight' })
    fireEvent.keyDown(box, { key: 'ArrowLeft' })
    expect(cockpitRouterPush).not.toHaveBeenCalled()
  })

  it('does nothing while the confirm dialog is open', async () => {
    seed()
    renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    await screen.findByTestId('cockpit-prev-next')
    fireEvent.click(screen.getAllByRole('button', { name: 'admin.scholarship.cooloff.cancelDecline' })[0])
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    ;(document.activeElement as HTMLElement | null)?.blur()
    key('ArrowRight')
    key('ArrowLeft')
    expect(cockpitRouterPush).not.toHaveBeenCalled()
  })
})
