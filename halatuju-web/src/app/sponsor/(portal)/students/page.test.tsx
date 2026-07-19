/**
 * @jest-environment jsdom
 *
 * Browse grid redesign: image-led cards with conditional badges, a null-safe countdown,
 * and no programme-months on the card (that fact lives only on the detail sidebar).
 */
import { render, screen } from '@testing-library/react'
import StudentsPage from './page'
import type { SponsorPoolCard } from '@/lib/api'

jest.mock('next/link', () => ({ __esModule: true, default: ({ children }: { children: React.ReactNode }) => children }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const pool: SponsorPoolCard[] = [
  {
    id: 1, ref: 'S-AAA', state: 'Perak', school: 'SMK A', field: 'engineering', course: 'Diploma Mekanikal',
    academic: 'SPM · 7A', institution: 'Politeknik Ungku Omar', blurb: 'A determined leaver.',
    funding_categories: ['tuition'], programme_months: 24, award_amount: '3000', funded_amount: '0',
    progress_state: null, support_status: null, enrolment_verified: true,
    field_image_slug: 'kejuruteraan', reporting_date: '2099-09-01',
  },
  {
    id: 2, ref: 'S-BBB', state: 'Kedah', school: 'SMK B', field: 'health', course: 'Diploma Kejururawatan',
    academic: 'SPM · 5A', institution: '', blurb: '', funding_categories: [],
    programme_months: 36, award_amount: '2000', funded_amount: '0', progress_state: null, support_status: null,
    enrolment_verified: false, field_image_slug: '', reporting_date: null,
  },
]

jest.mock('@/lib/sponsor-portal-context', () => ({ useSponsorPortal: () => ({ pool }) }))

describe('sponsor browse grid', () => {
  it('renders image-led cards with the right badges and no months', () => {
    render(<StudentsPage />)
    // both refs shown (getByText throws if absent)
    expect(screen.getByText('S-AAA')).toBeTruthy()
    expect(screen.getByText('S-BBB')).toBeTruthy()
    // "Verified" shield on every card; "Enrolment verified" only on the confirmed one
    // (labels carry an emoji prefix, so match on substring).
    expect(screen.getAllByText('sponsorPool.verified', { exact: false })).toHaveLength(2)
    expect(screen.getAllByText('sponsorPool.enrolmentVerified', { exact: false })).toHaveLength(1)
    // countdown shows for the future-dated card, hidden for the null-date card
    expect(screen.getByText('sponsorPool.daysAway', { exact: false })).toBeTruthy()
    // programme months never appear on a card (detail-only fact)
    expect(screen.queryByText('sponsorPool.overMonths')).toBeNull()
    expect(screen.queryByText(/24 months/)).toBeNull()
    // the "fully fund" CTA on every card
    expect(screen.getAllByText('sponsorPool.fullyFund')).toHaveLength(2)
  })

  it('never renders a — placeholder (Phase 4d no-dash rule)', () => {
    render(<StudentsPage />)
    expect(screen.queryByText('—')).toBeNull()
  })
})
