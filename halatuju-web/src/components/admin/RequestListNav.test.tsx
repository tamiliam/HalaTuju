/**
 * @jest-environment jsdom
 *
 * Previous / Next on a request's detail page (Requests list R1), MOUNTED: keys, focus and the
 * greyed ends are behaviour a source check cannot see. The list's record is written exactly as the
 * list writes it (`writeListNav`), into jsdom's real sessionStorage.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import RequestListNav from './RequestListNav'
import { REQUESTS_LIST_NAV, writeListNav } from '@/lib/listNav'
import { urlRouter } from '@/test/giftUrl'

jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p ? `${k}${JSON.stringify(p)}` : k),
    locale: 'en',
  }),
}))

const BACK = '/admin/requests?tab=progress&page=2'

beforeEach(() => {
  jest.clearAllMocks()
  window.sessionStorage.clear()
  writeListNav(REQUESTS_LIST_NAV, { ids: [11, 7, 3], backHref: BACK, labelKey: 'tab.progress' })
})

const step = (which: 'prev' | 'next') =>
  document.querySelector(`[data-list-nav="${which}"]`) as HTMLButtonElement
const mounted = async (id: number) => {
  const view = render(<RequestListNav id={id} />)
  await waitFor(() => expect(document.querySelector('[data-list-nav="position"]')).not.toBeNull())
  return view
}

describe('where the request sits in the list it came from', () => {
  it('says which tab it came from, and returns there unchanged', async () => {
    await mounted(7)
    const back = screen.getByRole('link')
    expect(back.getAttribute('href')).toBe(BACK)
    expect(back.textContent).toContain('admin.requests.detail.backTo{"tab":"tab.progress"}')
    expect(document.querySelector('[data-list-nav="position"]')?.textContent)
      .toBe('admin.requests.detail.position{"n":"2","m":"3"}')
  })

  it('walks to the neighbours', async () => {
    await mounted(7)
    fireEvent.click(step('next'))
    expect(urlRouter.push).toHaveBeenLastCalledWith('/admin/requests/3')
    fireEvent.click(step('prev'))
    expect(urlRouter.push).toHaveBeenLastCalledWith('/admin/requests/11')
  })

  it('is greyed at each end, and a greyed step goes nowhere', async () => {
    const { unmount } = await mounted(11)
    expect(step('prev').disabled).toBe(true)
    expect(step('next').disabled).toBe(false)
    unmount()
    await mounted(3)
    expect(step('next').disabled).toBe(true)
    fireEvent.click(step('next'))
    expect(urlRouter.push).not.toHaveBeenCalled()
  })

  it('arrived by a direct link, it is the plain way back and nothing else', async () => {
    render(<RequestListNav id={99} />)
    await waitFor(() => expect(screen.getByRole('link').getAttribute('href')).toBe('/admin/requests'))
    expect(screen.getByRole('link').textContent).toContain('admin.requests.detail.back')
    expect(step('next')).toBeNull()
  })

  it('pressing Next onto the last request moves focus to Previous, never to nowhere', async () => {
    const { rerender } = await mounted(7)
    step('next').focus()
    fireEvent.click(step('next'))
    rerender(<RequestListNav id={3} />)
    await waitFor(() => expect(step('next').disabled).toBe(true))
    expect(document.activeElement).toBe(step('prev'))
  })
})

describe('the arrow keys', () => {
  it('→ is Next and ← is Previous', async () => {
    await mounted(7)
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(urlRouter.push).toHaveBeenLastCalledWith('/admin/requests/3')
    fireEvent.keyDown(document, { key: 'ArrowLeft' })
    expect(urlRouter.push).toHaveBeenLastCalledWith('/admin/requests/11')
  })

  it('do nothing past an end', async () => {
    await mounted(3)
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(urlRouter.push).not.toHaveBeenCalled()
  })

  it('are left alone while typing, with a modifier held, or with a dialog open', async () => {
    const { container } = await mounted(7)
    const box = document.createElement('textarea')
    container.appendChild(box)
    box.focus()
    fireEvent.keyDown(box, { key: 'ArrowRight' })
    box.blur()
    fireEvent.keyDown(document, { key: 'ArrowRight', altKey: true })
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    container.appendChild(dialog)
    fireEvent.keyDown(document, { key: 'ArrowLeft' })
    expect(urlRouter.push).not.toHaveBeenCalled()
  })

  it('a direct link has nothing to walk, so the keys do nothing', async () => {
    render(<RequestListNav id={99} />)
    await screen.findByRole('link')
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(urlRouter.push).not.toHaveBeenCalled()
  })
})
