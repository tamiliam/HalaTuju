'use client'

/**
 * "Pre-U institution" — where they COMPLETED their STPM, Matriculation, Asasi or Diploma (pre-U
 * sprint, 2026-11-26; the profile's `pre_u_studied_at`, NOT the destination `pre_u_institution`).
 * One field for apply step 3 (required) and the profile (not required).
 *
 * At rest: the label, the Tip box and the box. While the box has focus: the four route chips
 * (the first follows their results, `firstPreURoute`) and the search list, which ends with
 * 'Not in the list? Use "x" as typed' (free text is allowed).
 *
 * The lists (the Form 6 list is ~15 kB gz) are fetched when the field is drawn, never in the
 * route's first-load JS — `loadPreULists`. Until they arrive (or if the chunk fails) the box still
 * takes free text, so they are never stuck. The caller decides WHETHER to draw it (`showsPreUStudiedAt`).
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import FieldLabel from '@/components/FieldLabel'
import InstitutionPicker from '@/components/InstitutionPicker'
import { firstPreURoute, loadPreULists, PRE_U_ROUTES, type PreULists, type PreURoute } from '@/lib/preULists'

export default function PreUStudiedAtField({ resultsHeld, value, onChange, variant }: {
  resultsHeld: string | null | undefined
  value: string
  onChange: (name: string) => void
  variant: 'apply' | 'profile'
}) {
  const { t } = useT()
  const [lists, setLists] = useState<PreULists | null>(null)
  const [route, setRoute] = useState<PreURoute>(() => firstPreURoute(resultsHeld))
  const [focused, setFocused] = useState(false)
  // Review round 1: the held results often arrive after mount (the profile loads late) — the first
  // chip follows them then too. A chip they tapped stays until the results themselves change.
  useEffect(() => { setRoute(firstPreURoute(resultsHeld)) }, [resultsHeld])

  useEffect(() => {
    let live = true
    loadPreULists().then((l) => { if (live) setLists(l) }).catch(() => { /* free text still works */ })
    return () => { live = false }
  }, [])

  const tip = variant === 'apply'
    ? t(`scholarship.preU.tipApply.${resultsHeld === 'matric' || resultsHeld === 'asasi' || resultsHeld === 'diploma' ? resultsHeld : 'stpm'}`)
    : t('scholarship.preU.tipProfile')
  return (
    <div>
      <FieldLabel required={variant === 'apply'}>{t('scholarship.preU.label')}</FieldLabel>
      <p className="mb-2 rounded-lg bg-primary-50 px-3 py-2 text-sm text-ground-700">{tip}</p>
      {focused && (
        <div className="mb-2 flex flex-wrap gap-1.5" data-testid="pre-u-chips">
          {PRE_U_ROUTES.map((r) => (
            // mousedown is held so the box keeps its focus (and the list stays open) on a chip tap.
            <button key={r} type="button" aria-pressed={r === route}
              onMouseDown={(e) => e.preventDefault()} onClick={() => setRoute(r)}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${r === route ? 'bg-brand-fill text-brand-fill-ink' : 'bg-ground-100 text-ground-700'}`}>
              {t(`scholarship.preU.chip.${r}`)}
            </button>
          ))}
        </div>
      )}
      <InstitutionPicker options={lists ? lists[route] : []} value={value} onChange={onChange}
        placeholder={t('scholarship.preU.placeholder')} allowCustom customRow onFocusChange={setFocused} />
    </div>
  )
}
