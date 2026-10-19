/**
 * The two ways of jumping through the admin console's registry: the ⌘K palette's ranking
 * (`searchNav`) and the `G`-then-X chord (`chordTarget`, `CHORD_PREFIX`).
 *
 * ⚠ MOVED VERBATIM out of `navigation.ts` (request #39 Sprint 3, a moves-only commit), because that
 * file sat at its size line and Sprint 3 gives the registry rows a permission predicate. Every name
 * is re-exported from `navigation.ts`, so every importer is unchanged. The two functions take the
 * SHAPE they read (generic over the registry's item types) instead of importing those types back, so
 * this leaf imports nothing and no import loop forms (`importCycles.test.ts`). The bodies are
 * unchanged; only the type annotations name their types this way.
 */

/**
 * Rank navigable items for the ⌘K palette.
 *
 * Deliberately not a fuzzy-search dependency: there are ~20 reachable routes, and the ranking
 * that matters is "the word I typed starts this label" over "it appears somewhere in it".
 * Order: label starts with the query, then a word inside it starts with the query, then any
 * substring. Ties keep registry order, so a blank query lists the menu as the sidebar shows it.
 *
 * Reserved slots are excluded — offering to navigate somewhere that does not exist is worse
 * than not offering it.
 */
export function searchNav<I extends { placeholder?: boolean }>(
  query: string, items: readonly { item: I; label: string }[],
): I[] {
  const q = query.trim().toLowerCase()
  const live = items.filter(({ item }) => !item.placeholder)
  if (!q) return live.map(({ item }) => item)

  const rank = ({ label }: { label: string }): number => {
    const l = label.toLowerCase()
    if (l.startsWith(q)) return 0
    if (l.split(/\s+/).some((w) => w.startsWith(q))) return 1
    return l.includes(q) ? 2 : -1
  }

  return live
    .map((entry, i) => ({ entry, r: rank(entry), i }))
    .filter((x) => x.r >= 0)
    .sort((a, b) => (a.r - b.r) || (a.i - b.i))
    .map((x) => x.entry.item)
}

/** The first key of the jump. Held here so the listener, the hint chip and the tests agree. */
export const CHORD_PREFIX = 'g'

/**
 * The route a `G`-then-X jump should open, or undefined if that letter goes nowhere.
 *
 * Resolved against the VISIBLE groups rather than the whole registry, so a chord can never
 * carry someone to a page their sidebar does not offer. That is a courtesy, not a fence — the
 * page's own guard and the endpoint still refuse them (see `navigation.ts`'s module docstring) —
 * but a shortcut that lands on a 403 is a worse experience than one that does nothing.
 *
 * A reserved slot is skipped for the same reason `searchNav` skips it: there is no page there.
 */
export function chordTarget<I extends { placeholder?: boolean; state: string; chord?: string }>(
  letter: string,
  groups: readonly { items: readonly I[] }[],
): I | undefined {
  const want = letter.toUpperCase()
  for (const group of groups) {
    for (const item of group.items) {
      if (item.placeholder || item.state !== 'show') continue
      if (item.chord === want) return item
    }
  }
  return undefined
}
