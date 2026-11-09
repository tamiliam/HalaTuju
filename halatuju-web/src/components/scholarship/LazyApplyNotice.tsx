'use client'

/**
 * The closed-gift and already-applied cards, fetched only when one is drawn (see `ApplyNotice`).
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyGiftChooser` reason: a failed chunk
 * says so in place instead of throwing the whole page away. Nothing is drawn while the chunk is in
 * the air (a moment, once per visit). The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'

import { useT } from '@/lib/i18n'

type Notice = typeof import('./ApplyNotice')['default']

export default function LazyApplyNotice(props: { kind: 'closed' | 'applied'; onSeeOpen?: () => void }) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<Notice | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'an' */ './ApplyNotice')
      .then((m) => { if (live) setLoaded(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])

  if (failed) {
    return (
      <p role="alert" className="rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
        {t('verifyEmail.networkError')}
      </p>
    )
  }
  return Loaded ? <Loaded {...props} /> : null
}
