/**
 * @jest-environment jsdom
 *
 * H8: "See a sample". The link shows on cards that have a sample and not on ones without; it opens
 * the viewer (drawing + caption "never send this"); Close and Escape shut it; a tap enlarges the picture.
 * Mounted through the REAL Action Centre card and the Documents tab card, with the real English words.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import { DocSample } from './DocSample'
import { SAMPLE_FILE } from '@/lib/docSamples'
import { SingleDocCard } from './ScholarshipDocuments/cards'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'
import { interpolateMessage } from '@/lib/branding'
import en from '@/messages/en.json'

const lookup = (key: string, params?: Record<string, string>): string => {
  const value = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined), en)
  return typeof value === 'string' ? interpolateMessage(value, params) : key
}

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ ...jest.requireActual('@/lib/i18n'), useT: () => ({ t: lookup, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null, CoachCard: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const item = (over: Partial<ResolutionItem>): ResolutionItem => ({
  id: 1, fact: 'income', code: 'x', params: {}, prompt: '', kind: 'doc', doc_type: 'parent_ic', status: 'open',
  source: 'check2' as ResolutionItem['source'], resolution_text: '', created_at: '2026-11-01T09:00:00.000Z',
  resolved_at: null, ...over,
})

describe('DocSample (the link and the viewer)', () => {
  it('opens with the title, drawing and caption, then closes', () => {
    render(<DocSample docType="parent_ic" />)
    expect(screen.queryByTestId('sample-viewer')).toBeNull()
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByTestId('sample-caption').textContent).toBe(
      'This is a sample drawing, not a real parent/guardian IC. Do not upload it.')
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/mykad.svg')
    fireEvent.click(screen.getByTestId('sample-close'))
    expect(screen.queryByTestId('sample-viewer')).toBeNull()
  })

  it('the caption names the type (a payslip, an EPF statement)', () => {
    const { unmount } = render(<DocSample docType="salary_slip" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByTestId('sample-caption').textContent).toContain('not a real salary slip')
    unmount()
    render(<DocSample docType="epf" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByTestId('sample-caption').textContent).toContain('not a real EPF statement')
  })

  it('shows "What we check" with 1 to 4 real points for EVERY mapped type', () => {
    for (const docType of Object.keys(SAMPLE_FILE)) {
      const { unmount } = render(<DocSample docType={docType} />)
      fireEvent.click(screen.getByText('See a sample'))
      expect(screen.getByTestId('sample-check-heading').textContent).toBe('What we check')
      const points = Array.from(screen.getByTestId('sample-check-list').querySelectorAll('li'))
      expect(points.length).toBeGreaterThanOrEqual(1)
      expect(points.length).toBeLessThanOrEqual(4)
      // A missing key would show the raw key.
      points.forEach((li) => expect(li.textContent).not.toContain('scholarship.docs'))
      unmount()
    }
  })

  it('shows the Matriculation points on a Matriculation card', () => {
    render(<DocSample docType="higher_results" kind="matric" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByTestId('sample-check-list').textContent).toContain('College name and matric number')
  })

  it('Escape closes it', () => {
    render(<DocSample docType="salary_slip" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/payslip.svg')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByTestId('sample-viewer')).toBeNull()
  })

  it('a tap on the picture enlarges it and a second tap shrinks it', () => {
    render(<DocSample docType="epf" />)
    fireEvent.click(screen.getByText('See a sample'))
    const img = screen.getByRole('img') as HTMLImageElement
    expect(img.style.width).toBe('100%')
    fireEvent.click(screen.getByTestId('sample-zoom'))
    expect(img.style.width).toBe('220%')
    fireEvent.click(screen.getByTestId('sample-zoom'))
    expect(img.style.width).toBe('100%')
  })

  it('shows nothing for "other"', () => {
    const { container } = render(<DocSample docType="other" />)
    expect(container.innerHTML).toBe('')
  })

  it('a Matriculation higher-results card opens the Matriculation drawing', () => {
    render(<DocSample docType="higher_results" kind="matric" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/higher_results_matric.svg')
  })
})

describe('on the cards', () => {
  it('an Action Centre document card has the link; a typed-reply card does not', async () => {
    mockApi.getResolutionItems.mockResolvedValue({
      open: [item({ id: 1, doc_type: 'parent_ic', params: { household_member: 'mother' } }),
        item({ id: 2, kind: 'explanation', doc_type: '', code: 'explain_x' })],
      resolved: [],
    })
    mockApi.listDocuments.mockResolvedValue({ documents: [] })
    render(<ActionCentre token="tkn" studentName="Test Student 07" applicationId={7} />)
    await waitFor(() => expect(screen.getAllByText('To do').length).toBeGreaterThan(0))
    expect(screen.getAllByText('See a sample')).toHaveLength(1)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/mykad.svg')
  })

  it('an Action Centre higher-results card maps to the matric sample, and to STPM', async () => {
    mockApi.getResolutionItems.mockResolvedValue({
      open: [item({ id: 3, doc_type: 'higher_results', params: { results_kind: 'matric' } })],
      resolved: [],
    })
    mockApi.listDocuments.mockResolvedValue({ documents: [] })
    const matric = render(<ActionCentre token="tkn" studentName="Test Student 07" applicationId={7} />)
    await waitFor(() => expect(screen.getAllByText('See a sample')).toHaveLength(1))
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/higher_results_matric.svg')
    matric.unmount()

    mockApi.getResolutionItems.mockResolvedValue({
      open: [item({ id: 4, doc_type: 'higher_results', params: { results_kind: 'stpm' } })],
      resolved: [],
    })
    render(<ActionCentre token="tkn" studentName="Test Student 07" applicationId={7} />)
    await waitFor(() => expect(screen.getAllByText('See a sample')).toHaveLength(1))
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/higher_results_stpm.svg')
  })

  it('the Documents tab card has the link', () => {
    render(<SingleDocCard docType="water_bill" docs={[]} busyKeys={new Set()} onUpload={() => {}}
      onDelete={() => {}} t={lookup} token="tkn" lang="en" />)
    fireEvent.click(screen.getByText('See a sample'))
    expect(screen.getByRole('img').getAttribute('src')).toBe('/samples/water_bill.svg')
  })
})
