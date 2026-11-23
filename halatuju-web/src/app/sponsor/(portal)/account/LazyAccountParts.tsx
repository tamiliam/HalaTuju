'use client'

/**
 * My Account's two heavy parts, each its own chunk. The import is owned by `lazyPart`, not
 * `React.lazy`: a chunk that cannot be fetched (a tab held across a deploy) says so in place
 * (`sponsorPortal.partLoadFailed`: the account itself did load) instead of crashing the
 * whole page to the root error page. Nothing is drawn while the chunk is in the air.
 */
import { lazyPart } from '@/components/LazyPart'

const OPTS = { quiet: true, failedKey: 'sponsorPortal.partLoadFailed' }

export const LazyInviteFriends = lazyPart(() => import('./InviteFriends').then((m) => m.InviteFriends), OPTS)
export const LazyGivingStatement = lazyPart(() => import('./GivingStatement').then((m) => m.GivingStatement), OPTS)
