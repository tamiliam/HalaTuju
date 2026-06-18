'use client'

// Self-contained pathway / "Your Plans" picker, reused on /profile so a shortlisted
// student (locked out of /apply) can still change their pathway. It REUSES the exact
// leaf pickers from /apply (PathwaySelect / ProgrammePicker / InstitutionPicker) and the
// same pure helpers, and runs its own eligibility fetch (the dropdowns are eligible-only).
// Covers the pathway fields only — the apply-only extras (top-3 ranking, other
// scholarships) are deliberately left out. i18n reuses the `scholarship.apply.plan.*` keys.
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import FieldLabel from '@/components/FieldLabel'
import PathwaySelect from '@/components/PathwaySelect'
import ProgrammePicker from '@/components/ProgrammePicker'
import InstitutionPicker from '@/components/InstitutionPicker'
import AliranPicker from '@/components/AliranPicker'
import {
  checkEligibility, calculatePathways, checkStpmEligibility,
  type EligibleCourse, type StudentProfile,
} from '@/lib/api'
import {
  eligiblePathways, PATHWAY_ORDER, programmesForPathway, isProgrammePathway,
  eligibleMatricTracks, STPM_STREAMS, stpmDegreesToCourses, UNCERTAINTY_REASONS,
  pismpAlirans, bidangForAliran, aliranForChosen,
  type ChosenProgramme, type PismpAliran,
} from '@/lib/scholarship'
import { collegesForTrack } from '@/data/matric-colleges'
import { stpmSchoolsForStream } from '@/data/stpm-schools'

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
  value: form, onChange, profile, token,
}: {
  value: PathwayForm
  onChange: (patch: Partial<PathwayForm>) => void
  profile: StudentProfile | null
  token: string | null
}) {
  const { t } = useT()
  const examType: 'spm' | 'stpm' = profile?.exam_type === 'stpm' ? 'stpm' : 'spm'

  // Eligibility data feeds the eligible-only dropdowns (same call /apply makes).
  const [pathwayStats, setPathwayStats] = useState<Record<string, number> | null>(null)
  const [eligibleCourses, setEligibleCourses] = useState<EligibleCourse[]>([])
  const [matricTracks, setMatricTracks] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  // PISMP: the chosen school type (Aliran) is local to this picker — the bidang list and
  // the committed course both derive from it. The eligible PISMP courses already carry an
  // `aliran` from the backend.
  const pismpCourses = programmesForPathway(eligibleCourses, 'pismp')
  const availableAlirans = pismpAlirans(pismpCourses)
  const [pismpAliran, setPismpAliran] = useState<string>('')

  // Keep the selected school type in sync: derive it from an already-chosen course (so
  // editing on /profile re-opens on the right Aliran), else auto-select when there's only
  // one school type to choose from.
  useEffect(() => {
    if (form.chosenPathway !== 'pismp') return
    const fromChosen = aliranForChosen(pismpCourses, form.chosenProgramme?.courseId)
    if (fromChosen) { if (fromChosen !== pismpAliran) setPismpAliran(fromChosen); return }
    if (!pismpAliran && availableAlirans.length === 1) setPismpAliran(availableAlirans[0])
  }, [form.chosenPathway, form.chosenProgramme, eligibleCourses]) // eslint-disable-line react-hooks/exhaustive-deps

  // Switching school type clears the bidang (it belonged to the old Aliran).
  const chooseAliran = (a: PismpAliran) => { setPismpAliran(a); setProgramme(null) }

  useEffect(() => {
    if (!token || !profile) return
    setLoading(true)
    if (profile.exam_type === 'stpm') {
      checkStpmEligibility({
        stpm_grades: profile.stpm_grades || {}, spm_grades: profile.grades || {},
        cgpa: profile.stpm_cgpa ?? 0, muet_band: profile.muet_band ?? 0,
        gender: profile.gender, nationality: profile.nationality, colorblind: profile.colorblind,
      }, { token })
        .then((res) => setEligibleCourses(stpmDegreesToCourses(res.eligible_courses)))
        .catch(() => setEligibleCourses([]))
        .finally(() => setLoading(false))
      setPathwayStats({}); setMatricTracks([])
      return
    }
    Promise.all([
      checkEligibility(profile, { token })
        .then((res) => { setPathwayStats(res.pathway_stats || {}); setEligibleCourses(res.eligible_courses || []) }),
      calculatePathways(profile.grades || {}, profile.coq_score ?? 0, null, { token })
        .then((res) => setMatricTracks(eligibleMatricTracks(res.pathways))),
    ]).catch(() => { setPathwayStats(null); setEligibleCourses([]); setMatricTracks([]) })
      .finally(() => setLoading(false))
  }, [token, profile])

  const setCertainty = (c: 'sure' | 'uncertain') => onChange(
    c === 'sure'
      ? { pathwayCertainty: 'sure', pathwaysConsidered: [], uncertaintyReasons: [] }
      : {
          pathwayCertainty: 'uncertain', chosenPathway: '',
          pathwaysConsidered: form.pathwaysConsidered.length ? form.pathwaysConsidered : ['stpm'],
          uncertaintyReasons: form.uncertaintyReasons.length ? form.uncertaintyReasons : ['exploring'],
        }
  )
  const setPathway = (key: string) => onChange({
    chosenPathway: key, chosenProgramme: null, preUTrack: '', preUInstitution: '',
  })
  const setProgramme = (c: ChosenProgramme | null) => onChange({ chosenProgramme: c })
  const setPreUTrack = (key: string) => onChange({ preUTrack: key, preUInstitution: '' })
  const setPreUInstitution = (name: string) => onChange({ preUInstitution: name })
  const toggleLeaning = (key: string) => onChange({
    pathwaysConsidered: form.pathwaysConsidered.includes(key)
      ? form.pathwaysConsidered.filter((k) => k !== key)
      : [...form.pathwaysConsidered, key],
  })
  const toggleReason = (key: string) => onChange({
    uncertaintyReasons: form.uncertaintyReasons.includes(key)
      ? form.uncertaintyReasons.filter((k) => k !== key)
      : [...form.uncertaintyReasons, key],
  })

  const chip = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-sm ${on ? 'border-primary-500 bg-primary-50 font-medium text-primary-700' : 'border-gray-300 text-gray-600'}`

  return (
    <div className="space-y-5">
      {/* The whole step turns on one question. */}
      <div>
        <FieldLabel>{t('scholarship.apply.plan.question')}</FieldLabel>
        <div className="grid grid-cols-2 gap-3">
          {(['sure', 'uncertain'] as const).map((c) => (
            <button key={c} type="button" onClick={() => setCertainty(c)}
              className={`rounded-xl border p-3 text-center text-sm font-medium transition-colors ${form.pathwayCertainty === c ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-300 text-gray-600 hover:border-gray-400'}`}>
              {t(`scholarship.apply.plan.${c}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Decided → eligible pathway dropdown (SPM) or degree picker (STPM). */}
      {form.pathwayCertainty === 'sure' && (examType === 'stpm' ? (
        <div>
          <FieldLabel>{t('scholarship.apply.plan.degreeLabel')}</FieldLabel>
          <ProgrammePicker courses={eligibleCourses} value={form.chosenProgramme} onChange={setProgramme} loading={loading} />
        </div>
      ) : (
        <div>
          <FieldLabel>{t('scholarship.apply.plan.pathwayLabel')}</FieldLabel>
          <PathwaySelect pathways={eligiblePathways(pathwayStats)} value={form.chosenPathway} onChange={setPathway} loading={loading} />
        </div>
      ))}

      {/* Still deciding → optional leanings (SPM) + reasons + note. */}
      {form.pathwayCertainty === 'uncertain' && (
        <div className="space-y-5">
          {examType !== 'stpm' && (
            <div>
              <FieldLabel>{t('scholarship.apply.plan.leaningLabel')}</FieldLabel>
              <div className="flex flex-wrap gap-2">
                {PATHWAY_ORDER.map((key) => (
                  <button key={key} type="button" onClick={() => toggleLeaning(key)} className={chip(form.pathwaysConsidered.includes(key))}>
                    {t(`scholarship.apply.plan.pathway.${key}`)}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div>
            <FieldLabel>{t('scholarship.apply.plan.reasonLabel')}</FieldLabel>
            <div className="flex flex-wrap gap-2">
              {UNCERTAINTY_REASONS.map((r) => (
                <button key={r} type="button" onClick={() => toggleReason(r)} className={chip(form.uncertaintyReasons.includes(r))}>
                  {t(`scholarship.apply.plan.reason.${r}`)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Decided SPM pathway → programme combobox, or matric track / STPM stream → institution. */}
      {form.pathwayCertainty === 'sure' && examType !== 'stpm' && form.chosenPathway && (
        form.chosenPathway === 'pismp' ? (
          // Teacher-training: navigate Aliran (school type) → Bidang (subject), instead
          // of type-searching a course name the student may not know.
          <div className="space-y-4">
            <div>
              <FieldLabel>{t('scholarship.apply.plan.aliranLabel')}</FieldLabel>
              {loading ? (
                <p className="text-sm text-gray-400">{t('scholarship.apply.plan.loading')}</p>
              ) : availableAlirans.length === 0 ? (
                <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-gray-600">{t('scholarship.apply.plan.noProgrammes')}</p>
              ) : (
                <AliranPicker alirans={availableAlirans} value={pismpAliran} onChange={chooseAliran} />
              )}
            </div>
            {pismpAliran && (
              <div>
                <FieldLabel>{t('scholarship.apply.plan.bidangLabel')}</FieldLabel>
                <ProgrammePicker key={pismpAliran}
                  courses={bidangForAliran(pismpCourses, pismpAliran)}
                  value={form.chosenProgramme} onChange={setProgramme} loading={loading} />
              </div>
            )}
          </div>
        ) : isProgrammePathway(form.chosenPathway) ? (
          <div>
            <FieldLabel>{t('scholarship.apply.plan.programmeLabel')}</FieldLabel>
            <ProgrammePicker key={form.chosenPathway}
              courses={programmesForPathway(eligibleCourses, form.chosenPathway)}
              value={form.chosenProgramme} onChange={setProgramme} loading={loading} />
          </div>
        ) : form.chosenPathway === 'matric' ? (
          <div className="space-y-4">
            <div>
              <FieldLabel>{t('scholarship.apply.plan.trackLabel')}</FieldLabel>
              {loading ? <p className="text-sm text-gray-400">{t('scholarship.apply.plan.loading')}</p>
                : matricTracks.length === 0 ? <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-gray-600">{t('scholarship.apply.plan.noTracks')}</p>
                : (
                  <div className="flex flex-wrap gap-2">
                    {matricTracks.map((tr) => (
                      <button key={tr} type="button" onClick={() => setPreUTrack(tr)} className={chip(form.preUTrack === tr)}>
                        {t(`scholarship.apply.plan.track.${tr}`)}
                      </button>
                    ))}
                  </div>
                )}
            </div>
            {form.preUTrack && (
              <div>
                <FieldLabel>{t('scholarship.apply.plan.collegeLabel')}</FieldLabel>
                <InstitutionPicker key={`m-${form.preUTrack}`}
                  options={collegesForTrack(form.preUTrack).map((c) => ({ name: c.name, hint: c.state }))}
                  value={form.preUInstitution} onChange={setPreUInstitution}
                  placeholder={t('scholarship.apply.plan.collegePlaceholder')} />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <FieldLabel>{t('scholarship.apply.plan.streamLabel')}</FieldLabel>
              <div className="flex flex-wrap gap-2">
                {STPM_STREAMS.map((s) => (
                  <button key={s} type="button" onClick={() => setPreUTrack(s)} className={chip(form.preUTrack === s)}>
                    {t(`scholarship.apply.plan.stream.${s}`)}
                  </button>
                ))}
              </div>
            </div>
            {form.preUTrack && (
              <div>
                <FieldLabel>{t('scholarship.apply.plan.schoolLabel')}</FieldLabel>
                <InstitutionPicker key={`s-${form.preUTrack}`}
                  options={stpmSchoolsForStream(form.preUTrack).map((s) => ({ name: s.name, hint: s.state }))}
                  value={form.preUInstitution} onChange={setPreUInstitution}
                  placeholder={t('scholarship.apply.plan.schoolPlaceholder')} />
              </div>
            )}
          </div>
        )
      )}

    </div>
  )
}
