/**
 * @jest-environment jsdom
 *
 * "Academic results" on Programme → Configuration (owner rulings D16b + D16c, 2026-10-27).
 *
 * The core `results_slip` row is renamed "Academic results" and drawn like household income: locked
 * Required ("Always required"), its description and a small, NEUTRAL "Not one upload — …" note
 * (what is asked follows each intake's minimum STPM CGPA, set on the Rules tab). There is no per-gift
 * switch: the separate D16 card is gone and a save never sends `asks_higher_results`. Every other
 * row keeps its own label.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ProgrammeConfigTab from './ProgrammeConfigTab'
import RequirementFields from './RequirementFields'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
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

const item = (code: string, is_core: boolean, state: api.ProgrammeItemState): api.ProgrammeConfigItem => ({
  kind: 'document', code, label_key: `scholarship.docs.type.${code}`, is_core,
  default_state: state, state,
})

const CONFIG = {
  programme: { code: 'gift-a', name: 'Gift A', organisation: 'Org' },
  live_applicants: 0,
  items: [item('ic', true, 'required'), item('results_slip', true, 'required'),
    item('income_proof', true, 'required'), item('photo', false, 'optional')],
  sources: [],
  // An api still serving D16's field must not bring the switch back.
  asks_higher_results: false,
} as api.ProgrammeConfiguration

const row = (code: string) => screen.getByTestId(`row-document:${code}`)

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
  mockApi.saveProgrammeConfiguration.mockResolvedValue(CONFIG)
})

const loaded = async () => {
  render(<ProgrammeConfigTab />)
  await waitFor(() => expect(row('results_slip')).toBeTruthy())
}

describe('Academic results row', () => {
  it('is renamed and keeps its description; other rows keep their own labels', async () => {
    await loaded()
    const r = row('results_slip')
    expect(within(r).getByText('admin.programme.config.academic.title')).toBeTruthy()
    expect(within(r).queryByText('scholarship.docs.type.results_slip')).toBeNull()
    expect(within(r).getByText('admin.programme.config.desc.document.results_slip')).toBeTruthy()
    expect(within(row('ic')).getByText('scholarship.docs.type.ic')).toBeTruthy()
    expect(within(row('income_proof')).getByText('scholarship.docs.type.income_proof')).toBeTruthy()
  })

  it('is locked Required, like household income', async () => {
    await loaded()
    for (const code of ['results_slip', 'income_proof']) {
      const r = row(code)
      expect(within(r).getByTestId('always-required')).toBeTruthy()
      const radios = within(r).getAllByRole('radio') as HTMLButtonElement[]
      expect(radios.map((b) => [b.dataset.state, b.getAttribute('aria-checked'), b.disabled])).toEqual([
        ['off', 'false', true], ['optional', 'false', true], ['required', 'true', false],
      ])
    }
    expect(within(row('results_slip')).getByRole('radiogroup').getAttribute('aria-label'))
      .toBe('admin.programme.config.academic.title')
  })

  it('carries the neutral "Not one upload" note, styled like the household-income one', async () => {
    await loaded()
    const note = within(row('results_slip')).getByTestId('academic-note')
    expect(note.textContent).toBe('admin.programme.config.academic.note')
    const heavy = within(row('income_proof')).getByText('admin.programme.config.heavyNote')
    expect(note.className).toBe(heavy.className)
    expect(row('results_slip').className).toBe(row('income_proof').className)
    expect(within(row('income_proof')).queryByTestId('academic-note')).toBeNull()
  })

  it('has no per-gift switch, and a save never sends asks_higher_results', async () => {
    await loaded()
    expect(screen.queryByTestId('asks-higher')).toBeNull()
    expect(screen.queryByTestId('academic-choice')).toBeNull()
    expect(screen.queryByRole('switch')).toBeNull()
    expect(within(row('results_slip')).getAllByRole('radiogroup')).toHaveLength(1)
    fireEvent.click(within(row('photo')).getByRole('radio', { name: 'admin.programme.config.state.required' }))
    fireEvent.click(screen.getByText('admin.programme.config.save'))
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    expect(mockApi.saveProgrammeConfiguration.mock.calls[0]).toHaveLength(4)
  })
})

describe('the intake STPM floor', () => {
  it('says that blank makes the intake SPM-only', () => {
    const draft = { aCount: '', spmExtra: '', credits: '', pngk: '', merit: '', income: '',
      perPerson: '', birthStates: [] }
    render(<RequirementFields draft={draft} onChange={jest.fn()} idPrefix="t" />)
    const field = screen.getByText('admin.years.req.pngk').closest('label') as HTMLElement
    expect(within(field).getByText('admin.years.req.pngkHint')).toBeTruthy()
  })
})
