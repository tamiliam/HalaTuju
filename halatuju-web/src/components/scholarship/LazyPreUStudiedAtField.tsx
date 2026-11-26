'use client'

/**
 * The "Pre-U institution" field, fetched when it is drawn instead of riding in the page's
 * first-load JS (pre-U sprint, 2026-11-26).
 *
 * WHY: `/scholarship/apply` went ~3 kB over its first-load budget when the field (with
 * `InstitutionPicker`) was imported statically. It is drawn only on step 3, and only for a student
 * holding STPM, Matriculation, Asasi or Diploma results; every other visit paid for it. The budget
 * is never raised; the weight is paid for here. Same shape as `LazyPathwayPicker`: the import is
 * owned here (a failed chunk says so in place), nothing is drawn while it is in the air, and the
 * specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState, type ComponentProps, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Field = typeof import('@/components/scholarship/PreUStudiedAtField')['default']
type Props = ComponentProps<Field>

export default function LazyPreUStudiedAtField(props: Props) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'pu' */ '@/components/scholarship/PreUStudiedAtField')
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
