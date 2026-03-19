'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/lib/auth-context'
import { getProfile, syncProfile } from '@/lib/api'
import ProgressStepper from '@/components/ProgressStepper'
import { KEY_PROFILE } from '@/lib/storage'

const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'W.P. Kuala Lumpur', 'W.P. Putrajaya', 'W.P. Labuan',
]

export default function ProfileInputPage() {
  const router = useRouter()
  const { t } = useT()
  const { token } = useAuth()
  const [gender, setGender] = useState<string>('')
  const [nationality, setNationality] = useState<string>('malaysian')
  const [state, setState] = useState<string>('')
  const [colorblind, setColorblind] = useState<boolean>(false)
  const [disability, setDisability] = useState<boolean>(false)

  useEffect(() => {
    const savedProfile = localStorage.getItem(KEY_PROFILE)
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile)
      if (parsed.gender) setGender(parsed.gender)
      if (parsed.nationality) setNationality(parsed.nationality)
      if (parsed.state) setState(parsed.state)
      if (parsed.colorblind !== undefined) setColorblind(parsed.colorblind)
      if (parsed.disability !== undefined) setDisability(parsed.disability)
    }

    if (token) {
      getProfile({ token }).then(p => {
        if (p.preferred_state) setState(p.preferred_state)
        if (p.gender) setGender(p.gender)
        if (p.nationality) setNationality(p.nationality)
        if (p.colorblind !== undefined) setColorblind(p.colorblind === true || String(p.colorblind) === 'Ya')
        if (p.disability !== undefined) setDisability(p.disability === true || String(p.disability) === 'Ya')
      }).catch(() => {})
    }
  }, [token])

  const isComplete = gender !== ''

  const handleContinue = () => {
    if (isComplete) {
      // Preserve CoQ score set on grades page
      const existing = localStorage.getItem(KEY_PROFILE)
      const prev = existing ? JSON.parse(existing) : {}
      const profile = {
        ...prev,
        gender,
        nationality,
        state,
        colorblind,
        disability,
      }
      localStorage.setItem(KEY_PROFILE, JSON.stringify(profile))

      if (token) {
        syncProfile({
          gender,
          nationality,
          preferred_state: state,
          colorblind,
          disability,
        }, { token }).catch(() => {})
      }

      router.push('/dashboard')
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={120} height={40} />
            </Link>
            <ProgressStepper currentStep={3} />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('onboarding.profileTitle')}
          </h1>
          <p className="text-gray-600">
            {t('onboarding.profileSubtitleNew')}
          </p>
        </div>

        {/* Compact single card */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-8">
          {/* Row 1: State + Nationality */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
            {/* Negeri */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('onboarding.state')}
              </label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
              >
                <option value="">{t('onboarding.selectState')}</option>
                {MALAYSIAN_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Kewarganegaraan */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('onboarding.nationality')}
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setNationality('malaysian')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'malaysian'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={nationality === 'malaysian' ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" fill={nationality === 'malaysian' ? '#bfdbfe' : '#e5e7eb'} />
                    <polyline points="9 22 9 12 15 12 15 22" />
                  </svg>
                  {t('onboarding.malaysian')}
                </button>
                <button
                  onClick={() => setNationality('non_malaysian')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'non_malaysian'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={nationality === 'non_malaysian' ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" fill={nationality === 'non_malaysian' ? '#bfdbfe' : '#e5e7eb'} />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                  </svg>
                  {t('onboarding.nonMalaysian')}
                </button>
              </div>
            </div>
          </div>

          {/* Row 2: Jantina */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('onboarding.gender')} <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setGender('male')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  gender === 'male'
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={gender === 'male' ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                  <circle cx="12" cy="7" r="4" fill={gender === 'male' ? '#bfdbfe' : '#e5e7eb'} />
                </svg>
                {t('onboarding.male')}
              </button>
              <button
                onClick={() => setGender('female')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                  gender === 'female'
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={gender === 'female' ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                  <circle cx="12" cy="7" r="4" fill={gender === 'female' ? '#bfdbfe' : '#e5e7eb'} />
                </svg>
                {t('onboarding.female')}
              </button>
            </div>
          </div>

          {/* Row 4: Keperluan Khas */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('onboarding.specialNeeds')}
            </label>
            <p className="text-xs text-gray-400 mb-3">{t('onboarding.healthNote')}</p>
            <div className="flex flex-wrap gap-3">
              <label className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border cursor-pointer transition-all ${
                colorblind
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}>
                <input
                  type="checkbox"
                  checked={colorblind}
                  onChange={(e) => setColorblind(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                />
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={colorblind ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill={colorblind ? '#bfdbfe' : '#e5e7eb'} />
                  <circle cx="12" cy="12" r="3" />
                  <line x1="2" y1="2" x2="22" y2="22" stroke={colorblind ? '#1d4ed8' : '#6b7280'} />
                </svg>
                <span className="text-sm text-gray-700">{t('onboarding.colorBlindness')}</span>
              </label>
              <label className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border cursor-pointer transition-all ${
                disability
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}>
                <input
                  type="checkbox"
                  checked={disability}
                  onChange={(e) => setDisability(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                />
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={disability ? '#1d4ed8' : '#6b7280'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" fill={disability ? '#bfdbfe' : '#e5e7eb'} />
                  <path d="M12 8a1 1 0 100-2 1 1 0 000 2z" fill={disability ? '#1d4ed8' : '#6b7280'} />
                  <path d="M12 10v4M10 18l2-4 2 4" />
                </svg>
                <span className="text-sm text-gray-700">{t('onboarding.physicalDisability')}</span>
              </label>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <Link
            href="/onboarding/grades"
            className="px-6 py-3 text-gray-600 hover:text-gray-900"
          >
            {t('common.back')}
          </Link>
          <button
            onClick={handleContinue}
            disabled={!isComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('onboarding.seeRecommendations')}
          </button>
        </div>
      </div>
    </main>
  )
}
