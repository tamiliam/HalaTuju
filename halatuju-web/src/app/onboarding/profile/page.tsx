'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'

const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'W.P. Kuala Lumpur', 'W.P. Putrajaya', 'W.P. Labuan',
]

export default function ProfileInputPage() {
  const router = useRouter()
  const { t } = useT()
  const [gender, setGender] = useState<string>('')
  const [nationality, setNationality] = useState<string>('malaysian')
  const [state, setState] = useState<string>('')
  const [coqScore, setCoqScore] = useState<string>('')
  const [colorblind, setColorblind] = useState<boolean>(false)
  const [disability, setDisability] = useState<boolean>(false)

  useEffect(() => {
    const savedProfile = localStorage.getItem('halatuju_profile')
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile)
      if (parsed.gender) setGender(parsed.gender)
      if (parsed.nationality) setNationality(parsed.nationality)
      if (parsed.state) setState(parsed.state)
      if (parsed.coqScore !== undefined) setCoqScore(String(parsed.coqScore))
      if (parsed.colorblind !== undefined) setColorblind(parsed.colorblind)
      if (parsed.disability !== undefined) setDisability(parsed.disability)
    }
  }, [])

  const isComplete = gender !== ''

  const handleContinue = () => {
    if (isComplete) {
      const profile = {
        gender,
        nationality,
        state,
        coqScore: coqScore ? parseFloat(coqScore) : 0,
        colorblind,
        disability,
      }
      localStorage.setItem('halatuju_profile', JSON.stringify(profile))
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
              <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
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
                  className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'malaysian'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  🇲🇾 {t('onboarding.malaysian')}
                </button>
                <button
                  onClick={() => setNationality('non_malaysian')}
                  className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                    nationality === 'non_malaysian'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  🌍 {t('onboarding.nonMalaysian')}
                </button>
              </div>
            </div>
          </div>

          {/* Row 2: Co-curricular Score */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('onboarding.coqScore')}
            </label>
            <p className="text-xs text-gray-400 mb-2">{t('onboarding.coqHint')}</p>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min="0"
                max="10"
                step="0.01"
                value={coqScore}
                onChange={(e) => {
                  const val = e.target.value
                  if (val === '' || (parseFloat(val) >= 0 && parseFloat(val) <= 10)) {
                    setCoqScore(val)
                  }
                }}
                placeholder="0.00"
                className="w-32 px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none text-center font-medium"
              />
              <span className="text-sm text-gray-400">/ 10</span>
            </div>
          </div>

          {/* Row 3: Jantina */}
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
                <span className="text-xl">👨</span>
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
                <span className="text-xl">👩</span>
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
                <span className="text-base">🎨</span>
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
                <span className="text-base">♿</span>
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
