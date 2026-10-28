/**
 * @jest-environment jsdom
 *
 * The super-admin System health light (2026-10-28): the light's colour is the WORST row, the panel
 * renders the five rows with their plain-English lines, there is no "View logs" link, and it polls.
 * Who sees it at all is AppShell's decision and is pinned in AppShell.test.tsx.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { HEALTH_POLL_MS, SystemHealthLight, lastOkText, lineText, worstStatus } from './SystemHealthLight'
import type { HealthRow, SystemHealth } from '@/lib/admin-api'

// `t` echoes the key and its params, so a test can see which string and which values were chosen.
const t = (k: string, p?: Record<string, string>) => (p ? `${k}${JSON.stringify(p)}` : k)
jest.mock('@/lib/i18n', () => ({
  // A prefix, so the component's `tOr` sees a resolved string (a bare key would read as missing).
  useT: () => ({ t: (k: string, p?: Record<string, string>) => `T:${k}${p ? JSON.stringify(p) : ''}` }),
  // The real `tOr`'s contract, restated: the fallback only when `t` echoes the key back.
  tOr: (tt: (k: string, p?: Record<string, string>) => string, k: string, fb: string,
    p?: Record<string, string>) => { const v = tt(k, p); return v === k ? fb : v },
}))

const mockGet = jest.fn()
jest.mock('@/lib/admin-api', () => ({ getSystemHealth: (...a: unknown[]) => mockGet(...a) }))

const row = (key: HealthRow['key'], status: HealthRow['status'], code = 'ok',
  params: Record<string, string> = {}): HealthRow => ({ key, status, code, params, last_ok_at: null })

const payload = (rows: HealthRow[]): SystemHealth => ({
  overall: 'green', checked_at: new Date().toISOString(), rows,
})

const ALL_GREEN = [row('gemini', 'green'), row('vision', 'green'), row('email', 'green'),
  row('cron', 'green', 'ok', { count: '26' }), row('credit', 'green')]

const light = () => screen.getByTestId('system-health-light')

beforeEach(() => { mockGet.mockReset() })

describe('worstStatus', () => {
  it('is the worst row, whatever the order', () => {
    expect(worstStatus(ALL_GREEN)).toBe('green')
    expect(worstStatus([row('email', 'amber'), ...ALL_GREEN])).toBe('amber')
    expect(worstStatus([row('cron', 'red'), row('email', 'amber'), row('gemini', 'green')])).toBe('red')
    expect(worstStatus([])).toBeNull()
  })
})

describe('the light', () => {
  it('shows the worst row, not the server summary', async () => {
    // overall says green; a row says red — the light follows the rows (owner change (a)).
    mockGet.mockResolvedValue(payload([...ALL_GREEN.slice(0, 4), row('credit', 'red', 'payment_error', { time: '09:10' })]))
    render(<SystemHealthLight token="tok" />)
    await waitFor(() => expect(light().getAttribute('data-status')).toBe('red'))
    expect(mockGet).toHaveBeenCalledWith(false, { token: 'tok' })
  })

  it('is grey until the first answer, and stays so on a failed fetch', async () => {
    mockGet.mockRejectedValue(new Error('403'))
    render(<SystemHealthLight token="tok" />)
    expect(light().getAttribute('data-status')).toBe('unknown')
    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    expect(light().getAttribute('data-status')).toBe('unknown')
  })

  it('never fetches without a token', () => {
    render(<SystemHealthLight token={null} />)
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('checks again every five minutes while mounted', async () => {
    jest.useFakeTimers()
    try {
      mockGet.mockResolvedValue(payload(ALL_GREEN))
      const { unmount } = render(<SystemHealthLight token="tok" />)
      await act(async () => { await Promise.resolve() })
      expect(mockGet).toHaveBeenCalledTimes(1)
      await act(async () => { jest.advanceTimersByTime(HEALTH_POLL_MS) })
      expect(mockGet).toHaveBeenCalledTimes(2)
      unmount()
      await act(async () => { jest.advanceTimersByTime(HEALTH_POLL_MS * 2) })
      expect(mockGet).toHaveBeenCalledTimes(2)
    } finally {
      jest.useRealTimers()
    }
  })
})

describe('the panel', () => {
  const open = async (rows: HealthRow[]) => {
    mockGet.mockResolvedValue(payload(rows))
    render(<SystemHealthLight token="tok" />)
    await waitFor(() => expect(light().getAttribute('data-status')).not.toBe('unknown'))
    fireEvent.click(screen.getByRole('button', { name: /admin\.systemHealth\.open/ }))
    return screen.getByTestId('system-health-panel')
  }

  it('renders the five rows, the pill and the footer, and fetches again on open', async () => {
    const panel = await open([row('gemini', 'green', 'idle'), row('vision', 'amber', 'failures',
      { count: '1', attempts: '4' }), row('email', 'green'), row('cron', 'green', 'ok', { count: '26' }),
    row('credit', 'green')])
    for (const key of ['gemini', 'vision', 'email', 'cron', 'credit']) {
      expect(within(panel).getByTestId(`health-row-${key}`)).toBeTruthy()
    }
    expect(within(panel).getByText('T:admin.systemHealth.row.vision')).toBeTruthy()
    expect(within(panel).getByText('T:admin.systemHealth.line.read.failures{"count":"1","attempts":"4"}'))
      .toBeTruthy()
    expect(within(panel).getByText('T:admin.systemHealth.overall.amber')).toBeTruthy()
    expect(within(panel).getByText('T:admin.systemHealth.footer')).toBeTruthy()
    expect(within(panel).getByTestId('health-row-vision').getAttribute('data-status')).toBe('amber')
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThanOrEqual(2))
  })

  it('has no "View logs" link — owner change (b)', async () => {
    const panel = await open(ALL_GREEN)
    expect(within(panel).queryByRole('link')).toBeNull()
    expect(panel.textContent ?? '').not.toMatch(/log/i)
  })

  it('refresh asks the server to skip its cache, and keeps the panel open', async () => {
    const panel = await open(ALL_GREEN)
    fireEvent.click(within(panel).getByRole('menuitem', { name: 'T:admin.systemHealth.refresh' }))
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith(true, { token: 'tok' }))
    expect(screen.getByTestId('system-health-panel')).toBeTruthy()
  })
})

describe('the words', () => {
  it('names the worst job, its age and its cadence', () => {
    const text = lineText(t, row('cron', 'red', 'missed',
      { job: 'query-emails', amount: '26', unit: 'hours', cadence: 'hourly' }))
    expect(text).toContain('admin.systemHealth.line.cron.missed')
    expect(text).toContain('"age":"admin.systemHealth.unit.hours{\\"n\\":\\"26\\"}"')
    expect(text).toContain('"cadence":"admin.systemHealth.cadence.hourly"')
  })

  it('falls back to the code when a line has no string', () => {
    expect(lineText((k) => k, row('email', 'amber', 'brand_new_code'))).toBe('brand_new_code')
  })

  it('says today, yesterday or a date for last OK', () => {
    const now = new Date(2026, 9, 28, 15, 0)
    expect(lastOkText(t, null, now)).toBe('admin.systemHealth.lastOkNone')
    expect(lastOkText(t, new Date(2026, 9, 28, 14, 5).toISOString(), now))
      .toBe('admin.systemHealth.lastOk{"time":"14:05"}')
    expect(lastOkText(t, new Date(2026, 9, 27, 23, 10).toISOString(), now))
      .toBe('admin.systemHealth.lastOkYesterday{"time":"23:10"}')
    expect(lastOkText(t, new Date(2026, 9, 21, 9, 0).toISOString(), now))
      .toBe('admin.systemHealth.lastOk{"time":"21 Oct"}')
  })
})
