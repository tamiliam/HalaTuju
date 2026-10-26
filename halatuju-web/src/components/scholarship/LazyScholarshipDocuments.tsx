'use client'

/**
 * The Documents tab, fetched when the student opens it instead of riding in
 * `/scholarship/application`'s first-load JS (third results route S3a/S3b, 2026-10-26).
 *
 * WHY: the higher-results upload added English words to every route and tipped this one, already
 * at its budget, about a kilobyte over. The Documents tab — the cards, every per-document checklist
 * and the income wizard — is drawn only on ONE step of the wizard, yet every visit to the page paid
 * for it. The budget is never raised; the weight is paid for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyInterviewBookingPanel` reason: a
 * failed chunk (a tab held across a deploy) says so in place instead of throwing the page away.
 * Nothing is drawn while the chunk is in the air (a moment, once per visit). The specifier is a
 * LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState, type ComponentProps, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Docs = typeof import('@/components/ScholarshipDocuments')['default']
type Props = ComponentProps<Docs>

export default function LazyScholarshipDocuments(props: Props) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/components/ScholarshipDocuments')
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
