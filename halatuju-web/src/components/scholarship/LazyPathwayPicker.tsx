'use client'

/**
 * The "My Plans" picker, fetched when it is drawn instead of riding in the page's first-load JS:
 * `/profile`'s section (third results route S3b, 2026-10-26) and, since 2026-10-30, the apply
 * form's Plans step (Scholarship My Plans redesign — `/scholarship/apply` fell ~2.7 kB).
 *
 * WHY: `/profile` sat 0.07 kB under its budget once the higher-results upload's words joined the
 * English catalogue every route loads. The picker (with its course, college and school pickers) is
 * drawn only while the "application" section is being EDITED; every other visit paid for it. The
 * budget is never raised; the weight is paid for here. Same shape as `LazyAliranPicker`: the
 * import is owned here (a failed chunk says so in place), nothing is drawn while it is in the air,
 * and the specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState, type ComponentProps, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Picker = typeof import('@/components/PathwayPicker')['default']
type Props = ComponentProps<Picker>

export default function LazyPathwayPicker(props: Props) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/components/PathwayPicker')
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
