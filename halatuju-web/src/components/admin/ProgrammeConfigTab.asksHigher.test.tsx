/**
 * @jest-environment jsdom
 *
 * "Ask for STPM-level results" on Programme → Configuration (owner ruling D16, 2026-10-27).
 *
 * One site Toggle (never a tick box) in the tab's SAME draft and SaveBar: flipping it counts as a
 * change, Save sends `asks_higher_results` ONLY when it changed, Discard puts it back, and an older
 * api that serves no value draws no switch (a web-first deploy shows nothing it cannot save).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProgrammeConfigTab from './ProgrammeConfigTab'
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

const CONFIG: api.ProgrammeConfiguration = {
  programme: { code: 'gift-a', name: 'Gift A', organisation: 'Org' },
  live_applicants: 0,
  items: [],
  sources: [],
  asks_higher_results: true,
}

const toggle = () => screen.getByRole('switch', { name: 'admin.programme.config.asksHigher' })

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
  mockApi.saveProgrammeConfiguration.mockImplementation(async (_i, _p, _o, _s, asks) => ({
    ...CONFIG, asks_higher_results: asks ?? CONFIG.asks_higher_results,
  }))
})

const loaded = async () => {
  render(<ProgrammeConfigTab />)
  await waitFor(() => expect(screen.getByTestId('asks-higher')).toBeTruthy())
}

describe('Ask for STPM-level results', () => {
  it('is a switch, on by default', async () => {
    await loaded()
    expect(toggle().getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('asks-higher').querySelector('input[type="checkbox"]')).toBeNull()
  })

  it('flipping it counts as a change and Save sends it', async () => {
    await loaded()
    fireEvent.click(toggle())
    expect(toggle().getAttribute('aria-checked')).toBe('false')
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.changed|1')
    fireEvent.click(screen.getByText('admin.programme.config.save'))
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    expect(mockApi.saveProgrammeConfiguration.mock.calls[0][4]).toBe(false)
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.saved'))
    expect(toggle().getAttribute('aria-checked')).toBe('false')
  })

  it('flipped back is no change; Discard restores it', async () => {
    await loaded()
    fireEvent.click(toggle())
    fireEvent.click(toggle())
    expect(screen.queryByTestId('save-outcome')).toBeNull()
    fireEvent.click(toggle())
    fireEvent.click(screen.getByText('admin.programme.config.discard'))
    expect(toggle().getAttribute('aria-checked')).toBe('true')
  })

  it('an older api that serves no value draws no switch', async () => {
    mockApi.getProgrammeConfiguration.mockResolvedValue({ ...CONFIG, asks_higher_results: undefined })
    render(<ProgrammeConfigTab />)
    await waitFor(() => expect(screen.getByTestId('live-warning')).toBeTruthy())
    expect(screen.queryByTestId('asks-higher')).toBeNull()
  })
})
