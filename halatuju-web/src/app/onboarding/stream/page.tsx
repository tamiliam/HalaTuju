'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const STREAMS = [
  {
    id: 'science',
    title: 'Science Stream',
    subtitle: 'Sains',
    description: 'Physics, Chemistry, Biology, Additional Mathematics',
    icon: '🔬',
  },
  {
    id: 'arts',
    title: 'Arts Stream',
    subtitle: 'Sastera',
    description: 'Economics, Accounts, Business, Geography, History',
    icon: '📚',
  },
  {
    id: 'technical',
    title: 'Technical/Vocational',
    subtitle: 'Teknikal/Vokasional',
    description: 'Engineering, Design, Construction, ICT',
    icon: '🔧',
  },
]

export default function StreamSelectionPage() {
  const router = useRouter()
  const [selectedStream, setSelectedStream] = useState<string | null>(null)

  const handleContinue = () => {
    if (selectedStream) {
      // Store in session/localStorage
      localStorage.setItem('halatuju_stream', selectedStream)
      router.push('/onboarding/grades')
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
              <div className="w-16 h-1 bg-gray-200 rounded">
                <div className="w-1/3 h-full bg-primary-500 rounded" />
              </div>
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-500 text-sm font-bold">
                2
              </div>
              <div className="w-16 h-1 bg-gray-200 rounded" />
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-500 text-sm font-bold">
                3
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-12 max-w-3xl">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            What stream did you take?
          </h1>
          <p className="text-gray-600">
            This helps us show you the right subjects for grade entry.
          </p>
        </div>

        <div className="space-y-4 mb-10">
          {STREAMS.map((stream) => (
            <button
              key={stream.id}
              onClick={() => setSelectedStream(stream.id)}
              className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                selectedStream === stream.id
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className="text-4xl">{stream.icon}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {stream.title}
                    </h3>
                    <span className="text-sm text-gray-500">({stream.subtitle})</span>
                  </div>
                  <p className="text-gray-600 text-sm">{stream.description}</p>
                </div>
                <div
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                    selectedStream === stream.id
                      ? 'border-primary-500 bg-primary-500'
                      : 'border-gray-300'
                  }`}
                >
                  {selectedStream === stream.id && (
                    <svg
                      className="w-4 h-4 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="flex justify-between">
          <Link
            href="/"
            className="px-6 py-3 text-gray-600 hover:text-gray-900"
          >
            Back
          </Link>
          <button
            onClick={handleContinue}
            disabled={!selectedStream}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Continue
          </button>
        </div>
      </div>
    </main>
  )
}
