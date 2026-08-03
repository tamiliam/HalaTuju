/**
 * @jest-environment jsdom
 *
 * `?ref=` capture — both referrals that wear that parameter name.
 *
 * ⚠ THIS TEST EXISTS BECAUSE A SOURCE-SHAPE GUARD WOULD HAVE PASSED THROUGHOUT THE BUG.
 * `KEY_SPONSOR_REF` was imported, read and cleared in `SponsorDetailsForm`, so any grep for the
 * key found it and looked healthy. It had no WRITER anywhere in the codebase, so
 * `referrals.attribute_referral(code, ...)` could never fire from the live UI — every attribution
 * fell through to the email fallback, which is why five of eight invitees still read "Invited"
 * after joining. Only running the hook shows it.
 *
 * The case-sensitivity assertion is the other half. A sponsor code is `secrets.token_urlsafe(9)`;
 * lower-casing it — exactly what the partner-code path must do — silently invalidates it, and a
 * wrong code and no code fail identically at the server.
 */
import { render } from '@testing-library/react'
import { useReferral } from '../useReferral'
import { KEY_REFERRAL_SOURCE, KEY_SPONSOR_REF } from '@/lib/storage'

let pathname = '/'
let params = new URLSearchParams()

jest.mock('next/navigation', () => ({
  useSearchParams: () => params,
  usePathname: () => pathname,
}))

function Harness() {
  useReferral()
  return null
}

const run = (path: string, search: string) => {
  pathname = path
  params = new URLSearchParams(search)
  render(<Harness />)
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  pathname = '/'
  params = new URLSearchParams()
})

describe('a sponsor invite code', () => {
  it('is captured at all — the writer that did not exist', () => {
    run('/sponsor', '?ref=Ab3xY9zQw')
    expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBe('Ab3xY9zQw')
  })

  it('keeps its capitalisation, because the code is case-sensitive', () => {
    run('/sponsor', '?ref=Ab3xY9zQw')
    expect(sessionStorage.getItem(KEY_SPONSOR_REF)).not.toBe('ab3xy9zqw')
  })

  it('is captured on the register page too, not only the landing', () => {
    run('/sponsor/register', '?ref=Ab3xY9zQw')
    expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBe('Ab3xY9zQw')
  })

  it('never lands in the student referral key', () => {
    // Otherwise a sponsor's invite code becomes their "how did you hear about us" the day they
    // apply as a student, and turns up as a junk chip against no organisation.
    run('/sponsor', '?ref=Ab3xY9zQw')
    expect(localStorage.getItem(KEY_REFERRAL_SOURCE)).toBeNull()
  })

  it('does not overwrite one already captured — first touch wins', () => {
    sessionStorage.setItem(KEY_SPONSOR_REF, 'FirstOne')
    run('/sponsor', '?ref=SecondOne')
    expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBe('FirstOne')
  })
})

describe('a partner referral code', () => {
  it('still lands in the student key, lower-cased, off a non-sponsor page', () => {
    run('/', '?ref=SMC')
    expect(localStorage.getItem(KEY_REFERRAL_SOURCE)).toBe('smc')
    expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBeNull()
  })

  it('does not overwrite one already captured', () => {
    localStorage.setItem(KEY_REFERRAL_SOURCE, 'cumig')
    run('/', '?ref=smc')
    expect(localStorage.getItem(KEY_REFERRAL_SOURCE)).toBe('cumig')
  })
})

it('writes nothing at all when there is no ref', () => {
  run('/sponsor', '')
  expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBeNull()
  expect(localStorage.getItem(KEY_REFERRAL_SOURCE)).toBeNull()
})
