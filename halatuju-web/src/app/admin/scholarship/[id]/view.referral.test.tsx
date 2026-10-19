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

/** Mount with this referral, and return the pill that reads `text`. The api serves the
 *  application's source under `source` (sources Sprint C); the old `referred_by_org` key for the
 *  same value was served one release and left in Sprint D. */
const pill = async (referral_source: string, source: Org, text: string) => {
  renderCockpit({ role: 'super', app: buildApplicationDetail('interviewing', {
    referral_source, source,
  }) })
  await screen.findByText('Test Student 07')
  return screen.getByText(text)
}

describe("the referral pill reads THIS application's source (sources Sprint C)", () => {
  it('reads the `source` key', async () => {
    const el = await pill('newsrc', { id: 3, code: 'newsrc', name: 'A New Source' }, 'A New Source')
    expect(el.getAttribute('title')).toBe('A New Source')
  })

  it('no longer reads the retired `referred_by_org` key (sources Sprint D)', async () => {
    renderCockpit({ role: 'super', app: buildApplicationDetail('interviewing', {
      referral_source: 'newsrc', source: null,
      ...({ referred_by_org: { id: 3, code: 'newsrc', name: 'A New Source' } } as object),
    }) })
    await screen.findByText('Test Student 07')
    expect(screen.queryByText('A New Source')).toBeNull()
    expect(screen.getByText('NEWSRC').getAttribute('title')).toBe('newsrc')
  })
})

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
