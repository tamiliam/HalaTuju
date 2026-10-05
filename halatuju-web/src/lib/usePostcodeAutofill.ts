'use client'

/**
 * The profile's postcode → City/State autofill, with the postcode table loaded ON DEMAND.
 *
 * Request #26: `malaysia-postcodes` (~11 kB gz) was a static import that only `/profile` paid for,
 * on every first load, for one interaction. It now loads on the fifth digit. Because the lookup is
 * now LATE, second review E: a result is applied only if nothing has moved since it was asked —
 * no newer postcode, and no City or State the student typed or picked meanwhile (`edited`). A
 * failed chunk only skips the autofill.
 */
import { useRef } from 'react'

export function usePostcodeAutofill(apply: (city: string, state: string) => void) {
  const turn = useRef(0)
  const applyRef = useRef(apply)
  applyRef.current = apply

  /** City, State, Cancel — anything that makes a pending lookup's answer stale. */
  const edited = () => { turn.current++ }

  /** Call with the postcode box's new value on every change. */
  const lookup = (postcode: string) => {
    const mine = ++turn.current
    if (postcode.length !== 5) return Promise.resolve()
    return import('malaysia-postcodes').then(({ findPostcode }) => {
      if (turn.current !== mine) return
      const result = findPostcode(postcode)
      if (result.found && result.city && result.state) applyRef.current(result.city, result.state)
    }).catch(() => {})
  }
  return { lookup, edited }
}
