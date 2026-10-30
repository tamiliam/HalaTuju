'use client'

/**
 * INSTITUTION FIRST, THEN COURSE — the offer branch of the scholarship "My Plans" step for every
 * programme pathway and for an STPM degree (Scholarship My Plans redesign, owner rulings 2026-10-30).
 *
 *   university / Asasi / degree     University → Course
 *   polytechnic, community college,
 *   MARA, ILJTM, ILKBS, other public
 *   skills training                 State → Polytechnic or campus → Course
 *
 * The student names the place she holds (or awaits) an offer for, so the box she types into holds
 * one institution's courses, never a whole pathway's. The lists are the catalogue, unfiltered,
 * unless "Eligible only" passes an `allowed` set (`lib/planPicker.ts`). The pick carries the
 * institution's catalogue name and id into `chosen_programme`, which the offer-letter comparison
 * reads. The chosen state and institution are local: changing either clears the course below it.
 */
import { useEffect, useState } from 'react'

import FieldLabel from '@/components/FieldLabel'
import ProgrammePicker from '@/components/ProgrammePicker'
import type { PathwayOfferings } from '@/lib/api'
import { useT } from '@/lib/i18n'
import {
  DEGREE_PATHWAY, asksStateFirst, coursesAt, institutionKind, institutionOf, offeringInstitutions,
  offeringStates, type Allowed,
} from '@/lib/planPicker'
import type { ChosenProgramme } from '@/lib/scholarship'

export default function InstitutionCoursePicker({
  pathway, offerings, loading, allowed, value, onChange, apply = false,
}: {
  pathway: string
  offerings: PathwayOfferings | null
  loading: boolean
  allowed: Allowed
  value: ChosenProgramme | null
  onChange: (cp: ChosenProgramme | null) => void
  /** the apply form: required marks and tips on the labels */
  apply?: boolean
}) {
  const { t } = useT()
  const stateFirst = asksStateFirst(pathway)
  const [state, setState] = useState('')
  const [instId, setInstId] = useState('')

  // Re-open on the saved pick (editing on /profile, or coming back to the step).
  useEffect(() => {
    const inst = institutionOf(offerings, value)
    if (inst) { setInstId(inst.id); setState(inst.state) }
  }, [offerings, value])

  if (loading || !offerings) {
    return <input className="input text-ground-placeholder" disabled readOnly value={t('scholarship.apply.plan.loading')} />
  }

  const kind = institutionKind(pathway)
  const states = stateFirst ? offeringStates(offerings, allowed) : []
  const institutions = stateFirst && !state ? [] : offeringInstitutions(offerings, stateFirst ? state : null, allowed)
  const inst = institutions.find((i) => i.id === instId) ?? null
  const courses = inst ? coursesAt(offerings, inst.id, allowed) : []
  const instLabel = t(`scholarship.apply.plan.institutionLabel.${kind}`)
  const courseLabel = t(pathway === DEGREE_PATHWAY ? 'scholarship.apply.plan.degreeLabel' : 'scholarship.apply.plan.programmeLabel')

  if ((stateFirst ? states : institutions).length === 0) {
    return (
      <p className="rounded-xl border border-caution-200 bg-caution-50 p-3 text-sm text-ground-600">
        {t('scholarship.apply.plan.noProgrammes')}
      </p>
    )
  }

  const chooseState = (s: string) => { setState(s); setInstId(''); if (value) onChange(null) }
  const chooseInst = (id: string) => { setInstId(id); if (value) onChange(null) }

  return (
    <div className="space-y-4">
      <div className={stateFirst ? 'grid gap-4 sm:grid-cols-2' : ''}>
        {stateFirst && (
          <div>
            <FieldLabel required={apply}>{t('scholarship.apply.plan.stateLabel')}</FieldLabel>
            <select className="input" aria-label={t('scholarship.apply.plan.stateLabel')} value={state}
              onChange={(e) => chooseState(e.target.value)}>
              <option value="">{t('scholarship.apply.plan.statePlaceholder')}</option>
              {states.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        )}
        {(!stateFirst || state) && (
          <div>
            <FieldLabel required={apply} tip={apply ? t('scholarship.apply.plan.institutionTip') : undefined}>{instLabel}</FieldLabel>
            <select className="input" aria-label={instLabel} value={inst ? inst.id : ''}
              onChange={(e) => chooseInst(e.target.value)}>
              <option value="">{t('scholarship.apply.plan.institutionPlaceholder')}</option>
              {institutions.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
            </select>
          </div>
        )}
      </div>
      {inst && (
        <div>
          <FieldLabel required={apply} tip={apply ? t('scholarship.apply.plan.programmeTip') : undefined}>{courseLabel}</FieldLabel>
          <ProgrammePicker
            key={inst.id}
            courses={courses}
            value={value}
            onChange={(cp) => onChange(cp ? { ...cp, institution: inst.name, institutionId: inst.institution_id } : null)}
          />
          <p className="mt-1 text-xs text-ground-500">
            {t('scholarship.apply.plan.coursesHere', { count: String(courses.length) })}
          </p>
        </div>
      )}
    </div>
  )
}
