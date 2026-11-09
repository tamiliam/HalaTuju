'use client'

import { useEffect, useState, type ComponentType } from 'react'
import type { ShellBannersProps } from './ShellBanners'

// ONE literal specifier, so the bundler emits one chunk (the `lazySource` house pattern, without its
// "Loading…" line: a banner that has not arrived is simply not there yet).
const load = () => import('@/components/admin/ShellBanners')

/**
 * The console's top-banner slot, fetched after first paint (staff nudges, 2026-11-08): the shell
 * rides on every admin route, so the banners stay off its first load. A failed chunk shows nothing —
 * a banner is a nudge and must never break the console.
 */
export function LazyShellBanners(props: ShellBannersProps) {
  const [Banners, setBanners] = useState<ComponentType<ShellBannersProps> | null>(null)
  useEffect(() => {
    let live = true
    load().then((m) => { if (live) setBanners(() => m.default) }).catch(() => {})
    return () => { live = false }
  }, [])
  return Banners ? <Banners {...props} /> : null
}
