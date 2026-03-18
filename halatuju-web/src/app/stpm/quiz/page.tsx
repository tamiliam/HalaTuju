'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  getStpmQuizQuestions,
  resolveStpmQuizQ3Q4,
  submitStpmQuiz,
  type StpmQuizQuestion,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { STPM_SUBJECT_TO_API_KEY } from '@/lib/subjects'
import {
  KEY_STPM_GRADES,
  KEY_STPM_QUIZ_SIGNALS,
  KEY_STPM_QUIZ_BRANCH,
  KEY_REPORT_GENERATED,
} from '@/lib/storage'

const ICON_EMOJI: Record<string, string> = {
  wrench_gears: '\u{1f527}', laptop_code: '\u{1f4bb}', handshake_chart: '\u{1f91d}',
  heart_stethoscope: '\u{2764}\ufe0f', question_sparkle: '\u{2728}', paintbrush_ruler: '\u{1f3a8}',
  chef_suitcase: '\u{1f468}\u200d\u{1f373}', leaf_tractor: '\u{1f33f}', bolt_ship: '\u{26a1}',
  lightning_bolt: '\u{26a1}', hardhat_crane: '\u{1f3d7}\ufe0f', airplane_ship: '\u{2708}\ufe0f',
  oil_rig_flame: '\u{1f6e2}\ufe0f', hands_tools: '\u{1f6e0}\ufe0f', brain_lightbulb: '\u{1f9e0}',
  people_bubbles: '\u{1f465}', pencil_star: '\u{270f}\ufe0f', workshop_garage: '\u{1f3ed}',
  desk_monitor: '\u{1f5a5}\ufe0f', trees_sun: '\u{1f333}', building_people: '\u{1f3e2}',
  hammer_check: '\u{1f528}', book_magnifier: '\u{1f4d6}', clipboard_group: '\u{1f4cb}',
  loop_arrows: '\u{1f504}', shield_check: '\u{1f6e1}\ufe0f', money_rocket: '\u{1f4b0}',
  gradcap_arrow: '\u{1f393}', lightning_briefcase: '\u{26a1}', crowd_sweat: '\u{1f630}',
  brain_weight: '\u{1f9e0}', arm_weight: '\u{1f4aa}', flexed_arm_star: '\u{1f4aa}',
  wallet_coins: '\u{1f45b}', house_heart: '\u{1f3e0}', handshake_door: '\u{1f91d}',
  trophy_star: '\u{1f3c6}',
  // STPM-specific icons
  microscope: '\u{1f52c}', stethoscope: '\u{1fa7a}', gear: '\u{2699}\ufe0f',
  computer: '\u{1f4bb}', test_tube: '\u{1f9ea}', dna: '\u{1f9ec}',
  scales: '\u{2696}\ufe0f', briefcase: '\u{1f4bc}', palette: '\u{1f3a8}',
  books: '\u{1f4da}', globe: '\u{1f30d}', chart: '\u{1f4c8}',
  calculator: '\u{1f5a9}', megaphone: '\u{1f4e3}', handshake: '\u{1f91d}',
  graduation: '\u{1f393}', rocket: '\u{1f680}', target: '\u{1f3af}',
  lightbulb: '\u{1f4a1}', compass: '\u{1f9ed}', thumbs_up: '\u{1f44d}',
  thinking: '\u{1f914}', shrug: '\u{1f937}', muscle: '\u{1f4aa}',
  family: '\u{1f46a}', star: '\u{2b50}', seedling: '\u{1f331}',
}

/**
 * Convert localStorage STPM grades (uppercase IDs) to API format (lowercase keys).
 * Returns {subjects, grades} ready for the quiz API.
 */
function convertGradesToApiFormat(stpmGrades: Record<string, string>): {
  subjects: string[]
  grades: Record<string, string>
} {
  const subjects: string[] = []
  const grades: Record<string, string> = {}

  for (const [frontendId, grade] of Object.entries(stpmGrades)) {
    if (!grade || frontendId === 'PA') continue // PA is not used for quiz branching
    const apiKey = STPM_SUBJECT_TO_API_KEY[frontendId]
    if (apiKey) {
      subjects.push(apiKey)
      grades[apiKey] = grade
    }
  }

  return { subjects, grades }
}

