/**
 * @jest-environment jsdom
 *
 * Request #34 (2026-10-19): a reviewer's request is shown to the student as the task's TITLE, and
 * a multi-line request lost its line breaks there. The title now keeps them (`whitespace-pre-line`,
 * as `ScholarshipNextSteps` already does for `info_request_note`) — as text, never HTML.
 */
import { render, screen } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({
  __esModule: true, default: () => null, CoachCard: () => null,
}))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const PROMPT = 'Please send two things:\n1. Your bank statement\n2. Your offer letter'

const OFFICER_TASK: ResolutionItem = {
  id: 91, fact: 'other', code: 'officer_request', params: {},
  prompt: PROMPT, kind: 'explanation', doc_type: '', status: 'open',
  source: 'officer', resolution_text: '', created_at: '2026-10-19T09:00:00.000Z',
  resolved_at: null,
}

it("a reviewer's multi-line request keeps its line breaks in the title", async () => {
  mockApi.getResolutionItems.mockResolvedValue({ open: [OFFICER_TASK], resolved: [] })
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  render(<ActionCentre token="test-token" studentName="Test Student 07" applicationId={7} />)
  const heading = await screen.findByRole('heading', { level: 3, name: /Please send two things/ })
  expect(heading.textContent).toBe(PROMPT)                     // the newlines survive
  expect(heading.className).toContain('whitespace-pre-line')   // ...and the browser shows them
  expect(heading.querySelector('br')).toBeNull()               // text, never HTML
})
