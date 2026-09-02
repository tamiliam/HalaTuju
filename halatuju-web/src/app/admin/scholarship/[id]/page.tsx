'use client'

/**
 * The officer cockpit's ROUTE, and nothing else.
 *
 * ⚠ THE SCREEN ITSELF IS `./view.tsx`, AND `next build` IS WHY. Next type-checks a page module and
 * rejects three things in turn — a defaulted first parameter, ANY prop beyond its own `PageProps`,
 * and ANY extra module-level export. So a page cannot take an id as a prop and cannot export the
 * component that does. The view moved out whole; this file hands it no id, so it falls back to
 * `useParams()`, which is where production's id has always come from.
 *
 * The move is what let the sandbox finally MOUNT this surface (Layer 1 F7c) — it is 3,500 lines
 * and the only screen in the arc nobody had ever opened in a browser. **The body did not change.**
 *
 * ⚠ `tsc --noEmit`, `jest` and `next lint` were ALL green while this was still broken. The build
 * is the only gate that reads Next's page contract.
 */
import { AdminScholarshipDetailView } from './view'

export default function AdminScholarshipDetailPage() {
  return <AdminScholarshipDetailView />
}
