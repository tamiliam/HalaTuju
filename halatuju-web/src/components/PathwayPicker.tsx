'use client'

/**
 * THE SCHOLARSHIP "MY PLANS" PICKER — one component for `/scholarship/apply` (its Plans step) and
 * `/profile` ("Your Plans", where a shortlisted student locked out of /apply can still change it).
 * Both pages reach it through `components/scholarship/LazyPathwayPicker.tsx`.
 *
 * Owner rulings 2026-10-30 (decisions.md):
 *  - It opens on ONE question, "Have you received an offer for your next step of study?" — stored as
 *    today's `pathway_certainty` ('sure' = an offer, 'uncertain' = waiting), same branches.
 *  - With an offer, she NAMES the place: pathway, then institution first, then the course
 *    (`InstitutionCoursePicker`; PISMP by school type then subject; matriculation by track then
 *    college; Form 6 by stream then school; an STPM or third-route holder University → Degree).
 *  - The lists are NOT filtered by her results. "Eligible only" (default OFF, top-right — portalled
 *    into the apply card's header when the page gives a `switchSlot`) narrows them, and is offered
 *    only where HalaTuju holds entry rules for the results she has. `lib/planPicker.ts` holds the
 *    rules; `lib/planPicker.scope.test.ts` guards that nothing here asks about results unless the
 *    switch is on.
 *  - Option A stands: every course, Bumiputera-only ones included; her answer is never read here.
 */
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import FieldLabel from '@/components/FieldLabel'
import PathwaySelect from '@/components/PathwaySelect'
import ProgrammePicker from '@/components/ProgrammePicker'
import Toggle from '@/components/Toggle'
import InstitutionCoursePicker from '@/components/scholarship/InstitutionCoursePicker'
import LazyAliranPicker from '@/components/scholarship/LazyAliranPicker'
import LazyMatricCollegePicker from '@/components/scholarship/LazyMatricCollegePicker'
import LazyStpmSchoolPicker from '@/components/scholarship/LazyStpmSchoolPicker'
import { getPathwayOfferings, type PathwayOfferings, type StudentProfile } from '@/lib/api'
import { useT } from '@/lib/i18n'
import type { PlanEligibility } from '@/lib/planEligibility'
import {
  DEGREE_PATHWAY, MATRIC_TRACKS, aliranOfCourse, degreeChoices, institutionOf, isOfferingPathway,
  pismpAliransOf, pismpBidang, shownPathway, storedPathway, type Allowed,
} from '@/lib/planPicker'
import { isTertiary, isThirdRoute } from '@/lib/qualification'
import {
  PATHWAY_ORDER, STPM_STREAMS, UNCERTAINTY_REASONS, profileAcademicSummary,
  type ChosenProgramme, type PismpAliran, type TopChoice,
} from '@/lib/scholarship'

export interface PathwayForm {
  pathwayCertainty: '' | 'sure' | 'uncertain'
  chosenPathway: string
  chosenProgramme: ChosenProgramme | null
  preUTrack: string
  preUInstitution: string
  pathwaysConsidered: string[]
  uncertaintyReasons: string[]
  uncertaintyNote: string
}

