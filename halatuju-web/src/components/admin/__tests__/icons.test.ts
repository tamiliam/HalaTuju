import { ICON_NAMES } from '@/components/admin/icons'
import { NAV_GROUPS } from '@/lib/navigation'

/**
 * Every menu row must have a glyph — the guard that did not exist while two rows had none.
 *
 * ⚠ WHY THIS FILE EXISTS. `Sidebar` renders `<Icon name={item.id} />`, and `Icon` falls back to a
 * DOT when the name is unknown. That fallback is correct in production (a missing picture must not
 * throw inside the console shell) and is exactly why the defect was invisible: `orgSettings` was
 * added on 2026-09-03 with no glyph, `faq` had never had one, and both rendered as a bare dot for
 * days with every gate green. The owner found it by looking at the screen.
 *
 * The lesson it is written from (docs/lessons.md, Layer 1 F7b): **when an injected fault produces
 * silence, do not move on because the code is now correct — ask which test should have failed, and
 * write it.**
 *
 * ⚠ BOTH SIDES ARE DERIVED AT RUNTIME, never restated here. A hand-written list of ids is the
 * thing that falls behind the registry — the F6/F7c lesson, that a guard is blind to whatever is
 * outside its scope, and a literal list is the smallest possible scope.
 */

// ⚠ `Array.from`, NOT a spread. A `Set` is not iterable under this tsconfig's target, and the
// spread pushes the project's `tsc` baseline from 24 to 25 — which TD-221 counts, and which the
// same mistake already cost once in `page.test.tsx`. Second instance; hence this note.
const navIds = () => Array.from(new Set(NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id))))

describe('the console icon set covers the navigation registry', () => {
  it('has a glyph for every menu row, so none can fall back to the dot', () => {
    const missing = navIds().filter((id) => !ICON_NAMES.includes(id))
    // Named rather than counted: a failure has to say WHICH row to draw.
    expect(missing).toEqual([])
  })

  it('reads a registry that actually has rows, so an empty scan cannot pass', () => {
    // The self-check the first version of this guard would have wanted: `[].filter(...)` is `[]`,
    // so a registry that failed to import would produce a green tick and prove nothing.
    expect(navIds().length).toBeGreaterThan(15)
    expect(navIds()).toContain('orgSettings')
    expect(navIds()).toContain('faq')
  })

  it('still keeps `dot` as the fallback, because a missing glyph must not throw in production', () => {
    // The guard above makes the fallback unreachable by an honest path. It stays reachable by an
    // accident — that is its whole job — and a future sprint deleting it would trade a dot for a
    // crash in the shell that renders every admin page.
    expect(ICON_NAMES).toContain('dot')
  })
})
