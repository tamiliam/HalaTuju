/**
 * The card-name comparison (#67 scope 3), on its own so /scholarship/apply — which needs only
 * this — does not carry the IC editor's other rules in its first load.
 */

/**
 * Is this name the card's own, letter for letter, once case and spaces are set aside? (#67 scope 3
 * review.) The server's lock allows exactly that (it also tidies "A / P" to "A/P"); so does this,
 * because spaces are dropped. No card name is never a match.
 */
export function sameLettersAsCard(name: string | null | undefined, cardName: string | null | undefined): boolean {
  const letters = (s: string | null | undefined) => (s || '').toLowerCase().replace(/\s+/g, '')
  return !!letters(cardName) && letters(name) === letters(cardName)
}
