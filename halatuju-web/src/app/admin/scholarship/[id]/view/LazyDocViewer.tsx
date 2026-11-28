'use client'

/**
 * The document viewer, fetched as its own chunk only when the officer opens a document.
 *
 * WHY (chip S1 landing, 2026-11-28): chip S1 gave the viewer its Checks panel (`DocChecksPanel`),
 * and `/admin/scholarship/[id]` read 250.225 kB first-load against the 250 kB ceiling. The viewer
 * draws nothing until a document is open (`doc` null returns null), yet it and its panel rode in
 * every visit. The budget is never raised; the weight is paid for here. The cockpit mounts this
 * wrapper ONLY while `viewerDoc` is set, the same condition as the viewer's own early return, so it
 * never hides a viewer that would draw. `quiet` keeps the brief load silent (no loading line at the
 * top of the case page); a failed chunk still says so in place.
 *
 * The import is owned by `lazySource` with a LITERAL specifier so the bundler emits a real chunk.
 */
import { lazySource } from '@/components/source/LazySource'

export const LazyDocViewer = lazySource(
  () => import('@/components/DocViewer').then((m) => m.default),
  { quiet: true },
)
