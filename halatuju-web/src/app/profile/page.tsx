'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { maskIc } from '@/lib/ic-utils'
import {
  getProfile,
  updateProfile,
  getSavedCourses,
  unsaveCourse,
  updateSavedCourseStatus,
  sendVerificationEmail,
} from '@/lib/api'
import type { SavedCourseWithStatus } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import { useToast } from '@/components/Toast'
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'
import { KEY_PROFILE } from '@/lib/storage'
import { findPostcode } from 'malaysia-postcodes'

const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'W.P. Kuala Lumpur', 'W.P. Putrajaya', 'W.P. Labuan',
]

const INCOME_RANGES = [
  '< RM1,000',
  'RM1,001 – RM3,000',
  'RM3,001 – RM5,000',
  'RM5,001 – RM10,000',
  '> RM10,000',
]

const STATUS_OPTIONS = [
  { value: 'interested', label: 'profile.status.interested', color: 'bg-gray-100 text-gray-600' },
  { value: 'planning', label: 'profile.status.planning', color: 'bg-blue-100 text-blue-700' },
  { value: 'applied', label: 'profile.status.applied', color: 'bg-amber-100 text-amber-700' },
  { value: 'got_offer', label: 'profile.status.got_offer', color: 'bg-green-100 text-green-700' },
]

type EditingSection = 'identity' | 'contactDetails' | 'contact' | 'family' | 'application' | null

function countIncomplete(fields: (string | boolean | number | null | undefined)[]): number {
  return fields.filter(f => f === '' || f === null || f === undefined).length
}

function FieldValue({ value, t }: { value: string; t: (key: string) => string }) {
  if (!value) {
    return <span className="text-sm text-amber-500 italic">{t('profile.notSet')}</span>
  }
  return <span className="text-sm text-gray-900">{value}</span>
}

function FieldLabel({ label, empty }: { label: string; empty: boolean }) {
  return (
    <span className="text-sm text-gray-500 flex items-center gap-1.5">
      {empty && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />}
      {label}
    </span>
  )
}

