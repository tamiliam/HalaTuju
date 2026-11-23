'use client'

/**
 * The Trust & Transparency sections, fetched as their own chunk. Owned by `lazyPart`, not
 * `React.lazy`: a failed chunk says so in place (`sponsorPortal.loadFailed`) instead of crashing the
 * page. Nothing is drawn while the chunk is in the air.
 */
import { lazyPart } from '@/components/LazyPart'

export const LazyTrustView = lazyPart(
  () => import('./TrustView').then((m) => m.TrustView),
  { quiet: true, failedKey: 'sponsorPortal.loadFailed' },
)
