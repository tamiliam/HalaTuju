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

/** Mount with this referral, and return the pill that reads `text`. */
const pill = async (referral_source: string, referred_by_org: Org, text: string) => {
  renderCockpit({ role: 'super', app: buildApplicationDetail('interviewing', {
    referral_source, referred_by_org,
  }) })
  await screen.findByText('Test Student 07')
  return screen.getByText(text)
}

describe('the referral pill', () => {
  it("names a new source by the linked organisation's served name — pill and tooltip", async () => {
    // Review fix (2026-10-08): a source added on Sources has no acronym entry, and it used to read
    // "Other" — a real partner's students filed under the catch-all.
    const el = await pill('newsrc', { id: 3, code: 'newsrc', name: 'A New Source' }, 'A New Source')
    expect(el.getAttribute('title')).toBe('A New Source')
  })

  it('reads a fixed choice from i18n', async () => {
    const el = await pill('social', null, 'Social')
    expect(el.getAttribute('title')).toBe('scholarship.apply.org.social')
  })

  it('shows the code (upper case in the pill), never a message key, when it has no name', async () => {
    const el = await pill('newsrc', { id: 3, code: 'another', name: 'Another Org' }, 'NEWSRC')
    expect(el.getAttribute('title')).toBe('newsrc')
  })

  it('keeps "Other" for other and the retired coordinators', async () => {
    expect(await pill('govind', null, 'Other')).toBeTruthy()
  })
})
