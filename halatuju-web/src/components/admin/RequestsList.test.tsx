/**
 * @jest-environment jsdom
 *
 * The Requests list (Requests list R1), MOUNTED: tabs, counts, the kind filter, the debounced
 * search, the pager, the address bar and the late-reply guard are all behaviour, so they are
 * asserted on a rendered list against a mocked api — never on the source.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import RequestsList, { SEARCH_DEBOUNCE_MS } from './RequestsList'
import * as api from '@/lib/admin-api'
import type { OrgRequestListPage, OrgRequestListRow } from '@/lib/admin-api'
import { REQUESTS_LIST_NAV, readListNav } from '@/lib/listNav'
import { address, deferred, openAt } from '@/test/giftUrl'

jest.mock('@/lib/admin-api')
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p ? `${k}${JSON.stringify(p)}` : k),
    locale: 'en',
  }),
}))

const mockApi = api as jest.Mocked<typeof api>

const row = (id: number, over: Partial<OrgRequestListRow> = {}): OrgRequestListRow => ({
  id, title: `Request ${id}`, kind: 'bug', status: 'submitted', submitted_by_name: 'Asha',
  created_at: '2026-11-01T00:00:00Z', tags: [], ...over,
})
const pageOf = (rows: OrgRequestListRow[], over: Partial<OrgRequestListPage> = {}): OrgRequestListPage => ({
  count: rows.length, total_pages: 1, page: 1, page_size: 25, requests: rows,
  ids: rows.map((r) => r.id), summary: { action: 2, progress: 5, closed: 9, all: 16 }, ...over,
})

const onDark = jest.fn()
const mount = (props: Partial<Parameters<typeof RequestsList>[0]> = {}) =>
  render(<RequestsList token="tok" org={undefined} isSuper={false} reloadKey={0} onDark={onDark}
    {...props} />)

const calls = () => mockApi.getOrgRequests.mock.calls.map((c) => c[0])
const lastCall = () => mockApi.getOrgRequests.mock.calls.at(-1)?.[0]
const tab = (name: string) => screen.getByRole('tab', { name: new RegExp(name) })

beforeEach(() => {
  jest.clearAllMocks()
  window.sessionStorage.clear()
  openAt('/admin/requests')
  mockApi.getOrgRequests.mockResolvedValue(pageOf([row(1), row(2)]))
})

describe('the tabs', () => {
  it('lands on Needs action and counts every tab from the WHOLE list', async () => {
    mount()
    await screen.findByText('Request 1')
    expect(lastCall()).toEqual({ group: 'action', kind: '', q: '', page: 1, org: undefined })
    expect(tab('tabAction').getAttribute('aria-selected')).toBe('true')
    expect(tab('tabAction').textContent).toContain('2')
    expect(tab('tabProgress').textContent).toContain('5')
    expect(tab('tabClosed').textContent).toContain('9')
    expect(tab('filterAll').textContent).toContain('16')
  })

  it('shows no count until the first answer arrives — "0" and "not counted" differ', async () => {
    const first = deferred<OrgRequestListPage>()
    mockApi.getOrgRequests.mockReturnValueOnce(first.promise)
    mount()
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    expect(tab('tabAction').textContent).toBe('admin.requests.list.tabAction')
    await act(async () => { first.resolve(pageOf([], { summary: { action: 0, progress: 0, closed: 0, all: 0 } })) })
    expect(tab('tabAction').textContent).toContain('0')
  })

  it('a tab asks the server for its own rows, from page 1, and the address bar says so', async () => {
    openAt('/admin/requests?page=3')
    mount()
    await screen.findByText('Request 1')
    fireEvent.click(tab('tabClosed'))
    await waitFor(() => expect(lastCall()).toMatchObject({ group: 'closed', page: 1 }))
    expect(address()).toBe('/admin/requests?tab=closed')
  })
})

describe('the kind filter and the search box', () => {
  it('filters by kind on the server and keeps the tab counts as they were', async () => {
    mount()
    await screen.findByText('Request 1')
    fireEvent.change(screen.getByRole('combobox', { name: 'admin.requests.list.kindLabel' }),
      { target: { value: 'bug' } })
    await waitFor(() => expect(lastCall()).toMatchObject({ kind: 'bug', group: 'action' }))
    expect(address()).toBe('/admin/requests?kind=bug')
  })

  it('asks once typing pauses, not on every keystroke', async () => {
    mount()
    await screen.findByText('Request 1')
    const box = screen.getByRole('searchbox', { name: 'admin.requests.list.searchLabel' })
    for (const text of ['e', 'ex', 'exp']) fireEvent.change(box, { target: { value: text } })
    await waitFor(() => expect(lastCall()).toMatchObject({ q: 'exp', page: 1 }),
      { timeout: SEARCH_DEBOUNCE_MS * 5 })
    expect(calls().filter((c) => c.q).map((c) => c.q)).toEqual(['exp'])
    expect(address()).toBe('/admin/requests?q=exp')
  })
})

describe('the address bar', () => {
  it('opens on the tab, kind, search and page it names', async () => {
    openAt('/admin/requests?tab=closed&kind=feature&q=abc&page=3')
    mount()
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    expect(calls()[0]).toEqual({ group: 'closed', kind: 'feature', q: 'abc', page: 3, org: undefined })
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('abc')
  })

  it('ignores what it does not know rather than asking the server to refuse it', async () => {
    openAt('/admin/requests?tab=open&kind=chore&page=-2')
    mount()
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    expect(calls()[0]).toEqual({ group: 'action', kind: '', q: '', page: 1, org: undefined })
  })
})

describe('paging', () => {
  it('says which rows are showing of how many, and pages on the server', async () => {
    mockApi.getOrgRequests.mockResolvedValue(pageOf([row(26), row(27), row(28)], {
      count: 28, total_pages: 2, page: 2, page_size: 25,
    }))
    openAt('/admin/requests?page=2')
    mount()
    await screen.findByText('Request 26')
    expect(document.querySelector('[data-list-showing]')?.textContent)
      .toBe('admin.requests.list.showing{"from":"26","to":"28","total":"28"}')
    fireEvent.click(screen.getAllByText('admin.previous')[0].closest('button') as HTMLButtonElement)
    await waitFor(() => expect(lastCall()).toMatchObject({ page: 1 }))
    expect(address()).toBe('/admin/requests')
  })

  it('a page past the end goes back to page 1 instead of calling the feature dark', async () => {
    mockApi.getOrgRequests.mockRejectedValueOnce(Object.assign(new Error('404'), { status: 404 }))
    openAt('/admin/requests?page=9')
    mount()
    await waitFor(() => expect(lastCall()).toMatchObject({ page: 1 }))
    expect(onDark).not.toHaveBeenCalled()
  })

  it('a 404 on page 1 is the dark feature', async () => {
    mockApi.getOrgRequests.mockRejectedValue(Object.assign(new Error('404'), { status: 404 }))
    mount()
    await waitFor(() => expect(onDark).toHaveBeenCalled())
  })
})

describe('the rows', () => {
  it('draw what the server served — the kind, the filed-as chip and the tags', async () => {
    mockApi.getOrgRequests.mockResolvedValue(pageOf([
      row(5, { kind: 'feature', filed_kind: 'bug', tags: ['analysed'], organisation_name: 'Org A' }),
      row(6, { tags: ['answer_needed'] }),
    ]))
    mount({ isSuper: true })
    const five = (await screen.findByText('Request 5')).closest('a') as HTMLElement
    expect(five.getAttribute('href')).toBe('/admin/requests/5')
    expect(within(five).getByText('admin.requests.kind.feature')).toBeTruthy()
    expect(within(five).getByText(/admin\.requests\.kind\.filedAs/).textContent).toContain('admin.requests.kind.bug')
    expect(within(five).getByText('admin.requests.list.analysed')).toBeTruthy()
    expect(within(five).getByText(/Org A/)).toBeTruthy()
    const six = screen.getByText('Request 6').closest('a') as HTMLElement
    expect(within(six).getByText('admin.requests.list.answerNeeded')).toBeTruthy()
  })

  it("leave the page's ids and the way back for the detail page's Previous / Next", async () => {
    openAt('/admin/requests?tab=progress')
    mockApi.getOrgRequests.mockResolvedValue(pageOf([row(9), row(4)]))
    mount()
    await screen.findByText('Request 9')
    expect(readListNav(REQUESTS_LIST_NAV)).toEqual({
      ids: [9, 4], backHref: '/admin/requests?tab=progress',
      labelKey: 'admin.requests.list.tabProgress',
    })
  })
})

describe('a late reply', () => {
  it('to an older question never overwrites the newer answer', async () => {
    const older = deferred<OrgRequestListPage>()
    const newer = deferred<OrgRequestListPage>()
    mockApi.getOrgRequests.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    mount()
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalledTimes(1))
    fireEvent.click(tab('tabClosed'))
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalledTimes(2))
    await act(async () => { newer.resolve(pageOf([row(70, { title: 'Closed one' })])) })
    await act(async () => { older.resolve(pageOf([row(80, { title: 'Stale one' })])) })
    expect(screen.getByText('Closed one')).toBeTruthy()
    expect(screen.queryByText('Stale one')).toBeNull()
    expect(readListNav(REQUESTS_LIST_NAV)?.ids).toEqual([70])
  })
})
