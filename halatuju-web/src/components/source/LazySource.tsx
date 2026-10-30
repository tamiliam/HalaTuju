'use client'

/**
 * `lazySource(load)` — a source console screen fetched as its own chunk the first time a SOURCE
 * user opens the page (source sign-in, 2026-10-30). Same arrangement as
 * `admin/LazyPermissionEditor.tsx`: the import is owned here, not by `next/dynamic` (which re-throws
 * a failed chunk load). Each PAGE writes its own one-line loader with a LITERAL specifier, so the
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
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

export function lazySource<P extends object>(load: () => Promise<ComponentType<P>>): ComponentType<P> {
  return function LazySourceScreen(props: P) {
    const { t } = useT()
    const [Screen, setScreen] = useState<ComponentType<P> | null>(null)
    const [failed, setFailed] = useState(false)
    useEffect(() => {
      let live = true
      load()
        .then((c) => { if (live) setScreen(() => c) })
        .catch(() => { if (live) setFailed(true) })
      return () => { live = false }
    }, [])
    if (Screen) return <Screen {...props} />
    if (!failed) return <p className="text-sm text-ground-500">{t('common.loading')}</p>
    return <p className="text-sm text-critical-600" role="alert">{t('admin.sourceConsole.loadFailed')}</p>
  }
}
