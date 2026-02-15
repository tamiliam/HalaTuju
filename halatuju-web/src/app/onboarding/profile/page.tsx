'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function ProfileInputPage() {
  const router = useRouter()
  const [gender, setGender] = useState<string>('')
  const [nationality, setNationality] = useState<string>('malaysian')
  const [colorblind, setColorblind] = useState<boolean>(false)
  const [disability, setDisability] = useState<boolean>(false)

  useEffect(() => {
    const savedProfile = localStorage.getItem('halatuju_profile')
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile)
      if (parsed.gender) setGender(parsed.gender)
      if (parsed.nationality) setNationality(parsed.nationality)
      if (parsed.colorblind !== undefined) setColorblind(parsed.colorblind)
      if (parsed.disability !== undefined) setDisability(parsed.disability)
    }
  }, [])

  const isComplete = gender !== ''

  const handleContinue = () => {
    if (isComplete) {
      // Store profile
      const profile = {
        gender,
        nationality,
        colorblind,
        disability,
      }
      localStorage.setItem('halatuju_profile', JSON.stringify(profile))
      router.push('/dashboard')
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Progress Header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">H</span>
              </div>
              <span className="font-semibold text-gray-900">HalaTuju</span>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center text-white text-sm font-bold">
                1
              </div>
              <div className="w-16 h-1 bg-primary-500 rounded" />
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center text-white text-sm font-bold">
                2
              </div>
              <div className="w-16 h-1 bg-primary-500 rounded" />
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center text-white text-sm font-bold">
                3
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-12 max-w-2xl">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            A Few More Details
          </h1>
          <p className="text-gray-600">
            Some courses have specific requirements. This helps us filter accurately.
          </p>
        </div>

        <div className="space-y-8 mb-10">
          {/* Gender */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <label className="block text-lg font-medium text-gray-900 mb-4">
              Gender <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-4">
              <button
                onClick={() => setGender('male')}
                className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                  gender === 'male'
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-3xl mb-2">👨</div>
                <div className="font-medium">Male</div>
                <div className="text-sm text-gray-500">Lelaki</div>
              </button>
              <button
                onClick={() => setGender('female')}
                className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                  gender === 'female'
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-3xl mb-2">👩</div>
                <div className="font-medium">Female</div>
                <div className="text-sm text-gray-500">Perempuan</div>
              </button>
            </div>
          </div>

          {/* Nationality */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <label className="block text-lg font-medium text-gray-900 mb-4">
              Nationality
            </label>
            <div className="flex gap-4">
              <button
                onClick={() => setNationality('malaysian')}
                className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                  nationality === 'malaysian'
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-3xl mb-2">🇲🇾</div>
                <div className="font-medium">Malaysian</div>
              </button>
              <button
                onClick={() => setNationality('non_malaysian')}
                className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                  nationality === 'non_malaysian'
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-3xl mb-2">🌍</div>
                <div className="font-medium">Non-Malaysian</div>
              </button>
            </div>
          </div>

          {/* Health Conditions */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <label className="block text-lg font-medium text-gray-900 mb-2">
              Health Conditions
            </label>
            <p className="text-sm text-gray-500 mb-4">
              Some courses have health requirements. Check if any apply to you.
            </p>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={colorblind}
                  onChange={(e) => setColorblind(e.target.checked)}
                  className="w-5 h-5 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                />
                <div>
                  <span className="font-medium">Colour blindness</span>
                  <span className="text-sm text-gray-500 ml-2">(Buta warna)</span>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={disability}
                  onChange={(e) => setDisability(e.target.checked)}
                  className="w-5 h-5 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                />
                <div>
                  <span className="font-medium">Physical disability</span>
                  <span className="text-sm text-gray-500 ml-2">(OKU)</span>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div className="flex justify-between">
          <Link
            href="/onboarding/grades"
            className="px-6 py-3 text-gray-600 hover:text-gray-900"
          >
            Back
          </Link>
          <button
            onClick={handleContinue}
            disabled={!isComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            See My Recommendations
          </button>
        </div>
      </div>
    </main>
  )
}
