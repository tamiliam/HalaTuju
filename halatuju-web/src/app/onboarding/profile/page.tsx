'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import BrandLogo from '@/components/BrandLogo'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/lib/auth-context'
import { getProfile, type SyncProfileData } from '@/lib/api'
import ProgressStepper from '@/components/ProgressStepper'
import SchoolSelect from '@/components/SchoolSelect'
import { KEY_PROFILE, KEY_GRADES, KEY_ALIRAN, KEY_ELEKTIF, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_KOKO_SCORE, KEY_STPM_KOKO_CONFIRMED, KEY_MUET_BAND, KEY_EXAM_TYPE, KEY_SPM_PREREQ, KEY_SPM_ELEKTIF, KEY_SPM_STREAM } from '@/lib/storage'
import { resultsSyncFields, syncProfileSafely } from '@/lib/resultsSync'
import { resultsEditPath } from '@/lib/qualification'
import { hasApplyReturn, clearApplyReturn, peekApplyStash, popOnboardingReturn, peekOnboardingReturn } from '@/lib/scholarship'
import { applyPagePath } from '@/lib/applyPagePath'
import { isMalaysian } from '@/lib/bumiputera'

const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'W.P. Kuala Lumpur', 'W.P. Putrajaya', 'W.P. Labuan',
]

