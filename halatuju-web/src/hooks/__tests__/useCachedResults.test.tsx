/**
 * @jest-environment jsdom
 *
 * ⚠ THIS TEST EXISTS BECAUSE A SOURCE-SHAPE GUARD WOULD HAVE PASSED THROUGHOUT THE BUG. The old
 * dashboard imported every storage key, read them all and rendered a sensible empty state — any
 * grep found the machinery and it looked healthy. What was wrong was the ORDER: the read ran on
 * mount, and the cache it reads is written later, after `getProfile` returns. Nothing about the
 * source shows that; only running it through a hydration does.
 *
 * The live symptom (org request #11, 2026-08-13): a shortlisted applicant signing in as a student
 * was shown *No profile found. Please complete the onboarding.*
 */
import { render, act } from '@testing-library/react'
import { useCachedResults } from '../useCachedResults'
import { KEY_EXAM_TYPE, KEY_GRADES, KEY_PROFILE } from '@/lib/storage'
import type { CachedResults } from '@/lib/resultsCache'

const SPM_GRADES = JSON.stringify({ bm: 'A', eng: 'B+' })
const DEMOGRAPHICS = JSON.stringify({ gender: 'male', nationality: 'malaysian' })

let seen: { results: CachedResults; ready: boolean }

function Harness({ signal }: { signal: unknown }) {
  seen = useCachedResults(signal)
  return null
}

beforeEach(() => {
  localStorage.clear()
})

describe('useCachedResults', () => {
  it('RE-READS when the profile lands, so a sign-in does not read an empty cache forever', () => {
    // Mount BEFORE AuthProvider has written anything — exactly the first view after a sign-in.
    const { rerender } = render(<Harness signal={null} />)
    expect(seen.results.view).toBe('none')
    expect(seen.ready).toBe(true)          // we have read; we simply found nothing yet

    // AuthProvider's caching effect writes the profile it just fetched, then hands us the signal.
    act(() => {
      localStorage.setItem(KEY_GRADES, SPM_GRADES)
      localStorage.setItem(KEY_PROFILE, DEMOGRAPHICS)
    })
    rerender(<Harness signal={{ nric: '000000-00-0000' }} />)

    expect(seen.results.view).toBe('spm')  // was 'none' for the life of the page before the fix
  })

  it('does not flash back to loading on a re-read', () => {
    const { rerender } = render(<Harness signal={null} />)
    expect(seen.ready).toBe(true)
    rerender(<Harness signal={{ changed: true }} />)
    expect(seen.ready).toBe(true)
  })

  it('the Form 6 case end to end: STPM declared, only SPM results cached', () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
    localStorage.setItem(KEY_GRADES, SPM_GRADES)
    localStorage.setItem(KEY_PROFILE, DEMOGRAPHICS)

    render(<Harness signal={{ nric: '000000-00-0000' }} />)

    // NOT 'none' — this is the exact state that rendered "No profile found" for a student who
    // had completed onboarding and been shortlisted.
    expect(seen.results.view).toBe('spm')
  })
})
