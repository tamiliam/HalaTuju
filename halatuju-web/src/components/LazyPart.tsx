'use client'

/**
 * `lazyPart(load, { failedKey, quiet })` — a part fetched as its own chunk, the import owned here and
 * not by `next/dynamic` / `React.lazy` (which re-throw a failed chunk load and crash the page). A
 * tab held open across a deploy asks for a hash that is gone; the part then says so in one line
 * (`failedKey`, which the CALLER names so this file holds no route's words and rides no slice).
 * `quiet` draws nothing while the chunk is in the air. `lazySource` (admin / source console) is
 * this with the admin words.
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

export function lazyPart<P extends object>(
  load: () => Promise<ComponentType<P>>,
  opts: { failedKey: string; quiet?: boolean },
): ComponentType<P> {
  return function LazyPartScreen(props: P) {
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
    if (failed) return <p className="text-sm text-critical-600" role="alert">{t(opts.failedKey)}</p>
    return opts.quiet ? null : <p className="text-sm text-ground-500">{t('common.loading')}</p>
  }
}
