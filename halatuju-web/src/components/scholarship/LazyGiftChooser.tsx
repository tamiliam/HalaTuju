'use client'

/**
 * The gift chooser, fetched only when a student actually has to choose.
 *
 * WHY (apply gift clarity, 2026-10-05): `/scholarship/apply` measured 272.15 kB against its 272 kB
 * budget once the gift work landed. The chooser is drawn only on a bare visit while several gifts
 * are open — most students arrive on a gift's own `?p=` link and never see it — so they should not
 * download it. The budget is never raised; the weight is paid for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyStpmSchoolPicker` reason: a failed
 * chunk says so in place instead of throwing the whole page away.
 *
 * Nothing is drawn while the chunk is in the air (a moment, once per visit). The specifier is a
 * LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'

import type { IntakeChoice } from '@/lib/api'
import { useT } from '@/lib/i18n'

type Chooser = typeof import('./GiftChooser')['default']

export default function LazyGiftChooser(props: {
  choices: IntakeChoice[]
  onPick: (code: string) => void
}) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<Chooser | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('./GiftChooser')
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
