'use client'

/**
 * The Action Centre, fetched when a student's status shows it instead of riding in the first-load
 * JS of `/scholarship/application` (student-help bundle trim, 2026-11-17).
 *
 * WHY: the student-help batch (H4-H9) grew the Action Centre and its words, and tipped
 * `/scholarship/application` about 8 kB over its line. The Action Centre draws nothing until its
 * task fetch lands, so loading its code (and the Documents slice of words it now carries) first
 * costs one short wait before that fetch, and no first-paint change. The budget is never raised;
 * the weight is paid for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyScholarshipDocuments` reason: a
 * failed chunk (a tab held across a deploy) says so in place instead of throwing the page away.
 * Nothing is drawn while the chunk is in the air. The specifier is a LITERAL so the bundler emits
 * a real chunk; it shares the Documents tab's chunk name, as the two share most of their code.
 */
import { useEffect, useState, type ComponentProps, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Centre = typeof import(/* webpackChunkName: 'sd' */ '@/components/ActionCentre')['default']
type Props = ComponentProps<Centre>

export default function LazyActionCentre(props: Props) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'sd' */ '@/components/ActionCentre')
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
