/**
 * /profile: every field the page edits, the load that fills them, and the derived readings
 * (incomplete counts, household validity, IC edit rights). A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change.
 */
import { useState, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { formatIc } from '@/lib/ic-utils'
import { canEditIc, icFixableSide } from '@/lib/icEditor'
import { getProfile, getSavedCourses } from '@/lib/api'
import { chosenProgrammeFromApi } from '@/lib/scholarship'
import { isThirdRoute, resultsEditPath } from '@/lib/qualification'
import { isMalaysian } from '@/lib/bumiputera'
import { EMPTY_FAMILY, EMPTY_PATHWAY, countIncomplete } from '@/components/profile/profileFields'
import { useToast } from '@/components/ToastContext'
import { usePostcodeAutofill } from '@/lib/usePostcodeAutofill'
import type { SavedCourseWithStatus, StudentProfile } from '@/lib/api'
import type { FamilyRosterForm } from '@/components/FamilyRosterFields'
import type { PathwayForm } from '@/components/PathwayPicker'
import type { OtherMember } from '@/lib/familyRoster'

export function useProfileForm() {
  const { t } = useT()
  const { session, token } = useAuth()
  const { showToast } = useToast()

  const [name, setName] = useState('')
  const [nric, setNric] = useState('')
  const [gender, setGender] = useState<'male' | 'female' | ''>('')
  const [nationality, setNationality] = useState<'malaysian' | 'non_malaysian'>('malaysian')
  // Bumi coverage Sprint B: course guide only; null = not answered. Asked only of a Malaysian.
  const [bumiputera, setBumiputera] = useState<boolean | null>(null)
  const malaysian = isMalaysian(nationality), savedBumiputera = malaysian ? bumiputera : null
  const [state, setState] = useState('')
  const [address, setAddress] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [city, setCity] = useState('')
  const postcode = usePostcodeAutofill((c, st) => { setCity(c); setState(st) })
  const [email, setEmail] = useState('')
  // Single source of truth for the family-finance answers, shared with /apply
  // (form.householdIncome/householdSize → DB column household_income/household_size).
  // The legacy free-text family_income range + siblings count are being retired
  // (TD-061 will drop the columns in the next sprint after this backfill verifies).
  const [householdIncome, setHouseholdIncome] = useState<string>('')
  const [householdSize, setHouseholdSize] = useState<string>('')
  const [colorblind, setColorblind] = useState(false)
  const [disability, setDisability] = useState(false)
  const [identityVerified, setIdentityVerified] = useState(false)
  // The IC lock, kept SEPARATE from identityVerified above. The padlock keys on this one; the
  // green "Verified" badge keys on that one. They are not the same question — see icEditor.ts.
  // Default true so a payload that predates the field renders locked rather than offering an
  // edit the server would refuse.
  const [nricLocked, setNricLocked] = useState(true)
  const [icFlagCodes, setIcFlagCodes] = useState<string[]>([])
  const [icCardNric, setIcCardNric] = useState('')
  const [icCardName, setIcCardName] = useState('')
  const [nricDraft, setNricDraft] = useState('')      // the in-progress correction
  const [nricError, setNricError] = useState('')
  // Structured family roster — the durable profile-level home (two-way synced with
  // an open B40 application by the backend). Shown in Family & Background.
  const [family, setFamily] = useState<FamilyRosterForm>(EMPTY_FAMILY)
  // Application Tracking surfaces. Merit is read-only (computed). Pathway is editable
  // here via the shared PathwayPicker (so a shortlisted student locked out of /apply can
  // still change it); two-way synced with an open application by the backend.
  const [meritScore, setMeritScore] = useState<number | null>(null)
  const [pathwayForm, setPathwayForm] = useState<PathwayForm>(EMPTY_PATHWAY)
  // Full profile object kept for PathwayPicker's eligibility fetch (grades/exam_type/etc).
  const [profileObj, setProfileObj] = useState<StudentProfile | null>(null)
  // Third results route S2b: every student edits on the form for the results she HOLDS (an STPM
  // holder sent to the SPM form was demoted by finishing it — S2b review); a Matriculation / Asasi /
  // Diploma holder reads the SERVER's overall CGPA here (`merit_score` is the SPM merit).
  const thirdHeld = isThirdRoute(profileObj?.results_held) ? profileObj?.results_held : null
  const resultsPath = resultsEditPath(profileObj?.results_held)
  const meritShown = thirdHeld ? (profileObj?.overall_cgpa != null ? profileObj.overall_cgpa.toFixed(2) : null) : meritScore
  const meritLabel = t(thirdHeld ? 'onboarding.cgpaLabel' : 'profile.meritScore')
  const [angkaGiliran, setAngkaGiliran] = useState('')
  // Guided school (optional) — shown in the Application Tracking card above Angka Giliran.
  const [school, setSchool] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactEmailVerified, setContactEmailVerified] = useState(false)
  const [contactPhone, setContactPhone] = useState('')
  const [contactPhoneVerified, setContactPhoneVerified] = useState(false)
  // Student phone verification is paused server-side (cost). Already-verified numbers keep
  // their badge; the Verify control is hidden and replaced by a "planned" note when off.
  const [phoneVerifyEnabled, setPhoneVerifyEnabled] = useState(false)
  const [whatsappOptIn, setWhatsappOptIn] = useState(true)
  const [loginMethod, setLoginMethod] = useState('')
  const [sendingVerification, setSendingVerification] = useState(false)
  // Phone verification over WhatsApp (S4 / TD-136) — opt-in, student-initiated.
  const [verifyingPhone, setVerifyingPhone] = useState(false)
  const [phoneCode, setPhoneCode] = useState('')
  const [sendingPhoneVerify, setSendingPhoneVerify] = useState(false)
  const [checkingPhoneCode, setCheckingPhoneCode] = useState(false)


  const [savedCourses, setSavedCourses] = useState<SavedCourseWithStatus[]>([])

  // UI state
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  // Derived once so the field, the padlock and the flag panel cannot disagree about whether
  // this student may edit. `icEditable` is the ONLY thing that grants the edit.
  const icEditable = canEditIc({ nric_locked: nricLocked })
  const icFixable = icFixableSide(icFlagCodes, icEditable)

  const loadData = useCallback(async () => {
    if (!token) return
    try {
      const [profileData, coursesData] = await Promise.all([
        getProfile({ token }),
        getSavedCourses({ token }),
      ])

      setName(profileData.name || '')
      setNric(profileData.nric || '')
      setGender(profileData.gender || '')
      setNationality(profileData.nationality || 'malaysian')
      setBumiputera(typeof profileData.bumiputera === 'boolean' ? profileData.bumiputera : null)
      setState(profileData.preferred_state || '')
      setAddress(profileData.address || '')
      setPostalCode(profileData.postal_code || '')
      setCity(profileData.city || '')
      setEmail(profileData.email || session?.user?.email || '')
      setHouseholdIncome(profileData.household_income != null ? String(profileData.household_income) : '')
      setHouseholdSize(profileData.household_size != null ? String(profileData.household_size) : '')
      setColorblind(!!profileData.colorblind)
      setDisability(!!profileData.disability)
      setIdentityVerified(!!profileData.identity_verified)
      setNricLocked(profileData.nric_locked !== false)
      setIcFlagCodes(profileData.ic_flags || [])
      setIcCardNric(profileData.ic_card_nric || '')
      setIcCardName(profileData.ic_card_name || '')
      // Through formatIc, not raw: 11 production profiles store the number with no dashes
      // (050202022022), so the editable box would show a wall of digits. formatIc strips and
      // re-inserts, so it is a no-op for the properly formatted rows — and saving an edit now
      // normalises one of those 11 on the way past, since the claim endpoint requires dashes.
      setNricDraft(formatIc(profileData.nric || ''))
      setFamily({
        fatherName: profileData.father_name || '',
        fatherOccupation: profileData.father_occupation || '',
        fatherOccupationOther: profileData.father_occupation_other || '',
        motherName: profileData.mother_name || '',
        motherOccupation: profileData.mother_occupation || '',
        motherOccupationOther: profileData.mother_occupation_other || '',
        otherFamilyMembers: Array.isArray(profileData.other_family_members) ? profileData.other_family_members : [],
        siblingsInSchool: profileData.siblings_in_school ?? 0,
        siblingsInTertiary: profileData.siblings_in_tertiary ?? 0,
      })
      setMeritScore(profileData.merit_score ?? null)
      setProfileObj(profileData)
      setPathwayForm({
        pathwayCertainty: (profileData.pathway_certainty as PathwayForm['pathwayCertainty']) || '',
        chosenPathway: profileData.chosen_pathway || '',
        // chosen_programme is stored SNAKE ({course_id, course_name, field_key, institution,
        // institution_id}) — the shape /apply writes and the cockpit/verdict read; the picker is CAMEL.
        chosenProgramme: chosenProgrammeFromApi(profileData.chosen_programme),
        preUTrack: profileData.pre_u_track || '',
        preUInstitution: profileData.pre_u_institution || '',
        pathwaysConsidered: Array.isArray(profileData.pathways_considered) ? profileData.pathways_considered : [],
        uncertaintyReasons: Array.isArray(profileData.uncertainty_reasons) ? profileData.uncertainty_reasons : [],
        uncertaintyNote: profileData.uncertainty_note || '',
      })
      setAngkaGiliran(profileData.angka_giliran || '')
      setSchool(profileData.school || '')
      setContactEmail(profileData.contact_email || '')
      setContactEmailVerified(profileData.contact_email_verified || false)
      setContactPhone(profileData.contact_phone || '')
      setContactPhoneVerified(profileData.contact_phone_verified || false)
      setPhoneVerifyEnabled(profileData.phone_verify_enabled || false)
      setWhatsappOptIn(profileData.whatsapp_opt_in ?? true)
      // Determine login method from session
      if (session?.user?.email) {
        setLoginMethod(`Google (${session.user.email})`)
      } else if (session?.user?.phone) {
        setLoginMethod(`Phone (${session.user.phone})`)
      }

      setSavedCourses(coursesData.saved_courses || [])
    } catch (err) {
      showToast('Failed to load profile. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }, [token, session])

  // Family-roster handlers (shape matches FamilyRosterFields' props).
  const updateFamily = <K extends keyof FamilyRosterForm>(key: K, value: FamilyRosterForm[K]) =>
    setFamily(prev => ({ ...prev, [key]: value }))
  const addFamilyMember = () =>
    setFamily(prev => ({ ...prev, otherFamilyMembers: [...prev.otherFamilyMembers, { role: 'brother', occupation: '' }] }))
  const removeFamilyMember = (i: number) =>
    setFamily(prev => ({ ...prev, otherFamilyMembers: prev.otherFamilyMembers.filter((_, j) => j !== i) }))
  const updateFamilyMember = (i: number, patch: Partial<OtherMember>) =>
    setFamily(prev => ({ ...prev, otherFamilyMembers: prev.otherFamilyMembers.map((m, j) => (j === i ? { ...m, ...patch } : m)) }))

  // Pathway picker patch handler (PathwayPicker computes the patches).
  const updatePathway = (patch: Partial<PathwayForm>) => setPathwayForm(prev => ({ ...prev, ...patch }))

  // Read-only family summary (Family & Background view mode).
  const professionLabel = (code: string, other: string) =>
    !code ? '' : code === 'other'
      ? (other || t('scholarship.nextSteps.story.cardA.prof.other'))
      : t(`scholarship.nextSteps.story.cardA.prof.${code}`)
  const familySummary = (who: 'father' | 'mother') => {
    const name = who === 'father' ? family.fatherName : family.motherName
    const occ = who === 'father' ? family.fatherOccupation : family.motherOccupation
    const other = who === 'father' ? family.fatherOccupationOther : family.motherOccupationOther
    if (!name && !occ) return '—'
    const prof = professionLabel(occ, other)
    return prof ? `${name || '—'} (${prof})` : (name || '—')
  }

  // Incomplete field counts per section
  const identityIncomplete = countIncomplete([name, gender])
  // contact_email is auto-defaulted server-side from the auth email (and treated
  // as verified there), so it only counts as "incomplete" when truly absent.
  // A paused phone-verify must not count as "incomplete" (it can no longer be actioned).
  const contactDetailsIncomplete = (!contactEmail || !contactEmailVerified ? 1 : 0) + (phoneVerifyEnabled && !contactPhoneVerified ? 1 : 0)
  const contactIncomplete = countIncomplete([state, address, postalCode, city])
  const familyIncomplete = countIncomplete([householdIncome, householdSize])
  const appIncomplete = countIncomplete([angkaGiliran])

  // Household income/size validity — same strict rules as /apply (size 1–20, income ≥0).
  // Drives the inline red errors + the Family Save button's disabled state.
  const hhSizeNum = parseInt(householdSize, 10)
  const householdSizeInvalid = !householdSize.trim() || Number.isNaN(hhSizeNum) || hhSizeNum < 1 || hhSizeNum > 20
  const hhIncomeNum = parseInt(householdIncome, 10)
  const householdIncomeInvalid = !householdIncome.trim() || Number.isNaN(hhIncomeNum) || hhIncomeNum < 0

  return {
    name,
    setName,
    nric,
    setNric,
    gender,
    setGender,
    nationality,
    setNationality,
    bumiputera,
    setBumiputera,
    state,
    setState,
    address,
    setAddress,
    postalCode,
    setPostalCode,
    city,
    setCity,
    email,
    setEmail,
    householdIncome,
    setHouseholdIncome,
    householdSize,
    setHouseholdSize,
    colorblind,
    setColorblind,
    disability,
    setDisability,
    identityVerified,
    setIdentityVerified,
    nricLocked,
    setNricLocked,
    icFlagCodes,
    setIcFlagCodes,
    icCardNric,
    setIcCardNric,
    icCardName,
    setIcCardName,
    nricDraft,
    setNricDraft,
    nricError,
    setNricError,
    family,
    setFamily,
    meritScore,
    setMeritScore,
    pathwayForm,
    setPathwayForm,
    profileObj,
    setProfileObj,
    angkaGiliran,
    setAngkaGiliran,
    school,
    setSchool,
    contactEmail,
    setContactEmail,
    contactEmailVerified,
    setContactEmailVerified,
    contactPhone,
    setContactPhone,
    contactPhoneVerified,
    setContactPhoneVerified,
    phoneVerifyEnabled,
    setPhoneVerifyEnabled,
    whatsappOptIn,
    setWhatsappOptIn,
    loginMethod,
    setLoginMethod,
    sendingVerification,
    setSendingVerification,
    verifyingPhone,
    setVerifyingPhone,
    phoneCode,
    setPhoneCode,
    sendingPhoneVerify,
    setSendingPhoneVerify,
    checkingPhoneCode,
    setCheckingPhoneCode,
    savedCourses,
    setSavedCourses,
    loading,
    setLoading,
    saving,
    setSaving,
    postcode,
    malaysian,
    savedBumiputera,
    icEditable,
    icFixable,
    thirdHeld,
    resultsPath,
    meritShown,
    meritLabel,
    loadData,
    updateFamily,
    addFamilyMember,
    removeFamilyMember,
    updateFamilyMember,
    updatePathway,
    familySummary,
    identityIncomplete,
    contactDetailsIncomplete,
    contactIncomplete,
    familyIncomplete,
    appIncomplete,
    householdSizeInvalid,
    householdIncomeInvalid,
  }
}

export type ProfileForm = ReturnType<typeof useProfileForm>
