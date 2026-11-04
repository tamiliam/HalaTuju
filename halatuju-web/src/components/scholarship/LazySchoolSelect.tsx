'use client'

/**
 * The apply form's School field, its suggesting component fetched as the page opens (Mobile M4).
 *
 * WHY: the phone form's draft and sticky Back / Continue bar (Mobile M4) left `/scholarship/apply` with
 * 0.13 kB of room under its first-load line, under the 0.25 kB the gate needs. The budget is never
 * raised; this pays for it. `SchoolSelect` (~0.65 kB) is a plain text field PLUS suggestions, and the
 * typed text is ALWAYS the value — so until the component arrives, or if its chunk never does, the
 * field below is that same plain text field: same value, same limit, same words. Nothing is lost and
 * nothing submitted changes; only the suggestions wait. (`/profile` and `/onboarding/profile` keep the
 * eager import — their lines have room.) The import starts on mount, long before the first tap.
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'

type Select = typeof import('@/components/SchoolSelect')['default']

export default function LazySchoolSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<Select | null>(null)
  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'sp' */ '@/components/SchoolSelect').then((m) => { if (live) setLoaded(() => m.default) }).catch(() => {})
    return () => { live = false }
  }, [])
  if (Loaded) return <Loaded value={value} onChange={onChange} />
  return (
    <input className="input" maxLength={255} value={value} autoComplete="off" data-testid="school-plain"
      placeholder={t('scholarship.apply.schoolSearchPlaceholder')} onChange={(e) => onChange(e.target.value)} />
  )
}
