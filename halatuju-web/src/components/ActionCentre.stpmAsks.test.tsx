/**
 * @jest-environment jsdom
 *
 * STPM CGPA C4 — the two Check-2 asks a student answers on the onboarding STPM results page
 * (`stpm_grades_incomplete`, `stpm_koko_confirm`). Each card shows its own button linking to
 * /onboarding/stpm-grades (and sets the onboarding return to the application), and NO reply box —
 * the page's own save closes the ask on the server. Synthetic data only.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'
import { onboardingAskFor } from '@/lib/actionCentre'
import { peekOnboardingReturn } from '@/lib/scholarship'
import en from '@/messages/en.json'

const lookup = (key: string): string => {
  const v = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined), en)
  return typeof v === 'string' ? v : key
}

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ ...jest.requireActual('@/lib/i18n'), useT: () => ({ t: lookup, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null, CoachCard: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const ASK = (code: string): ResolutionItem => ({
  id: 77, fact: 'academic', code, params: {},
  prompt: '', kind: 'explanation', doc_type: '', status: 'open',
  source: 'check2' as ResolutionItem['source'], resolution_text: '',
  created_at: '2026-10-28T09:00:00.000Z', resolved_at: null,
})

beforeEach(() => {
  jest.clearAllMocks()
  window.sessionStorage.clear()
})

describe('onboardingAskFor', () => {
  it('maps both STPM asks to the STPM results page, and nothing else', () => {
    expect(onboardingAskFor('stpm_grades_incomplete')?.path).toBe('/onboarding/stpm-grades')
    expect(onboardingAskFor('stpm_koko_confirm')?.path).toBe('/onboarding/stpm-grades')
    expect(onboardingAskFor('semester_result_missing')).toBeNull()
  })
})

describe.each([
  ['stpm_grades_incomplete', 'Add the rest of your STPM subjects', 'Add my STPM subjects'],
  ['stpm_koko_confirm', 'Please confirm your co-curriculum score', 'Confirm my score'],
])('%s', (code, title, button) => {
  it('links to the STPM results page with no reply box', async () => {
    mockApi.getResolutionItems.mockResolvedValue({ open: [ASK(code)], resolved: [] })
    mockApi.listDocuments.mockResolvedValue({ documents: [] })
    const { container } = render(<ActionCentre token="test-token" studentName="Test Student" applicationId={7} />)
    await screen.findByText(title)
    const link = screen.getByRole('link', { name: button })
    expect(link.getAttribute('href')).toBe('/onboarding/stpm-grades')
    expect(container.querySelector('textarea')).toBeNull()
    fireEvent.click(link)
    expect(peekOnboardingReturn()).toBe('/scholarship/application')
  })
})