export default function PathwayPicker({
  value: form, onChange, profile, token, apply = false, switchSlot = null, topChoices, onTopChoices,
}: {
  value: PathwayForm
  onChange: (patch: Partial<PathwayForm>) => void
  profile: StudentProfile | null
  token: string | null
  /** the apply form: required marks and tips on the labels */
  apply?: boolean
  /** where to draw "Eligible only" (the apply card's header); inline when absent */
  switchSlot?: HTMLElement | null
  /** the apply form's waiting branch: a tertiary student's top-3 degrees */
  topChoices?: (TopChoice | null)[]
  onTopChoices?: (slots: (TopChoice | null)[]) => void
}) {
  const { t } = useT()
  // The RESULTS we hold, not the declared exam (TD-325).
  const summary = profileAcademicSummary(profile)
  const examType = summary.examType
  const tertiary = isTertiary(examType)
  const offer = form.pathwayCertainty === 'sure'
  // "Eligible only" exists where HalaTuju holds entry rules for her results: not without results,
  // not for Matriculation / Asasi / Diploma holders (ruling D2).
  const canNarrow = summary.hasData && !isThirdRoute(examType)

  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [elig, setElig] = useState<PlanEligibility | null>(null)
  useEffect(() => {
    if (!eligibleOnly || elig || !profile || !token) return
    let live = true
    // The ONLY road to the eligibility endpoints, and only once she switches it on.
    import('@/lib/planEligibility')
      .then((m) => m.loadPlanEligibility(examType, profile, token))
      .then((e) => { if (live) setElig(e) })
      .catch(() => { if (live) setEligibleOnly(false) })
    return () => { live = false }
  }, [eligibleOnly, elig, profile, token, examType])
  const narrowing = eligibleOnly && canNarrow
  const eligLoading = narrowing && !elig
  const allowed: Allowed = narrowing && elig ? elig.courseIds : null
  // The pathway DRAWN: a MARA-division diploma is stored as `university` but shown under MARA
  // (`lib/planPicker.ts` shownPathway / storedPathway). ONLY on the programme-pathway branch: an STPM
  // or third-route holder picks from the degree list, where the pathway is never derived (review 2).
  const pathway = tertiary ? form.chosenPathway : shownPathway(form.chosenPathway, form.chosenProgramme)

  // The catalogue of the pathway on screen; a tertiary holder's is the degree list.
  const offeringKey = tertiary ? DEGREE_PATHWAY : (isOfferingPathway(pathway) ? pathway : '')
  const needOfferings = !!offeringKey && (offer || (tertiary && !!onTopChoices && form.pathwayCertainty === 'uncertain'))
  const [offerings, setOfferings] = useState<PathwayOfferings | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)   // "Retry" asks again (a failed fetch is not kept)
  useEffect(() => {
    setFailed(false)   // every pathway change starts clean — matric / Form 6 fetch nothing (review 2026-10-30)
    if (!needOfferings) return
    let live = true
    getPathwayOfferings(offeringKey)
      .then((o) => { if (live) setOfferings(o) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [offeringKey, needOfferings, attempt])
  const current = offerings && offerings.pathway === offeringKey ? offerings : null
  const listLoading = !current || eligLoading

  // PISMP: the school type is local; it re-opens on a saved pick, or the Action Centre's ?aliran hint.
  const [pismpAliran, setPismpAliran] = useState('')
  const alirans = pathway === 'pismp' ? pismpAliransOf(current, allowed) : []
  useEffect(() => {
    if (pathway !== 'pismp' || !current) return
    const fromChosen = aliranOfCourse(current, form.chosenProgramme?.courseId)
    if (fromChosen) { setPismpAliran(fromChosen); return }
    const present: string[] = pismpAliransOf(current, allowed)
    const hint = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('aliran') : null
    setPismpAliran((a) => a || (hint && present.includes(hint) ? hint : present.length === 1 ? present[0] : ''))
  }, [pathway, form.chosenProgramme, current, allowed])

  const setCertainty = (c: 'sure' | 'uncertain') => onChange(
    c === 'sure'
      ? { pathwayCertainty: 'sure', pathwaysConsidered: [], uncertaintyReasons: [] }
      : {
          pathwayCertainty: 'uncertain', chosenPathway: '',
          pathwaysConsidered: form.pathwaysConsidered.length ? form.pathwaysConsidered : ['stpm'],
          uncertaintyReasons: form.uncertaintyReasons.length ? form.uncertaintyReasons : ['exploring'],
        }
  )
  const setPathway = (key: string) => {
    setPismpAliran('')
    onChange({ chosenPathway: key, chosenProgramme: null, preUTrack: '', preUInstitution: '' })
  }
  // The ONE place the saved pathway follows the pick: the MARA division's diploma saves `university`.
  const setProgramme = (c: ChosenProgramme | null) => {
    const stored = tertiary ? form.chosenPathway : storedPathway(pathway, c)
    onChange(stored === form.chosenPathway ? { chosenProgramme: c } : { chosenProgramme: c, chosenPathway: stored })
  }
  const chooseAliran = (a: PismpAliran) => { setPismpAliran(a); setProgramme(null) }
  const toggle = (list: string[], key: string) => (list.includes(key) ? list.filter((k) => k !== key) : [...list, key])
  const chip = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-sm ${on ? 'border-brand-shape bg-primary-50 font-medium text-primary-700' : 'border-ground-300 text-ground-600'}`
  const label = (key: string, tip?: string, required = apply) => (
    <FieldLabel required={required} tip={apply && tip ? t(`scholarship.apply.plan.${tip}`) : undefined}>
      {t(`scholarship.apply.plan.${key}`)}
    </FieldLabel>
  )
  const loadingLine = <p className="text-sm text-ground-400">{t('scholarship.apply.plan.loading')}</p>
  const failedLine = (
    <p role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
      {t('verifyEmail.networkError')}
      <button type="button" className="font-medium underline" onClick={() => setAttempt((a) => a + 1)}>{t('common.retry')}</button>
    </p>
  )
  const caution = (key: string) => (
    <p className="rounded-xl border border-caution-200 bg-caution-50 p-3 text-sm text-ground-600">{t(`scholarship.apply.plan.${key}`)}</p>
  )

  const pathways = narrowing && elig
    ? PATHWAY_ORDER.filter((k) => elig.pathways.has(k) || k === pathway) : PATHWAY_ORDER
  const tracks = narrowing && elig
    ? MATRIC_TRACKS.filter((tr) => elig.matricTracks.includes(tr) || tr === form.preUTrack) : MATRIC_TRACKS

  // What she named, read back to her: "<course> · <institution>, <state>" (or the pre-U track / school).
  const cp = form.chosenProgramme
  const preU = pathway === 'matric' ? 'track' : 'stream'
  const named = !offer ? '' : cp
    ? [cp.courseName, [cp.institution, institutionOf(current, cp)?.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ')
    : form.preUInstitution && form.preUTrack
      ? `${t(`scholarship.apply.plan.${preU}.${form.preUTrack}`)} · ${form.preUInstitution}` : ''

  const switchEl = (
    <div className="flex items-center gap-3">
      <span className="min-w-0 text-right">
        <span className="block text-sm font-medium text-ground-700">{t('search.eligibleOnly')}</span>
        <span className="block text-xs text-ground-500">{t('search.eligibleToggleDesc')}</span>
      </span>
      <Toggle on={eligibleOnly} onChange={setEligibleOnly} label={t('search.eligibleOnly')} />
    </div>
  )
  const showSwitch = canNarrow && offer

  const tertiaryTop = degreeChoices(current, null)
  const setTop = (i: number, prog: ChosenProgramme | null) => {
    const slots: (TopChoice | null)[] = [0, 1, 2].map((j) => topChoices?.[j] ?? null)
    slots[i] = prog
      ? { courseId: prog.courseId, courseName: prog.courseName,
          institution: tertiaryTop.find((c) => c.course_id === prog.courseId)?.institution_name ?? '' }
      : null
    onTopChoices?.(slots)
  }

  return (
    <div className="space-y-5">
      {showSwitch && (switchSlot ? createPortal(switchEl, switchSlot) : <div className="flex justify-end">{switchEl}</div>)}

      {/* The whole step turns on one question. */}
      <div>
        {label('question', 'tip')}
        <div className="grid grid-cols-2 gap-3">
          {(['sure', 'uncertain'] as const).map((c) => (
            <button key={c} type="button" onClick={() => setCertainty(c)}
              className={`rounded-xl border p-3 text-center text-sm font-medium transition-colors ${form.pathwayCertainty === c ? 'border-brand-shape bg-primary-50 text-primary-700' : 'border-ground-300 text-ground-600 hover:border-ground-400'}`}>
              {t(`scholarship.apply.plan.${c}`)}
            </button>
          ))}
        </div>
      </div>

      {/* An offer: which pathway (an SPM leaver), then the place. */}
      {offer && !tertiary && (
        <div>
          {label('pathwayLabel', 'pathwayTip')}
          <PathwaySelect pathways={pathways} value={pathway} onChange={setPathway}
            loading={eligLoading} label={t('scholarship.apply.plan.pathwayLabel')} />
        </div>
      )}

      {offer && failed && failedLine}

      {offer && !failed && (tertiary || (pathway && pathway !== 'pismp' && isOfferingPathway(pathway))) && (
        <InstitutionCoursePicker key={offeringKey} pathway={offeringKey} offerings={current} loading={listLoading}
          allowed={allowed} value={form.chosenProgramme} onChange={setProgramme} apply={apply} />
      )}

      {offer && !failed && !tertiary && pathway === 'pismp' && (
        // Teacher training: school type (Aliran) → subject (Bidang), not a typed course name.
        <div className="space-y-4">
          <div>
            {label('aliranLabel', 'aliranTip')}
            {listLoading ? loadingLine : alirans.length === 0 ? caution('noProgrammes')
              : <LazyAliranPicker alirans={alirans} value={pismpAliran} onChange={chooseAliran} />}
          </div>
          {pismpAliran && !listLoading && (
            <div>
              {label('bidangLabel', 'programmeTip')}
              <ProgrammePicker key={pismpAliran} courses={pismpBidang(current, pismpAliran, allowed)}
                value={form.chosenProgramme} onChange={setProgramme} />
            </div>
          )}
        </div>
      )}

      {offer && !tertiary && pathway === 'matric' && (
        <div className="space-y-4">
          <div>
            {label('trackLabel', 'trackTip')}
            {eligLoading ? loadingLine : tracks.length === 0 ? caution('noTracks') : (
              <div className="flex flex-wrap gap-2">
                {tracks.map((tr) => (
                  <button key={tr} type="button" onClick={() => onChange({ preUTrack: tr, preUInstitution: '' })} className={chip(form.preUTrack === tr)}>
                    {t(`scholarship.apply.plan.track.${tr}`)}
                  </button>
                ))}
              </div>
            )}
          </div>
          {form.preUTrack && (
            <div>
              {label('collegeLabel', 'collegeTip')}
              <LazyMatricCollegePicker key={`m-${form.preUTrack}`} track={form.preUTrack} value={form.preUInstitution}
                onChange={(name) => onChange({ preUInstitution: name })} placeholder={t('scholarship.apply.plan.collegePlaceholder')} />
            </div>
          )}
        </div>
      )}

      {offer && !tertiary && pathway === 'stpm' && (
        <div className="space-y-4">
          <div>
            {label('streamLabel', 'streamTip')}
            <div className="flex flex-wrap gap-2">
              {STPM_STREAMS.map((s) => (
                <button key={s} type="button" onClick={() => onChange({ preUTrack: s, preUInstitution: '' })} className={chip(form.preUTrack === s)}>
                  {t(`scholarship.apply.plan.stream.${s}`)}
                </button>
              ))}
            </div>
          </div>
          {form.preUTrack && (
            <div>
              {label('schoolLabel', 'schoolTip')}
              <LazyStpmSchoolPicker key={`s-${form.preUTrack}`} stream={form.preUTrack} value={form.preUInstitution}
                onChange={(name) => onChange({ preUInstitution: name })} placeholder={t('scholarship.apply.plan.schoolPlaceholder')} />
            </div>
          )}
        </div>
      )}

      {/* Read back what she named, and what happens to the letter. */}
      {named && (
        <>
          <p className="flex items-center gap-2 rounded-xl border border-positive-200 bg-positive-50 p-3 text-sm text-positive-800">
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12l5 5L20 7" />
            </svg>
            <span data-testid="plan-named">{named}</span>
          </p>
          <p className="rounded-xl bg-primary-50 p-3 text-sm text-primary-800">{t('scholarship.apply.plan.offerNote')}</p>
        </>
      )}

      {/* Waiting: the same optional answers as before. */}
      {form.pathwayCertainty === 'uncertain' && (
        <div className="space-y-5">
          <p className="rounded-xl border border-ground-200 bg-ground-50 p-3 text-sm text-ground-600">
            {t('scholarship.apply.plan.uncertainIntro')}
          </p>
          {!tertiary && (
            <div>
              {label('leaningLabel', 'leaningTip', false)}
              <div className="flex flex-wrap gap-2">
                {PATHWAY_ORDER.map((key) => (
                  <button key={key} type="button" className={chip(form.pathwaysConsidered.includes(key))}
                    onClick={() => onChange({ pathwaysConsidered: toggle(form.pathwaysConsidered, key) })}>
                    {t(`scholarship.apply.plan.pathway.${key}`)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {tertiary && onTopChoices && (
            <div>
              {label('topProgrammesLabel', 'topProgrammesTip', false)}
              {!current ? (failed ? failedLine : loadingLine) : (
                <div className="space-y-2">
                  {[0, 1, 2].map((i) => {
                    const tc = topChoices?.[i] ?? null
                    const taken = (topChoices ?? []).filter((c, j) => j !== i && c).map((c) => (c as TopChoice).courseId)
                    return (
                      <div key={`top-${i}`} className="flex items-center gap-2">
                        <span className="w-5 shrink-0 text-sm font-medium text-ground-400">{i + 1}.</span>
                        <div className="min-w-0 flex-1">
                          <ProgrammePicker courses={tertiaryTop.filter((c) => !taken.includes(c.course_id))}
                            value={tc ? { courseId: tc.courseId, courseName: tc.courseName, fieldKey: '' } : null}
                            onChange={(prog) => setTop(i, prog)} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
          <div>
            {label('reasonLabel', 'reasonTip', false)}
            <div className="flex flex-wrap gap-2">
              {UNCERTAINTY_REASONS.map((r) => (
                <button key={r} type="button" className={chip(form.uncertaintyReasons.includes(r))}
                  onClick={() => onChange({ uncertaintyReasons: toggle(form.uncertaintyReasons, r) })}>
                  {t(`scholarship.apply.plan.reason.${r}`)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
