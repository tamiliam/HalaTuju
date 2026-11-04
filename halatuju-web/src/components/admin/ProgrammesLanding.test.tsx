/**
 * @jest-environment jsdom
 *
 * Organisation → Programmes, the landing (T5c P5). Pinned here:
 *  * the gift-door roles get the full card grid (`GiftProgrammes`), and nobody else does;
 *  * a reviewer's card carries ONE count, "Cases assigned to you"; a mentor's "Scholars you mentor"; a person
 *    who is both sees both;
 *  * ⚠ A COUNT THE SERVER DID NOT SEND IS NOT DRAWN — never as a zero;
 *  * archived programmes wear a grey Archived pill;
 *  * `opens` decides the link: the gift's Overview, or the mentor's students narrowed to this gift;
 *  * nothing assigned → the empty state, not an empty grid.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'

import ProgrammesLanding, { cardHref } from './ProgrammesLanding'
import * as api from '@/lib/admin-api/myProgrammes'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: mockLocale }) }))
let mockLocale = 'en'
let mockRole: Record<string, unknown> = { role: 'reviewer' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
const mockSelect = jest.fn()
jest.mock('@/lib/programmeScope', () => ({ useProgrammeScope: () => ({ select: mockSelect, chosen: '' }) }))
jest.mock('@/lib/admin-api/myProgrammes')
jest.mock('./GiftProgrammes', () => ({
  __esModule: true, default: ({ title }: { title?: string }) => <div data-testid="gift-grid">{title}</div>,
}))

const mockApi = api as jest.Mocked<typeof api>

const prog = (over: Partial<api.MyProgramme> = {}): api.MyProgramme => ({
  id: 7, code: 'b40', name_en: 'B40 Gift', name_ms: 'Hadiah B40', name_ta: 'பி40 கொடை',
  is_active: true, lifecycle: 'active', archived: false, opens: 'overview', ...over,
})

const serve = (programmes: api.MyProgramme[], every_gift = false) =>
  mockApi.getMyProgrammes.mockResolvedValue({ every_gift, programmes })

beforeEach(() => {
  jest.clearAllMocks()
  mockLocale = 'en'
  mockRole = { role: 'reviewer' }
})

describe('who gets which drawing', () => {
  it.each(['org_admin', 'super'])('%s gets the full gift grid, titled as the page', async (role) => {
    mockRole = role === 'super' ? { role: 'admin', is_super_admin: true } : { role }
    render(<ProgrammesLanding />)
    expect(screen.getByTestId('gift-grid').textContent).toBe('admin.programmes.landing.title')
    expect(mockApi.getMyProgrammes).not.toHaveBeenCalled()
  })

  it('a plain admin gets the narrowed cards, with the counts an admin is served', async () => {
    mockRole = { role: 'admin' }
    serve([prog({ intake_years: 2, applications: 143, awarded: 12 })], true)
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(screen.queryByTestId('gift-grid')).toBeNull()
    expect(within(card).getByTestId('count-intake_years').textContent).toContain('2')
    expect(within(card).getByTestId('count-applications').textContent).toContain('143')
    expect(within(card).getByTestId('count-awarded').textContent).toContain('12')
    expect(within(card).queryByTestId('count-cases')).toBeNull()
    // Every gift is served, so the subtitle is the organisation's own, not "only where you have work".
    expect(screen.getByText('admin.programmes.subtitle')).toBeTruthy()
  })
})

describe('the counts', () => {
  it('a reviewer sees ONE count — the cases assigned to them', async () => {
    serve([prog({ cases: 4 })])
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(within(card).getAllByTestId(/^count-/)).toHaveLength(1)
    expect(within(card).getByTestId('count-cases').textContent).toBe('admin.programmes.landing.cases4')
    expect(screen.getByText('admin.programmes.landing.workSub')).toBeTruthy()
  })

  it('a mentor sees the scholars they mentor, and the card opens their students for that gift', async () => {
    mockRole = { role: 'mentor' }
    serve([prog({ id: 9, scholars: 3, opens: 'my_students' })])
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(within(card).getByTestId('count-scholars').textContent).toBe('admin.programmes.landing.scholars3')
    expect(card.getAttribute('href')).toBe('/admin/my-students?programme=9')
    fireEvent.click(card)
    // Not a step INTO the gift, so the breadcrumb is left alone.
    expect(mockSelect).not.toHaveBeenCalled()
  })

  it('a reviewer who also mentors sees both counts', async () => {
    serve([prog({ cases: 2, scholars: 5 })])
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(within(card).getAllByTestId(/^count-/).map((n) => n.dataset.testid))
      .toEqual(['count-cases', 'count-scholars'])
  })

  it('⚠ a MISSING count is not drawn — and a served zero is', async () => {
    serve([prog({ cases: 0 })])
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(within(card).getByTestId('count-cases').textContent).toBe('admin.programmes.landing.cases0')
    expect(within(card).queryByTestId('count-scholars')).toBeNull()
    expect(within(card).queryByTestId('count-applications')).toBeNull()
  })
})

describe('the card', () => {
  it('opens the gift Overview WITH the gift, and selects it for the breadcrumb', async () => {
    serve([prog({ cases: 1 })])
    render(<ProgrammesLanding />)
    const card = await screen.findByTestId('my-programme-b40')
    expect(card.getAttribute('href')).toBe('/admin/programme/overview?programme=b40')
    fireEvent.click(card)
    expect(mockSelect).toHaveBeenCalledWith('b40')
  })

  it('an ARCHIVED card vouches for its gift (the scopes list holds active gifts only)', async () => {
    serve([prog({ id: 8, code: 'old', archived: true, lifecycle: 'archived', is_active: false, cases: 1 })])
    render(<ProgrammesLanding />)
    fireEvent.click(await screen.findByTestId('my-programme-old'))
    expect(mockSelect).toHaveBeenCalledWith('old', { code: 'old', name: 'B40 Gift', isActive: false })
  })

  it('wears a grey Archived pill only when the programme is archived', async () => {
    serve([prog({ cases: 1 }), prog({ id: 8, code: 'old', archived: true, lifecycle: 'archived', cases: 1 })])
    render(<ProgrammesLanding />)
    await screen.findByTestId('my-programme-old')
    expect(within(screen.getByTestId('my-programme-b40')).queryByTestId('archived-pill')).toBeNull()
    const pill = within(screen.getByTestId('my-programme-old')).getByTestId('archived-pill')
    expect(pill.textContent).toBe('admin.programmes.lifecycle.archived')
    expect(pill.className).toContain('bg-ground-100')
  })

  it('names the gift in the reader\'s language, falling back to English', async () => {
    mockLocale = 'ta'
    serve([prog({ cases: 1 }), prog({ id: 8, code: 'x', name_ta: '', name_en: 'Only English', cases: 1 })])
    render(<ProgrammesLanding />)
    expect(await screen.findByText('பி40 கொடை')).toBeTruthy()
    expect(screen.getByText('Only English')).toBeTruthy()
  })

  it('cardHref follows `opens`', () => {
    expect(cardHref(prog({ opens: 'my_students', id: 3 }))).toBe('/admin/my-students?programme=3')
    expect(cardHref(prog())).toBe('/admin/programme/overview?programme=b40')
  })
})

describe('nothing assigned', () => {
  it('says so, and who to ask, instead of drawing an empty grid', async () => {
    serve([])
    render(<ProgrammesLanding />)
    const empty = await screen.findByTestId('my-programmes-empty')
    expect(within(empty).getByText('admin.programmes.landing.emptyTitle')).toBeTruthy()
    expect(within(empty).getByText('admin.programmes.landing.emptyFoot')).toBeTruthy()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('says the list could not be loaded when the call fails', async () => {
    mockApi.getMyProgrammes.mockRejectedValue(new Error('boom'))
    render(<ProgrammesLanding />)
    expect(await screen.findByText('admin.programmes.loadFailed')).toBeTruthy()
  })
})
