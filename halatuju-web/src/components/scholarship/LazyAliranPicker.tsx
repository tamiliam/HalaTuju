'use client'

/**
 * The apply form's PISMP school-type (Aliran) picker, fetched when a student reaches it instead of
 * riding in `/scholarship/apply`'s first-load JS.
 *
 * WHY (apply gift clarity, 2026-10-05): `/scholarship/apply` measured 272.14 kB against its 272 kB
 * budget once the gift work landed. The picker is drawn only for a student who is SURE, holds SPM
 * results, chose the teacher-training (PISMP) pathway and has eligible courses — every other
 * applicant was paying for it. The budget is never raised; the weight is paid for here. The same
 * picker still loads statically inside `PathwayPicker` (/profile), which is not this route.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyStpmSchoolPicker` reason: a failed
 * chunk says so in place instead of throwing the whole form away mid-application.
 *
 * Nothing is drawn while the chunk is in the air (a moment, once per visit); the label above it is
 * drawn by the page. The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'

import { useT } from '@/lib/i18n'
import type { PismpAliran } from '@/lib/scholarship'

type Picker = typeof import('@/components/AliranPicker')['default']

export default function LazyAliranPicker(props: {
  alirans: PismpAliran[]
  value: string
  onChange: (aliran: PismpAliran) => void
}) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<Picker | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/components/AliranPicker')
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
