/**
 * @jest-environment jsdom
 *
 * The referral pill in the cockpit header (per-gift referral sources, Sprint 2, 2026-10-08).
 *
 * Its tooltip used to be `scholarship.apply.org.<code>`, a message key per source on a fixed list.
 * Sources are now the registry's own rows, so a source added on Sources has no key, and the old
 * keys for the partner organisations were deleted. The tooltip reads the fixed three from i18n, a
 * source by the linked organisation's SERVED name, and otherwise the code — never a raw key.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

type Org = { id: number; code: string; name: string } | null

const pill = async (referral_source: string, referred_by_org: Org) => {
  renderCockpit({ role: 'super', app: buildApplicationDetail('interviewing', {
    referral_source, referred_by_org,
  }) })
  await screen.findByText('Test Student 07')
  return screen.getByText(referral_source === 'social' ? 'Social' : 'Other')
}

describe('the referral pill tooltip', () => {
  it("names a source by the linked organisation's served name", async () => {
    const el = await pill('newsrc', { id: 3, code: 'newsrc', name: 'A New Source' })
    expect(el.getAttribute('title')).toBe('A New Source')
  })

  it('reads a fixed choice from i18n', async () => {
    const el = await pill('social', null)
    expect(el.getAttribute('title')).toBe('scholarship.apply.org.social')
  })

  it('shows the code, never a message key, when it has no name to give', async () => {
    const el = await pill('newsrc', { id: 3, code: 'another', name: 'Another Org' })
    expect(el.getAttribute('title')).toBe('newsrc')
  })
})
