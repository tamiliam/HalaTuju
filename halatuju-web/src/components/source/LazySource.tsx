'use client'

/**
 * `lazySource(load)` — a source console screen fetched as its own chunk the first time a SOURCE
 * user opens the page (source sign-in, 2026-10-30). The import is owned here, not by `next/dynamic`
 * (which re-throws a failed chunk load). Each PAGE writes its own one-line loader with a LITERAL specifier, so the
 * bundler emits a real chunk and a page carries only its own loader, not every screen's.
 *
 * WHY: the staff pages these share a route with (Overview, Applications, the cockpit, Scholars,
 * Profile, Invitations) are opened by staff far more often than by a source, and every route is
 * budgeted against the median (`npm run bundle-budget`). Imported statically, the source screens
 * put the median over its line (148.6 kB against 148); behind this boundary a staff visitor
 * downloads none of them.
 *
 * ⚠ WHEN A CHUNK FAILS (a tab held open across a deploy asks for a hash that is gone), it says so
 * in one line rather than leaving a blank page.
 *
 * OPTION: `quiet` draws nothing while the chunk is in the air (for a part that mostly draws nothing
 * once loaded, so a "Loading..." line would be a stray). The mechanics live in `LazyPart.tsx`; this
 * is the admin-words version (a non-admin route must use `lazyPart` and name its own words, or it
 * would reach the admin slice).
 */
import type { ComponentType } from 'react'
import { lazyPart } from '@/components/LazyPart'

export function lazySource<P extends object>(
  load: () => Promise<ComponentType<P>>,
  opts: { quiet?: boolean } = {},
): ComponentType<P> {
  return lazyPart(load, { failedKey: 'admin.sourceConsole.loadFailed', quiet: opts.quiet })
}
