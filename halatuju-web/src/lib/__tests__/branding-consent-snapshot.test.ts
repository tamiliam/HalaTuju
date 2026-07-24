/**
 * FROZEN consent byte-identity snapshot (platform Sprint 6, decision D5).
 *
 * `branding-consent.fixture.json` was captured from the CURRENT (untouched) `scholarship.consent`
 * strings — the exact bytes a student/guardian sees today — and is FROZEN. This test renders each
 * consent string the way `t()` does (branding AUTO_TOKENS injected beneath the call-site consent
 * params) and asserts it still equals the frozen bytes.
 *
 * Phase 1: the messages have no `{programmeName}` yet, so the branding params are inert and the
 * render equals today's copy. Phase 4 swaps `**BrightPath Bursary Programme**` for a
 * `{programmeName}`-templated form; with `programmeName = 'BrightPath Bursary'` (platform) it must
 * render the IDENTICAL bytes — this test proves it.
 *
 * IF THIS FAILS after a message edit: your change broke byte-identity. Fix the CHANGE, never the
 * fixture — the fixture is the pre-edit ground truth.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { PLATFORM, brandingParams, interpolateMessage, type Locale } from '@/lib/branding'
import frozen from './branding-consent.fixture.json'

const MESSAGES: Record<Locale, { scholarship: { consent: Record<string, string> } }> = {
  en: en as never,
  ms: ms as never,
  ta: ta as never,
}

// The fixed consent params used to capture the fixture (see the generator in the retro/scratch).
// These mirror ScholarshipConsent.tsx's call: student name/NRIC + the three derived pronouns.
const CONSENT_PARAMS: Record<string, string> = {
  student_name: 'Aisyah binti Rahman',
  student_nric: '051201-14-5678',
  he_or_she: 'she',
  his_or_her: 'her',
  him_or_her: 'her',
}

const CASES: Array<[Locale, 'text' | 'textMinor']> = [
  ['en', 'text'], ['en', 'textMinor'],
  ['ms', 'text'], ['ms', 'textMinor'],
  ['ta', 'text'], ['ta', 'textMinor'],
]

describe('consent byte-identity (FROZEN)', () => {
  it.each(CASES)('%s.%s renders the frozen bytes', (locale, key) => {
    const raw = MESSAGES[locale].scholarship.consent[key]
    // Render exactly as t() will: branding params first, explicit consent params win over them.
    const params = { ...brandingParams(PLATFORM, locale), ...CONSENT_PARAMS }
    const rendered = interpolateMessage(raw, params)
    expect(rendered).toBe((frozen as Record<string, string>)[`${locale}.${key}`])
  })

  it('the fixture covers all six consent surfaces', () => {
    expect(Object.keys(frozen)).toHaveLength(6)
  })
})