export default function StpmQuizPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { t, locale } = useT()

  // Quiz state
  const [allQuestions, setAllQuestions] = useState<StpmQuizQuestion[]>([])
  const [branch, setBranch] = useState<string>('')
  const [apiSubjects, setApiSubjects] = useState<string[]>([])
  const [apiGrades, setApiGrades] = useState<Record<string, string>>({})
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<(number | null)[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Track Q2 field signal → Q3/Q4 resolution
  const [q2Resolved, setQ2Resolved] = useState(false)

  // Load questions on mount
  useEffect(() => {
    if (authLoading || !isAuthenticated) return

    const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
    if (!stpmGradesStr) {
      router.push('/onboarding/stpm-grades')
      return
    }

    const stpmGrades = JSON.parse(stpmGradesStr)
    const { subjects, grades } = convertGradesToApiFormat(stpmGrades)

    if (subjects.length < 2) {
      router.push('/onboarding/stpm-grades')
      return
    }

    setApiSubjects(subjects)
    setApiGrades(grades)

    const lang = locale === 'ms' ? 'bm' : locale
    getStpmQuizQuestions(subjects, grades, lang)
      .then((data) => {
        // Build initial question list: Q1, Q2 (Q3/Q4 resolved later), Q5, trunk Q7-Q10
        const initial: StpmQuizQuestion[] = [
          ...data.questions, // Q1 + Q2
          // Q3/Q4 placeholders — will be replaced after Q2 answer
        ]
        // Store the full response for Q3 resolution
        setBranch(data.branch)

        // We start with Q1 + Q2 only. Q3/Q4 get inserted after Q2 is answered.
        // Then Q5 + trunk (Q7-Q10) follow.
        const q5AndTrunk = [data.q5, ...data.trunk_remaining]
        // Store everything: initial questions + a marker for Q3/Q4 + rest
        setAllQuestions([...initial, ...q5AndTrunk])
        setAnswers(new Array(initial.length + q5AndTrunk.length).fill(null))
        setLoading(false)
      })
      .catch(() => {
        setError(t('stpmQuiz.loadError'))
        setLoading(false)
      })
  }, [authLoading, isAuthenticated, locale, router, t])

  // After Q2 is answered, resolve Q3 and Q4 from the backend
  const handleQ2Answered = useCallback(async (q2OptionIndex: number) => {
    if (q2Resolved || allQuestions.length < 2) return

    const q2 = allQuestions[1] // Q2 is always index 1
    const chosenOption = q2.options[q2OptionIndex]
    if (!chosenOption) return

    // Find the field signal from the chosen option
    const fieldSignal = Object.keys(chosenOption.signals).find(s => s.startsWith('field_'))
    if (!fieldSignal) return

    const lang = locale === 'ms' ? 'bm' : locale
    try {
      const resolved = await resolveStpmQuizQ3Q4(fieldSignal, branch, apiGrades, lang)

      // Insert Q3 and Q4 after Q2 (index 1), before Q5 and trunk
      const q1q2 = allQuestions.slice(0, 2) // Q1, Q2
      const rest = allQuestions.slice(2) // Q5, trunk Q7-Q10

      const newQuestions: StpmQuizQuestion[] = [...q1q2]
      if (resolved.q3) newQuestions.push(resolved.q3)
      if (resolved.q4) newQuestions.push(resolved.q4)
      newQuestions.push(...rest)

      setAllQuestions(newQuestions)
      setAnswers(new Array(newQuestions.length).fill(null).map((_, i) => {
        // Preserve existing answers for Q1 and Q2
        if (i < 2) return answers[i]
        return null
      }))
      setQ2Resolved(true)

      // Auto-advance to Q3
      setTimeout(() => setCurrentStep(2), 300)
    } catch {
      // If resolve fails, continue with remaining questions (skip Q3/Q4)
      setQ2Resolved(true)
      setTimeout(() => setCurrentStep(2), 300)
    }
  }, [q2Resolved, allQuestions, branch, apiGrades, locale, answers])

  const question = currentStep < allQuestions.length ? allQuestions[currentStep] : null
  const currentAnswer = currentStep < answers.length ? answers[currentStep] : null

  function handleCardClick(optIdx: number) {
    if (!question) return

    const updated = [...answers]
    updated[currentStep] = optIdx
    setAnswers(updated)

    // If Q2 was just answered, resolve Q3/Q4 before advancing
    if (currentStep === 1 && !q2Resolved) {
      handleQ2Answered(optIdx)
      return
    }

    // Auto-advance after 300ms
    if (currentStep < allQuestions.length - 1) {
      setTimeout(() => setCurrentStep(prev => prev + 1), 300)
    }
  }

  const handleSubmit = async () => {
    const lang = locale === 'ms' ? 'bm' : locale
    const quizAnswers = allQuestions.map((q, i) => ({
      question_id: q.id,
      option_index: answers[i]!,
    }))

    setSubmitting(true)
    try {
      const result = await submitStpmQuiz(quizAnswers, apiSubjects, apiGrades, lang)
      // Store signals in localStorage for dashboard to pick up
      localStorage.setItem(KEY_STPM_QUIZ_SIGNALS, JSON.stringify(result.student_signals))
      localStorage.setItem(KEY_STPM_QUIZ_BRANCH, result.branch)
      // Reset report gate — new quiz unlocks report generation
      localStorage.removeItem(KEY_REPORT_GENERATED)
      router.push('/dashboard')
    } catch {
      setError(t('stpmQuiz.submitError'))
      setSubmitting(false)
    }
  }

  const allAnswered = allQuestions.length > 0 && answers.every(a => a !== null)

  const answeredCount = answers.filter(a => a !== null).length

  // Auth gate
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
          <p className="text-gray-600">{t('stpmQuiz.loading')}</p>
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
            {t('common.retry')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-[#f5f7f8]">
      {/* Gradient header */}
      <header className="bg-gradient-to-r from-blue-500 to-purple-600 text-white">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="text-white/90 hover:text-white text-sm font-medium">
            &larr; HalaTuju
          </Link>
          <Link href="/dashboard" className="text-white/70 hover:text-white text-sm">
            {t('stpmQuiz.skip')}
          </Link>
        </div>

        {/* Progress bar */}
        <div className="px-6 pb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-white/90">
              {t('quiz.questionOf', { current: String(currentStep + 1), total: String(allQuestions.length) })}
            </span>
            <span className="text-sm text-white/60">
              {t('quiz.answered', { count: String(answeredCount) })}
            </span>
          </div>
          <div className="w-full bg-white/20 rounded-full h-1.5">
            <div
              className="bg-white h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / allQuestions.length) * 100}%` }}
            />
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-6 max-w-md">
        {/* Step dots */}
        <div className="flex justify-center gap-2 mb-6">
          {allQuestions.map((q, i) => {
            const hasAnswer = answers[i] !== null
            return (
              <button
                key={q.id}
                onClick={() => {
                  // Only allow navigating to answered questions or the current one
                  if (i <= currentStep || hasAnswer) setCurrentStep(i)
                }}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  i === currentStep
                    ? 'bg-blue-500 scale-125'
                    : hasAnswer
                      ? 'bg-blue-300'
                      : 'bg-gray-300'
                }`}
                aria-label={`Go to question ${i + 1}`}
              />
            )
          })}
        </div>

        {/* Question */}
        {question && (
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4 text-center">
              {question.prompt}
            </h2>

            {/* Card grid — 2x2 for 4 options, single column for 3 */}
            <div className={`grid gap-4 mb-5 ${
              question.options.length <= 3 ? 'grid-cols-1' : 'grid-cols-2'
            }`}>
              {question.options.map((option, optIdx) => {
                const selected = currentAnswer === optIdx
                return (
                  <button
                    key={optIdx}
                    onClick={() => handleCardClick(optIdx)}
                    className={`
                      ${question.options.length <= 3 ? 'py-4 px-5' : 'aspect-square p-5'}
                      rounded-2xl border-2
                      flex ${question.options.length <= 3 ? 'flex-row items-center gap-4' : 'flex-col items-center justify-center gap-3'}
                      transition-all duration-200 shadow-sm
                      ${selected
                        ? 'border-blue-500 bg-blue-50 shadow-lg scale-[1.04]'
                        : 'border-gray-100 bg-white hover:border-blue-200 hover:shadow-md'}
                      cursor-pointer active:scale-95
                    `}
                  >
                    <span className={question.options.length <= 3 ? 'text-3xl' : 'text-5xl leading-none'}>
                      {ICON_EMOJI[option.icon] || '\u2753'}
                    </span>
                    <span className={`text-sm font-bold ${question.options.length <= 3 ? 'text-left' : 'text-center'} leading-tight ${selected ? 'text-blue-700' : 'text-gray-700'}`}>
                      {option.text}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed text-sm"
          >
            {t('quiz.previous')}
          </button>

          {currentStep === allQuestions.length - 1 ? (
            <button
              onClick={handleSubmit}
              disabled={!allAnswered || submitting}
              className="btn-primary disabled:opacity-40"
            >
              {submitting ? t('quiz.submitting') : t('quiz.seeResults')}
            </button>
          ) : (
            <div />
          )}
        </div>
      </div>
    </main>
  )
}