export default function ProfilePage() {
  const router = useRouter()
  const { t, locale } = useT()
  const { ready: onboarded } = useOnboardingGuard()
  const { session, token, isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { showToast } = useToast()

  // Profile form state
  const [name, setName] = useState('')
  const [nric, setNric] = useState('')
  const [gender, setGender] = useState<'male' | 'female' | ''>('')
  const [nationality, setNationality] = useState<'malaysian' | 'non_malaysian'>('malaysian')
  const [state, setState] = useState('')
  const [address, setAddress] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [city, setCity] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [familyIncome, setFamilyIncome] = useState('')
  const [siblings, setSiblings] = useState<string>('')
  const [colorblind, setColorblind] = useState(false)
  const [disability, setDisability] = useState(false)
  const [angkaGiliran, setAngkaGiliran] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactEmailVerified, setContactEmailVerified] = useState(false)
  const [contactPhone, setContactPhone] = useState('')
  const [contactPhoneVerified, setContactPhoneVerified] = useState(false)
  const [loginMethod, setLoginMethod] = useState('')
  const [sendingVerification, setSendingVerification] = useState(false)

  // Course interests
  const [savedCourses, setSavedCourses] = useState<SavedCourseWithStatus[]>([])

  // UI state
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editingSection, setEditingSection] = useState<EditingSection>(null)
  const [snapshot, setSnapshot] = useState<Record<string, unknown>>({})

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
      setState(profileData.preferred_state || '')
      setAddress(profileData.address || '')
      setPostalCode(profileData.postal_code || '')
      setCity(profileData.city || '')
      setPhone(profileData.phone || '')
      setEmail(profileData.email || session?.user?.email || '')
      setFamilyIncome(profileData.family_income || '')
      setSiblings(profileData.siblings != null ? String(profileData.siblings) : '')
      setColorblind(profileData.colorblind === true || String(profileData.colorblind) === 'Ya')
      setDisability(profileData.disability === true || String(profileData.disability) === 'Ya')
      setAngkaGiliran(profileData.angka_giliran || '')
      setContactEmail(profileData.contact_email || '')
      setContactEmailVerified(profileData.contact_email_verified || false)
      setContactPhone(profileData.contact_phone || '')
      setContactPhoneVerified(profileData.contact_phone_verified || false)
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

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      showAuthGate('profile')
      return
    }
    if (token) loadData()
  }, [token, authLoading, isAuthenticated, showAuthGate, loadData])

  const handleSave = async () => {
    if (!token) return
    setSaving(true)
    try {
      await updateProfile({
        name,
        nric,
        ...(gender ? { gender } : {}),
        nationality,
        preferred_state: state,
        address,
        postal_code: postalCode,
        city,
        phone,
        email,
        contact_email: contactEmail,
        contact_phone: contactPhone,
        family_income: familyIncome,
        siblings: siblings ? parseInt(siblings, 10) : null,
        colorblind: colorblind ? 'Ya' : 'Tidak',
        disability: disability ? 'Ya' : 'Tidak',
        angka_giliran: angkaGiliran,
      }, { token })

      // Keep localStorage in sync so onboarding uses the same values
      const prev = JSON.parse(localStorage.getItem(KEY_PROFILE) || '{}')
      localStorage.setItem(KEY_PROFILE, JSON.stringify({
        ...prev, gender, nationality, state, colorblind, disability,
      }))

      window.dispatchEvent(new Event('profile-updated'))
    } catch (err) {
      showToast('Failed to save profile. Please try again.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const startEditing = (section: NonNullable<EditingSection>) => {
    setSnapshot({ name, nric, gender, nationality, state, address, postalCode, city, phone, email, familyIncome, siblings, colorblind, disability, angkaGiliran, contactEmail, contactPhone })
    setEditingSection(section)
  }

  const cancelEditing = () => {
    setName(snapshot.name as string || '')
    setGender(snapshot.gender as '' | 'male' | 'female' || '')
    setNationality(snapshot.nationality as 'malaysian' | 'non_malaysian' || 'malaysian')
    setState(snapshot.state as string || '')
    setAddress(snapshot.address as string || '')
    setPostalCode(snapshot.postalCode as string || '')
    setCity(snapshot.city as string || '')
    setPhone(snapshot.phone as string || '')
    setEmail(snapshot.email as string || '')
    setFamilyIncome(snapshot.familyIncome as string || '')
    setSiblings(snapshot.siblings as string || '')
    setColorblind(snapshot.colorblind as boolean || false)
    setDisability(snapshot.disability as boolean || false)
    setAngkaGiliran(snapshot.angkaGiliran as string || '')
    setContactEmail(snapshot.contactEmail as string || '')
    setContactPhone(snapshot.contactPhone as string || '')
    setEditingSection(null)
  }

  const saveSection = async () => {
    await handleSave()
    setEditingSection(null)
  }

  const handleStatusChange = async (courseId: string, newStatus: string) => {
    if (!token) return
    try {
      await updateSavedCourseStatus(courseId, newStatus, { token })
      setSavedCourses(prev =>
        prev.map(c => c.course_id === courseId ? { ...c, interest_status: newStatus } : c)
      )
    } catch (err) {
      showToast('Failed to update course status.', 'error')
    }
  }

  const handleRemoveCourse = async (courseId: string) => {
    if (!token) return
    try {
      await unsaveCourse(courseId, { token })
      setSavedCourses(prev => prev.filter(c => c.course_id !== courseId))
    } catch (err) {
      showToast('Failed to remove course.', 'error')
    }
  }

  const getStatusColor = (status: string) =>
    STATUS_OPTIONS.find(s => s.value === status)?.color || 'bg-gray-100 text-gray-600'

  // Incomplete field counts per section
  const identityIncomplete = countIncomplete([name, gender])
  const contactDetailsIncomplete = (!contactEmailVerified ? 1 : 0) + (!contactPhoneVerified ? 1 : 0)
  const contactIncomplete = countIncomplete([state, address, postalCode, city])
  const familyIncomplete = countIncomplete([familyIncome, siblings])
  const appIncomplete = countIncomplete([angkaGiliran])

  if (authLoading || loading || !onboarded) {
    return (
      <>
        <AppHeader />
        <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center">
          <p className="text-gray-500">{t('common.loading')}</p>
        </main>
      </>
    )
  }

  return (
    <>
      <AppHeader />
      <main className="min-h-screen bg-[#f8fafc]">
        <div className="container mx-auto px-6 py-10 max-w-2xl">
          {/* Page title */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">
              {t('profile.title')}
            </h1>
            <p className="text-gray-500">
              {t('profile.subtitle')}
            </p>
          </div>

          {/* Section 1: Personal Details (Identity) */}
          <div className={`bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5 ${identityIncomplete > 0 ? 'border-l-4 border-l-amber-400' : ''}`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-gray-900">{t('profile.personalDetails')}</h2>
                {identityIncomplete > 0 && (
                  <span className="px-2 py-0.5 bg-amber-50 text-amber-600 text-xs font-medium rounded-full">
                    {identityIncomplete} {t('profile.incomplete')}
                  </span>
                )}
              </div>
              {editingSection === null && (
                <button onClick={() => startEditing('identity')} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  {t('profile.edit')}
                </button>
              )}
            </div>

            {editingSection === 'identity' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.icMasked')}</label>
                  <div className="relative">
                    <input
                      type="text"
                      value={nric ? maskIc(nric) : '—'}
                      disabled
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm bg-gray-50 text-gray-500 font-mono cursor-not-allowed pr-10"
                    />
                    <svg className="w-4 h-4 text-gray-400 absolute right-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                    </svg>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.name')} <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('onboarding.gender')} <span className="text-red-500">*</span></label>
                    <div className="flex gap-2">
                      {(['male', 'female'] as const).map(g => (
                        <button
                          key={g}
                          onClick={() => setGender(g)}
                          className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                            gender === g
                              ? 'bg-primary-50 border-primary-500 text-primary-700'
                              : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                          }`}
                        >
                          {t(`onboarding.${g}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('onboarding.nationality')}</label>
                    <div className="flex gap-2">
                      {(['malaysian', 'non_malaysian'] as const).map(n => (
                        <button
                          key={n}
                          onClick={() => setNationality(n)}
                          className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                            nationality === n
                              ? 'bg-primary-50 border-primary-500 text-primary-700'
                              : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                          }`}
                        >
                          {n === 'malaysian' ? t('onboarding.malaysian') : t('onboarding.nonMalaysian')}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex gap-3 pt-4">
                  <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
                    {t('profile.cancel')}
                  </button>
                  <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">
                    {saving ? '...' : t('profile.save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500 flex items-center gap-1.5">
                    <svg className="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                    </svg>
                    {t('profile.icMasked')}
                  </span>
                  <span className="text-sm text-gray-900 font-mono">{nric ? maskIc(nric) : '—'}</span>
                </div>
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.name')} empty={!name} />
                  <FieldValue value={name} t={t} />
                </div>
                <div className="flex justify-between">
                  <FieldLabel label={t('onboarding.gender')} empty={!gender} />
                  {gender ? (
                    <span className="text-sm text-gray-900">{t(`onboarding.${gender}`)}</span>
                  ) : (
                    <FieldValue value="" t={t} />
                  )}
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">{t('onboarding.nationality')}</span>
                  <span className="text-sm text-gray-900">{nationality === 'malaysian' ? t('onboarding.malaysian') : t('onboarding.nonMalaysian')}</span>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: Contact Details (NEW) */}
          <div className={`bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5 ${contactDetailsIncomplete > 0 ? 'border-l-4 border-l-amber-400' : ''}`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-gray-900">{t('profile.contactDetails')}</h2>
                {contactDetailsIncomplete > 0 && (
                  <span className="px-2 py-0.5 bg-amber-50 text-amber-600 text-xs font-medium rounded-full">
                    {contactDetailsIncomplete} {t('profile.incomplete')}
                  </span>
                )}
              </div>
              {editingSection === null && (
                <button onClick={() => startEditing('contactDetails')} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  {t('profile.edit')}
                </button>
              )}
            </div>

            {editingSection === 'contactDetails' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.loginMethod')}</label>
                  <input
                    type="text"
                    value={loginMethod || '—'}
                    disabled
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm bg-gray-50 text-gray-500 cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.contactEmail')}</label>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={contactEmail}
                      onChange={e => setContactEmail(e.target.value)}
                      className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                    />
                    <button
                      onClick={async () => {
                        if (!contactEmail || !token) return
                        setSendingVerification(true)
                        try {
                          // Save first, then send verification
                          await updateProfile({ contact_email: contactEmail }, { token })
                          await sendVerificationEmail(contactEmail, locale, { token })
                          showToast(t('profile.verificationSent'), 'success')
                          window.dispatchEvent(new Event('profile-updated'))
                        } catch {
                          showToast('Failed to send verification email.', 'error')
                        } finally {
                          setSendingVerification(false)
                        }
                      }}
                      disabled={!contactEmail || sendingVerification}
                      className="px-4 py-2.5 bg-primary-50 text-primary-700 border border-primary-200 rounded-lg text-sm font-medium hover:bg-primary-100 disabled:opacity-50 whitespace-nowrap"
                    >
                      {sendingVerification ? '...' : t('profile.verify')}
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{t('profile.emailVerifyNote')}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.contactPhone')}</label>
                  <input
                    type="tel"
                    value={contactPhone}
                    onChange={e => setContactPhone(e.target.value)}
                    placeholder="+60 12-345 6789"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  />
                  <p className="text-xs text-gray-400 mt-1">{t('profile.phoneVerifyNote')}</p>
                </div>
                <div className="flex gap-3 pt-4">
                  <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
                    {t('profile.cancel')}
                  </button>
                  <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">
                    {saving ? '...' : t('profile.save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">{t('profile.loginMethod')}</span>
                  <span className="text-sm text-gray-900">{loginMethod || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.contactEmail')} empty={!contactEmail} />
                  {contactEmail ? (
                    <span className="text-sm text-gray-900 flex items-center gap-1.5">
                      {contactEmail}
                      {contactEmailVerified ? (
                        <span className="px-1.5 py-0.5 bg-green-50 text-green-600 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
                      ) : (
                        <span className="text-amber-500 text-xs">{t('profile.notVerified')}</span>
                      )}
                    </span>
                  ) : (
                    <FieldValue value="" t={t} />
                  )}
                </div>
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.contactPhone')} empty={!contactPhone} />
                  {contactPhone ? (
                    <span className="text-sm text-gray-900 flex items-center gap-1.5">
                      {contactPhone}
                      {contactPhoneVerified ? (
                        <span className="px-1.5 py-0.5 bg-green-50 text-green-600 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
                      ) : (
                        <span className="text-amber-500 text-xs">{t('profile.notVerified')}</span>
                      )}
                    </span>
                  ) : (
                    <FieldValue value="" t={t} />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Contact & Location */}
          <div className={`bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5 ${contactIncomplete > 0 ? 'border-l-4 border-l-amber-400' : ''}`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-gray-900">{t('profile.contactLocation')}</h2>
                {contactIncomplete > 0 && (
                  <span className="px-2 py-0.5 bg-amber-50 text-amber-600 text-xs font-medium rounded-full">
                    {contactIncomplete} {t('profile.incomplete')}
                  </span>
                )}
              </div>
              {editingSection === null && (
                <button onClick={() => startEditing('contact')} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  {t('profile.edit')}
                </button>
              )}
            </div>

            {editingSection === 'contact' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.street')}</label>
                  <textarea
                    value={address}
                    onChange={e => setAddress(e.target.value)}
                    placeholder="No. 12, Jalan ABC, Taman XYZ"
                    rows={2}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none resize-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.postalCode')}</label>
                    <input
                      type="text"
                      value={postalCode}
                      onChange={e => {
                        const val = e.target.value.replace(/\D/g, '').slice(0, 5)
                        setPostalCode(val)
                        if (val.length === 5) {
                          const result = findPostcode(val)
                          if (result.found && result.city && result.state) {
                            setCity(result.city)
                            setState(result.state)
                          }
                        }
                      }}
                      placeholder="08000"
                      maxLength={5}
                      className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.city')}</label>
                    <input
                      type="text"
                      value={city}
                      onChange={e => setCity(e.target.value)}
                      placeholder="Sungai Petani"
                      className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('onboarding.state')}</label>
                  <select
                    value={state}
                    onChange={e => setState(e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  >
                    <option value="">{t('onboarding.selectState')}</option>
                    {MALAYSIAN_STATES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-3 pt-4">
                  <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
                    {t('profile.cancel')}
                  </button>
                  <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">
                    {saving ? '...' : t('profile.save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.address')} empty={!address && !postalCode && !city && !state} />
                  <span className="text-sm text-gray-900 text-right max-w-[60%]">
                    {[address, [postalCode, city].filter(Boolean).join(' '), state].filter(Boolean).join(', ') || (
                      <span className="text-amber-500 italic">{t('profile.notSet')}</span>
                    )}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Section 4: Family & Background */}
          <div className={`bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5 ${familyIncomplete > 0 ? 'border-l-4 border-l-amber-400' : ''}`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-gray-900">{t('profile.familyBackground')}</h2>
                {familyIncomplete > 0 && (
                  <span className="px-2 py-0.5 bg-amber-50 text-amber-600 text-xs font-medium rounded-full">
                    {familyIncomplete} {t('profile.incomplete')}
                  </span>
                )}
              </div>
              {editingSection === null && (
                <button onClick={() => startEditing('family')} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  {t('profile.edit')}
                </button>
              )}
            </div>

            {editingSection === 'family' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.familyIncome')}</label>
                  <select
                    value={familyIncome}
                    onChange={e => setFamilyIncome(e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  >
                    <option value="">—</option>
                    {INCOME_RANGES.map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.siblings')}</label>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    value={siblings}
                    onChange={e => setSiblings(e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.colorBlindness')}</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setColorblind(true)}
                      className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                        colorblind
                          ? 'bg-primary-50 border-primary-500 text-primary-700'
                          : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                      }`}
                    >
                      {t('profile.yes')}
                    </button>
                    <button
                      onClick={() => setColorblind(false)}
                      className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                        !colorblind
                          ? 'bg-primary-50 border-primary-500 text-primary-700'
                          : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                      }`}
                    >
                      {t('profile.no')}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.physicalDisability')}</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDisability(true)}
                      className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                        disability
                          ? 'bg-primary-50 border-primary-500 text-primary-700'
                          : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                      }`}
                    >
                      {t('profile.yes')}
                    </button>
                    <button
                      onClick={() => setDisability(false)}
                      className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                        !disability
                          ? 'bg-primary-50 border-primary-500 text-primary-700'
                          : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                      }`}
                    >
                      {t('profile.no')}
                    </button>
                  </div>
                </div>
                <div className="flex gap-3 pt-4">
                  <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
                    {t('profile.cancel')}
                  </button>
                  <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">
                    {saving ? '...' : t('profile.save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.familyIncome')} empty={!familyIncome} />
                  <FieldValue value={familyIncome} t={t} />
                </div>
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.siblings')} empty={!siblings} />
                  <FieldValue value={siblings} t={t} />
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">{t('profile.colorBlindness')}</span>
                  <span className="text-sm text-gray-900">{colorblind ? t('profile.yes') : t('profile.no')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">{t('profile.physicalDisability')}</span>
                  <span className="text-sm text-gray-900">{disability ? t('profile.yes') : t('profile.no')}</span>
                </div>
              </div>
            )}
          </div>

          {/* Section 5: Application Tracking */}
          <div className={`bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5 ${appIncomplete > 0 ? 'border-l-4 border-l-amber-400' : ''}`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-gray-900">{t('profile.applicationTracking')}</h2>
                {appIncomplete > 0 && (
                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
                    {appIncomplete} {t('profile.incomplete')}
                  </span>
                )}
              </div>
              {editingSection === null && (
                <button onClick={() => startEditing('application')} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  {t('profile.edit')}
                </button>
              )}
            </div>

            {editingSection === 'application' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.angkaGiliran')}</label>
                  <input
                    type="text"
                    value={angkaGiliran}
                    onChange={e => setAngkaGiliran(e.target.value.toUpperCase().slice(0, 9))}
                    placeholder="AB123C456"
                    maxLength={9}
                    className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-1 outline-none font-mono uppercase ${
                      angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran)
                        ? 'border-red-400 focus:border-red-500 focus:ring-red-500'
                        : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500'
                    }`}
                  />
                  {angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran) && (
                    <p className="text-xs text-red-500 mt-1">{t('profile.angkaGiliranInvalid')}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-1">{t('profile.angkaGiliranHelper')}</p>
                </div>
                <div className="flex gap-3 pt-4">
                  <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
                    {t('profile.cancel')}
                  </button>
                  <button onClick={saveSection} disabled={saving || (!!angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran))} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">
                    {saving ? '...' : t('profile.save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <FieldLabel label={t('profile.angkaGiliran')} empty={!angkaGiliran} />
                  {angkaGiliran ? (
                    <span className="text-sm text-gray-900 font-mono">{angkaGiliran}</span>
                  ) : (
                    <FieldValue value="" t={t} />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Section 6: My Course Interests */}
          <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-6 mb-5">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-gray-900">{t('profile.courseInterests')}</h2>
              {savedCourses.length > 0 && (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs font-medium rounded-full">
                  {savedCourses.length}
                </span>
              )}
            </div>

            {savedCourses.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">{t('profile.noCourses')}</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {savedCourses.map(course => (
                  <div key={course.course_id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex-1 min-w-0">
                      <Link
                        href={`/course/${course.course_id}`}
                        className="text-sm font-medium text-gray-900 hover:text-primary-600 truncate block"
                      >
                        {course.course}
                      </Link>
                      <p className="text-xs text-gray-400 truncate">{course.level}</p>
                    </div>
                    <select
                      value={course.interest_status}
                      onChange={e => handleStatusChange(course.course_id, e.target.value)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium border-0 cursor-pointer ${getStatusColor(course.interest_status)}`}
                    >
                      {STATUS_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{t(opt.label)}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleRemoveCourse(course.course_id)}
                      className="p-1 text-gray-300 hover:text-red-500 transition-colors"
                      title="Remove"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  )
}
