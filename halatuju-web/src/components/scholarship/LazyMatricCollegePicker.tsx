'use client'

/**
 * The apply form's matriculation college picker, with the college list fetched when a student
 * reaches it instead of riding in `/scholarship/apply`'s first-load JS — the twin of
 * `LazyStpmSchoolPicker`, for the same reason.
 *
 * WHY (apply gift clarity, 2026-10-05): `/scholarship/apply` measured 272.14 kB against its 272 kB
 * budget once the gift work landed. The list (`@/data/matric-colleges`, ~0.56 kB gz) is needed only
 * by a student who chose the matriculation route AND picked a track. The budget is never raised; the
 * weight is paid for here. The same list still loads statically on `/profile`, `/course/[id]` and
 * `/pathway/matric`, which use it on arrival.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — a failed chunk says so in place instead of
 * throwing the whole form away mid-application. Nothing is drawn while the chunk is in the air; the
 * label above it is drawn by the page. The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import InstitutionPicker from '@/components/InstitutionPicker'

type Colleges = typeof import('@/data/matric-colleges')

export default function LazyMatricCollegePicker({ track, value, onChange, placeholder }: {
  track: string
  value: string
  onChange: (name: string) => void
  placeholder?: string
}) {
  const { t } = useT()
  const [colleges, setColleges] = useState<Colleges | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/data/matric-colleges')
      .then(m => { if (live) setColleges(m) })
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
  if (!colleges) return null
  return (
    <InstitutionPicker
      options={colleges.collegesForTrack(track).map((c) => ({ name: c.name, hint: c.state }))}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
    />
  )
}
