'use client'

/**
 * The apply form's Form 6 school picker, with the STPM centre list fetched when a student reaches
 * it instead of riding in `/scholarship/apply`'s first-load JS.
 *
 * WHY (TD-309 follow-up, 2026-09-30): `/scholarship/apply` sat at 285,405 gz bytes against its
 * 285 kB budget — above the line numerically, passing only on the build's rounding, the exact
 * shape TD-306 failed on in the deploy gate. The centre list (`@/data/stpm-schools`, ~15 kB gz) is
 * needed only by a student who chose the STPM route AND picked a stream, so every other applicant
 * was paying for it. The budget is never raised; the weight is paid for here. The same list still
 * loads statically on `/profile`, `/course/[id]` and `/pathway/stpm`, which use it on arrival.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyPostAwardTask` reason: a failed
 * chunk says so in place instead of throwing the whole form away mid-application.
 *
 * ⚠ NOTHING IS DRAWN WHILE THE CHUNK IS IN THE AIR (a moment, once per visit): an empty picker
 * would invite a search that can only find nothing. The label above it is drawn by the page.
 *
 * The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import InstitutionPicker from '@/components/InstitutionPicker'

type Schools = typeof import('@/data/stpm-schools')

export default function LazyStpmSchoolPicker({ stream, value, onChange, placeholder }: {
  stream: string
  value: string
  onChange: (name: string) => void
  placeholder?: string
}) {
  const { t } = useT()
  const [schools, setSchools] = useState<Schools | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/data/stpm-schools')
      .then(m => { if (live) setSchools(m) })
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
  if (!schools) return null
  return (
    <InstitutionPicker
      options={schools.stpmSchoolsForStream(stream).map((s) => ({ name: s.name, hint: s.state }))}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
    />
  )
}
