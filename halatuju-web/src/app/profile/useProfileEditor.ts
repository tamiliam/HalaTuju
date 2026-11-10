/**
 * /profile: which section is open, the snapshot Cancel restores, the validated Save, and the
 * `?next=` / `#pathway` entry points. A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change.
 */
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { validateIc } from '@/lib/ic-utils'
import { claimNric, updateProfile } from '@/lib/api'
import { isValidPhone, chosenProgrammeToApi } from '@/lib/scholarship'
import { EMPTY_FAMILY, EMPTY_PATHWAY } from '@/components/profile/profileFields'
import { useToast } from '@/components/ToastContext'
import { KEY_PROFILE } from '@/lib/storage'
import type { FamilyRosterForm } from '@/components/FamilyRosterFields'
import type { PathwayForm } from '@/components/PathwayPicker'
import type { ProfileForm } from './useProfileForm'

export type EditingSection = 'identity' | 'contactDetails' | 'contact' | 'family' | 'application' | null

export function useProfileEditor(f: ProfileForm) {
  const router = useRouter()
  const { t } = useT()
  const { token, refreshProfile } = useAuth()
  const { showToast } = useToast()
  const { name, setName, nric, gender, setGender, nationality, setNationality, bumiputera, setBumiputera, state, setState, address, setAddress, postalCode, setPostalCode, city, setCity, email, setEmail, householdIncome, setHouseholdIncome, householdSize, setHouseholdSize, colorblind, setColorblind, disability, setDisability, nricDraft, setNricError, family, setFamily, pathwayForm, setPathwayForm, angkaGiliran, setAngkaGiliran, school, setSchool, contactEmail, setContactEmail, contactPhone, setContactPhone, whatsappOptIn, setWhatsappOptIn, loading, setSaving, savedBumiputera, icEditable, postcode } = f

  // Optional "return to" target (e.g. ?next=/scholarship/apply) so an edit started
  // from the application flow can come straight back. Restricted to internal
  // scholarship paths to avoid open redirects.
  const [nextUrl, setNextUrl] = useState<string | null>(null)
  useEffect(() => {
    const n = new URLSearchParams(window.location.search).get('next')
    setNextUrl(n && n.startsWith('/scholarship') ? n : null)
  }, [])

  const [editingSection, setEditingSection] = useState<EditingSection>(null)
  const [snapshot, setSnapshot] = useState<Record<string, unknown>>({})

  const handleSave = async (): Promise<boolean> => {
    if (!token) return false
    // Validate the contact phone (optional, but if given it must be a real Malaysian
    // number — same rule as /apply: mobile 011=11 / other 01X=10 digits, landline 9-10).
    if (contactPhone.trim() && !isValidPhone(contactPhone)) {
      showToast(t('profile.invalidPhone'), 'error')
      return false
    }
    // Household income + size are shared with /apply and feed the per-capita need calc, so
    // they carry the SAME strict rules here (size integer 1–20; income required, ≥0) — a bad
    // value must not be saveable on /profile and flow into the application. Only gated on the
    // Family section (the only place they're editable), so it never blocks other sections.
    if (editingSection === 'family') {
      const size = parseInt(householdSize, 10)
      if (!householdSize.trim() || Number.isNaN(size) || size < 1 || size > 20) {
        showToast(t('profile.invalidHouseholdSize'), 'error')
        return false
      }
      const income = parseInt(householdIncome, 10)
      if (!householdIncome.trim() || Number.isNaN(income) || income < 0) {
        showToast(t('profile.invalidHouseholdIncome'), 'error')
        return false
      }
    }
    // The IC goes through the VALIDATED claim endpoint, never the profile PUT — which strips it
    // read-only on purpose. Enabling the input without this would let a student type, press
    // Save, see it succeed, and change nothing.
    //
    // ⚠ `confirm` is NEVER sent from here. It does not re-point a record: it moves the primary
    // key in raw SQL and re-parents saved courses, outcomes, reports and email verifications —
    // an account takeover. The sign-in prompt uses it deliberately ("this IC already has an
    // account, is it you?"); a profile edit must not. So a number belonging to somebody else is
    // a flat refusal here.
    if (icEditable && nricDraft && nricDraft !== nric) {
      const bad = validateIc(nricDraft)
      if (bad) {
        setNricError(t('profile.icInvalid'))
        showToast(t('profile.icInvalid'), 'error')
        return false
      }
      try {
        const res = await claimNric(nricDraft, false, { token })
        if (res.status === 'exists') {
          setNricError(t('profile.icTaken'))
          showToast(t('profile.icTaken'), 'error')
          return false
        }
      } catch {
        // 400 (format / date / age / state code) or 403 (already locked server-side).
        setNricError(t('profile.icRefused'))
        showToast(t('profile.icRefused'), 'error')
        return false
      }
    }
    setSaving(true)
    try {
      await updateProfile({
        name,
        // nric is read-only on PUT — only the claim path above can change it.
        ...(gender ? { gender } : {}),
        nationality,
        bumiputera: savedBumiputera,   // a Foreign student is never Bumiputera: null (the server agrees)
        preferred_state: state,
        address,
        postal_code: postalCode,
        city,
        email,
        contact_email: contactEmail,
        contact_phone: contactPhone,
        whatsapp_opt_in: whatsappOptIn,
        household_income: householdIncome ? parseInt(householdIncome, 10) : null,
        household_size: householdSize ? parseInt(householdSize, 10) : null,
        colorblind,
        disability,
        angka_giliran: angkaGiliran,
        school,
        // Structured family roster (the backend copies it onto an open application).
        father_name: family.fatherName.trim(),
        father_occupation: family.fatherOccupation,
        father_occupation_other: family.fatherOccupation === 'other' ? family.fatherOccupationOther.trim() : '',
        mother_name: family.motherName.trim(),
        mother_occupation: family.motherOccupation,
        mother_occupation_other: family.motherOccupation === 'other' ? family.motherOccupationOther.trim() : '',
        other_family_members: family.otherFamilyMembers,
        siblings_in_school: family.siblingsInSchool,
        siblings_in_tertiary: family.siblingsInTertiary,
        // Pathway / "Your Plans" (the backend copies it onto an open application).
        pathway_certainty: pathwayForm.pathwayCertainty,
        chosen_pathway: pathwayForm.chosenPathway,
        pre_u_track: pathwayForm.preUTrack,
        pre_u_institution: pathwayForm.preUInstitution,
        // Write back the SNAKE shape /apply uses + the cockpit/verdict read (course_name /
        // institution), so a /profile edit can't drift the stored programme's keys.
        chosen_programme: chosenProgrammeToApi(pathwayForm.chosenProgramme),
        pathways_considered: pathwayForm.pathwaysConsidered,
        uncertainty_reasons: pathwayForm.uncertaintyReasons,
        uncertainty_note: pathwayForm.uncertaintyNote,
      }, { token })

      // Keep localStorage in sync so onboarding uses the same values
      const prev = JSON.parse(localStorage.getItem(KEY_PROFILE) || '{}')
      localStorage.setItem(KEY_PROFILE, JSON.stringify({
        ...prev, gender, nationality, bumiputera: savedBumiputera, state, colorblind, disability,
      }))

      window.dispatchEvent(new Event('profile-updated'))
      return true
    } catch (err) {
      showToast('Failed to save profile. Please try again.', 'error')
      return false
    } finally {
      setSaving(false)
    }
  }

  const startEditing = (section: NonNullable<EditingSection>) => {
    setSnapshot({ name, nric, gender, nationality, bumiputera, state, address, postalCode, city, email, householdIncome, householdSize, colorblind, disability, angkaGiliran, school, contactEmail, contactPhone, whatsappOptIn, family, pathwayForm })
    setEditingSection(section)
  }

  // Third results route S3b (D13): "Continue with SPM results only" sends the student here to
  // choose a post-SPM pathway — `/profile#pathway` opens the section holding the pathway picker.
  const [pathwayHashDone, setPathwayHashDone] = useState(false)
  useEffect(() => {
    if (loading || pathwayHashDone || typeof window === 'undefined') return
    setPathwayHashDone(true)
    if (window.location.hash === '#pathway') startEditing('application')
  }, [loading, pathwayHashDone, startEditing])

  const cancelEditing = () => {
    postcode.edited()
    setName(snapshot.name as string || '')
    setGender(snapshot.gender as '' | 'male' | 'female' || '')
    setNationality(snapshot.nationality as 'malaysian' | 'non_malaysian' || 'malaysian')
    setBumiputera(typeof snapshot.bumiputera === 'boolean' ? snapshot.bumiputera : null)
    setState(snapshot.state as string || '')
    setAddress(snapshot.address as string || '')
    setPostalCode(snapshot.postalCode as string || '')
    setCity(snapshot.city as string || '')
    setEmail(snapshot.email as string || '')
    setHouseholdIncome(snapshot.householdIncome as string || '')
    setHouseholdSize(snapshot.householdSize as string || '')
    setColorblind(snapshot.colorblind as boolean || false)
    setDisability(snapshot.disability as boolean || false)
    setAngkaGiliran(snapshot.angkaGiliran as string || '')
    setSchool(snapshot.school as string || '')
    setContactEmail(snapshot.contactEmail as string || '')
    setContactPhone(snapshot.contactPhone as string || '')
    setWhatsappOptIn(snapshot.whatsappOptIn as boolean ?? true)
    setFamily((snapshot.family as FamilyRosterForm) || EMPTY_FAMILY)
    setPathwayForm((snapshot.pathwayForm as PathwayForm) || EMPTY_PATHWAY)
    setEditingSection(null)
  }

  const saveSection = async () => {
    postcode.edited()   // a postcode answer landing after Save must not fill unsaved City/State (review 7b)
    const ok = await handleSave()
    // Only leave the editor on a successful save — a validation failure (e.g. a bad
    // household size) keeps the section open so the inline error is visible and the
    // unsaved value isn't mistaken for saved.
    if (!ok) return
    setEditingSection(null)
    // Refresh the cached profile so pages that pre-fill from it (e.g. the apply
    // form) see the new values immediately instead of a stale cache.
    await refreshProfile()
    // If the edit was started from the application flow, return there.
    if (nextUrl) router.push(nextUrl)
  }

  return { nextUrl, editingSection, startEditing, cancelEditing, saveSection }
}

export type ProfileEditor = ReturnType<typeof useProfileEditor>
export type SectionProps = { f: ProfileForm; ed: ProfileEditor }
