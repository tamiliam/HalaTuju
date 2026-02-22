'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { getQuizQuestions, submitQuiz, type QuizQuestion, type QuizAnswer } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

export default function QuizPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { t } = useT()
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<(number | null)[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load questions on mount (only if authenticated)
  useEffect(() => {
    if (authLoading || !isAuthenticated) return
    const lang = localStorage.getItem('halatuju_lang') || 'en'
    getQuizQuestions(lang)
      .then(({ questions: qs }) => {
        setQuestions(qs)
        setAnswers(new Array(qs.length).fill(null))
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load quiz questions. Please try again.')
        setLoading(false)
      })
  }, [authLoading, isAuthenticated])

  const handleSelect = (optionIndex: number) => {
    const updated = [...answers]
    updated[currentStep] = optionIndex
    setAnswers(updated)

    // Auto-advance after a brief pause
    if (currentStep < questions.length - 1) {
      setTimeout(() => setCurrentStep(currentStep + 1), 300)
    }
  }

  const handleSubmit = async () => {
    const lang = localStorage.getItem('halatuju_lang') || 'en'
    const quizAnswers: QuizAnswer[] = questions.map((q, i) => ({
      question_id: q.id,
      option_index: answers[i]!,
    }))

    setSubmitting(true)
    try {
      const result = await submitQuiz(quizAnswers, lang)
      // Store signals in localStorage for dashboard to pick up
      localStorage.setItem('halatuju_quiz_signals', JSON.stringify(result.student_signals))
      localStorage.setItem('halatuju_signal_strength', JSON.stringify(result.signal_strength))
      router.push('/dashboard')
    } catch {
      setError('Failed to submit quiz. Please try again.')
      setSubmitting(false)
    }
  }

  const allAnswered = answers.every((a) => a !== null)
  const question = questions[currentStep]

  // Auth gate: show sign-in prompt if not authenticated
  if (!authLoading && !isAuthenticated) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {t('authGate.title')}
          </h1>
          <p className="text-gray-600 mb-6">
            {t('authGate.quizReason')}
          </p>
          <button
            onClick={() => showAuthGate('quiz')}
            className="btn-primary"
          >
            {t('saved.signIn')}
          </button>
          <Link href="/dashboard" className="block mt-4 text-gray-500 hover:text-gray-700 text-sm">
            {t('authGate.continueBrowsing')}
          </Link>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">Loading quiz...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="btn-primary">
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
          </Link>
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-700 text-sm">
            Skip Quiz
          </Link>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">
              Question {currentStep + 1} of {questions.length}
            </span>
            <span className="text-sm text-gray-400">
              {answers.filter((a) => a !== null).length} answered
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / questions.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-2 mb-8">
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentStep(i)}
              className={`w-3 h-3 rounded-full transition-all ${
                i === currentStep
                  ? 'bg-primary-500 scale-125'
                  : answers[i] !== null
                    ? 'bg-primary-300'
                    : 'bg-gray-300'
              }`}
              aria-label={`Go to question ${i + 1}`}
            />
          ))}
        </div>

        {/* Question */}
        {question && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-6 text-center">
              {question.prompt}
            </h2>

            <div className="space-y-3">
              {question.options.map((option, optIdx) => (
                <button
                  key={optIdx}
                  onClick={() => handleSelect(optIdx)}
                  className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                    answers[currentStep] === optIdx
                      ? 'border-primary-500 bg-primary-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-primary-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                        answers[currentStep] === optIdx
                          ? 'border-primary-500 bg-primary-500'
                          : 'border-gray-300'
                      }`}
                    >
                      {answers[currentStep] === optIdx && (
                        <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </div>
                    <span className="text-gray-700">{option.text}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>

          {currentStep < questions.length - 1 ? (
            <button
              onClick={() => setCurrentStep(currentStep + 1)}
              className="btn-primary"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!allAnswered || submitting}
              className="btn-primary"
            >
              {submitting ? 'Submitting...' : 'See My Results'}
            </button>
          )}
        </div>
      </div>
    </main>
  )
}
