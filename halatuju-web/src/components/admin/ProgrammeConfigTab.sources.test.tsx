/**
 * @jest-environment jsdom
 *
 * "Who referred you?" on Programme → Configuration — rendered (per-gift referral sources,
 * Sprint 1, 2026-10-08).
 *
 * The card's switches move a DRAFT and the tab's one SaveBar saves it, so what is pinned here is
 * the whole loop a person walks: a switch flips, the bar counts it, Save sends ONLY the changed
 * codes beside the items, the re-read is what the screen then shows; Discard puts it back; a gift
 * with nothing on says so in words (a new gift starts that way); and a failed load says so.
 * A mount, not a source guard: the subject is event handling and state, which a text scan cannot see.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProgrammeConfigTab from './ProgrammeConfigTab'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
// ⚠ A FRESH `t` EVERY RENDER, on purpose: the tab's `load` must not depend on it, or each render
// would re-fetch and overwrite an unsaved switch (the rule written above `load`).
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok' }) }))
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeScope: () => ({ chosen: 'gift-a', select: jest.fn() }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const CONFIG: api.ProgrammeConfiguration = {
  programme: { code: 'gift-a', name: 'Gift A', organisation: 'Org' },
  live_applicants: 0,
  items: [
    { kind: 'question', code: 'fears', label_key: 'admin.programme.question.fears', is_core: false, default_state: 'required', state: 'required' },
  ],
  sources: [
    { code: 'cumig', name: 'Concerned UM Indian Graduates', on: false },
    { code: 'smc', name: 'Sri Murugan Centre', on: true },
  ],
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
  mockApi.saveProgrammeConfiguration.mockImplementation(async (_items, _p, _o, sources) => ({
    ...CONFIG,
    sources: CONFIG.sources.map((s) => (sources && s.code in sources ? { ...s, on: sources[s.code] } : s)),
  }))
})

const loaded = async () => {
  render(<ProgrammeConfigTab />)
  await waitFor(() => expect(screen.getByTestId('sources-card')).toBeTruthy())
}
const toggle = (code: string) =>
  screen.getByTestId(`source-${code}`).querySelector('button[role="switch"]') as HTMLButtonElement
const saveButton = () => screen.getByText('admin.programme.config.save') as HTMLButtonElement

describe('the card', () => {
  it('lists the served sources with the SITE toggle, a count, and the fixed three', async () => {
    await loaded()
    expect(toggle('smc').getAttribute('aria-checked')).toBe('true')
    expect(toggle('cumig').getAttribute('aria-checked')).toBe('false')
    expect(toggle('smc').getAttribute('aria-label')).toBe('Sri Murugan Centre')
    expect(screen.getByTestId('sources-count').textContent).toBe('admin.programme.config.sourcesCount|1,2')
    // The fixed choices are words, never switches — in the apply form's own wording.
    expect(screen.getByTestId('sources-always').textContent).toContain(
      'scholarship.apply.org.halatuju · scholarship.apply.org.social · scholarship.apply.org.other')
    expect(screen.getByTestId('sources-card').querySelectorAll('[role="switch"]')).toHaveLength(2)
    expect(screen.getByText('admin.programme.config.sourcesLink').closest('a')?.getAttribute('href'))
      .toBe('/admin/sources')
    expect(screen.queryByTestId('sources-none')).toBeNull()
  })
})

describe('switch → pending → save → saved', () => {
  it('counts a switch in the shared bar and sends ONLY the changed code beside the items', async () => {
    await loaded()
    expect(saveButton().disabled).toBe(true)

    fireEvent.click(toggle('cumig'))
    expect(toggle('cumig').getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('sources-count').textContent).toBe('admin.programme.config.sourcesCount|2,2')
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.changed|1')
    expect(saveButton().disabled).toBe(false)

    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    const [items, programme, , sources] = mockApi.saveProgrammeConfiguration.mock.calls[0]
    expect(items).toEqual([])
    expect(programme).toBe('gift-a')
    expect(sources).toEqual({ cumig: true })

    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.saved'))
    expect(saveButton().disabled).toBe(true)
    expect(toggle('cumig').getAttribute('aria-checked')).toBe('true')
  })

  it('an item and a source together are one save with a count of two', async () => {
    await loaded()
    fireEvent.click(toggle('smc'))
    fireEvent.click(screen.getByTestId('row-question:fears').querySelector('button[data-state="off"]') as HTMLButtonElement)
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.changed|2')
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    const [items, , , sources] = mockApi.saveProgrammeConfiguration.mock.calls[0]
    expect(items).toEqual([{ kind: 'question', code: 'fears', state: 'off' }])
    expect(sources).toEqual({ smc: false })
  })

  it('switching back is not a change, and Discard restores the server copy', async () => {
    await loaded()
    fireEvent.click(toggle('smc'))
    fireEvent.click(toggle('smc'))
    expect(saveButton().disabled).toBe(true)
    fireEvent.click(toggle('smc'))
    expect(toggle('smc').getAttribute('aria-checked')).toBe('false')
    fireEvent.click(screen.getByText('admin.programme.config.discard'))
    expect(toggle('smc').getAttribute('aria-checked')).toBe('true')
    expect(saveButton().disabled).toBe(true)
    expect(mockApi.saveProgrammeConfiguration).not.toHaveBeenCalled()
  })

  it('a refused save keeps the switch and says so', async () => {
    await loaded()
    mockApi.saveProgrammeConfiguration.mockRejectedValueOnce(new Error('boom'))
    fireEvent.click(toggle('cumig'))
    fireEvent.click(saveButton())
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.errorGeneric'))
    expect(toggle('cumig').getAttribute('aria-checked')).toBe('true')
    expect(saveButton().disabled).toBe(false)
  })

  it('a source switched off in Sources meanwhile: re-reads, names it, keeps the rest, and the retry works', async () => {
    // Review fix (2026-10-08): the PUT refuses EVERYTHING with `unknown_source`, so re-sending the
    // same stale switch would fail for ever. The tab re-reads the list and keeps the other drafts.
    await loaded()
    mockApi.saveProgrammeConfiguration.mockRejectedValueOnce(Object.assign(new Error('x'), {
      body: { code: 'unknown_source', source: 'cumig' },
    }))
    mockApi.getProgrammeConfiguration.mockResolvedValueOnce({
      ...CONFIG, sources: [{ code: 'smc', name: 'Sri Murugan Centre', on: true }],
    })
    fireEvent.click(toggle('cumig'))                                   // the stale one
    fireEvent.click(toggle('smc'))                                     // still offered
    fireEvent.click(screen.getByTestId('row-question:fears').querySelector('button[data-state="off"]') as HTMLButtonElement)
    fireEvent.click(saveButton())

    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.sourceGone|Concerned UM Indian Graduates'))
    expect(screen.queryByTestId('source-cumig')).toBeNull()            // gone from the list
    expect(toggle('smc').getAttribute('aria-checked')).toBe('false')   // its draft kept
    expect(saveButton().disabled).toBe(false)

    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(2))
    const [items, , , sources] = mockApi.saveProgrammeConfiguration.mock.calls[1]
    expect(items).toEqual([{ kind: 'question', code: 'fears', state: 'off' }])
    expect(sources).toEqual({ smc: false })
  })
})

describe('the empty and failed states', () => {
  it('says plainly when nothing is on — a new gift starts that way', async () => {
    mockApi.getProgrammeConfiguration.mockResolvedValue({
      ...CONFIG, sources: CONFIG.sources.map((s) => ({ ...s, on: false })),
    })
    await loaded()
    expect(screen.getByTestId('sources-none').textContent).toBe('admin.programme.config.sourcesNone')
    expect(screen.getByTestId('sources-count').textContent).toBe('admin.programme.config.sourcesCount|0,2')
    // …and switching one on takes the sentence away.
    fireEvent.click(toggle('smc'))
    expect(screen.queryByTestId('sources-none')).toBeNull()
  })

  it('says so when there are no active sources at all, and still names the fixed three', async () => {
    mockApi.getProgrammeConfiguration.mockResolvedValue({ ...CONFIG, sources: [] })
    await loaded()
    expect(screen.getByTestId('sources-none')).toBeTruthy()
    expect(screen.getByTestId('sources-always')).toBeTruthy()
  })

  it('a failed load shows the load error and no card', async () => {
    mockApi.getProgrammeConfiguration.mockRejectedValue(new Error('boom'))
    render(<ProgrammeConfigTab />)
    await waitFor(() => expect(screen.getByText('admin.programme.config.loadError')).toBeTruthy())
    expect(screen.queryByTestId('sources-card')).toBeNull()
  })

  it('loads once — a fresh translator per render does not re-fetch over a draft', async () => {
    await loaded()
    fireEvent.click(toggle('cumig'))
    expect(toggle('cumig').getAttribute('aria-checked')).toBe('true')
    expect(mockApi.getProgrammeConfiguration).toHaveBeenCalledTimes(1)
  })
})

// ── Request #44 (2026-10-25): Facebook / WhatsApp and Halatuju.xyz get a switch per gift ─────────
describe('the fixed choices', () => {
  const FIXED: api.ProgrammeConfigFixedSource[] = [
    { code: 'halatuju', on: true, switchable: true },
    { code: 'social', on: true, switchable: true },
    { code: 'other', on: true, switchable: false },
  ]
  const fixedToggle = (code: string) =>
    screen.getByTestId(`fixed-${code}`).querySelector('button[role="switch"]') as HTMLButtonElement | null

  beforeEach(() => {
    mockApi.getProgrammeConfiguration.mockResolvedValue({ ...CONFIG, fixed_sources: FIXED })
    mockApi.saveProgrammeConfiguration.mockImplementation(async (_items, _p, _o, sources) => ({
      ...CONFIG,
      fixed_sources: FIXED.map((f) => (sources && f.code in sources ? { ...f, on: sources[f.code] } : f)),
    }))
  })

  it('draw a site Toggle for Halatuju.xyz and Facebook / WhatsApp, and Other as always on', async () => {
    await loaded()
    expect(fixedToggle('halatuju')?.getAttribute('aria-checked')).toBe('true')
    expect(fixedToggle('social')?.getAttribute('aria-label')).toBe('scholarship.apply.org.social')
    expect(fixedToggle('other')).toBeNull()
    expect(screen.getByTestId('fixed-other').textContent).toContain('admin.programme.config.sourcesAlwaysOn')
    // The old read-only footer gives way to the switches; the source count is unchanged.
    expect(screen.queryByTestId('sources-always')).toBeNull()
    expect(screen.getByTestId('sources-count').textContent).toBe('admin.programme.config.sourcesCount|1,2')
    expect(screen.queryByRole('checkbox')).toBeNull()                 // toggles, never tick boxes
  })

  it('a switch counts in the shared bar and saves in the same `sources` map', async () => {
    await loaded()
    fireEvent.click(fixedToggle('social') as HTMLButtonElement)
    fireEvent.click(toggle('cumig'))
    expect(fixedToggle('social')?.getAttribute('aria-checked')).toBe('false')
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.changed|2')
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    expect(mockApi.saveProgrammeConfiguration.mock.calls[0][3]).toEqual({ social: false, cumig: true })
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.saved'))
    expect(fixedToggle('social')?.getAttribute('aria-checked')).toBe('false')
    expect(saveButton().disabled).toBe(true)
  })

  it('Discard puts a fixed switch back', async () => {
    await loaded()
    fireEvent.click(fixedToggle('halatuju') as HTMLButtonElement)
    fireEvent.click(screen.getByText('admin.programme.config.discard'))
    expect(fixedToggle('halatuju')?.getAttribute('aria-checked')).toBe('true')
    expect(saveButton().disabled).toBe(true)
  })

  it('an older api with no `fixed_sources` keeps the read-only footer and no extra switch', async () => {
    mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
    await loaded()
    expect(screen.getByTestId('sources-always')).toBeTruthy()
    expect(screen.queryByTestId('sources-fixed')).toBeNull()
    expect(screen.getByTestId('sources-card').querySelectorAll('[role="switch"]')).toHaveLength(2)
  })
})