export default function ProfileInputPage() {
  const router = useRouter()
  const { t } = useT()
  const { token, isAnonymous, refreshProfile } = useAuth()
  const [gender, setGender] = useState<string>('')
  const [nationality, setNationality] = useState<string>('malaysian')
  // Bumi coverage Sprint B: COURSE GUIDE ONLY (unlocks Bumiputera-only courses). null = not
  // answered yet. Asked only of a Malaysian; a Foreign student saves null.
  const [bumiputera, setBumiputera] = useState<boolean | null>(null)
  const [state, setState] = useState<string>('')
  // Optional guided school (reuses the MOE secondary-school list). Captured here so
  // the normal course-guide signup records it the same guided way the B40 apply form does.
  const [school, setSchool] = useState<string>('')
  const [colorblind, setColorblind] = useState<boolean>(false)
  const [disability, setDisability] = useState<boolean>(false)
  // Entered from the scholarship apply form's "edit results"? Then this final
  // step returns to the apply page instead of the dashboard.
  const [returning, setReturning] = useState<boolean>(false)
  // A non-apply caller (e.g. /profile editing grades) set a return path — the final
  // step then says "Save & return" and goes back there, not to recommendations.
  const [returnPath, setReturnPath] = useState<string | null>(null)
  // Request #35 "we ask for school twice": a school already known from the apply form's
  // stash or the profile. On the way back to the application the School box is then hidden —
  // the student just answered it on "About Me". Set only from those sources, never from typing,
  // so the box cannot vanish under a student who is filling it in.
  const [schoolKnown, setSchoolKnown] = useState<boolean>(false)

  // Back = the results form this student came from (S2b: three forms now, not one).
  const [backPath, setBackPath] = useState(resultsEditPath('spm'))
  useEffect(() => {
    setReturning(hasApplyReturn()); setReturnPath(peekOnboardingReturn())
    setBackPath(resultsEditPath(localStorage.getItem(KEY_EXAM_TYPE)))
  }, [])

  useEffect(() => {
    const stashSchool = (peekApplyStash()?.school ?? '').trim()
    const savedProfile = localStorage.getItem(KEY_PROFILE)
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile)
      if (parsed.gender) setGender(parsed.gender)
      if (parsed.nationality) setNationality(parsed.nationality)
      if (typeof parsed.bumiputera === 'boolean') setBumiputera(parsed.bumiputera)
      if (parsed.state) setState(parsed.state)
      if (parsed.school) setSchool(parsed.school)
      if (parsed.colorblind !== undefined) setColorblind(parsed.colorblind)
      if (parsed.disability !== undefined) setDisability(parsed.disability)
    }

    // The school typed on "About Me" (in the apply stash) shows at once; the profile's own wins below.
    if (stashSchool) { setSchool(stashSchool); setSchoolKnown(true) }

    if (token && !isAnonymous) {
      getProfile({ token }).then(p => {
        if (p.preferred_state) setState(p.preferred_state)
        if (p.school) { setSchool(p.school); setSchoolKnown(true) }
        if (p.gender) setGender(p.gender)
        if (p.nationality) setNationality(p.nationality)
        if (typeof p.bumiputera === 'boolean') setBumiputera(p.bumiputera)
        if (p.colorblind !== undefined) setColorblind(!!p.colorblind)
        if (p.disability !== undefined) setDisability(!!p.disability)

        // When the student got here from /apply's "edit results", the apply form's
        // in-progress homeState is more recent than the profile's preferred_state
        // (apply only commits on submit). Honour it so the same field doesn't
        // appear to re-prompt with a stale value the student already changed.
        const stash = peekApplyStash()
        if (stash?.homeState) setState(stash.homeState)
      }).catch(() => {})
    }
  }, [token, isAnonymous])

  const malaysian = isMalaysian(nationality)
  // Required like gender — but only asked of a Malaysian (a Foreign student is never Bumiputera).
  const isComplete = gender !== '' && (!malaysian || bumiputera !== null)
  // What is saved: the answer for a Malaysian, null for a Foreign student (the server agrees).
  const savedBumiputera = malaysian ? bumiputera : null

  const handleContinue = async () => {
    if (!isComplete) return

    // Preserve CoQ score set on grades page
    const existing = localStorage.getItem(KEY_PROFILE)
    const prev = existing ? JSON.parse(existing) : {}
    const profileData = {
      ...prev,
      gender,
      nationality,
      bumiputera: savedBumiputera,
      state,
      school,
      colorblind,
      disability,
    }
    localStorage.setItem(KEY_PROFILE, JSON.stringify(profileData))

    if (token && !isAnonymous) {
      // Build sync payload including grades from localStorage
      const syncPayload: SyncProfileData = {
        gender,
        nationality,
        bumiputera: savedBumiputera,
        preferred_state: state,
        colorblind,
        disability,
      }

      // School is optional — only sync it when the student actually entered one,
      // so a blank doesn't overwrite a school captured elsewhere (e.g. the apply form).
      if (school.trim()) syncPayload.school = school.trim()

      // Include SPM grades
      const gradesStr = localStorage.getItem(KEY_GRADES)
      if (gradesStr) {
        try { syncPayload.grades = JSON.parse(gradesStr) } catch { /* ignore */ }
      }

      // TD-063: persist the student's stream/aliran picks so the merit engine
      // uses them (instead of guessing the stream) on every server recompute.
      const aliranStr = localStorage.getItem(KEY_ALIRAN)
      if (aliranStr) {
        try { syncPayload.stream_subjects = JSON.parse(aliranStr) } catch { /* ignore */ }
      }

      // Persist the elective picks too — the durable record of which subjects are
      // electives, so the grades form can rebuild the selection after logout/login
      // (without this the electives are dropped on reload). Up to 7.
      const elektifStr = localStorage.getItem(KEY_ELEKTIF)
      if (elektifStr) {
        try { syncPayload.elective_subjects = JSON.parse(elektifStr) } catch { /* ignore */ }
      }

      // TD-069: the STPM path's SPM prerequisites, durably — the grades, which of them are
      // electives, and the stream pill. Without these a logout/login emptied the section.
      const spmPrereqStr = localStorage.getItem(KEY_SPM_PREREQ)
      if (spmPrereqStr) {
        try { syncPayload.spm_prereq_grades = JSON.parse(spmPrereqStr) } catch { /* ignore */ }
      }
      const spmElektifStr = localStorage.getItem(KEY_SPM_ELEKTIF)
      if (spmElektifStr) {
        try { syncPayload.spm_elective_subjects = JSON.parse(spmElektifStr) } catch { /* ignore */ }
      }
      const spmStream = localStorage.getItem(KEY_SPM_STREAM)
      if (spmStream) syncPayload.spm_stream = spmStream

      // ⚠ WHICH RESULTS WERE COMPLETED, which is not the same claim as which exam was selected.
      // Only the three results editors write it, and only when their form is finished — so
      // reaching this page carries it, and abandoning a selection never does. The server checks
      // it is backed by results on file and drops it otherwise; this is the honest half of a
      // guarantee the browser cannot make alone. It travels WITH the whole completed list and the
      // third route's fields, as one set (`resultsSyncFields`, third results route S2b).
      Object.assign(syncPayload, resultsSyncFields(localStorage))

      const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
      if (stpmGradesStr) {
        try { syncPayload.stpm_grades = JSON.parse(stpmGradesStr) } catch { /* ignore */ }
      }

      const stpmCgpa = localStorage.getItem(KEY_STPM_CGPA)
      if (stpmCgpa) syncPayload.stpm_cgpa = parseFloat(stpmCgpa)
      // STPM CGPA sprint C2: the STPM co-curriculum score, stored for the MERIT (never the CGPA).
      const stpmKoko = stpmGradesStr ? parseFloat(localStorage.getItem(KEY_KOKO_SCORE) ?? '') : NaN
      if (Number.isFinite(stpmKoko)) syncPayload.stpm_koko = stpmKoko
      // C4: saved on the STPM step just now → the student's own confirmation of that score.
      if (Number.isFinite(stpmKoko) && localStorage.getItem(KEY_STPM_KOKO_CONFIRMED)) syncPayload.stpm_koko_confirmed = true

      const muetBand = localStorage.getItem(KEY_MUET_BAND)
      if (muetBand) syncPayload.muet_band = parseInt(muetBand)

      // Co-curricular (CoQ) score — entered in the grades step, kept on the
      // localStorage profile; persist it to the DB like any other result.
      const profStr = localStorage.getItem(KEY_PROFILE)
      if (profStr) {
        try {
          const p = JSON.parse(profStr)
          if (typeof p.coqScore === 'number') syncPayload.coq_score = p.coqScore
        } catch { /* ignore */ }
      }

      try {
        await syncProfileSafely(syncPayload, { token })
        localStorage.removeItem(KEY_STPM_KOKO_CONFIRMED)
        await refreshProfile()
      } catch {
        // Continue even if sync fails — localStorage has the data
      }
    }

    // A non-apply flow (e.g. an /application Action Centre academic ticket) may have
    // asked to return to a specific page after onboarding — honour it first.
    const back = popOnboardingReturn()
    if (back) {
      router.push(back)
      return
    }

    // Returning from the apply form's "edit results" detour → back to the apply
    // page (which restores the stashed edits and shows the updated results) —
    // carrying the gift's `?p=`, since a bare arrival there now asks afresh.
    if (returning) {
      clearApplyReturn()
      router.push(applyPagePath())
      return
    }
    router.push('/dashboard')
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-ground-0">
      {/* Header */}
      <div className="bg-ground-0 border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <BrandLogo width={120} height={40} />
            </Link>
            <ProgressStepper currentStep={3} />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-ground-900 mb-3">
            {t('onboarding.profileTitle')}
          </h1>
          <p className="text-ground-600">
            {t('onboarding.profileSubtitleNew')}
          </p>
        </div>

        {/* Compact single card */}
        <div className="bg-ground-0 rounded-2xl border border-ground-200 p-6 mb-8">
          {/* Row 1: State + Nationality */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
            {/* Negeri */}
            <div>
              <label className="block text-sm font-medium text-ground-700 mb-2">
                {t('onboarding.state')}
              </label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm bg-ground-0 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
              >
                <option value="">{t('onboarding.selectState')}</option>
                {MALAYSIAN_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Kewarganegaraan */}
            <div>
              <label className="block text-sm font-medium text-ground-700 mb-2">
                {t('onboarding.nationality')}
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setNationality('malaysian')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'malaysian'
                      ? 'bg-primary-50 border-brand-shape text-primary-700'
                      : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'
                  }`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={nationality === 'malaysian' ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" fill={nationality === 'malaysian' ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                    <polyline points="9 22 9 12 15 12 15 22" />
                  </svg>
                  {t('onboarding.malaysian')}
                </button>
                <button
                  onClick={() => setNationality('non_malaysian')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'non_malaysian'
                      ? 'bg-primary-50 border-brand-shape text-primary-700'
                      : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'
                  }`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={nationality === 'non_malaysian' ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" fill={nationality === 'non_malaysian' ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                  </svg>
                  {t('onboarding.nonMalaysian')}
                </button>
              </div>
            </div>
          </div>

          {/* Row 1b: School (optional, guided from the MOE secondary-school list). Hidden only on
              the way back to the application when a school is already known (request #35): it is
              still kept, saved, and editable on "About Me" and the Profile page. */}
          {!(returning && !returnPath && schoolKnown) && (
          <div className="mb-6" data-testid="onboarding-school">
            <label className="block text-sm font-medium text-ground-700 mb-2">
              {t('onboarding.school')} <span className="text-ground-400 font-normal">({t('onboarding.optional')})</span>
            </label>
            <SchoolSelect value={school} onChange={setSchool} />
          </div>
          )}

          {/* Row 2: Jantina + Bumiputera — side by side on wide screens, stacked on phones (the
              owner-approved Stitch layout). Bumiputera is asked only of a Malaysian. */}
          <div className={`grid grid-cols-1 ${malaysian ? 'md:grid-cols-2' : ''} gap-5 mb-6`}>
          <div>
            <label className="block text-sm font-medium text-ground-700 mb-2">
              {t('onboarding.gender')} <span className="text-critical-600">*</span>
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setGender('male')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  gender === 'male'
                    ? 'border-brand-shape bg-primary-50 text-primary-700'
                    : 'border-ground-200 text-ground-600 hover:border-ground-300'
                }`}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={gender === 'male' ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                  <circle cx="12" cy="7" r="4" fill={gender === 'male' ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                </svg>
                {t('onboarding.male')}
              </button>
              <button
                onClick={() => setGender('female')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  gender === 'female'
                    ? 'border-brand-shape bg-primary-50 text-primary-700'
                    : 'border-ground-200 text-ground-600 hover:border-ground-300'
                }`}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={gender === 'female' ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                  <circle cx="12" cy="7" r="4" fill={gender === 'female' ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                </svg>
                {t('onboarding.female')}
              </button>
            </div>
          </div>

          {/* Bumiputera — course guide only: it shows Bumiputera-only courses (UiTM, MARA). */}
          {malaysian && (
          <div data-testid="onboarding-bumiputera">
            <label className="block text-sm font-medium text-ground-700 mb-2">
              {t('onboarding.bumiputera')} <span className="text-critical-600">*</span>
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setBumiputera(true)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  bumiputera === true
                    ? 'border-brand-shape bg-primary-50 text-primary-700'
                    : 'border-ground-200 text-ground-600 hover:border-ground-300'
                }`}
              >
                {t('onboarding.bumiYes')}
              </button>
              <button
                onClick={() => setBumiputera(false)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  bumiputera === false
                    ? 'border-brand-shape bg-primary-50 text-primary-700'
                    : 'border-ground-200 text-ground-600 hover:border-ground-300'
                }`}
              >
                {t('onboarding.bumiNo')}
              </button>
            </div>
            <p className="text-xs text-ground-400 mt-2">{t('onboarding.bumiHelp')}</p>
          </div>
          )}
          </div>

          {/* Row 4: Keperluan Khas */}
          <div>
            <label className="block text-sm font-medium text-ground-700 mb-2">
              {t('onboarding.specialNeeds')}
            </label>
            <p className="text-xs text-ground-400 mb-3">{t('onboarding.healthNote')}</p>
            <div className="flex flex-wrap gap-3">
              <label className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border cursor-pointer transition-all ${
                colorblind
                  ? 'border-brand-shape bg-primary-50'
                  : 'border-ground-200 hover:border-ground-300'
              }`}>
                <input
                  type="checkbox"
                  checked={colorblind}
                  onChange={(e) => setColorblind(e.target.checked)}
                  className="w-4 h-4 rounded border-ground-300 text-primary-600 focus:ring-brand-shape"
                />
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={colorblind ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill={colorblind ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                  <circle cx="12" cy="12" r="3" />
                  <line x1="2" y1="2" x2="22" y2="22" stroke={colorblind ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} />
                </svg>
                <span className="text-sm text-ground-700">{t('onboarding.colorBlindness')}</span>
              </label>
              <label className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border cursor-pointer transition-all ${
                disability
                  ? 'border-brand-shape bg-primary-50'
                  : 'border-ground-200 hover:border-ground-300'
              }`}>
                <input
                  type="checkbox"
                  checked={disability}
                  onChange={(e) => setDisability(e.target.checked)}
                  className="w-4 h-4 rounded border-ground-300 text-primary-600 focus:ring-brand-shape"
                />
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={disability ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" fill={disability ? 'rgb(var(--brand-200))' : 'rgb(var(--ground-200))'} />
                  <path d="M12 8a1 1 0 100-2 1 1 0 000 2z" fill={disability ? 'rgb(var(--brand-700))' : 'rgb(var(--ground-500))'} />
                  <path d="M12 10v4M10 18l2-4 2 4" />
                </svg>
                <span className="text-sm text-ground-700">{t('onboarding.physicalDisability')}</span>
              </label>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <Link
            href={backPath}
            className="px-6 py-3 text-ground-600 hover:text-ground-900"
          >
            {t('common.back')}
          </Link>
          <button
            onClick={handleContinue}
            disabled={!isComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {returnPath ? t('onboarding.saveAndReturn') : returning ? t('onboarding.saveReturnToApplication') : t('onboarding.seeRecommendations')}
          </button>
        </div>
      </div>
    </main>
  )
}
