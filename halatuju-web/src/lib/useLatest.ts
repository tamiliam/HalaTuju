import { useRef } from 'react'

/**
 * A ref that always holds the value of the latest render.
 *
 * Why it exists: an effect or loader often needs the CURRENT `t` (the translator) only to word an
 * error, yet `t` changes identity whenever the language or the message catalogue changes. Listing
 * `t` in the dependency array would re-run the effect (a refetch) on every language switch;
 * leaving it out needs a lint suppression. Reading `latest.current` inside the callback keeps the
 * effect firing on exactly the same inputs as before, with no suppression. The ref object itself
 * never changes, so listing it in a dependency array adds no firing.
 */
export function useLatest<T>(value: T) {
  const ref = useRef(value)
  ref.current = value
  return ref
}
